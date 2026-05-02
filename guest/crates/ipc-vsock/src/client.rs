use std::sync::{Arc, Mutex};
use tonic::transport::{Channel, ClientTlsConfig, Certificate, Identity};
use rand::RngCore;

use proto::crossdesk::v1::AuthContext;

/// Per-stream credential vault.
///
/// Auth in CrossDesk lives **inside the protobuf payload** (`AuthContext`
/// embedded in every ClientFrame / GuestFrame / ShareGuestFrame), not in gRPC
/// metadata headers. This struct hands the session/heartbeat/filesystem
/// loops a freshly-incremented `AuthContext` to stamp on every outbound frame.
///
/// The earlier `tonic::Interceptor`-based design pushed credentials into
/// `x-auth-*` headers, which the host never reads — auth always failed at
/// peer-fingerprint check. Centralising on payload-based auth keeps wire
/// format and validator in lockstep.
#[derive(Clone)]
pub struct AuthCarrier {
    peer_cert_fingerprint: String,
    stream_nonce: Vec<u8>,
    sequence: Arc<Mutex<u64>>,
}

impl AuthCarrier {
    /// `peer_cert_fingerprint` is the SHA-256 of the *host* leaf cert, lowercase
    /// hex, no separators — matches what `AuthValidator.extract_peer_fingerprint`
    /// computes server-side.
    pub fn new(peer_cert_fingerprint: String) -> Self {
        let mut nonce = vec![0u8; 16];
        rand::thread_rng().fill_bytes(&mut nonce);

        Self {
            peer_cert_fingerprint,
            stream_nonce: nonce,
            sequence: Arc::new(Mutex::new(0)),
        }
    }

    /// Mint the next AuthContext. Sequence starts at 1 and increments strictly
    /// monotonically; the host's AuthValidator enforces strict +1 deltas.
    pub fn next(&self) -> AuthContext {
        // Lock contention is impossible in single-stream usage; in the
        // worst case (lock poisoning) we surface 0 — the host will reject the
        // sequence and tear the stream, which is exactly the right outcome.
        let seq = match self.sequence.lock() {
            Ok(mut g) => {
                *g += 1;
                *g
            }
            Err(_) => 0,
        };

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
