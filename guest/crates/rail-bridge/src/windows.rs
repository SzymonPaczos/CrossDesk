use crate::events::build_rail_event;
use proto::crossdesk::v1::RailWindowEvent;
use std::collections::HashSet;
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::{Mutex, OnceLock};
use tokio::sync::mpsc;
use tracing::{debug, error, info};
use windows::Win32::Foundation::{HWND, LPARAM, WPARAM};
use windows::Win32::System::Threading::GetCurrentThreadId;
use windows::Win32::UI::Accessibility::{SetWinEventHook, UnhookWinEvent, HWINEVENTHOOK};
use windows::Win32::UI::WindowsAndMessaging::{
    DispatchMessageW, GetMessageW, GetWindowLongW, IsWindowVisible, PostThreadMessageW,
    EVENT_OBJECT_CREATE, EVENT_OBJECT_DESTROY, EVENT_OBJECT_LOCATIONCHANGE, GWL_STYLE, MSG,
    WINEVENT_OUTOFCONTEXT, WINEVENT_SKIPOWNPROCESS, WM_QUIT, WS_CHILD, WS_POPUP,
};

static EVENT_SENDER: OnceLock<mpsc::Sender<RailWindowEvent>> = OnceLock::new();

/// Win32 thread ID of the message-pump thread, captured once on startup so a
/// subsequent `request_shutdown()` can post `WM_QUIT` to break the
/// `GetMessageW` loop. Zero means the thread has not started yet.
static HOOK_THREAD_ID: AtomicU32 = AtomicU32::new(0);

/// HWNDs (as isize) we've already announced to the host with a CREATED event.
///
/// A window's `EVENT_OBJECT_CREATE` typically fires *before* the window is
/// visible, so the old code (which dropped every non-visible event) never
/// forwarded a CREATED — the host then saw only later MOVE events for an HWND
/// it had no record of ("ghost window" warnings), and CREATE-only work like
/// icon extraction never ran. We instead emit CREATED on the first event
/// where the window is top-level *and* visible, and track it here so
/// subsequent events map to MOVE/etc. and DESTROY fires only for known
/// windows.
static SEEN_WINDOWS: OnceLock<Mutex<HashSet<isize>>> = OnceLock::new();

fn seen_windows() -> std::sync::MutexGuard<'static, HashSet<isize>> {
    // Recover from a poisoned lock rather than unwinding across the FFI
    // callback boundary — the only state is a HashSet of integers, so a prior
    // panic leaves it in a perfectly usable state.
    SEEN_WINDOWS
        .get_or_init(|| Mutex::new(HashSet::new()))
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

pub fn start_hook_thread(sender: mpsc::Sender<RailWindowEvent>) {
    if EVENT_SENDER.set(sender).is_err() {
        error!("EVENT_SENDER already initialized");
        return;
    }

    std::thread::spawn(|| {
        info!("Starting WinEvent hook thread");
        // Recording the thread ID before SetWinEventHook means an early
        // shutdown signal still finds a valid target — PostThreadMessageW will
        // simply queue WM_QUIT before GetMessageW first runs.
        // Safety: GetCurrentThreadId has no inputs and cannot fail.
        HOOK_THREAD_ID.store(unsafe { GetCurrentThreadId() }, Ordering::SeqCst);

        // Safety: the SetWinEventHook + GetMessageW + DispatchMessageW + UnhookWinEvent
        // sequence is the documented Win32 out-of-context hook pattern. All raw pointers
        // come from this stack frame (`&mut msg`) and outlive every call that uses them.
        unsafe {
            let hook = SetWinEventHook(
                EVENT_OBJECT_CREATE,
                EVENT_OBJECT_LOCATIONCHANGE,
                None,
                Some(winevent_proc),
                0,
                0,
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
            );

            if hook.is_invalid() {
                error!("Failed to set WinEventHook");
                HOOK_THREAD_ID.store(0, Ordering::SeqCst);
                return;
            }

            // Out-of-context hooks require a message pump on this thread.
            let mut msg = MSG::default();
            while GetMessageW(&mut msg, HWND::default(), 0, 0).into() {
                DispatchMessageW(&msg);
            }

            let _ = UnhookWinEvent(hook);
        }

        HOOK_THREAD_ID.store(0, Ordering::SeqCst);
        info!("WinEvent hook thread exited");
    });
}

/// Asks the hook thread to exit. Safe to call from any thread, including
/// before `start_hook_thread` (no-op) and after it has already exited (no-op).
pub fn request_shutdown() {
    let tid = HOOK_THREAD_ID.load(Ordering::SeqCst);
    if tid == 0 {
        return;
    }
    // Safety: PostThreadMessageW accepts any DWORD thread id; if the thread has
    // already exited the call returns ERR_INVALID_THREAD_ID which we log and
    // ignore — no UB regardless of `tid`'s liveness.
    unsafe {
        if let Err(e) = PostThreadMessageW(tid, WM_QUIT, WPARAM(0), LPARAM(0)) {
            error!("PostThreadMessageW(WM_QUIT) failed: {e:?}");
        }
    }
}

unsafe extern "system" fn winevent_proc(
    _hwineventhook: HWINEVENTHOOK,
    event: u32,
    hwnd: HWND,
    idobject: i32,
    idchild: i32,
    _ideventthread: u32,
    _dwmsgeventtime: u32,
) {
    // OBJID_WINDOW == 0; ignore everything below the window object.
    if idobject != 0 || idchild != 0 || hwnd.is_invalid() {
        return;
    }

    let style = GetWindowLongW(hwnd, GWL_STYLE) as u32;
    let is_child = (style & WS_CHILD.0) != 0;

    // Top-level windows and popups (e.g. context menus) pass; ordinary child
    // controls do not — we only want app-level windows on the host side.
    if is_child && (style & WS_POPUP.0) == 0 {
        return;
    }

    let key = hwnd.0 as isize;

    // DESTROY fires after the window is gone: forward it only for a window we
    // actually announced, and forget it so the HWND can be reused cleanly.
    if event == EVENT_OBJECT_DESTROY {
        if seen_windows().remove(&key) {
            forward(build_rail_event(EVENT_OBJECT_DESTROY, hwnd));
        }
        return;
    }

    // Everything else must be visible to matter. A window is usually NOT yet
    // visible at its CREATE, so the create is announced lazily on the first
    // visible event below.
    if !IsWindowVisible(hwnd).as_bool() {
        return;
    }

    // First visible sighting → announce CREATED (carries geometry + the
    // extracted icon); later sightings keep their natural kind (MOVE, etc.).
    let first_sighting = seen_windows().insert(key);
    let effective_event = if first_sighting {
        EVENT_OBJECT_CREATE
    } else {
        event
    };
    forward(build_rail_event(effective_event, hwnd));
}

/// Push a (possibly `None`) rail event onto the channel, non-blocking.
fn forward(rail_event: Option<RailWindowEvent>) {
    let Some(rail_event) = rail_event else { return };
    if let Some(sender) = EVENT_SENDER.get() {
        // try_send: this is the Win32 pump thread, so blocking on a full
        // queue would stall every other window event in the system.
        if let Err(e) = sender.try_send(rail_event) {
            debug!("Failed to send rail event: {:?}", e);
        }
    }
}
