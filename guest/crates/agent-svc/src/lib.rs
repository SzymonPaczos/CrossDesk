//! NT Service entry-point: SCM registration and tokio main-loop lifecycle.
//!
//! The Windows-service-specific code lives in `service` (cfg(windows));
//! the gRPC plane driver in `planes` is platform-agnostic so the
//! integration harness can run a real guest binary on macOS or Linux
//! against MockTransport.

pub mod host_uuid;
#[cfg(windows)]
pub mod service;

pub mod planes;

pub mod session;
pub mod heartbeat;
pub mod filesystem;
pub mod credentials;
