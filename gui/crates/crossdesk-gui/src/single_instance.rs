//! Per-user single-instance guard backed by a PID file under
//! `$XDG_RUNTIME_DIR` (or `/tmp` fallback).
//!
//! Why not Qt's `QLockFile`: cxx-qt-lib 0.7 doesn't expose it. Rolling
//! our own keeps the dependency surface minimal — no new crates needed.
//!
//! Behavior:
//!
//! 1. [`acquire`] tries to create `<runtime_dir>/crossdesk-gui.lock`
//!    with `O_EXCL` semantics + writes the current PID.
//! 2. If creation fails because the file exists, we read the PID and
//!    check whether that process is still alive (sending signal 0 via
//!    `kill(2)` is the standard POSIX way to ask).
//! 3. Stale (PID dead) → unlink + retry once. Live → return
//!    [`AcquireError::AlreadyRunning`].
//! 4. Successful acquisition returns a [`LockGuard`] whose `Drop`
//!    removes the file. The guard is held by `main()` for the entire
//!    QGuiApplication lifetime.
//!
//! Limitations: a TOCTOU race exists between "is PID alive" and
//! "remove file + create our own". Two simultaneous launches on a cold
//! cache could both pass the alive-check, both create the file, both
//! claim ownership. This is acceptable because:
//!   - Desktop launchers don't fire that fast in practice.
//!   - The worst case (two windows) is exactly what the absence of
//!     this guard produces today, so it's not a regression.
//!
//! Tests live in this module under `#[cfg(test)]`.
//!
//! Cross-platform note: PID-based liveness check uses `libc::kill`
//! which is Unix-only. crossdesk-gui ships on Linux; the macOS dev
//! target also has libc. Windows is not a supported build target for
//! the GUI.

use std::fs::{File, OpenOptions};
use std::io::{self, Read, Write};
use std::path::PathBuf;
use std::process;

/// File name used under the runtime directory. Per-user (the runtime
/// directory itself is user-scoped under XDG), so a second user logged
/// in at the same time gets their own lock.
const LOCK_NAME: &str = "crossdesk-gui.lock";

/// RAII guard removing the lock file on drop.
#[derive(Debug)]
pub struct LockGuard {
    path: PathBuf,
}

impl Drop for LockGuard {
    fn drop(&mut self) {
        // Best-effort: if the file was already removed (e.g. tmpfs
        // cleared) we don't need to surface the error — process exit
        // is imminent anyway.
        let _ = std::fs::remove_file(&self.path);
    }
}

#[derive(Debug)]
pub enum AcquireError {
    /// Another live process holds the lock.
    AlreadyRunning { pid: i32 },
    /// Underlying IO failure (permissions, missing runtime dir, etc.).
    Io(io::Error),
}

impl std::fmt::Display for AcquireError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::AlreadyRunning { pid } => write!(f, "another instance running (pid={pid})"),
            Self::Io(err) => write!(f, "io error: {err}"),
        }
    }
}

impl From<io::Error> for AcquireError {
    fn from(err: io::Error) -> Self {
        Self::Io(err)
    }
}

/// Try to claim the per-user GUI lock. Returns a guard whose drop
/// removes the file, or an error describing why it couldn't be taken.
pub fn acquire() -> Result<LockGuard, AcquireError> {
    let path = lock_path();
    acquire_at(&path)
}

fn lock_path() -> PathBuf {
    if let Ok(runtime_dir) = std::env::var("XDG_RUNTIME_DIR") {
        let mut p = PathBuf::from(runtime_dir);
        p.push(LOCK_NAME);
        return p;
    }
    // /tmp is the lowest-common-denominator fallback. It's world-writable
    // but the lock file's content (a PID) isn't sensitive.
    let mut p = std::env::temp_dir();
    p.push(LOCK_NAME);
    p
}

fn acquire_at(path: &PathBuf) -> Result<LockGuard, AcquireError> {
    match create_exclusive(path) {
        Ok(mut f) => {
            write_pid(&mut f)?;
            Ok(LockGuard { path: path.clone() })
        }
        Err(e) if e.kind() == io::ErrorKind::AlreadyExists => handle_existing_lock(path),
        Err(e) => Err(e.into()),
    }
}

fn create_exclusive(path: &PathBuf) -> io::Result<File> {
    if let Some(parent) = path.parent() {
        // Best-effort mkdir -p; ignore "already exists".
        let _ = std::fs::create_dir_all(parent);
    }
    OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(path)
}

fn write_pid(f: &mut File) -> io::Result<()> {
    writeln!(f, "{}", process::id())
}

fn handle_existing_lock(path: &PathBuf) -> Result<LockGuard, AcquireError> {
    let pid = read_pid(path)?;
    if pid_is_alive(pid) {
        return Err(AcquireError::AlreadyRunning { pid });
    }
    // Stale lock — remove and retry once. If the retry hits an
    // AlreadyExists race, we surrender to the winner.
    std::fs::remove_file(path)?;
    let mut f = create_exclusive(path)?;
    write_pid(&mut f)?;
    Ok(LockGuard { path: path.clone() })
}

fn read_pid(path: &PathBuf) -> io::Result<i32> {
    let mut contents = String::new();
    File::open(path)?.read_to_string(&mut contents)?;
    contents
        .trim()
        .parse::<i32>()
        .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, format!("bad PID file: {e}")))
}

/// `kill(pid, 0)` is the POSIX way to ask "does this process exist
/// and can I signal it". 0 → exists. ESRCH → dead. EPERM → exists
/// but not ours (treat as alive — wouldn't want to steal another
/// user's lock).
fn pid_is_alive(pid: i32) -> bool {
    if pid <= 0 {
        return false;
    }
    // Safety: `kill` with signal 0 is documented as side-effect-free.
    // POSIX guarantees errno is set on -1 return; we read it via
    // `io::Error::last_os_error`.
    let res = unsafe { libc_kill(pid, 0) };
    if res == 0 {
        return true;
    }
    let errno = io::Error::last_os_error().raw_os_error().unwrap_or(0);
    // EPERM (1) = exists, not ours. ESRCH (3) = no such process.
    errno == 1
}

// Avoid pulling the `libc` crate just for one syscall. CXX-Qt builds
// link libc anyway via the C++ side.
extern "C" {
    #[link_name = "kill"]
    fn libc_kill(pid: i32, sig: i32) -> i32;
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn first_acquire_succeeds() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.lock");
        let guard = acquire_at(&path).expect("first acquire");
        assert!(path.exists(), "lock file should exist while guard alive");
        drop(guard);
        assert!(!path.exists(), "lock file removed on drop");
    }

    #[test]
    fn second_acquire_with_live_pid_returns_already_running() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.lock");
        let _first = acquire_at(&path).expect("first acquire");
        let result = acquire_at(&path);
        match result {
            Err(AcquireError::AlreadyRunning { pid }) => {
                assert_eq!(pid as u32, process::id());
            }
            other => panic!("expected AlreadyRunning, got {other:?}"),
        }
    }

    #[test]
    fn stale_lock_is_replaced() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.lock");
        // Hand-write a PID that's almost certainly dead. 2^30 is well
        // above any reasonable pid_max but still positive.
        std::fs::write(&path, format!("{}\n", 1_073_741_823_i32)).unwrap();
        let guard = acquire_at(&path).expect("stale lock should be reclaimed");
        // After acquire, the file contains *our* PID.
        let contents = std::fs::read_to_string(&path).unwrap();
        assert_eq!(contents.trim(), process::id().to_string());
        drop(guard);
    }

    #[test]
    fn malformed_lock_surfaces_io_error() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.lock");
        std::fs::write(&path, "not a number\n").unwrap();
        match acquire_at(&path) {
            Err(AcquireError::Io(_)) => {}
            other => panic!("expected Io error on malformed lock, got {other:?}"),
        }
    }

    #[test]
    fn pid_zero_treated_as_dead() {
        assert!(!pid_is_alive(0));
        assert!(!pid_is_alive(-1));
    }

    #[test]
    fn current_pid_is_alive() {
        let me: i32 = process::id().try_into().unwrap();
        assert!(pid_is_alive(me));
    }
}
