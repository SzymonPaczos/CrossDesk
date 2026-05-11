use cxx_qt_build::{CxxQtBuilder, QmlModule};
use std::path::Path;
use std::process::Command;

fn main() {
    // Compile .ts translation sources to .qm binaries before the Qt resource
    // compiler embeds them.  lrelease must be on PATH (it ships with Qt tools).
    let manifest = std::env::var("CARGO_MANIFEST_DIR").unwrap();
    for lang in &["pl", "en"] {
        let ts = format!("{}/i18n/crossdesk_{}.ts", manifest, lang);
        let qm = format!("{}/i18n/crossdesk_{}.qm", manifest, lang);
        if Path::new(&ts).exists() {
            Command::new("lrelease")
                .args([&ts, "-qm", &qm])
                .status()
                .ok();
        }
        println!("cargo:rerun-if-changed={}", ts);
    }

    CxxQtBuilder::new()
        .qt_module("Quick")
        .qt_module("QuickControls2")
        .cc_builder(|cc| {
            cc.file("src/i18n/translator.cpp");
        })
        .qml_module(QmlModule {
            uri: "com.crossdesk.gui",
            rust_files: &["src/qobjects/wizard.rs", "src/qobjects/manager.rs"],
            qml_files: &[
                "qml/Main.qml",
                "qml/wizard/InstallWizard.qml",
                "qml/wizard/Step1Iso.qml",
                "qml/wizard/Step2Review.qml",
                "qml/wizard/ProgressView.qml",
                "qml/manager/Manager.qml",
                "qml/manager/Dashboard.qml",
                "qml/manager/Apps.qml",
                "qml/manager/Storage.qml",
                "qml/manager/Lifecycle.qml",
                "qml/manager/Diagnose.qml",
                "qml/manager/Logs.qml",
                "qml/manager/Settings.qml",
                "qml/manager/About.qml",
            ],
            qrc_files: &["qml.qrc"],
            ..Default::default()
        })
        .build();
}
