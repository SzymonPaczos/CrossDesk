//! Two entry points coexist here, gated by cfg:
//!
//! - Windows production: hand off to the SCM via
//!   `service::start_service_dispatcher`.
//! - Anywhere with `--features mock` (and any non-Windows host
//!   regardless of features): run the gRPC planes directly under a
//!   tokio runtime. This is what the in-process integration harness
//!   exercises on macOS/Linux.

#[cfg(all(windows, not(feature = "mock")))]
fn main() -> anyhow::Result<()> {
    agent_svc::service::start_service_dispatcher()?;
    Ok(())
}

#[cfg(any(not(windows), feature = "mock"))]
fn main() -> anyhow::Result<()> {
    use tracing_subscriber::{fmt, EnvFilter};
    // Mock/dev binary writes structured logs to stderr so the
    // integration harness can grep for handshake markers. Production
    // (Windows SCM path) logs to %CROSSDESK_LOG_PATH% via append_log.
    fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .with_writer(std::io::stderr)
        .init();

    let rt = tokio::runtime::Runtime::new()?;
    rt.block_on(agent_svc::planes::run())
}
