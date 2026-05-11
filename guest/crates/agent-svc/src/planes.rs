//! Cross-platform driver for the three CrossDesk service planes
//! (control, heartbeat, filesystem). Lives outside `service.rs` so it
//! compiles on macOS and Linux for the integration harness — the
//! Windows-NT-service entry point in `service::run_service` calls
//! into here, and so does the `--features mock` dev binary.

use std::path::{Path, PathBuf};

use ipc_vsock::client::AuthCarrier;
use ipc_vsock::tls::{fingerprint_sha256, TlsMaterial};
use observability::trace::{generate_root, inject_interceptor};
use proto::crossdesk::v1::control_service_client::ControlServiceClient;
use proto::crossdesk::v1::filesystem_service_client::FilesystemServiceClient;
use proto::crossdesk::v1::heartbeat_service_client::HeartbeatServiceClient;

const DEFAULT_AGENT_DIR: &str = r"C:\CrossDesk";
const DEFAULT_PKI_SUBDIR: &str = "pki";
/// Production target is `vsock://2:50051` once the AF_HYPERV connector lands;
/// the TCP form is what `qemu -net user` portfwd exposes during development
/// and what the in-process integration harness drives over MockTransport.
/// The `https` scheme is mandatory: tonic's `tls_config` runs only when
/// the URL is `https://`; an `http://` URL silently bypasses TLS and the
/// host server (which requires mTLS) tears the connection down with a
/// confusing `WRONG_VERSION_NUMBER` SSL error.
const DEFAULT_HOST_ENDPOINT: &str = "https://127.0.0.1:50051";

const ENV_AGENT_DIR: &str = "CROSSDESK_AGENT_DIR";
const ENV_PKI_DIR: &str = "CROSSDESK_PKI_DIR";
const ENV_HOST_ENDPOINT: &str = "CROSSDESK_HOST_ENDPOINT";

pub fn agent_dir() -> PathBuf {
    std::env::var_os(ENV_AGENT_DIR)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(DEFAULT_AGENT_DIR))
}

pub fn pki_dir() -> PathBuf {
    std::env::var_os(ENV_PKI_DIR)
        .map(PathBuf::from)
        .unwrap_or_else(|| agent_dir().join(DEFAULT_PKI_SUBDIR))
}

pub fn host_endpoint() -> String {
    std::env::var(ENV_HOST_ENDPOINT).unwrap_or_else(|_| DEFAULT_HOST_ENDPOINT.to_string())
}

/// Drive all three planes against the resolved endpoint and PKI dir.
/// Returns when the first plane terminates or errors; the SCM wrapper
/// (or mock entry point) handles the surrounding lifecycle.
pub async fn run() -> anyhow::Result<()> {
    run_with_pki(&pki_dir(), host_endpoint()).await
}

/// Variant that takes explicit `pki` and `endpoint` so the integration
/// harness can drive a freshly-spawned guest at a specific port without
/// fiddling with environment.
pub async fn run_with_pki(pki_path: &Path, endpoint: String) -> anyhow::Result<()> {
    let pki = TlsMaterial::from_dir(pki_path)?;
    // `peer_cert_fingerprint` in proto/AuthContext is the SENDER's own
    // mTLS leaf — the server's AuthValidator compares it against the
    // TLS layer's view of the client cert (i.e. *our* `guest.crt`).
    // Stamping `host.crt` here used to silently fail the spoof check.
    let own_fp = fingerprint_sha256(&pki.cert_pem)?;

    let channel =
        ipc_vsock::channel::connect(&pki.ca_pem, &pki.cert_pem, &pki.key_pem, endpoint).await?;

    // Each plane is a separate gRPC stream; the host's AuthValidator
    // tracks expected sequence numbers keyed by `stream_nonce`. We
    // therefore need three distinct AuthCarriers (each gets its own
    // random nonce + counter) — sharing one carrier across planes
    // races the validator's sequence check and yields spurious
    // "replay attack" rejections under load.
    //
    // All three planes share one root W3C trace context so a host-
    // side log filter on `trace_id` returns every event for this
    // agent session across control, heartbeat, and filesystem.
    // `inject_interceptor` stamps `traceparent` on every outgoing
    // request via tonic's `InterceptedService`.
    let trace_root = generate_root();
    tracing::info!(trace_id = %trace_root.trace_id, "agent-svc opening planes");

    let session_handle = tokio::spawn(crate::session::run_control_session(
        ControlServiceClient::with_interceptor(
            channel.clone(),
            inject_interceptor(trace_root.clone()),
        ),
        AuthCarrier::new(own_fp.clone()),
    ));
    let heartbeat_handle = tokio::spawn(crate::heartbeat::run_heartbeat_loop(
        HeartbeatServiceClient::with_interceptor(
            channel.clone(),
            inject_interceptor(trace_root.clone()),
        ),
        AuthCarrier::new(own_fp.clone()),
    ));
    let filesystem_handle = tokio::spawn(crate::filesystem::run_filesystem_channel(
        FilesystemServiceClient::with_interceptor(channel, inject_interceptor(trace_root)),
        AuthCarrier::new(own_fp),
    ));

    // First plane to die brings the rest down — they all sit on the same
    // gRPC channel so failure is correlated. SCM stop signal is observed
    // separately in `service::run_service`.
    tokio::select! {
        r = session_handle    => r??,
        r = heartbeat_handle  => r??,
        r = filesystem_handle => r??,
    };
    Ok(())
}
