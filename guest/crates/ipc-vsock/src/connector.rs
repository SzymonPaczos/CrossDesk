use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};
use tokio::net::TcpStream;
use tower::Service;
use tonic::transport::Uri;

/// A custom connector that allows Tonic to connect over Hyper-V sockets (vsock equivalent on Windows).
#[derive(Clone)]
pub struct VsockConnector {
    // ID maszyny hosta, dla vsock zazwyczaj to jest znany GUID lub 2 w Linuksie
    pub host_guid: String,
    pub port: u32,
}

impl Service<Uri> for VsockConnector {
    type Response = TcpStream; // TODO: Replace with custom AsyncVsockStream wrapper
    type Error = std::io::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>> + Send>>;

    fn poll_ready(&mut self, _cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        Poll::Ready(Ok(()))
    }

    fn call(&mut self, _uri: Uri) -> Self::Future {
        // ObObecnie Tokio nie ma natywnego wsparcia dla AF_HYPERV.
        // Wymagałoby to napisania integracji z `mio`.
        // Jako mock dla Fazy 2 uruchamiamy normalne połączenie TCP,
        // jednak w produkcji tutaj znajdzie się wywołanie WSAConnect z AF_HYPERV.
        
        // TODO: Implementacja AF_HYPERV WSAConnect
        let addr = format!("127.0.0.1:{}", self.port);
        
        Box::pin(async move {
            tracing::info!("Connecting to vsock/TCP fallback on {}", addr);
            TcpStream::connect(addr).await
        })
    }
}
