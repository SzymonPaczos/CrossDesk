//! Production transport. Two distinct call paths share a single
//! `RealTransport` type:
//!
//! - **Windows** (`cfg(target_os = "windows")`): When the URI scheme
//!   is `vsock`, dial AF_HYPERV via `WSAConnect` against the
//!   `SOCKADDR_HV` carrying the host's `VmId` GUID. When the URI
//!   scheme is `https` (dev path on Mac portfwd), fall back to TCP.
//! - **Non-Windows**: AF_HYPERV does not exist in the kernel; we
//!   only dial TCP loopback. This is the macOS / Linux integration
//!   harness path.
//!
//! Mock counterpart lives in `super::mock`. Both implementations
//! satisfy `tower::Service<Uri, Response = TokioIo<TcpStream>>`,
//! which is the abstraction tonic 0.12 requires.

use hyper_util::rt::TokioIo;
use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};
use tokio::net::TcpStream;
use tonic::transport::Uri;
use tower::Service;

#[derive(Clone, Debug, Default)]
pub struct RealTransport;

impl Service<Uri> for RealTransport {
    type Response = TokioIo<TcpStream>;
    type Error = std::io::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>> + Send>>;

    fn poll_ready(&mut self, _cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        Poll::Ready(Ok(()))
    }

    fn call(&mut self, uri: Uri) -> Self::Future {
        let scheme = uri.scheme_str().unwrap_or("https").to_string();
        let host = uri.host().unwrap_or("127.0.0.1").to_string();
        let port = uri.port_u16().unwrap_or(50051);
        Box::pin(async move { dial(&scheme, &host, port).await })
    }
}

#[cfg(target_os = "windows")]
async fn dial(scheme: &str, host: &str, port: u16) -> std::io::Result<TokioIo<TcpStream>> {
    if scheme == "vsock" {
        return dial_af_hyperv(host, port).await;
    }
    let addr = format!("{host}:{port}");
    tracing::info!(target = %addr, "real transport dialing TCP loopback");
    Ok(TokioIo::new(TcpStream::connect(addr).await?))
}

#[cfg(not(target_os = "windows"))]
async fn dial(_scheme: &str, host: &str, port: u16) -> std::io::Result<TokioIo<TcpStream>> {
    // AF_HYPERV is Windows-kernel-only. Production builds for the
    // guest target Windows; the macOS/Linux compile path exists for
    // the integration harness, which always speaks `https://` over
    // TCP loopback.
    let addr = format!("{host}:{port}");
    tracing::info!(target = %addr, "real transport dialing TCP loopback");
    Ok(TokioIo::new(TcpStream::connect(addr).await?))
}

/// AF_HYPERV connector — implemented on Windows only. Today this is
/// a placeholder that returns `Unsupported`; once the SCM-bootstrap
/// path runs in a Hyper-V VM with vsock enabled, this body wires
/// `WSAConnect` against `SOCKADDR_HV { Family: AF_HYPERV (34),
/// VmId: <host GUID>, ServiceId: <port> }` and hands the resulting
/// SOCKET to tokio. The URI host carries the VmId GUID.
///
/// Tracked in FOLLOWUPS as the AF_HYPERV vsock connector item.
#[cfg(target_os = "windows")]
async fn dial_af_hyperv(_host: &str, _port: u16) -> std::io::Result<TokioIo<TcpStream>> {
    tracing::error!(
        "AF_HYPERV connector not implemented — falling back to error. \
         See FOLLOWUPS 'AF_HYPERV vsock connector' item."
    );
    Err(std::io::Error::new(
        std::io::ErrorKind::Unsupported,
        "AF_HYPERV connector not yet implemented",
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::str::FromStr;

    #[tokio::test]
    async fn https_uri_dials_tcp_on_any_platform() {
        // Spin up a TCP listener and verify RealTransport's `https`
        // path lands on it.
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();
        tokio::spawn(async move {
            let _ = listener.accept().await;
        });

        let mut transport = RealTransport;
        let uri = Uri::from_str(&format!("https://127.0.0.1:{port}")).unwrap();
        transport.call(uri).await.expect("https dial");
    }

    #[cfg(target_os = "windows")]
    #[tokio::test]
    async fn vsock_uri_returns_unsupported_until_implemented() {
        let mut transport = RealTransport;
        let uri = Uri::from_str("vsock://00000000-0000-0000-0000-000000000000:50051").unwrap();
        let err = transport.call(uri).await.expect_err("vsock should fail");
        assert_eq!(err.kind(), std::io::ErrorKind::Unsupported);
    }
}
