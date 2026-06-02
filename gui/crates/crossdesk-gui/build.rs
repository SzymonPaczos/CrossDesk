use cxx_qt_build::{CxxQtBuilder, QmlModule};
use std::path::Path;
use std::process::Command;

fn main() {
    // Compile .ts translation sources to .qm binaries before the Qt resource
    // compiler embeds them.  lrelease must be on PATH (it ships with Qt tools).
    // Safety: CARGO_MANIFEST_DIR is always set by cargo when invoking build
    // scripts (documented in The Cargo Book §Build Scripts).
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
        // Register the sidebar icons via the top-level resource path so they
        // resolve at qrc:/icons/*.svg (referenced that way from Manager.qml).
        // Going through the QmlModule's `qrc_files` field did NOT register
        // them at that root path in cxx-qt 0.7.3 (QML logged "Cannot open
        // qrc:/icons/*.svg" — verified live), whereas the top-level `.qrc()`
        // emits an explicit, linked resource initializer (cxx-qt-build
        // generate_cpp_from_qrc_files + build_initializers). Icons are a
        // separate qrc from qml.qrc so this path never depends on the .qm
        // translation files (which need lrelease at build time).
        .qrc("icons.qrc")
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
            // Translations (.qm) ride along here; tolerant of missing .qm when
            // lrelease is absent (unlike the top-level .qrc above).
            qrc_files: &["qml.qrc"],
            ..Default::default()
        })
        .build();
}
