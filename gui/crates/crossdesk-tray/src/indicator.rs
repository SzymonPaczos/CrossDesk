//! Tray indicator trait — owners of the actual platform integration.
//!
//! Real backends:
//! - **KSNI** (Linux KDE / freedesktop StatusNotifierItem) — to be wired
//!   in Phase 7 Week 29. Provides full menu support, icon swap, tooltip.
//! - **GNOME Shell extension** — Phase 7 Week 30. GNOME's shell doesn't
//!   render SNI natively; we ship an extension that adds an indicator.
//! - **NSStatusItem** (macOS) — convenience for the Mac dev environment;
//!   keeps the indicator visible in the menubar so we can verify state
//!   propagation without compiling on Linux.
//!
//! `NullIndicator` is the universal fallback: logs state changes, never
//! fails, doesn't draw anything. CI / headless smoke tests use it.

use crate::state::TrayState;
use anyhow::Result;
use tracing::info;

pub trait Indicator: Send + Sync {
    fn show(&self) -> Result<()>;
    fn hide(&self) -> Result<()>;
    fn update(&self, state: &TrayState) -> Result<()>;
}

#[derive(Default)]
pub struct NullIndicator;

impl Indicator for NullIndicator {
    fn show(&self) -> Result<()> {
        info!("[null tray] show");
        Ok(())
    }

    fn hide(&self) -> Result<()> {
        info!("[null tray] hide");
        Ok(())
    }

    fn update(&self, state: &TrayState) -> Result<()> {
        info!(
            vm_state = %state.vm_state.label(),
            fsm = %state.fsm_state,
            apps = state.running_apps.len(),
            "[null tray] update"
        );
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::VmState;

    #[test]
    fn null_indicator_show_hide_update_dont_fail() {
        let n = NullIndicator;
        n.show().unwrap();
        n.hide().unwrap();
        n.update(&TrayState {
            vm_state: VmState::Running,
            ..TrayState::default()
        })
        .unwrap();
    }
}
