//! Tray indicator state — what colour the dot is, what the tooltip
//! says, what the menu items show. Pure data; rendered by `Indicator`.

use std::time::{Duration, SystemTime};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum VmState {
    Off,
    Booting,
    Running,
    Suspended,
    HardDestroying,
    Unknown,
}

impl VmState {
    pub fn label(&self) -> &'static str {
        match self {
            VmState::Off => "OFF",
            VmState::Booting => "BOOTING",
            VmState::Running => "RUNNING",
            VmState::Suspended => "SUSPENDED",
            VmState::HardDestroying => "HARD_DESTROYING",
            VmState::Unknown => "UNKNOWN",
        }
    }

    /// Status-dot colour as a stable identifier the icon resolver
    /// translates to a freedesktop icon name (KSNI uses
    /// `crossdesk-status-{green,yellow,red,grey}`).
    pub fn dot_colour(&self) -> &'static str {
        match self {
            VmState::Running => "green",
            VmState::Booting | VmState::Suspended => "yellow",
            VmState::HardDestroying => "red",
            VmState::Off | VmState::Unknown => "grey",
        }
    }
}

#[derive(Clone, Debug)]
pub struct TrayState {
    pub vm_state: VmState,
    pub fsm_state: String,
    pub uptime: Duration,
    pub running_apps: Vec<RunningApp>,
    pub last_updated: SystemTime,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RunningApp {
    pub app_id: String,
    pub display_name: String,
    pub hwnd: u64,
}

impl Default for TrayState {
    fn default() -> Self {
        Self {
            vm_state: VmState::Unknown,
            fsm_state: "UNKNOWN".to_string(),
            uptime: Duration::ZERO,
            running_apps: Vec::new(),
            last_updated: SystemTime::UNIX_EPOCH,
        }
    }
}

impl TrayState {
    pub fn tooltip(&self) -> String {
        if self.vm_state == VmState::Unknown {
            return "CrossDesk: not connected".to_string();
        }
        let app_count = self.running_apps.len();
        let mins = self.uptime.as_secs() / 60;
        format!(
            "CrossDesk: {} ({} app{}, up {} min)",
            self.vm_state.label(),
            app_count,
            if app_count == 1 { "" } else { "s" },
            mins,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dot_colour_running_is_green() {
        assert_eq!(VmState::Running.dot_colour(), "green");
    }

    #[test]
    fn dot_colour_destroy_is_red() {
        assert_eq!(VmState::HardDestroying.dot_colour(), "red");
    }

    #[test]
    fn label_round_trips_states() {
        for state in [
            VmState::Off,
            VmState::Booting,
            VmState::Running,
            VmState::Suspended,
            VmState::HardDestroying,
            VmState::Unknown,
        ] {
            assert!(!state.label().is_empty());
        }
    }

    #[test]
    fn tooltip_when_unknown_says_not_connected() {
        let s = TrayState::default();
        assert!(s.tooltip().contains("not connected"));
    }

    #[test]
    fn tooltip_when_running_describes_apps_and_uptime() {
        let s = TrayState {
            vm_state: VmState::Running,
            fsm_state: "HEALTHY".to_string(),
            uptime: Duration::from_secs(1234),
            running_apps: vec![
                RunningApp {
                    app_id: "notepad".into(),
                    display_name: "Notepad".into(),
                    hwnd: 0x1,
                },
                RunningApp {
                    app_id: "calc".into(),
                    display_name: "Calc".into(),
                    hwnd: 0x2,
                },
            ],
            last_updated: SystemTime::UNIX_EPOCH,
        };
        let t = s.tooltip();
        assert!(t.contains("RUNNING"));
        assert!(t.contains("2 apps"));
        assert!(t.contains("20 min"));
    }

    #[test]
    fn tooltip_singular_app() {
        let s = TrayState {
            vm_state: VmState::Running,
            uptime: Duration::from_secs(60),
            running_apps: vec![RunningApp {
                app_id: "n".into(),
                display_name: "N".into(),
                hwnd: 1,
            }],
            ..TrayState::default()
        };
        assert!(s.tooltip().contains("1 app,"));
    }
}
