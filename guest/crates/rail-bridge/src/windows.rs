use std::sync::OnceLock;
use tokio::sync::mpsc;
use windows::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
use windows::Win32::UI::WindowsAndMessaging::{
    DispatchMessageW, GetMessageW, SetWinEventHook, UnhookWinEvent,
    EVENT_OBJECT_CREATE, EVENT_OBJECT_DESTROY, EVENT_OBJECT_FOCUS, EVENT_OBJECT_LOCATIONCHANGE,
    EVENT_OBJECT_NAMECHANGE, HWINEVENTHOOK, MSG, WINEVENT_OUTOFCONTEXT, WINEVENT_SKIPOWNPROCESS,
    GetAncestor, GA_ROOT, IsWindowVisible, GetWindowLongW, GWL_STYLE, WS_CHILD, WS_POPUP,
};
use tracing::{debug, error, info};
use proto::crossdesk::v1::RailWindowEvent;
use crate::events::build_rail_event;

static EVENT_SENDER: OnceLock<mpsc::Sender<RailWindowEvent>> = OnceLock::new();

pub fn start_hook_thread(sender: mpsc::Sender<RailWindowEvent>) {
    if EVENT_SENDER.set(sender).is_err() {
        error!("EVENT_SENDER already initialized");
        return;
    }

    std::thread::spawn(|| {
        info!("Starting WinEvent hook thread");
        unsafe {
            // Zakładamy globalnego hooka na zdarzenia powiązane z oknami
            let hook = SetWinEventHook(
                EVENT_OBJECT_CREATE,
                EVENT_OBJECT_LOCATIONCHANGE, // Zakres zawiera m.in. CREATE, DESTROY, FOCUS
                None,
                Some(winevent_proc),
                0, // Wszystkie procesy
                0, // Wszystkie wątki
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
            );

            if hook.is_invalid() {
                error!("Failed to set WinEventHook");
                return;
            }

            // Pętla komunikatów wymagana dla hooków out-of-context
            let mut msg = MSG::default();
            while GetMessageW(&mut msg, HWND::default(), 0, 0).into() {
                DispatchMessageW(&msg);
            }

            UnhookWinEvent(hook);
        }
    });
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
    // Interesują nas tylko zdarzenia dotyczące całego okna (OBJID_WINDOW == 0)
    if idobject != 0 || idchild != 0 || hwnd.is_invalid() {
        return;
    }

    // Filtracja okien potomnych: chcemy tylko okna top-level i popupy (menu kontekstowe)
    let style = GetWindowLongW(hwnd, GWL_STYLE) as u32;
    let is_child = (style & WS_CHILD.0) != 0;
    
    // Zezwalamy na Top-Level i okna typu POPUP (czyli np. context menu w Win32)
    // Aby przepuścić dymki/menu, nie odrzucamy WS_POPUP pomimo że bywają ukryte na pasku zadań.
    if is_child && (style & WS_POPUP.0) == 0 {
        return;
    }

    // Dodatkowo wymuszamy widoczność, z wyjątkiem eventu DESTROY (okno może zniknąć znikając z widoku przed destrukcją)
    if event != EVENT_OBJECT_DESTROY && !IsWindowVisible(hwnd).as_bool() {
        return;
    }

    if let Some(rail_event) = build_rail_event(event, hwnd) {
        if let Some(sender) = EVENT_SENDER.get() {
            // Wysyłamy nieblokująco, bo to wątek Win32 z pętlą GetMessage
            if let Err(e) = sender.try_send(rail_event) {
                // Pełna kolejka (backpressure) lub błąd kanału
                debug!("Failed to send rail event: {:?}", e);
            }
        }
    }
}
