//! Mock scanner — Mac dev, CI without a Windows guest. Returns a
//! deterministic canned list so the host's catalog code is testable.

use crate::entry::{DiscoveredEntry, Source};
use crate::scanner::{Scanner, ScannerError};

#[derive(Default)]
pub struct MockScanner {
    pub entries: Vec<DiscoveredEntry>,
}

impl MockScanner {
    #[allow(dead_code)] // Used by tests; production daemon calls default()
                        // and seeds entries through the host's mgmt RPC.
    pub fn with_canned() -> Self {
        Self {
            entries: vec![
                DiscoveredEntry {
                    source: Source::AppPaths,
                    canonical_id: "winword".into(),
                    display_name: "Microsoft Word".into(),
                    executable: r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"
                        .into(),
                    version: Some("16.0.18025.20104".into()),
                    publisher: Some("Microsoft Corporation".into()),
                },
                DiscoveredEntry {
                    source: Source::UninstallHklm64,
                    canonical_id: "vs-code".into(),
                    display_name: "Visual Studio Code".into(),
                    executable: r"C:\Program Files\Microsoft VS Code\Code.exe".into(),
                    version: Some("1.91.0".into()),
                    publisher: Some("Microsoft Corporation".into()),
                },
                DiscoveredEntry {
                    source: Source::UninstallHkcu,
                    canonical_id: "spotify".into(),
                    display_name: "Spotify".into(),
                    executable: r"C:\Users\Public\AppData\Roaming\Spotify\Spotify.exe".into(),
                    version: None,
                    publisher: Some("Spotify AB".into()),
                },
                DiscoveredEntry {
                    source: Source::Uwp,
                    canonical_id: "Microsoft.WindowsCalculator".into(),
                    display_name: "Windows Calculator".into(),
                    executable: String::new(),
                    version: Some("11.2401.0.0".into()),
                    publisher: Some("Microsoft".into()),
                },
            ],
        }
    }
}

impl Scanner for MockScanner {
    fn scan(&self) -> Result<Vec<DiscoveredEntry>, ScannerError> {
        Ok(self.entries.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_mock_returns_empty() {
        let scanner = MockScanner::default();
        assert!(scanner.scan().unwrap().is_empty());
    }

    #[test]
    fn canned_list_covers_each_source_type() {
        let scanner = MockScanner::with_canned();
        let results = scanner.scan().unwrap();
        let sources: std::collections::HashSet<_> = results.iter().map(|e| e.source).collect();
        assert!(sources.contains(&Source::AppPaths));
        assert!(sources.contains(&Source::UninstallHklm64));
        assert!(sources.contains(&Source::UninstallHkcu));
        assert!(sources.contains(&Source::Uwp));
    }

    #[test]
    fn canned_word_executable_is_office_path() {
        let scanner = MockScanner::with_canned();
        let results = scanner.scan().unwrap();
        let word = results
            .iter()
            .find(|e| e.canonical_id == "winword")
            .unwrap();
        assert!(word.executable.contains("WINWORD.EXE"));
    }

    #[test]
    fn entries_are_clonable() {
        let scanner = MockScanner::with_canned();
        let a = scanner.scan().unwrap();
        let b = scanner.scan().unwrap();
        assert_eq!(a, b);
    }
}
