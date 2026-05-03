use std::sync::OnceLock;
use std::sync::atomic::{AtomicU32, Ordering};
use tokio::sync::mpsc;
use windows::Win32::Foundation::{HWND, LPARAM, WPARAM};
use windows::Win32::System::Threading::GetCurrentThreadId;
use windows::Win32::UI::WindowsAndMessaging::{
    DispatchMessageW, GetMessageW, PostThreadMessageW, SetWinEventHook, UnhookWinEvent,
    EVENT_OBJECT_CREATE, EVENT_OBJECT_DESTROY, EVENT_OBJECT_FOCUS, EVENT_OBJECT_LOCATIONCHANGE,
    EVENT_OBJECT_NAMECHANGE, GetAncestor, GA_ROOT, GetWindowLongW, GWL_STYLE, HWINEVENTHOOK,
    IsWindowVisible, MSG, WINEVENT_OUTOFCONTEXT, WINEVENT_SKIPOWNPROCESS, WM_QUIT, WS_CHILD,
    WS_POPUP,
};
use tracing::{debug, error, info};
use proto::crossdesk::v1::RailWindowEvent;
use crate::events::build_rail_event;

static EVENT_SENDER: OnceLock<mpsc::Sender<RailWindowEvent>> = OnceLock::new();

/// Win32 thread ID of the message-pump thread, captured once on startup so a
/// subsequent `request_shutdown()` can post `WM_QUIT` to break the
/// `GetMessageW` loop. Zero means the thread has not started yet.
static HOOK_THREAD_ID: AtomicU32 = AtomicU32::new(0);

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
        HOOK_THREAD_ID.store(unsafe { GetCurrentThreadId() }, Ordering::SeqCst);

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

            UnhookWinEvent(hook);
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

    // DESTROY arrives after the window has already disappeared; everything
    // else must be visible to be worth forwarding.
    if event != EVENT_OBJECT_DESTROY && !IsWindowVisible(hwnd).as_bool() {
        return;
    }

    if let Some(rail_event) = build_rail_event(event, hwnd) {
        if let Some(sender) = EVENT_SENDER.get() {
            // try_send: this is the Win32 pump thread, so blocking on a full
            // queue would stall every other window event in the system.
            if let Err(e) = sender.try_send(rail_event) {
                debug!("Failed to send rail event: {:?}", e);
            }
        }
    }
}
