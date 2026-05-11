unsafe extern "C" {
    fn crossdesk_install_translator(locale: *const u8, len: i32);
    fn crossdesk_system_locale(buf: *mut u8, buflen: i32);
}

/// Returns the two-letter language code from the OS locale API (not LANG env var).
/// On macOS this reads NSLocale; on Linux it reads setlocale / LC_MESSAGES.
pub fn system_locale() -> String {
    let mut buf = [0u8; 16];
    // Safety: buf is valid memory of exactly `buf.len()` bytes; C++ writes at most
    // buflen-1 non-NUL bytes and always NUL-terminates.
    unsafe { crossdesk_system_locale(buf.as_mut_ptr(), buf.len() as i32) }
    let s = std::str::from_utf8(&buf).unwrap_or("en");
    let end = s.find('\0').unwrap_or(s.len());
    s[..end].to_owned()
}

pub fn install_translator(locale: &str) {
    // Safety: the C++ function reads exactly `len` bytes from `locale`,
    // which is a valid UTF-8 str with at least that many bytes.
    unsafe { crossdesk_install_translator(locale.as_ptr(), locale.len() as i32) }
}
