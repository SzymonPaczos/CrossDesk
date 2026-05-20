mod i18n;
mod manager;
mod qobjects;
mod single_instance;
mod wizard;

use cxx_qt_lib::{QGuiApplication, QQmlApplicationEngine, QString, QUrl};

fn main() {
    // Single-instance guard. If another crossdesk-gui process is already
    // running for this user, exit silently — Dolphin's "Open in Windows
    // app" action + ms-word:// URL handlers re-fire `crossdesk launch`,
    // which now spawns the GUI on the daemon-down branch. Without this
    // guard repeated clicks would pile up duplicate windows.
    let _lock = match single_instance::acquire() {
        Ok(guard) => Some(guard),
        Err(single_instance::AcquireError::AlreadyRunning { pid }) => {
            eprintln!(
                "crossdesk-gui: another instance is already running (pid={pid}), exiting"
            );
            return;
        }
        Err(single_instance::AcquireError::Io(err)) => {
            // Soft-fail: don't block the user just because /run is funky.
            eprintln!(
                "crossdesk-gui: single-instance lock failed ({err}); continuing anyway"
            );
            None
        }
    };

    let mut app = QGuiApplication::new();

    // Prefer LANG env var when it names a real locale (e.g. "pl_PL.UTF-8").
    // "C", "POSIX", and empty values are not real locales; fall through to
    // QLocale::system() which reads the OS API (NSLocale on macOS, LC_MESSAGES
    // on Linux) — correct even when LANG is "C.UTF-8" or unset.
    let locale = std::env::var("LANG")
        .ok()
        .and_then(|l| {
            let lang = l.split('_').next().unwrap_or("").to_owned();
            if lang.is_empty() || lang == "C" || lang == "POSIX" {
                None
            } else {
                Some(lang)
            }
        })
        .unwrap_or_else(i18n::system_locale);

    if app.as_mut().is_some() {
        i18n::install_translator(&locale);
    }

    let mut engine = QQmlApplicationEngine::new();
    if let Some(engine_mut) = engine.as_mut() {
        engine_mut.load(&QUrl::from(&QString::from(
            "qrc:/qt/qml/com/crossdesk/gui/qml/Main.qml",
        )));
    }

    if let Some(app_mut) = app.as_mut() {
        app_mut.exec();
    }
}
