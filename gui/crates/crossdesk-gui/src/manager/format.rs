//! Pure-Rust formatters used by Manager panes.
//!
//! Kept separate from `manager::state` because cxx-qt's bridge module
//! is awkward to unit-test directly; routing the formatting through a
//! plain Rust module gives us full coverage on the i18n + display
//! logic without spinning up a Qt event loop.

use std::time::Duration;

/// Format a `Duration` as a human-readable uptime label.
///
/// Examples:
///
/// - `Duration::from_secs(0)` → `"0s"`
/// - `Duration::from_secs(45)` → `"45s"`
/// - `Duration::from_secs(120)` → `"2m"`
/// - `Duration::from_secs(3661)` → `"1h 1m"`
/// - `Duration::from_secs(90061)` → `"1d 1h"`
pub fn format_uptime(d: Duration) -> String {
    let total = d.as_secs();
    if total < 60 {
        return format!("{total}s");
    }
    let mins = total / 60;
    if mins < 60 {
        return format!("{mins}m");
    }
    let hours = mins / 60;
    let rem_mins = mins % 60;
    if hours < 24 {
        return format!("{hours}h {rem_mins}m");
    }
    let days = hours / 24;
    let rem_hours = hours % 24;
    format!("{days}d {rem_hours}h")
}

/// Format byte count with binary units (Mi/Gi). Defensive against
/// silly inputs — anything ≥ 1 EB just shows the EB number.
pub fn format_bytes(bytes: u64) -> String {
    const KI: u64 = 1024;
    const MI: u64 = KI * 1024;
    const GI: u64 = MI * 1024;
    const TI: u64 = GI * 1024;
    if bytes < KI {
        return format!("{bytes} B");
    }
    if bytes < MI {
        return format!("{:.1} KiB", bytes as f64 / KI as f64);
    }
    if bytes < GI {
        return format!("{:.1} MiB", bytes as f64 / MI as f64);
    }
    if bytes < TI {
        return format!("{:.2} GiB", bytes as f64 / GI as f64);
    }
    format!("{:.2} TiB", bytes as f64 / TI as f64)
}

/// Map an FSM state label to a translated display string, with the
/// translation deferred to the QML layer (which holds the QTranslator).
/// Here we just normalise the label so unknown values don't leak raw.
pub fn normalise_fsm_state(raw: &str) -> &'static str {
    match raw {
        "HEALTHY" => "HEALTHY",
        "DEGRADED" => "DEGRADED",
        "PROBING" => "PROBING",
        "SOFT_RECOVERY" => "SOFT_RECOVERY",
        "HARD_DESTROY" => "HARD_DESTROY",
        "SUSPENDED" => "SUSPENDED",
        _ => "UNKNOWN",
    }
}

/// Map an FSM state to a 3-tier severity bucket the QML side uses to
/// pick colours/icons without needing a switch on every state.
pub fn fsm_severity(raw: &str) -> &'static str {
    match normalise_fsm_state(raw) {
        "HEALTHY" => "ok",
        "DEGRADED" | "SUSPENDED" => "warn",
        "PROBING" | "SOFT_RECOVERY" | "HARD_DESTROY" => "critical",
        _ => "unknown",
    }
}

/// Compatibility-rating star formatter. 0 stars → "unrated".
pub fn format_stars(n: u32) -> String {
    if n == 0 {
        return "unrated".to_string();
    }
    let n = n.min(5) as usize;
    let filled = "★".repeat(n);
    let empty = "☆".repeat(5 - n);
    format!("{filled}{empty}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn uptime_zero_seconds() {
        assert_eq!(format_uptime(Duration::ZERO), "0s");
    }

    #[test]
    fn uptime_seconds_under_minute() {
        assert_eq!(format_uptime(Duration::from_secs(45)), "45s");
    }

    #[test]
    fn uptime_full_minute() {
        assert_eq!(format_uptime(Duration::from_secs(60)), "1m");
        assert_eq!(format_uptime(Duration::from_secs(120)), "2m");
    }

    #[test]
    fn uptime_hours_minutes() {
        assert_eq!(format_uptime(Duration::from_secs(3661)), "1h 1m");
        assert_eq!(format_uptime(Duration::from_secs(7200)), "2h 0m");
    }

    #[test]
    fn uptime_days_hours() {
        assert_eq!(format_uptime(Duration::from_secs(86400)), "1d 0h");
        assert_eq!(format_uptime(Duration::from_secs(86400 + 3600)), "1d 1h");
    }

    #[test]
    fn bytes_zero() {
        assert_eq!(format_bytes(0), "0 B");
    }

    #[test]
    fn bytes_under_kib() {
        assert_eq!(format_bytes(512), "512 B");
    }

    #[test]
    fn bytes_kib() {
        assert_eq!(format_bytes(2048), "2.0 KiB");
    }

    #[test]
    fn bytes_mib() {
        assert_eq!(format_bytes(2 * 1024 * 1024), "2.0 MiB");
    }

    #[test]
    fn bytes_gib() {
        assert_eq!(
            format_bytes(3 * 1024 * 1024 * 1024 + 512 * 1024 * 1024),
            "3.50 GiB"
        );
    }

    #[test]
    fn bytes_tib() {
        assert_eq!(format_bytes(2_u64 * 1024 * 1024 * 1024 * 1024), "2.00 TiB");
    }

    #[test]
    fn fsm_normalise_known() {
        assert_eq!(normalise_fsm_state("HEALTHY"), "HEALTHY");
        assert_eq!(normalise_fsm_state("SOFT_RECOVERY"), "SOFT_RECOVERY");
    }

    #[test]
    fn fsm_normalise_unknown_collapses() {
        assert_eq!(normalise_fsm_state("garbage"), "UNKNOWN");
    }

    #[test]
    fn fsm_severity_ok_warn_critical() {
        assert_eq!(fsm_severity("HEALTHY"), "ok");
        assert_eq!(fsm_severity("DEGRADED"), "warn");
        assert_eq!(fsm_severity("HARD_DESTROY"), "critical");
        assert_eq!(fsm_severity("garbage"), "unknown");
    }

    #[test]
    fn stars_zero_is_unrated() {
        assert_eq!(format_stars(0), "unrated");
    }

    #[test]
    fn stars_three_of_five() {
        assert_eq!(format_stars(3), "★★★☆☆");
    }

    #[test]
    fn stars_clamped_at_five() {
        assert_eq!(format_stars(99), "★★★★★");
    }
}
