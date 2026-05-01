use windows::Win32::Foundation::HWND;
use windows::Win32::UI::WindowsAndMessaging::{
    EVENT_OBJECT_CREATE, EVENT_OBJECT_DESTROY, EVENT_OBJECT_FOCUS, EVENT_OBJECT_LOCATIONCHANGE,
    EVENT_OBJECT_NAMECHANGE, GetWindowThreadProcessId, GetWindowRect, GetWindowTextW, GetWindowTextLengthW,
};
use proto::crossdesk::v1::{RailWindowEvent, Rect, rail_window_event::Kind as RailEventKind};

pub fn build_rail_event(event: u32, hwnd: HWND) -> Option<RailWindowEvent> {
    let kind = match event {
        EVENT_OBJECT_CREATE => RailEventKind::Created,
        EVENT_OBJECT_DESTROY => RailEventKind::Destroyed,
        EVENT_OBJECT_LOCATIONCHANGE => RailEventKind::Moved, // Lub Resized zależnie od delty, na razie wspólne
        EVENT_OBJECT_FOCUS => RailEventKind::FocusGained,
        EVENT_OBJECT_NAMECHANGE => RailEventKind::TitleChanged,
        _ => return None,
    };

    let mut process_id = 0;
    unsafe {
        GetWindowThreadProcessId(hwnd, Some(&mut process_id));
    }

    let mut geometry = None;
    if event != EVENT_OBJECT_DESTROY {
        let mut rect = windows::Win32::Foundation::RECT::default();
        unsafe {
            if GetWindowRect(hwnd, &mut rect).is_ok() {
                geometry = Some(Rect {
                    x: rect.left,
                    y: rect.top,
                    width: (rect.right - rect.left).max(0) as u32,
                    height: (rect.bottom - rect.top).max(0) as u32,
                });
            }
        }
    }

    let mut title = String::new();
    if event == EVENT_OBJECT_CREATE || event == EVENT_OBJECT_NAMECHANGE {
        unsafe {
            let len = GetWindowTextLengthW(hwnd);
            if len > 0 {
                let mut buf = vec![0u16; (len + 1) as usize];
                if GetWindowTextW(hwnd, &mut buf) > 0 {
                    if let Some(pos) = buf.iter().position(|&c| c == 0) {
                        buf.truncate(pos);
                    }
                    title = String::from_utf16_lossy(&buf);
                }
            }
        }
    }

    Some(RailWindowEvent {
        window_id: hwnd.0 as u64,
        process_id,
        kind: kind.into(),
        geometry,
        title,
        icon_png: vec![], // TODO w pełnej implementacji
    })
}
