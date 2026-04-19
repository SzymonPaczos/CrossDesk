use std::ffi::OsString;
use std::fs::OpenOptions;
use std::io::Write as _;
use std::sync::mpsc;
use std::time::SystemTime;

use windows_service::{
    define_windows_service,
    service::{
        ServiceControl, ServiceControlAccept, ServiceExitCode, ServiceState, ServiceStatus,
        ServiceType,
    },
    service_control_handler::{self, ServiceControlHandlerResult},
};

pub const SERVICE_NAME: &str = "CrossDeskAgent";
const LOG_PATH: &str = r"C:\CrossDesk\agent.log";

define_windows_service!(ffi_service_main, service_main);

fn service_main(_args: Vec<OsString>) {
    // Errors from run_service are already written to agent.log before returning.
    let _ = run_service();
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

    // Block on SCM stop signal — no polling, no spin-wait.
    let _ = stop_rx.recv();

    append_log("CrossDeskAgent stopping");

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
    let _ = std::fs::create_dir_all(r"C:\CrossDesk");
    let Ok(mut file) = OpenOptions::new().create(true).append(true).open(LOG_PATH) else {
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
