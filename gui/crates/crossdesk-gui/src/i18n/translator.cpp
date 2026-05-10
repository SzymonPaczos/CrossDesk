#include "translator.h"
#include <QTranslator>
#include <QCoreApplication>
#include <QString>

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
