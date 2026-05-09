//! Windows-only registry walker. Compiled in only when the host
//! target is Windows.
//!
//! Phase 8 stub: structure is in place, registry key paths are
//! enumerated, but the actual `RegOpenKeyExW` / `RegEnumValueW`
//! calls remain to be wired. End-to-end verification happens on the
//! Windows guest once it's running. Until then `WindowsScanner.scan`
//! returns an empty Vec; callers transparently see "no discovered
//! apps" which is correct for an empty / freshly-booted guest.

use crate::entry::DiscoveredEntry;
use crate::scanner::{Scanner, ScannerError};

pub struct WindowsScanner;

impl WindowsScanner {
    pub fn new() -> Self {
        WindowsScanner
    }
}

impl Default for WindowsScanner {
    fn default() -> Self {
        Self::new()
    }
}

impl Scanner for WindowsScanner {
    fn scan(&self) -> Result<Vec<DiscoveredEntry>, ScannerError> {
        // TODO(phase-8-week-34): walk
        //   HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths
        //   HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall
        //   HKLM\SOFTWARE\Wow6432Node\...\Uninstall
        //   HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall
        // For Phase 8 we ship the enum + trait + mock; the windows
        // walker lights up on the running guest in a follow-up
        // commit once we have a real installed-app fixture to test
        // against.
        Ok(Vec::new())
    }
}
