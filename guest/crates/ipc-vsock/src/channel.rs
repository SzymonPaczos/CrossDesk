//! Channel construction. The transport choice is the abstraction
//! per DEC-0005: production calls [`connect`] (uses [`RealTransport`]),
//! tests call [`connect_with_transport`] supplying any
//! `tower::Service<Uri>`.

use hyper_util::rt::TokioIo;
use std::io;
use tokio::net::TcpStream;
use tonic::transport::{Channel, Uri};
use tower::Service;

use crate::client::build_endpoint;
use crate::transport::real::RealTransport;

/// Open a Channel to the host using the production transport.
///
/// Endpoint examples while we are on TCP loopback dev path:
///   - `http://127.0.0.1:50051` (dev fallback over TCP)
///   - `http://[::1]:50051`     (loopback v6)
///
/// Once the AF_HYPERV connector lands, the URL will switch to a vsock
/// scheme and `RealTransport::call` interprets it.
pub async fn connect(
    ca_cert_pem: &[u8],
    guest_cert_pem: &[u8],
    guest_key_pem: &[u8],
    endpoint_url: String,
) -> anyhow::Result<Channel> {
    connect_with_transport(
        ca_cert_pem,
        guest_cert_pem,
        guest_key_pem,
        endpoint_url,
        RealTransport,
    )
    .await
}

/// Connect using an explicit `tower::Service<Uri>` transport. Lets tests
/// inject `MockTransport` with failure hooks without touching production
/// configuration.
pub async fn connect_with_transport<S>(
    ca_cert_pem: &[u8],
    guest_cert_pem: &[u8],
    guest_key_pem: &[u8],
    endpoint_url: String,
    transport: S,
) -> anyhow::Result<Channel>
where
    S: Service<Uri, Response = TokioIo<TcpStream>, Error = io::Error> + Clone + Send + 'static,
    S::Future: Send + 'static,
{
    let endpoint = build_endpoint(ca_cert_pem, guest_cert_pem, guest_key_pem, endpoint_url)?;
    Ok(endpoint.connect_with_connector(transport).await?)
}
