//! Production transport. Today: TCP loopback (the dev-host port-forwarded
//! into the VM via `qemu -net user`). Future: AF_HYPERV `WSAConnect` against
//! the host UUID. The `tower::Service<Uri>` shape stays stable across the
//! switch so call sites don't change.
//!
//! Mock counterpart lives in `super::mock`. They share this trait surface
//! by both implementing `tower::Service<Uri, Response = TcpStream>`.

use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};
use hyper_util::rt::TokioIo;
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
        let host = uri.host().unwrap_or("127.0.0.1").to_string();
        let port = uri.port_u16().unwrap_or(50051);
        Box::pin(async move {
            let addr = format!("{host}:{port}");
            tracing::info!(target = %addr, "real transport dialing TCP loopback");
            Ok(TokioIo::new(TcpStream::connect(addr).await?))
        })
    }
}
