//! NT Service entry-point: SCM registration and tokio main-loop lifecycle.

#[cfg(windows)]
pub mod lifecycle;
#[cfg(windows)]
pub mod service;

pub mod session;
pub mod heartbeat;
pub mod filesystem;
