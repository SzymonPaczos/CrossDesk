//! Windows-only registry walker — real implementation.
//!
//! Walks four registry sources in priority order:
//! 1. `HKLM\...\App Paths` — launch-by-name registrations (WinApps' only source)
//! 2. `HKLM\...\Uninstall` (64-bit view) — canonical installed-apps list
//! 3. `HKLM\...\Wow6432Node\...\Uninstall` — 32-bit apps on 64-bit Windows
//! 4. `HKCU\...\Uninstall` — per-user installs (Squirrel/Electron apps)
//!
//! Any single source failing to open degrades gracefully: the other three
//! are still walked. Individual subkey failures are silently skipped.

use std::ffi::OsString;
use std::os::windows::ffi::OsStringExt;

use windows::Win32::Foundation::{ERROR_NO_MORE_ITEMS, ERROR_SUCCESS};
use windows::Win32::System::Registry::{
    RegCloseKey, RegEnumKeyExW, RegGetValueW, RegOpenKeyExW, HKEY,
    HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE, KEY_READ, KEY_WOW64_32KEY,
    KEY_WOW64_64KEY, REG_SAM_FLAGS, RRF_RT_REG_SZ,
};
use windows::core::{w, PCWSTR, PWSTR};

use crate::entry::{DiscoveredEntry, Source};
use crate::scanner::{Scanner, ScannerError};

const APP_PATHS: PCWSTR =
    w!("SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths");
const UNINSTALL: PCWSTR =
    w!("SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall");
const UNINSTALL_WOW: PCWSTR =
    w!("SOFTWARE\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall");

// Win32 docs: subkey names are at most 255 characters; +1 for the null.
const MAX_KEY_NAME: usize = 256;

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
        let mut entries: Vec<DiscoveredEntry> = Vec::new();

        // Source 1: App Paths — same source WinApps reads; we complement it.
        if let Some(hkey) = open_key(HKEY_LOCAL_MACHINE, APP_PATHS, KEY_READ | KEY_WOW64_64KEY) {
            entries.extend(scan_app_paths(hkey));
            // Safety: hkey is a valid open handle returned by RegOpenKeyExW.
            unsafe { let _ = RegCloseKey(hkey); }
        }

        // Source 2: HKLM Uninstall — 64-bit installed apps.
        if let Some(hkey) = open_key(HKEY_LOCAL_MACHINE, UNINSTALL, KEY_READ | KEY_WOW64_64KEY) {
            entries.extend(scan_uninstall(hkey, Source::UninstallHklm64));
            // Safety: valid open handle.
            unsafe { let _ = RegCloseKey(hkey); }
        }

        // Source 3: HKLM Uninstall — 32-bit apps via WoW registry redirection.
        if let Some(hkey) = open_key(HKEY_LOCAL_MACHINE, UNINSTALL_WOW, KEY_READ | KEY_WOW64_32KEY) {
            entries.extend(scan_uninstall(hkey, Source::UninstallHklm32));
            // Safety: valid open handle.
            unsafe { let _ = RegCloseKey(hkey); }
        }

        // Source 4: HKCU Uninstall — per-user installs (Squirrel, Electron).
        if let Some(hkey) = open_key(HKEY_CURRENT_USER, UNINSTALL, KEY_READ) {
            entries.extend(scan_uninstall(hkey, Source::UninstallHkcu));
            // Safety: valid open handle.
            unsafe { let _ = RegCloseKey(hkey); }
        }

        Ok(entries)
    }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/// Opens a registry key. Returns None on any error so callers degrade gracefully.
fn open_key(root: HKEY, subkey: PCWSTR, access: REG_SAM_FLAGS) -> Option<HKEY> {
    let mut hkey = HKEY::default();
    // Safety: root is a valid predefined HKEY constant; subkey is a null-
    // terminated wide string produced by the w!() macro.
    let err = unsafe { RegOpenKeyExW(root, subkey, 0, access, &mut hkey) };
    (err == ERROR_SUCCESS).then_some(hkey)
}

/// Iterates every direct subkey of `parent`, calling `visit(name)` for each.
/// Individual enumeration errors (except ERROR_NO_MORE_ITEMS) are skipped.
fn enum_subkeys(parent: HKEY, mut visit: impl FnMut(String)) {
    let mut index: u32 = 0;
    loop {
        let mut buf: Vec<u16> = vec![0u16; MAX_KEY_NAME];
        let mut len: u32 = MAX_KEY_NAME as u32;
        // Safety: parent is open, buf is MAX_KEY_NAME chars, len matches.
        let err = unsafe {
            RegEnumKeyExW(
                parent,
                index,
                PWSTR(buf.as_mut_ptr()),
                &mut len,
                None,
                PWSTR::null(),
                None,
                None,
            )
        };
        if err == ERROR_NO_MORE_ITEMS {
            break;
        }
        if err == ERROR_SUCCESS {
            let name = OsString::from_wide(&buf[..len as usize])
                .to_string_lossy()
                .into_owned();
            if !name.is_empty() {
                visit(name);
            }
        }
        index += 1;
    }
}

/// Reads a REG_SZ value from `hkey`. Returns None if absent, empty, or on error.
fn read_sz(hkey: HKEY, name: PCWSTR) -> Option<String> {
    // First call: get the required buffer size in bytes.
    let mut size: u32 = 0;
    // Safety: hkey is open; name is a static null-terminated wide string.
    unsafe {
        RegGetValueW(hkey, PCWSTR::null(), name, RRF_RT_REG_SZ, None, None, Some(&mut size));
    }
    if size < 2 {
        return None; // value absent or zero-length (2 bytes = just null terminator)
    }

    let cap = (size / 2) as usize; // bytes → UTF-16 code units
    let mut buf: Vec<u16> = vec![0u16; cap];
    // Safety: hkey is open; buf has the capacity the first call reported.
    let err = unsafe {
        RegGetValueW(
            hkey,
            PCWSTR::null(),
            name,
            RRF_RT_REG_SZ,
            None,
            Some(buf.as_mut_ptr() as *mut _),
            Some(&mut size),
        )
    };
    if err != ERROR_SUCCESS {
        return None;
    }

    // Strip null terminator(s) written by the API.
    let end = buf.iter().position(|&c| c == 0).unwrap_or(buf.len());
    let s = OsString::from_wide(&buf[..end])
        .to_string_lossy()
        .into_owned();
    if s.is_empty() { None } else { Some(s) }
}

/// Converts a Rust String to a null-terminated UTF-16 Vec for PCWSTR.
fn to_wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

// ---------------------------------------------------------------------------
// App Paths source
// ---------------------------------------------------------------------------

fn scan_app_paths(parent: HKEY) -> Vec<DiscoveredEntry> {
    let mut out = Vec::new();

    enum_subkeys(parent, |subkey_name| {
        let wide = to_wide(&subkey_name);
        let subkey_pcwstr = PCWSTR(wide.as_ptr());
        let mut hkey = HKEY::default();
        // Safety: parent is open; subkey_pcwstr is a null-terminated wide string.
        let err = unsafe {
            RegOpenKeyExW(parent, subkey_pcwstr, 0, KEY_READ | KEY_WOW64_64KEY, &mut hkey)
        };
        if err != ERROR_SUCCESS {
            return;
        }

        // The default value (empty name) holds the full path to the executable.
        let executable = read_sz(hkey, w!(""));
        // Safety: hkey was successfully opened above.
        unsafe { let _ = RegCloseKey(hkey); }

        // Strip .exe suffix to get a human-readable display name.
        let display_name = subkey_name
            .strip_suffix(".exe")
            .or_else(|| subkey_name.strip_suffix(".EXE"))
            .unwrap_or(&subkey_name)
            .to_owned();

        out.push(DiscoveredEntry {
            source: Source::AppPaths,
            canonical_id: subkey_name,
            display_name,
            executable: executable.unwrap_or_default(),
            version: None,
            publisher: None,
        });
    });

    out
}

// ---------------------------------------------------------------------------
// Uninstall sources (HKLM 64, HKLM 32, HKCU)
// ---------------------------------------------------------------------------

fn scan_uninstall(parent: HKEY, source: Source) -> Vec<DiscoveredEntry> {
    let mut out = Vec::new();

    enum_subkeys(parent, |subkey_name| {
        let wide = to_wide(&subkey_name);
        let subkey_pcwstr = PCWSTR(wide.as_ptr());
        let access = if source == Source::UninstallHklm32 {
            KEY_READ | KEY_WOW64_32KEY
        } else {
            KEY_READ | KEY_WOW64_64KEY
        };
        let mut hkey = HKEY::default();
        // Safety: parent is open; subkey_pcwstr is a null-terminated wide string.
        let err = unsafe { RegOpenKeyExW(parent, subkey_pcwstr, 0, access, &mut hkey) };
        if err != ERROR_SUCCESS {
            return;
        }

        // DisplayName is mandatory — skip entries without it (system noise / orphaned keys).
        let display_name = read_sz(hkey, w!("DisplayName"));
        if display_name.is_none() {
            // Safety: hkey was successfully opened.
            unsafe { let _ = RegCloseKey(hkey); }
            return;
        }

        // DisplayIcon is often "path\to\app.exe,0" — extract just the path.
        let executable = read_sz(hkey, w!("DisplayIcon"))
            .map(|s| s.split(',').next().unwrap_or("").trim().to_owned())
            .filter(|s| !s.is_empty())
            .unwrap_or_default();

        let version = read_sz(hkey, w!("DisplayVersion"));
        let publisher = read_sz(hkey, w!("Publisher"));

        // Safety: hkey was successfully opened.
        unsafe { let _ = RegCloseKey(hkey); }

        out.push(DiscoveredEntry {
            source,
            canonical_id: subkey_name,
            // Infallible because: the is_none() guard above returned early
            // when display_name was None, so it is Some here.
            display_name: display_name.unwrap(),
            executable,
            version,
            publisher,
        });
    });

    out
}
