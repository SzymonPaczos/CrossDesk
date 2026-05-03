//! NT Service entry-point: SCM registration and tokio main-loop lifecycle.

pub mod host_uuid;
#[cfg(windows)]
pub mod service;

pub mod session;
pub mod heartbeat;
pub mod filesystem;
