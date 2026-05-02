use cxx_qt_lib::{QCoreApplication, QString, QTranslator};

pub fn install_translator(app: std::pin::Pin<&mut cxx_qt_lib::QGuiApplication>, locale: &str) {
    let mut translator = QTranslator::new();
    let resource = QString::from(format!(":/i18n/crossdesk_{locale}.qm"));
    let loaded = if let Some(t) = translator.as_mut() {
        t.load_from_file(&resource)
    } else {
        false
    };

    if loaded {
        QCoreApplication::install_translator(app, &mut translator);
    }
}
