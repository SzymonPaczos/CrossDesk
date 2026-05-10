//! Manager qobject — the QML-facing state object that backs every
//! Manager pane (Dashboard / Apps / Storage / Lifecycle / Diagnose /
//! Logs / Settings / About).
//!
//! Phase 6: mock-driven. The qobject exposes properties and invokables;
//! a stub data source seeds canned values so the Mac dev environment
//! can render every pane against believable data without a daemon.
//!
//! Phase 7 Week 27 swaps the stub for a tonic gRPC client connected to
//! `unix://$XDG_RUNTIME_DIR/crossdesk-host.sock`. The QML doesn't need
//! to know — it sees the same property names, just real values.

use cxx_qt_lib::{QList, QString, QStringList};

use crate::manager::format::{format_bytes, format_stars, format_uptime, fsm_severity};

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
        // Routing — Phase 7 will query daemon; Phase 6 mock always true
        #[qproperty(bool, has_vm)]
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
}

impl cxx_qt::Initialize for qobject::ManagerState {
    fn initialize(self: core::pin::Pin<&mut Self>) {
        // Seed mock state so QML has something to render against in
        // Mac dev mode. Phase 7 Week 27 will subscribe to mgmt::Status
        // and overwrite these fields on every push.
        let mut this = self;
        this.as_mut().set_vm_state(QString::from("RUNNING"));
        this.as_mut().set_fsm_state(QString::from("HEALTHY"));
        this.as_mut().set_fsm_severity(QString::from(fsm_severity("HEALTHY")));
        this.as_mut().set_uptime_label(QString::from(&format_uptime(
            std::time::Duration::from_secs(842),
        )));
        this.as_mut().set_ewma_rtt_ms(1);
        this.as_mut().set_cpu_percent(12);
        this.as_mut().set_ram_percent(48);
        this.as_mut().set_ram_label(QString::from(&format!(
            "{} / {}",
            format_bytes(2 * 1024 * 1024 * 1024),
            format_bytes(4 * 1024 * 1024 * 1024)
        )));
        this.as_mut().set_running_apps(QStringList::default());
        let curated = mock_curated_apps();
        this.as_mut().set_curated_apps(qsl(&curated));
        this.as_mut().set_discovered_apps(QStringList::default());
        this.as_mut().set_active_mounts(QStringList::default());
        this.as_mut().set_recent_mounts(QStringList::default());
        this.as_mut().set_recent_activity(qsl(&mock_activity()));
        this.as_mut().set_log_lines(qsl(&mock_log_lines()));
        this.as_mut().set_language(QString::from("auto"));
        this.as_mut().set_theme(QString::from("system"));
        this.as_mut().set_hidpi_scale(0);
        this.as_mut().set_diagnostics(qsl(&mock_diagnostics()));
        this.as_mut().set_has_vm(true);
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

fn qsl(items: &[String]) -> QStringList {
    let mut list = QList::<QString>::default();
    for s in items {
        list.append(QString::from(s.as_str()));
    }
    QStringList::from(&list)
}

fn mock_curated_apps() -> Vec<String> {
    vec![
        format!("notepad|Notepad|Built-in|{}", format_stars(5)),
        format!("calc|Calculator|Built-in|{}", format_stars(5)),
        format!("cmd|Command Prompt|Built-in|{}", format_stars(5)),
        format!("paint|Paint|Built-in|{}", format_stars(5)),
        format!("word|Microsoft Word|Office|{}", format_stars(4)),
        format!("excel|Microsoft Excel|Office|{}", format_stars(5)),
    ]
}

fn mock_activity() -> Vec<String> {
    vec![
        "16:04  ✓ Notepad launched".to_string(),
        "16:01  ↻ Suspend → Resume cycle (1.7 s)".to_string(),
        "15:43  ✓ JIT mount: ~/Documents/spec.docx → Word, 12.4 s".to_string(),
        "15:42  ✓ JIT detach: spec.docx (LockReport: 0 handles)".to_string(),
    ]
}

fn mock_log_lines() -> Vec<String> {
    vec![
        "16:04:23 [info]    heartbeat_state_transition HEALTHY→DEGRADED".to_string(),
        "16:04:23 [warn]    heartbeat_graceful_shutdown_dispatched".to_string(),
        "16:04:24 [info]    heartbeat_state_transition DEGRADED→HEALTHY".to_string(),
        "16:04:30 [info]    rail_create hwnd=0x4321 title='Notepad'".to_string(),
    ]
}

fn mock_diagnostics() -> Vec<String> {
    vec![
        "ok|kvm_device|".to_string(),
        "ok|freerdp|xfreerdp 3.5.1".to_string(),
        "ok|libvirt|".to_string(),
        "warn|notify-send|notify-send not on PATH".to_string(),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::manager::format::fsm_severity;

    #[test]
    fn fsm_severity_round_trip() {
        assert_eq!(fsm_severity("HEALTHY"), "ok");
        assert_eq!(fsm_severity("DEGRADED"), "warn");
    }

    #[test]
    fn mock_curated_apps_has_office() {
        let apps = mock_curated_apps();
        assert!(apps.iter().any(|a| a.contains("word|Microsoft Word")));
    }

    #[test]
    fn mock_activity_chronological_format() {
        let lines = mock_activity();
        for line in lines {
            // each line begins with HH:MM
            assert!(&line[2..3] == ":");
        }
    }
}
