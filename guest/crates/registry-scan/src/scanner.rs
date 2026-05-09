//! Scanner trait — `default_scanner()` returns the right impl for
//! the build target.

use crate::entry::DiscoveredEntry;
use std::fmt;

#[derive(Debug)]
pub enum ScannerError {
    Io(std::io::Error),
    /// Backend-specific failure with a short reason. Caller logs and
    /// returns a partial result rather than failing the whole scan.
    Backend(String),
}

impl fmt::Display for ScannerError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ScannerError::Io(e) => write!(f, "io: {e}"),
            ScannerError::Backend(s) => write!(f, "backend: {s}"),
        }
    }
}

impl std::error::Error for ScannerError {}

impl From<std::io::Error> for ScannerError {
    fn from(e: std::io::Error) -> Self {
        ScannerError::Io(e)
    }
}

pub trait Scanner: Send + Sync {
    /// Enumerate every install the backend can see.
    ///
    /// Implementations MUST gracefully degrade: a registry-key open
    /// failure for one source should not prevent other sources from
    /// being walked.
    fn scan(&self) -> Result<Vec<DiscoveredEntry>, ScannerError>;
}
