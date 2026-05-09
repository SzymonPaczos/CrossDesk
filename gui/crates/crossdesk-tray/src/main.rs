//! `crossdesk-tray` binary.
//!
//! Phase 6 / Week 25: tray icon stub. Boots a Null indicator on every
//! platform and logs state every 5 seconds. Real KSNI / NSStatusItem
//! lights up in Phase 7; mgmt-socket subscription lights up in Week 27.

use anyhow::Result;
use crossdesk_tray::{Indicator, NullIndicator, TrayState, VmState};
use std::time::Duration;
use tracing::info;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .json()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    info!("crossdesk-tray starting (Phase 6 stub: NullIndicator)");

    let indicator = NullIndicator;
    indicator.show()?;

    let mut state = TrayState {
        vm_state: VmState::Unknown,
        fsm_state: "UNKNOWN".to_string(),
        ..TrayState::default()
    };

    // Phase 6 Week 27 wires this loop to mgmt::Status stream. For now
    // we just demonstrate the indicator interface end-to-end with a
    // simulated state cycle.
    let mut tick = 0u32;
    loop {
        tick = tick.wrapping_add(1);
        state.vm_state = match tick % 4 {
            0 => VmState::Running,
            1 => VmState::Booting,
            2 => VmState::Running,
            _ => VmState::Suspended,
        };
        indicator.update(&state)?;
        tokio::time::sleep(Duration::from_secs(5)).await;
    }
}
