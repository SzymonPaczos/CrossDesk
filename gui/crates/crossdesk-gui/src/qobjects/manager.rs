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
    has_install_state_under(&state_dir_from_env())
}

/// Resolve the user's XDG state directory from the environment.
/// Separated for unit testing — the bare ``detect_has_vm`` reads the
/// real process environment, but tests inject ``state_dir`` directly.
fn state_dir_from_env() -> std::path::PathBuf {
    use std::path::PathBuf;
    std::env::var("XDG_STATE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            let home = std::env::var("HOME").unwrap_or_else(|_| "/".to_owned());
            PathBuf::from(home).join(".local/state")
        })
}

/// Pure-IO core of [`detect_has_vm`]. Takes the resolved state dir so
/// tests can point it at a tempdir without touching the process env.
fn has_install_state_under(state_dir: &std::path::Path) -> bool {
    state_dir.join("crossdesk/install.state.json").exists()
}

/// Returns true when the host daemon's management Unix socket is
/// present, meaning the daemon is up and the mgmt plane is bound.
///
/// Mirrors `crossdesk_host.ipc.management.mgmt_socket_path()` from
/// the Python host: honour ``$XDG_RUNTIME_DIR`` per the freedesktop
/// spec; fall back to ``~/.local/run/`` for environments that don't
/// set it (Mac dev, minimal containers).
///
/// Phase 7 Week 27 will replace this with a real gRPC Status
/// subscription; today's check is a fast existence probe so the GUI
/// can render the "daemon offline" panel within the first paint
/// cycle without blocking on a gRPC connect.
fn detect_daemon_running() -> bool {
    has_mgmt_socket_under(&runtime_dir_from_env())
}

fn runtime_dir_from_env() -> std::path::PathBuf {
    use std::path::PathBuf;
    if let Ok(dir) = std::env::var("XDG_RUNTIME_DIR") {
        return PathBuf::from(dir);
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| "/".to_owned());
    PathBuf::from(home).join(".local/run")
}

/// Pure-IO core of [`detect_daemon_running`]. Takes the resolved
/// runtime dir so tests can point it at a tempdir.
fn has_mgmt_socket_under(runtime_dir: &std::path::Path) -> bool {
    runtime_dir.join("crossdesk-host.sock").exists()
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
        // Detection mirrors crossdesk_host.ipc.management.mgmt_socket_path:
        // the mgmt-plane Unix socket exists iff the daemon is currently
        // running. Phase 7 Week 27 will replace this with a real gRPC
        // Status handshake; today's fast existence probe means the
        // GUI renders the right state (Dashboard vs "daemon offline")
        // on first paint without blocking on a connect.
        this.as_mut().set_daemon_connected(detect_daemon_running());
    }
}

impl qobject::ManagerState {
    fn refresh(self: core::pin::Pin<&mut Self>) {
        // Phase 7 Week 27 will re-emit a Status request through the
        // mgmt-socket client. Today, the only thing that can change
        // between two paints without a daemon push is the daemon
        // process going up/down — re-check socket existence so the
        // QML "Retry connection" button on the daemon-offline panel
        // does the right thing.
        let mut this = self;
        this.as_mut().set_daemon_connected(detect_daemon_running());
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
    use super::{has_install_state_under, has_mgmt_socket_under, qsl};
    use crate::manager::format::fsm_severity;
    use cxx_qt_lib::{QList, QString};
    use std::fs;

    #[test]
    fn fsm_severity_round_trip() {
        assert_eq!(fsm_severity("HEALTHY"), "ok");
        assert_eq!(fsm_severity("DEGRADED"), "warn");
        // "UNKNOWN" falls through the match arm in
        // crate::manager::format::fsm_severity because it's not one of
        // the recognised state names (it's the post-normalisation
        // catch-all string itself). The QML side renders any non-
        // recognised severity as the neutral "—" placeholder.
        assert_eq!(fsm_severity("UNKNOWN"), "unknown");
    }

    #[test]
    fn has_install_state_false_when_directory_empty() {
        let tmp = tempdir();
        assert!(!has_install_state_under(tmp.path()));
    }

    #[test]
    fn has_install_state_true_when_marker_file_present() {
        let tmp = tempdir();
        let crossdesk_dir = tmp.path().join("crossdesk");
        fs::create_dir_all(&crossdesk_dir).unwrap();
        fs::write(crossdesk_dir.join("install.state.json"), "{}").unwrap();
        assert!(has_install_state_under(tmp.path()));
    }

    #[test]
    fn has_install_state_false_when_crossdesk_dir_exists_without_marker() {
        let tmp = tempdir();
        fs::create_dir_all(tmp.path().join("crossdesk")).unwrap();
        assert!(!has_install_state_under(tmp.path()));
    }

    #[test]
    fn has_install_state_false_when_state_dir_missing() {
        let tmp = tempdir();
        let missing = tmp.path().join("definitely-not-here");
        assert!(!has_install_state_under(&missing));
    }

    #[test]
    fn has_install_state_does_not_follow_wrong_filename() {
        let tmp = tempdir();
        let crossdesk_dir = tmp.path().join("crossdesk");
        fs::create_dir_all(&crossdesk_dir).unwrap();
        // Adjacent file with the wrong name: the probe must not be
        // fooled by an unrelated artefact in the crossdesk/ tree.
        fs::write(crossdesk_dir.join("install.state.bak"), "{}").unwrap();
        assert!(!has_install_state_under(tmp.path()));
    }

    #[test]
    fn qsl_empty_slice_returns_empty_list() {
        let list = qsl(&[]);
        let qlist: QList<QString> = (&list).into();
        assert_eq!(qlist.len(), 0);
    }

    #[test]
    fn qsl_preserves_order_and_content() {
        let list = qsl(&["alpha".to_owned(), "beta".to_owned(), "gamma".to_owned()]);
        let qlist: QList<QString> = (&list).into();
        assert_eq!(qlist.len(), 3);
        assert_eq!(qlist.get(0), Some(&QString::from("alpha")));
        assert_eq!(qlist.get(1), Some(&QString::from("beta")));
        assert_eq!(qlist.get(2), Some(&QString::from("gamma")));
    }

    #[test]
    fn qsl_handles_non_ascii_text() {
        let list = qsl(&["Łódź".to_owned(), "東京".to_owned(), "café".to_owned()]);
        let qlist: QList<QString> = (&list).into();
        assert_eq!(qlist.len(), 3);
        assert_eq!(qlist.get(0), Some(&QString::from("Łódź")));
        assert_eq!(qlist.get(2), Some(&QString::from("café")));
    }

    #[test]
    fn has_mgmt_socket_false_when_runtime_dir_empty() {
        let tmp = tempdir();
        assert!(!has_mgmt_socket_under(tmp.path()));
    }

    #[test]
    fn has_mgmt_socket_true_when_socket_present() {
        let tmp = tempdir();
        // We don't need a real Unix socket; the GUI's startup probe only
        // checks `Path::exists()`, which returns true for any
        // file/socket/dir entry.
        fs::write(tmp.path().join("crossdesk-host.sock"), "").unwrap();
        assert!(has_mgmt_socket_under(tmp.path()));
    }

    #[test]
    fn has_mgmt_socket_false_when_runtime_dir_missing() {
        let tmp = tempdir();
        let missing = tmp.path().join("definitely-not-here");
        assert!(!has_mgmt_socket_under(&missing));
    }

    #[test]
    fn has_mgmt_socket_does_not_follow_wrong_name() {
        let tmp = tempdir();
        fs::write(tmp.path().join("crossdesk-host.sock.bak"), "").unwrap();
        fs::write(tmp.path().join("other.sock"), "").unwrap();
        assert!(!has_mgmt_socket_under(tmp.path()));
    }

    fn tempdir() -> tempfile::TempDir {
        tempfile::tempdir().expect("create tempdir")
    }
}
