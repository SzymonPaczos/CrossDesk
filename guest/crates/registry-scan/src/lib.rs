//! Windows registry scanner — enumerates installed apps from every
//! source the host's app catalog can reasonably consume.
//!
//! Sources (in order of completeness, beating WinApps' single source):
//!
//! 1. ``HKLM\Software\Microsoft\Windows\CurrentVersion\App Paths``
//!    — apps registered for `start` lookup ("winword", "excel").
//!    This is what WinApps uses.
//! 2. ``HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall``
//!    — every installer entry (the canonical "installed apps" list).
//! 3. ``HKLM\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall``
//!    — 32-bit apps installed on 64-bit Windows.
//! 4. ``HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall``
//!    — per-user installs (often Squirrel-style apps like Slack).
//!
//! UWP / Chocolatey / Scoop discovery shells out to PowerShell because
//! their state lives outside the registry; that path is gated behind
//! a feature flag (`uwp` / `pkgmgr`) to keep the cross-compile surface
//! small.
//!
//! The crate ships a real backend (`#[cfg(target_os = "windows")]`)
//! and a mock backend (`#[cfg(not(target_os = "windows"))]` plus a
//! `mock` feature for selective override on Windows hosts during
//! tests). The Mac dev environment always lands on the mock and gets
//! a deterministic canned list, so the daemon's `ListDiscoveredApps`
//! pipeline can be exercised end-to-end without a Windows guest.

pub mod entry;
pub mod scanner;

#[cfg(target_os = "windows")]
mod windows_impl;

#[cfg(not(target_os = "windows"))]
mod mock_impl;

pub use entry::DiscoveredEntry;
pub use scanner::{Scanner, ScannerError};

/// Build the platform-appropriate scanner.
///
/// On Windows: real registry walker.
/// On other targets: deterministic mock returning canned entries so
/// the host catalog code is testable without a Windows guest.
pub fn default_scanner() -> Box<dyn Scanner> {
    #[cfg(target_os = "windows")]
    {
        Box::new(windows_impl::WindowsScanner::new())
    }
    #[cfg(not(target_os = "windows"))]
    {
        Box::new(mock_impl::MockScanner::default())
    }
}
