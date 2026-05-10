unsafe extern "C" {
    fn crossdesk_install_translator(locale: *const u8, len: i32);
}

pub fn install_translator(locale: &str) {
    // Safety: the C++ function reads exactly `len` bytes from `locale`,
    // which is a valid UTF-8 str with at least that many bytes.
    unsafe { crossdesk_install_translator(locale.as_ptr(), locale.len() as i32) }
}
