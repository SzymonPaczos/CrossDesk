//! mTLS material loaders for the guest side.
//!
//! Certificates ship inside the tools ISO at install time (see
//! `infra/autounattend.xml` FirstLogonCommands) and end up at:
//!     C:\CrossDesk\pki\ca.crt
//!     C:\CrossDesk\pki\guest.crt
//!     C:\CrossDesk\pki\guest.key
//!
//! Helpers below are deliberately filesystem-agnostic so unit tests can feed
//! in-memory PEM bytes.

use std::path::Path;

#[derive(Debug, Clone)]
pub struct TlsMaterial {
    pub ca_pem: Vec<u8>,
    pub cert_pem: Vec<u8>,
    pub key_pem: Vec<u8>,
}

impl TlsMaterial {
    pub fn from_dir(dir: &Path) -> anyhow::Result<Self> {
        Ok(Self {
            ca_pem: std::fs::read(dir.join("ca.crt"))?,
            cert_pem: std::fs::read(dir.join("guest.crt"))?,
            key_pem: std::fs::read(dir.join("guest.key"))?,
        })
    }
}

/// SHA-256 fingerprint of a PEM-encoded leaf certificate, lowercase hex,
/// no separators — matches what AuthValidator computes server-side.
pub fn fingerprint_sha256(cert_pem: &[u8]) -> anyhow::Result<String> {
    use sha2::{Digest, Sha256};

    let pem = pem::parse(cert_pem)?;
    let mut hasher = Sha256::new();
    hasher.update(pem.contents());
    Ok(hex::encode(hasher.finalize()))
}
