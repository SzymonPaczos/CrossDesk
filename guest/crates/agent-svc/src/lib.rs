//! NT Service entry-point: SCM registration and tokio main-loop lifecycle.

#[cfg(windows)]
pub mod lifecycle;
#[cfg(windows)]
pub mod service;
