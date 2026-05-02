use cxx_qt_build::{CxxQtBuilder, QmlModule};

fn main() {
    CxxQtBuilder::new()
        .qt_module("Quick")
        .qt_module("QuickControls2")
        .qml_module(QmlModule {
            uri: "com.crossdesk.gui",
            rust_files: &["src/wizard/state.rs"],
            qml_files: &[
                "qml/Main.qml",
                "qml/wizard/InstallWizard.qml",
                "qml/wizard/Step1Iso.qml",
                "qml/wizard/Step2Identity.qml",
                "qml/wizard/Step3Resources.qml",
                "qml/wizard/ProgressView.qml",
            ],
            ..Default::default()
        })
        .build();
}
