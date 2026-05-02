//! Transport-channel construction for the guest agent.
//!
//! Today this is a thin wrapper around `client::create_secure_channel` — the
//! real AF_VSOCK / AF_HYPERV connector lives in `connector.rs` (currently
//! falls back to TCP loopback for development on hosts without vhost-vsock
//! enabled). When the custom Hyper-V WSAConnect connector lands, the public
//! `connect_vsock` entry point will route through it transparently and callers
//! don't need to know.

use tonic::transport::Channel;

use crate::client::create_secure_channel;

/// Open a Channel to the host. Endpoint examples:
///   - `http://127.0.0.1:50051` (dev fallback over TCP)
///   - `http://[::1]:50051`     (loopback v6)
///   - vsock URLs once the connector lands (see `connector.rs`)
pub async fn connect(
    ca_cert_pem: &[u8],
    guest_cert_pem: &[u8],
    guest_key_pem: &[u8],
    endpoint_url: String,
) -> anyhow::Result<Channel> {
    create_secure_channel(ca_cert_pem, guest_cert_pem, guest_key_pem, endpoint_url).await
}
