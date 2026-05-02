use cxx_qt_lib::QString;

use crate::wizard::progress;

/// Minimum/maximum bounds for the resource sliders on Step 3.
const RAM_GB_DEFAULT: i32 = 8;
const VCPU_DEFAULT: i32 = 4;
const DISK_GB_DEFAULT: i32 = 80;

#[cxx_qt::bridge]
pub mod qobject {
    unsafe extern "C++" {
        include!("cxx-qt-lib/qstring.h");
        type QString = cxx_qt_lib::QString;
    }

    extern "RustQt" {
        #[qobject]
        #[qml_element]
        #[qproperty(QString, iso_path)]
        #[qproperty(QString, vm_name)]
        #[qproperty(QString, timezone)]
        #[qproperty(QString, locale)]
        #[qproperty(i32, ram_gb)]
        #[qproperty(i32, vcpu)]
        #[qproperty(i32, disk_gb)]
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
    iso_path: QString,
    vm_name: QString,
    timezone: QString,
    locale: QString,
    ram_gb: i32,
    vcpu: i32,
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
            iso_path: QString::default(),
            vm_name: QString::from("windows-11-dev"),
            timezone: QString::from("Europe/Warsaw"),
            locale: QString::from("en-US"),
            ram_gb: RAM_GB_DEFAULT,
            vcpu: VCPU_DEFAULT,
            disk_gb: DISK_GB_DEFAULT,
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
        // No-op: defaults set via Default impl. Kept for future signal wiring.
    }
}

impl qobject::WizardState {
    pub fn start_install(mut self: std::pin::Pin<&mut Self>) {
        self.as_mut().set_current_step(0);
        self.as_mut().set_progress_pct(0);
        self.as_mut().set_finished(false);
        self.as_mut().set_installing(true);
        self.as_mut()
            .set_progress_label(QString::from(progress::step_label(0)));
    }

    pub fn advance(mut self: std::pin::Pin<&mut Self>) {
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
            // Progress at the *start* of step N is N/total; expressed as percent
            // for the QML ProgressBar which expects 0..100.
            self.as_mut().set_progress_pct((next * 100) / total);
            self.as_mut()
                .set_progress_label(QString::from(progress::step_label(next as usize)));
        }
    }

    pub fn reset(mut self: std::pin::Pin<&mut Self>) {
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
