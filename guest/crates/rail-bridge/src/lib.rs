#[cfg(windows)]
pub mod events;
#[cfg(windows)]
pub mod windows;

#[cfg(windows)]
pub use windows::{request_shutdown, start_hook_thread};

#[cfg(not(windows))]
pub fn start_hook_thread(
    _sender: tokio::sync::mpsc::Sender<proto::crossdesk::v1::RailWindowEvent>,
) {
    tracing::error!("Rail bridge is only supported on Windows.");
}

#[cfg(not(windows))]
pub fn request_shutdown() {}
