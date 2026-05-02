use cxx_qt_lib::QGuiApplication;
use std::pin::Pin;

// TODO: cxx-qt-lib 0.7.3 does not expose QTranslator or
// QCoreApplication::installTranslator. Wire translation loading once we
// add a custom cxx::bridge for QTranslator (or upgrade cxx-qt-lib).
pub fn install_translator(_app: Pin<&mut QGuiApplication>, _locale: &str) {}
