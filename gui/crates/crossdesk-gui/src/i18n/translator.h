#pragma once
extern "C" {
    void crossdesk_install_translator(const char* locale, int len);
    // Writes the two-letter language code from QLocale::system() into buf (NUL-terminated).
    void crossdesk_system_locale(char* buf, int buflen);
}
