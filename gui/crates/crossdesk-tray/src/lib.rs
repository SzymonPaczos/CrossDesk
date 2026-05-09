//! CrossDesk system tray icon (KSNI on Linux, NSStatusItem on macOS,
//! a Null fallback elsewhere).
//!
//! Phase 6 / Week 25 — pure trait surface + a Null mock that compiles
//! and runs everywhere. The real KSNI / NSStatusItem implementations
//! live behind `#[cfg(target_os = ...)]` and light up at compile time
//! on the matching platform without changing the call sites.
//!
//! The tray binary (`crossdesk-tray`) talks to the daemon over the
//! mgmt.proto Unix socket; this crate just owns the icon, the menu,
//! and the indicator state. Streaming wiring lives in `mgmt_client.rs`
//! and isn't exercised in v0.1.x — Phase 6 Week 28 / Phase 7 land
//! the live integration.

pub mod indicator;
pub mod state;

pub use indicator::{Indicator, NullIndicator};
pub use state::{TrayState, VmState};
