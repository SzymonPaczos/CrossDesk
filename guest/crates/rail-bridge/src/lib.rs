#[cfg(windows)]
pub mod events;
#[cfg(windows)]
pub mod windows;

#[cfg(windows)]
pub use windows::{start_hook_thread, request_shutdown};

#[cfg(not(windows))]
pub fn start_hook_thread(_sender: tokio::sync::mpsc::Sender<proto::crossdesk::v1::RailWindowEvent>) {
    tracing::error!("Rail bridge is only supported on Windows.");
}

#[cfg(not(windows))]
pub fn request_shutdown() {}
