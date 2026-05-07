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
    // Mock/dev binary emits the same JSON Lines schema as the Python
    // host; the integration harness greps stderr for handshake markers.
    // Production (Windows SCM path) logs through `append_log` to
    // %CROSSDESK_LOG_PATH%; switching that to JSON is tracked
    // separately so this commit stays scoped to the dev path.
    let _ = observability::init();

    let rt = tokio::runtime::Runtime::new()?;
    rt.block_on(agent_svc::planes::run())
}
