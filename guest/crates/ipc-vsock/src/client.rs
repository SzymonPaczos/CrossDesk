use rand::RngCore;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use tonic::transport::{Certificate, ClientTlsConfig, Endpoint, Identity};

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
    /// `peer_cert_fingerprint` is the SHA-256 of *our own* mTLS leaf
    /// cert — the field in proto/AuthContext is the sender's cert
    /// (the server compares it to its TLS-layer view of our peer).
    /// Lowercase hex, no separators.
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
            // Guest-originated frames leave traceparent empty; the host
            // stamps it on ServerFrame when it initiates a request.
            traceparent: String::new(),
        }
    }
}

/// Build a tonic `Endpoint` with the mTLS config used by the guest. Returned
/// by itself so callers can choose between `.connect()` (default connector)
/// and `.connect_with_connector(transport)` (explicit Transport impl).
pub fn build_endpoint(
    ca_cert_pem: &[u8],
    guest_cert_pem: &[u8],
    guest_key_pem: &[u8],
    endpoint_url: String,
) -> anyhow::Result<Endpoint> {
    let ca = Certificate::from_pem(ca_cert_pem);
    let identity = Identity::from_pem(guest_cert_pem, guest_key_pem);

    // The host cert's CN is `crossdesk-host` (see infra/certs/pki). Override
    // domain check to that name — vsock has no DNS, so SNI is artificial here.
    let tls = ClientTlsConfig::new()
        .ca_certificate(ca)
        .identity(identity)
        .domain_name("crossdesk-host");

    Ok(Endpoint::from_shared(endpoint_url)?.tls_config(tls)?)
}
