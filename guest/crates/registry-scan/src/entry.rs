//! Output type — what every scanner backend produces.

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DiscoveredEntry {
    pub source: Source,
    pub canonical_id: String,
    /// Display name as shown to the user. Already UTF-8 (registry
    /// is UTF-16 LE; the scanner converts.)
    pub display_name: String,
    /// Path to the launchable .exe. Empty when the source doesn't
    /// expose one (e.g. Uninstall keys without `DisplayIcon`).
    pub executable: String,
    /// Optional version string captured verbatim from the registry.
    pub version: Option<String>,
    /// Optional publisher / vendor.
    pub publisher: Option<String>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Source {
    AppPaths,
    UninstallHklm64,
    UninstallHklm32,
    UninstallHkcu,
    Uwp,
    Chocolatey,
    Scoop,
    StartMenu,
}

impl Source {
    pub fn label(self) -> &'static str {
        match self {
            Source::AppPaths => "App Paths",
            Source::UninstallHklm64 => "Uninstall (HKLM 64)",
            Source::UninstallHklm32 => "Uninstall (HKLM 32)",
            Source::UninstallHkcu => "Uninstall (HKCU)",
            Source::Uwp => "UWP",
            Source::Chocolatey => "Chocolatey",
            Source::Scoop => "Scoop",
            Source::StartMenu => "Start Menu",
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn source_label_round_trips() {
        for src in [
            Source::AppPaths,
            Source::UninstallHklm64,
            Source::UninstallHklm32,
            Source::UninstallHkcu,
            Source::Uwp,
            Source::Chocolatey,
            Source::Scoop,
            Source::StartMenu,
        ] {
            assert!(!src.label().is_empty());
        }
    }
}
