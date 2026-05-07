use std::ffi::OsString;
use std::fs::OpenOptions;
use std::io::Write as _;
use std::path::PathBuf;
use std::sync::mpsc;
use std::time::SystemTime;

use windows_service::{
    define_windows_service,
    service::{
        ServiceControl, ServiceControlAccept, ServiceExitCode, ServiceState, ServiceStatus,
        ServiceType,
    },
    service_control_handler::{self, ServiceControlHandlerResult},
    service_dispatcher,
};

use crate::planes;

pub const SERVICE_NAME: &str = "CrossDeskAgent";

const DEFAULT_LOG_FILE: &str = "agent.log";
const ENV_LOG_PATH: &str = "CROSSDESK_LOG_PATH";

fn log_path() -> PathBuf {
    std::env::var_os(ENV_LOG_PATH)
        .map(PathBuf::from)
        .unwrap_or_else(|| planes::agent_dir().join(DEFAULT_LOG_FILE))
}

define_windows_service!(ffi_service_main, service_main);

fn service_main(_args: Vec<OsString>) {
    // Errors from run_service are already written to agent.log before returning.
    let _ = run_service();
}

/// Entry point for the NT service binary. Hands the SCM the
/// macro-generated `ffi_service_main`, which is private by construction
/// of `define_windows_service!`.
pub fn start_service_dispatcher() -> Result<(), windows_service::Error> {
    service_dispatcher::start(SERVICE_NAME, ffi_service_main)
}

pub fn run_service() -> anyhow::Result<()> {
    let (stop_tx, stop_rx) = mpsc::channel::<()>();

    let status_handle = service_control_handler::register(SERVICE_NAME, move |ctrl| match ctrl {
        ServiceControl::Stop => {
            // best-effort: if the receiver is already gone, the service is exiting anyway
            let _ = stop_tx.send(());
            ServiceControlHandlerResult::NoError
        }
        ServiceControl::Interrogate => ServiceControlHandlerResult::NoError,
        _ => ServiceControlHandlerResult::NotImplemented,
    })?;

    status_handle.set_service_status(ServiceStatus {
        service_type: ServiceType::OWN_PROCESS,
        current_state: ServiceState::Running,
        controls_accepted: ServiceControlAccept::STOP,
        exit_code: ServiceExitCode::Win32(0),
        checkpoint: 0,
        wait_hint: std::time::Duration::default(),
        process_id: None,
    })?;

    append_log("CrossDeskAgent started");

    // Build a multi-thread runtime — the three CrossDesk planes run as
    // independent tasks, and rail-bridge spawns its own OS thread for the
    // Win32 message loop. expect() is the right escape hatch here: if Tokio
    // can't initialize, the agent has no way to recover and the SCM will
    // restart us.
    let rt = tokio::runtime::Runtime::new().expect("Failed to create Tokio runtime");

    rt.spawn(async {
        if let Err(e) = planes::run().await {
            append_log(&format!("agent planes terminated: {e:#}"));
        }
    });

    // Block on SCM stop signal — no polling, no spin-wait.
    let _ = stop_rx.recv();

    append_log("CrossDeskAgent stopping");

    // Break the rail-bridge Win32 message pump so its thread exits cleanly.
    rail_bridge::request_shutdown();

    status_handle.set_service_status(ServiceStatus {
        service_type: ServiceType::OWN_PROCESS,
        current_state: ServiceState::Stopped,
        controls_accepted: ServiceControlAccept::empty(),
        exit_code: ServiceExitCode::Win32(0),
        checkpoint: 0,
        wait_hint: std::time::Duration::default(),
        process_id: None,
    })?;

    Ok(())
}

fn append_log(msg: &str) {
    let path = log_path();
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let Ok(mut file) = OpenOptions::new().create(true).append(true).open(&path) else {
        // If the log file is inaccessible, drop the message; logging must never
        // panic or unwind the service thread.
        return;
    };
    let ts = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        // UNIX_EPOCH is always ≤ now on any functioning clock; 0 is a safe sentinel.
        .map_or(0, |d| d.as_secs());
    let _ = writeln!(file, "[{ts}] {msg}");
}
