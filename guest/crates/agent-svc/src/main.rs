//! Two entry points coexist here, gated by cfg:
//!
//! - Windows production: hand off to the SCM via
//!   `service::start_service_dispatcher`.
//! - Anywhere with `--features mock` (and any non-Windows host
//!   regardless of features): run the gRPC planes directly under a
//!   tokio runtime. This is what the in-process integration harness
//!   exercises on macOS/Linux.
//!
//! Console escape hatch (Windows, production build): `agent.exe console`
//! — or `CROSSDESK_CONSOLE=1` in the environment — runs the gRPC planes
//! directly under tokio WITHOUT the SCM dispatcher, while keeping the
//! real Windows implementations (LogonUserW credential verify, real
//! transport). This is for the TCP-SLIRP bring-up / diagnostics before
//! the NT service is registered: it needs no SCM, no service install,
//! and no elevation, so it can be run as the logged-in user over an RDP
//! session. The default (no arg, no env) still hands off to the SCM.

#[cfg(all(windows, not(feature = "mock")))]
fn main() -> anyhow::Result<()> {
    if console_mode_requested() {
        // Same body as the mock/non-Windows path, but compiled against
        // the real Windows impls (the `mock` feature is NOT enabled here).
        let _ = observability::init();
        let rt = tokio::runtime::Runtime::new()?;
        return rt.block_on(agent_svc::planes::run());
    }
    agent_svc::service::start_service_dispatcher()?;
    Ok(())
}

/// True when the operator asked for the foreground/console path instead
/// of the SCM dispatcher: either a literal ``console`` argument or
/// ``CROSSDESK_CONSOLE`` set to any non-empty value.
#[cfg(all(windows, not(feature = "mock")))]
fn console_mode_requested() -> bool {
    std::env::args().any(|a| a == "console")
        || std::env::var_os("CROSSDESK_CONSOLE").is_some()
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
