//! Manager qobject — the QML-facing state object that backs every
//! Manager pane (Dashboard / Apps / Storage / Lifecycle / Diagnose /
//! Logs / Settings / About).
//!
//! All fields start empty / disconnected. Phase 7 Week 27 subscribes to
//! mgmt::Status and overwrites them with live daemon data.

use cxx_qt_lib::{QList, QString, QStringList};

#[cxx_qt::bridge]
pub mod qobject {
    unsafe extern "C++" {
        include!("cxx-qt-lib/qstring.h");
        include!("cxx-qt-lib/qstringlist.h");
        type QString = cxx_qt_lib::QString;
        type QStringList = cxx_qt_lib::QStringList;
    }

    extern "RustQt" {
        #[qobject]
        #[qml_element]
        // VM + FSM
        #[qproperty(QString, vm_state)]
        #[qproperty(QString, fsm_state)]
        #[qproperty(QString, fsm_severity)]
        #[qproperty(QString, uptime_label)]
        #[qproperty(i32, ewma_rtt_ms)]
        #[qproperty(i32, miss_count)]
        #[qproperty(i32, soft_attempts)]
        #[qproperty(i32, auth_rejections)]
        // Resources
        #[qproperty(i32, cpu_percent)]
        #[qproperty(i32, ram_percent)]
        #[qproperty(QString, ram_label)]
        // Apps
        #[qproperty(QStringList, running_apps)]
        #[qproperty(QStringList, curated_apps)]
        #[qproperty(QStringList, discovered_apps)]
        // Storage
        #[qproperty(QStringList, active_mounts)]
        #[qproperty(QStringList, recent_mounts)]
        // Activity feed (already-formatted lines for the Logs/Recent tab)
        #[qproperty(QStringList, recent_activity)]
        #[qproperty(QStringList, log_lines)]
        // Settings
        #[qproperty(QString, language)]
        #[qproperty(QString, theme)]
        #[qproperty(bool, telemetry_enabled)]
        #[qproperty(bool, lean_mode)]
        #[qproperty(i32, hidpi_scale)]
        // Diagnose
        #[qproperty(QStringList, diagnostics)]
        #[qproperty(bool, diagnostics_any_failed)]
        // has_vm: VM image exists on disk (read from env or real check).
        // daemon_connected: host daemon is reachable (Phase 7 sets true on first Status push).
        #[qproperty(bool, has_vm)]
        #[qproperty(bool, daemon_connected)]
        type ManagerState = super::ManagerStateRust;

        #[qinvokable]
        fn refresh(self: Pin<&mut ManagerState>);

        #[qinvokable]
        fn launch_app(self: Pin<&mut ManagerState>, app_id: QString);

        #[qinvokable]
        fn suspend(self: Pin<&mut ManagerState>);

        #[qinvokable]
        fn resume(self: Pin<&mut ManagerState>);

        #[qinvokable]
        fn hard_destroy(self: Pin<&mut ManagerState>);

        #[qinvokable]
        fn rotate_credentials(self: Pin<&mut ManagerState>);

        #[qinvokable]
        fn run_diagnostics(self: Pin<&mut ManagerState>);

        #[qinvokable]
        fn apply_theme(self: Pin<&mut ManagerState>, theme: QString);

        #[qinvokable]
        fn apply_language(self: Pin<&mut ManagerState>, language: QString);
    }

    impl cxx_qt::Constructor<()> for ManagerState {}
}

#[derive(Default)]
pub struct ManagerStateRust {
    vm_state: QString,
    fsm_state: QString,
    fsm_severity: QString,
    uptime_label: QString,
    ewma_rtt_ms: i32,
    miss_count: i32,
    soft_attempts: i32,
    auth_rejections: i32,

    cpu_percent: i32,
    ram_percent: i32,
    ram_label: QString,

    running_apps: QStringList,
    curated_apps: QStringList,
    discovered_apps: QStringList,

    active_mounts: QStringList,
    recent_mounts: QStringList,

    recent_activity: QStringList,
    log_lines: QStringList,

    language: QString,
    theme: QString,
    telemetry_enabled: bool,
    lean_mode: bool,
    hidpi_scale: i32,

    diagnostics: QStringList,
    diagnostics_any_failed: bool,
    has_vm: bool,
    daemon_connected: bool,
}

/// Returns true when the CrossDesk install state file exists on disk,
/// meaning `crossdesk install` completed at least partially on this machine.
/// Phase 7 daemon handshake is the authoritative check; this is the Phase 6 proxy.
fn detect_has_vm() -> bool {
    use std::path::PathBuf;
    let state_dir = std::env::var("XDG_STATE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            let home = std::env::var("HOME").unwrap_or_else(|_| "/".to_owned());
            PathBuf::from(home).join(".local/state")
        });
    state_dir.join("crossdesk/install.state.json").exists()
}

impl cxx_qt::Initialize for qobject::ManagerState {
    fn initialize(self: core::pin::Pin<&mut Self>) {
        // Phase 7 Week 27 will subscribe to mgmt::Status and fill these from
        // a live daemon. Until then, everything starts empty / disconnected
        // so the UI shows genuine "not connected" state rather than fake data.
        let mut this = self;
        this.as_mut().set_vm_state(QString::from("UNKNOWN"));
        this.as_mut().set_fsm_state(QString::from("UNKNOWN"));
        this.as_mut().set_fsm_severity(QString::from("warn"));
        this.as_mut().set_uptime_label(QString::from("—"));
        this.as_mut().set_ewma_rtt_ms(0);
        this.as_mut().set_miss_count(0);
        this.as_mut().set_soft_attempts(0);
        this.as_mut().set_auth_rejections(0);
        this.as_mut().set_cpu_percent(0);
        this.as_mut().set_ram_percent(0);
        this.as_mut().set_ram_label(QString::from("—"));
        this.as_mut().set_running_apps(QStringList::default());
        this.as_mut().set_curated_apps(QStringList::default());
        this.as_mut().set_discovered_apps(QStringList::default());
        this.as_mut().set_active_mounts(QStringList::default());
        this.as_mut().set_recent_mounts(QStringList::default());
        this.as_mut().set_recent_activity(QStringList::default());
        this.as_mut().set_log_lines(QStringList::default());
        this.as_mut().set_language(QString::from("auto"));
        this.as_mut().set_theme(QString::from("system"));
        this.as_mut().set_telemetry_enabled(false);
        this.as_mut().set_lean_mode(false);
        this.as_mut().set_hidpi_scale(0);
        this.as_mut().set_diagnostics(QStringList::default());
        this.as_mut().set_diagnostics_any_failed(false);
        // CROSSDESK_HAS_VM=0/1 overrides the on-disk check (useful in tests / CI).
        // Without the override: presence of install.state.json means the install
        // wizard ran and a VM domain was created on this machine.
        let has_vm = match std::env::var("CROSSDESK_HAS_VM").as_deref() {
            Ok("0") => false,
            Ok("1") => true,
            _ => detect_has_vm(),
        };
        this.as_mut().set_has_vm(has_vm);
        // Phase 7: set to true when the mgmt socket handshake succeeds.
        this.as_mut().set_daemon_connected(false);
    }
}

impl qobject::ManagerState {
    fn refresh(self: core::pin::Pin<&mut Self>) {
        // Phase 7 Week 27: re-emit a Status request through the
        // mgmt-socket client. Phase 6 stub: no-op.
    }

    fn launch_app(self: core::pin::Pin<&mut Self>, _app_id: QString) {
        // Phase 7: forward to mgmt::Launch RPC.
    }

    fn suspend(self: core::pin::Pin<&mut Self>) {
        // Phase 7: forward to mgmt::Suspend RPC.
    }

    fn resume(self: core::pin::Pin<&mut Self>) {
        // Phase 7: forward to mgmt::Resume RPC.
    }

    fn hard_destroy(self: core::pin::Pin<&mut Self>) {
        // Phase 7: forward to mgmt::HardDestroy RPC.
    }

    fn rotate_credentials(self: core::pin::Pin<&mut Self>) {
        // Phase 7: forward to mgmt::RotateCredentials RPC.
    }

    fn run_diagnostics(self: core::pin::Pin<&mut Self>) {
        // Phase 7: forward to mgmt::RunDiagnostics RPC.
    }

    fn apply_theme(mut self: core::pin::Pin<&mut Self>, theme: QString) {
        self.as_mut().set_theme(theme);
    }

    fn apply_language(mut self: core::pin::Pin<&mut Self>, language: QString) {
        self.as_mut().set_language(language);
    }
}

// Phase 7: used to convert Vec<String> daemon responses into QStringList.
#[allow(dead_code)]
fn qsl(items: &[String]) -> QStringList {
    let mut list = QList::<QString>::default();
    for s in items {
        list.append(QString::from(s.as_str()));
    }
    QStringList::from(&list)
}

#[cfg(test)]
mod tests {
    use crate::manager::format::fsm_severity;

    #[test]
    fn fsm_severity_round_trip() {
        assert_eq!(fsm_severity("HEALTHY"), "ok");
        assert_eq!(fsm_severity("DEGRADED"), "warn");
        assert_eq!(fsm_severity("UNKNOWN"), "warn");
    }
}
