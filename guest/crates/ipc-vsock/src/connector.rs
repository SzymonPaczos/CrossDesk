use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};
use tokio::net::TcpStream;
use tonic::transport::Uri;
use tower::Service;

/// Dev-loopback connector used while the AF_HYPERV vsock backend is not
/// implemented yet. It claims a vsock-shaped target but actually dials
/// `127.0.0.1:<port>` over TCP, which is what `qemu -net user` portfwd sets
/// up between the macOS/Linux dev host and the guest. Production builds will
/// replace `call` with a `WSAConnect` against AF_HYPERV; the public surface
/// stays the same so call sites do not change.
#[derive(Clone)]
pub struct VsockConnector {
    pub host_guid: String,
    pub port: u32,
}

impl Service<Uri> for VsockConnector {
    type Response = TcpStream;
    type Error = std::io::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>> + Send>>;

    fn poll_ready(&mut self, _cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        Poll::Ready(Ok(()))
    }

    fn call(&mut self, _uri: Uri) -> Self::Future {
        let addr = format!("127.0.0.1:{}", self.port);
        Box::pin(async move {
            tracing::info!(target = %addr, "vsock dev-loopback connect");
            TcpStream::connect(addr).await
        })
    }
}
