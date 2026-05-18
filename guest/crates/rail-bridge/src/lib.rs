//! Forwards Win32 RAIL window events (create / destroy / move / focus /
//! title change) from the guest agent to the host gRPC stream.
//!
//! Active only on Windows targets: the platform shims under `#[cfg(not(windows))]`
//! exist so the workspace still builds during `cargo check` on the developer's
//! macOS/Linux host (a sanity-check, not a runtime path). The real implementation
//! drives a dedicated message-pump thread that owns the WinEvent hook for the
//! lifetime of the agent service — see [`start_hook_thread`].

#[cfg(windows)]
pub mod events;
#[cfg(windows)]
pub mod windows;

#[cfg(windows)]
pub use windows::{request_shutdown, start_hook_thread};

/// Non-Windows stub: logs an error and returns. Exists so the workspace
/// can `cargo check` on macOS/Linux dev hosts.
#[cfg(not(windows))]
pub fn start_hook_thread(
    _sender: tokio::sync::mpsc::Sender<proto::crossdesk::v1::RailWindowEvent>,
) {
    tracing::error!("Rail bridge is only supported on Windows.");
}

/// Non-Windows stub: no-op (no message pump exists to signal).
#[cfg(not(windows))]
pub fn request_shutdown() {}
