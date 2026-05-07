//! tonic transport layer over AF_VSOCK with mTLS handshake.
//!
//! Transport selection follows DEC-0005: production paths use
//! [`transport::real::RealTransport`]; tests and `--features mock` builds
//! get [`transport::mock::MockTransport`] with failure-injection hooks.
//! Both implement `tower::Service<Uri>` so tonic can dial through either.

pub mod channel;
pub mod client;
pub mod tls;
pub mod transport;

pub use transport::real::RealTransport;
#[cfg(any(test, feature = "mock"))]
pub use transport::mock::{MockHooks, MockTransport};
