use cxx_qt_lib::QString;

use crate::wizard::progress;

/// Fixed disk size: qcow2 is thin-provisioned so the cap rarely matters in practice.
const DISK_GB: i32 = 64;

#[cxx_qt::bridge]
pub mod qobject {
    unsafe extern "C++" {
        include!("cxx-qt-lib/qstring.h");
        type QString = cxx_qt_lib::QString;
    }

    extern "RustQt" {
        #[qobject]
        #[qml_element]
        // ISO source: "download" (fetch from Microsoft) or "browse" (local file)
        #[qproperty(QString, iso_source)]
        // download_language is auto-detected from host locale; shown read-only in QML
        #[qproperty(QString, download_language)]
        // --- browse mode ---
        #[qproperty(QString, iso_path)]
        // Auto-detected from host — shown read-only on the review step
        #[qproperty(QString, host_timezone)]
        #[qproperty(QString, host_locale)]
        #[qproperty(i32, host_ram_gb)]
        #[qproperty(i32, host_vcpu)]
        #[qproperty(i32, disk_gb)]
        // Progress tracking
        #[qproperty(i32, current_step)]
        #[qproperty(i32, total_steps)]
        #[qproperty(i32, progress_pct)]
        #[qproperty(QString, progress_label)]
        #[qproperty(bool, installing)]
        #[qproperty(bool, finished)]
        type WizardState = super::WizardStateRust;

        #[qinvokable]
        fn start_install(self: Pin<&mut WizardState>);

        #[qinvokable]
        fn advance(self: Pin<&mut WizardState>);

        #[qinvokable]
        fn reset(self: Pin<&mut WizardState>);

        #[qinvokable]
        fn current_step_duration_ms(self: &WizardState) -> i32;
    }

    impl cxx_qt::Constructor<()> for WizardState {}
}

pub struct WizardStateRust {
    iso_source: QString,
    download_language: QString,
    iso_path: QString,
    host_timezone: QString,
    host_locale: QString,
    host_ram_gb: i32,
    host_vcpu: i32,
    disk_gb: i32,
    current_step: i32,
    total_steps: i32,
    progress_pct: i32,
    progress_label: QString,
    installing: bool,
    finished: bool,
}

impl Default for WizardStateRust {
    fn default() -> Self {
        Self {
            iso_source: QString::from("download"),
            download_language: QString::default(), // filled from host_locale in initialize()
            iso_path: QString::default(),
            host_timezone: QString::default(),
            host_locale: QString::default(),
            host_ram_gb: 0,
            host_vcpu: 0,
            disk_gb: DISK_GB,
            current_step: 0,
            total_steps: progress::total_steps() as i32,
            progress_pct: 0,
            progress_label: QString::from(""),
            installing: false,
            finished: false,
        }
    }
}

impl cxx_qt::Initialize for qobject::WizardState {
    fn initialize(self: std::pin::Pin<&mut Self>) {
        let mut this = self;
        let locale = detect_locale();
        this.as_mut().set_host_timezone(QString::from(&detect_timezone()));
        this.as_mut().set_host_locale(QString::from(&locale));
        this.as_mut().set_host_ram_gb(detect_ram_gb());
        this.as_mut().set_host_vcpu(detect_vcpu());
        // Pre-select the download language that matches the host locale.
        this.as_mut().set_download_language(QString::from(&locale_to_download_language(&locale)));
    }
}

/// Map a BCP-47 locale code to the Windows ISO language label used by Microsoft's API.
fn locale_to_download_language(locale: &str) -> String {
    match locale.split('-').next().unwrap_or("en") {
        "pl" => "Polish",
        "de" => "German",
        "fr" => "French",
        "es" => "Spanish",
        "it" => "Italian",
        "pt" => "Portuguese (Brazil)",
        "ja" => "Japanese",
        "ko" => "Korean",
        "zh" => "Chinese (Simplified)",
        _    => "English (International)",
    }
    .to_owned()
}

/// Read /etc/localtime symlink to get the IANA timezone name.
/// Falls back to TZ env var, then "UTC".
fn detect_timezone() -> String {
    // Linux/macOS: /etc/localtime → .../zoneinfo/Region/City
    if let Ok(target) = std::fs::read_link("/etc/localtime") {
        let s = target.to_string_lossy();
        if let Some(idx) = s.find("zoneinfo/") {
            return s[idx + "zoneinfo/".len()..].to_owned();
        }
    }
    std::env::var("TZ").unwrap_or_else(|_| "UTC".to_owned())
}

/// Return the BCP-47 language tag from LANG env or system locale fallback.
fn detect_locale() -> String {
    // LANG=pl_PL.UTF-8 → "pl-PL"
    if let Ok(lang) = std::env::var("LANG") {
        let base = lang.split('.').next().unwrap_or("");
        if !base.is_empty() && base != "C" && base != "POSIX" {
            return base.replace('_', "-");
        }
    }
    "en-US".to_owned()
}

/// 50% of physical RAM, clamped to [4, 8] GB.
/// Balloon device lets the daemon shrink/grow at runtime up to this ceiling.
fn detect_ram_gb() -> i32 {
    let total_gb = read_total_ram_gb();
    ((total_gb / 2).max(4)).min(8)
}

fn read_total_ram_gb() -> i32 {
    // Linux: /proc/meminfo MemTotal in kB
    if let Ok(text) = std::fs::read_to_string("/proc/meminfo") {
        for line in text.lines() {
            if let Some(rest) = line.strip_prefix("MemTotal:") {
                let kb: i64 = rest.split_whitespace().next()
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(0);
                return (kb / 1024 / 1024) as i32;
            }
        }
    }
    // macOS / fallback: assume 16 GB
    16
}

/// Half of available parallelism, clamped to [2, 8].
fn detect_vcpu() -> i32 {
    let cpus = std::thread::available_parallelism()
        .map(|n| n.get() as i32)
        .unwrap_or(4);
    ((cpus / 2).max(2)).min(8)
}

impl qobject::WizardState {
    pub fn start_install(mut self: std::pin::Pin<&mut Self>) {
        // Guard against double-invocation from QML (a user double-clicking the
        // Install button would otherwise spawn two ProgressView Timers racing
        // on the same state).
        if *self.as_ref().installing() {
            return;
        }
        self.as_mut().set_current_step(0);
        self.as_mut().set_progress_pct(0);
        self.as_mut().set_finished(false);
        self.as_mut().set_installing(true);
        self.as_mut()
            .set_progress_label(QString::from(progress::step_label(0)));
    }

    pub fn advance(mut self: std::pin::Pin<&mut Self>) {
        // Re-entrancy guard: only the active install loop may advance the
        // counter. Any extra Timer firing after `finished` is a no-op.
        if !*self.as_ref().installing() {
            return;
        }
        let next = *self.as_ref().current_step() + 1;
        let total = progress::total_steps() as i32;
        if next >= total {
            self.as_mut().set_current_step(total);
            self.as_mut().set_progress_pct(100);
            self.as_mut()
                .set_progress_label(QString::from("Installation complete"));
            self.as_mut().set_installing(false);
            self.as_mut().set_finished(true);
        } else {
            self.as_mut().set_current_step(next);
            // Progress at the start of step N is N/total; the QML ProgressBar
            // expects 0..100.
            self.as_mut().set_progress_pct((next * 100) / total);
            self.as_mut()
                .set_progress_label(QString::from(progress::step_label(next as usize)));
        }
    }

    pub fn reset(mut self: std::pin::Pin<&mut Self>) {
        self.as_mut().set_iso_source(QString::from("download"));
        self.as_mut().set_iso_path(QString::default());
        self.as_mut().set_current_step(0);
        self.as_mut().set_progress_pct(0);
        self.as_mut().set_progress_label(QString::from(""));
        self.as_mut().set_installing(false);
        self.as_mut().set_finished(false);
    }

    pub fn current_step_duration_ms(&self) -> i32 {
        let idx = *self.current_step() as usize;
        progress::step_duration_ms(idx) as i32
    }
}
