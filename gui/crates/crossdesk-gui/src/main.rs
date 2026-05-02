mod i18n;
mod wizard;

use cxx_qt_lib::{QGuiApplication, QQmlApplicationEngine, QString, QUrl};

fn main() {
    let mut app = QGuiApplication::new();

    if let Some(app_mut) = app.as_mut() {
        i18n::install_translator(app_mut, "en");
    }

    let mut engine = QQmlApplicationEngine::new();
    if let Some(engine_mut) = engine.as_mut() {
        engine_mut.load(&QUrl::from(QString::from(
            "qrc:/qt/qml/com/crossdesk/gui/qml/Main.qml",
        )));
    }

    if let Some(app_mut) = app.as_mut() {
        app_mut.exec();
    }
}
