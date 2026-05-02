use std::ffi::OsString;
use std::fs::OpenOptions;
use std::io::Write as _;
use std::path::Path;
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

use ipc_vsock::client::AuthCarrier;
use ipc_vsock::tls::{fingerprint_sha256, TlsMaterial};
use proto::crossdesk::v1::control_service_client::ControlServiceClient;
use proto::crossdesk::v1::filesystem_service_client::FilesystemServiceClient;
use proto::crossdesk::v1::heartbeat_service_client::HeartbeatServiceClient;

pub const SERVICE_NAME: &str = "CrossDeskAgent";
const LOG_PATH: &str = r"C:\CrossDesk\agent.log";

/// PKI material installed by autounattend.xml at first boot.
const PKI_DIR: &str = r"C:\CrossDesk\pki";

/// Host gRPC endpoint. Production target is `vsock://2:50051` once the
/// AF_HYPERV connector lands; the TCP form below works against the dev host
/// running on the same Linux/Mac machine through QEMU `-net user` portfwd.
const HOST_ENDPOINT: &str = "http://127.0.0.1:50051";

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

    // Build a multi-thread runtime — the three CrossDesk planes run as
    // independent tasks, and rail-bridge spawns its own OS thread for the
    // Win32 message loop. expect() is the right escape hatch here: if Tokio
    // can't initialize, the agent has no way to recover and the SCM will
    // restart us.
    let rt = tokio::runtime::Runtime::new().expect("Failed to create Tokio runtime");

    rt.spawn(async {
        if let Err(e) = run_agent_planes().await {
            append_log(&format!("agent planes terminated: {e:#}"));
        }
    });

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

/// Top-level driver for the three CrossDesk service planes.
///
/// All three share one TLS-secured gRPC channel and one AuthCarrier (sequence
/// state is per-plane in proto, but the fingerprint+nonce are identical for
/// the lifetime of this connection).
async fn run_agent_planes() -> anyhow::Result<()> {
    let pki = TlsMaterial::from_dir(Path::new(PKI_DIR))?;
    // The fingerprint stamped onto every outgoing AuthContext is the *host*
    // cert's, since that is what AuthValidator on the other side compares
    // against the TLS-extracted leaf. Guest agent reads the host cert it's
    // pinned against (ca-signed) from its PKI directory.
    let host_cert_pem = std::fs::read(Path::new(PKI_DIR).join("host.crt"))?;
    let host_fp = fingerprint_sha256(&host_cert_pem)?;

    let channel = ipc_vsock::channel::connect(
        &pki.ca_pem,
        &pki.cert_pem,
        &pki.key_pem,
        HOST_ENDPOINT.to_string(),
    )
    .await?;

    let auth = AuthCarrier::new(host_fp);

    let session_handle = tokio::spawn(crate::session::run_control_session(
        ControlServiceClient::new(channel.clone()),
        auth.clone(),
    ));
    let heartbeat_handle = tokio::spawn(crate::heartbeat::run_heartbeat_loop(
        HeartbeatServiceClient::new(channel.clone()),
        auth.clone(),
    ));
    let filesystem_handle = tokio::spawn(crate::filesystem::run_filesystem_channel(
        FilesystemServiceClient::new(channel),
        auth,
    ));

    // First plane to die brings the rest down — they all sit on the same
    // gRPC channel so failure is correlated. SCM stop signal is observed
    // separately in run_service.
    tokio::select! {
        r = session_handle    => r??,
        r = heartbeat_handle  => r??,
        r = filesystem_handle => r??,
    };
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
