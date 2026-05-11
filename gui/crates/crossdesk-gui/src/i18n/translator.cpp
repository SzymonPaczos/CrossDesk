#include "translator.h"
#include <QTranslator>
#include <QCoreApplication>
#include <QLocale>
#include <QString>
#include <cstring>

extern "C" void crossdesk_system_locale(char* buf, int buflen) {
    // QLocale::system() reads the OS locale API (NSLocale on macOS, setlocale on Linux)
    // which is correct even when LANG env var is "C" or unset.
    QString name = QLocale::system().name(); // e.g. "pl_PL" or "en_US"
    int sep = name.indexOf('_');
    QString lang = (sep > 0) ? name.left(sep) : name;
    QByteArray bytes = lang.toUtf8();
    strncpy(buf, bytes.constData(), static_cast<size_t>(buflen) - 1);
    buf[buflen - 1] = '\0';
}

extern "C" void crossdesk_install_translator(const char* locale, int len) {
    QString loc = QString::fromUtf8(locale, len);
    auto* t = new QTranslator;
    bool ok = t->load(QString(":/i18n/crossdesk_%1.qm").arg(loc));
    if (!ok) {
        ok = t->load(QString(":/i18n/crossdesk_en.qm"));
    }
    if (ok) {
        QCoreApplication::installTranslator(t);
    } else {
        delete t;
    }
}
