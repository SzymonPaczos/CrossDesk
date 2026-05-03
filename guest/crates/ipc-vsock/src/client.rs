use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use tonic::transport::{Channel, ClientTlsConfig, Certificate, Identity};
use rand::RngCore;

use proto::crossdesk::v1::AuthContext;

/// Per-stream credential vault. Auth lives inside the protobuf payload
/// (`AuthContext` on every frame), not in gRPC metadata headers, so each
/// outbound frame asks this carrier for a freshly-incremented context.
#[derive(Clone)]
pub struct AuthCarrier {
    peer_cert_fingerprint: String,
    stream_nonce: Vec<u8>,
    sequence: Arc<AtomicU64>,
}

impl AuthCarrier {
    /// `peer_cert_fingerprint` is the SHA-256 of the host leaf cert, lowercase
    /// hex, no separators — matches `AuthValidator.extract_peer_fingerprint`
    /// on the server side.
    pub fn new(peer_cert_fingerprint: String) -> Self {
        let mut nonce = vec![0u8; 16];
        rand::thread_rng().fill_bytes(&mut nonce);

        Self {
            peer_cert_fingerprint,
            stream_nonce: nonce,
            sequence: Arc::new(AtomicU64::new(0)),
        }
    }

    /// Mint the next AuthContext. Sequence starts at 1 and increments strictly
    /// monotonically; the host's AuthValidator enforces strict +1 deltas.
    pub fn next(&self) -> AuthContext {
        let seq = self.sequence.fetch_add(1, Ordering::Relaxed) + 1;
        AuthContext {
            peer_cert_fingerprint: self.peer_cert_fingerprint.clone(),
            stream_nonce: self.stream_nonce.clone(),
            sequence: seq,
        }
    }
}

pub async fn create_secure_channel(
    ca_cert_pem: &[u8],
    guest_cert_pem: &[u8],
    guest_key_pem: &[u8],
    endpoint_url: String,
) -> Result<Channel, anyhow::Error> {
    let ca = Certificate::from_pem(ca_cert_pem);
    let identity = Identity::from_pem(guest_cert_pem, guest_key_pem);

    // The host cert's CN is `crossdesk-host` (see infra/certs/pki). Override
    // domain check to that name — vsock has no DNS, so SNI is artificial here.
    let tls = ClientTlsConfig::new()
        .ca_certificate(ca)
        .identity(identity)
        .domain_name("crossdesk-host");

    let channel = Channel::from_shared(endpoint_url)?
        .tls_config(tls)?
        .connect()
        .await?;

    Ok(channel)
}
