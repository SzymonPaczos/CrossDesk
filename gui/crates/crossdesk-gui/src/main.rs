mod i18n;
mod manager;
mod qobjects;
mod wizard;

use cxx_qt_lib::{QGuiApplication, QQmlApplicationEngine, QString, QUrl};

fn main() {
    let mut app = QGuiApplication::new();

    // Detect locale from LANG env var (e.g. "pl_PL.UTF-8" → "pl").
    // Falls back to "en" so the app stays functional without any LANG set.
    let locale = std::env::var("LANG")
        .ok()
        .and_then(|l| l.split('_').next().map(str::to_owned))
        .and_then(|l| if l.is_empty() { None } else { Some(l) })
        .unwrap_or_else(|| "en".to_owned());

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
