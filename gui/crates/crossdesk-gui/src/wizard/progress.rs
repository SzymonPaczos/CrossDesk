/// Hardcoded fake-installer script.
///
/// Each entry is `(duration_ms, label_key)`. Labels go through `qsTr` on the
/// QML side, so `label_key` is the source string in en.ts. Tweak durations to
/// shorten demos (e.g. drop everything to 1500 ms while iterating UX).
pub const INSTALL_STEPS: &[(u32, &str)] = &[
    (5_000, "Booting Windows installer…"),
    (5_000, "Partitioning virtual disk…"),
    (10_000, "Installing Windows…"),
    (5_000, "Applying autounattend.xml…"),
    (5_000, "Registering CrossDesk agent NT service…"),
];

pub fn total_steps() -> usize {
    INSTALL_STEPS.len()
}

pub fn step_duration_ms(index: usize) -> u32 {
    INSTALL_STEPS
        .get(index)
        .map(|(ms, _)| *ms)
        .unwrap_or(0)
}

pub fn step_label(index: usize) -> &'static str {
    INSTALL_STEPS
        .get(index)
        .map(|(_, label)| *label)
        .unwrap_or("Installation complete")
}
