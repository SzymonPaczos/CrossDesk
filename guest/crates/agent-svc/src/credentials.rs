//! Auth health-check handler — odpowiada na `ServerFrame.verify_credentials`
//! (DEC-0001 Windows password lifecycle, FOLLOWUPS:928-935 / 985-994).
//!
//! Host wysyła credentials z `~/.config/crossdesk/vm.toml` przed każdym
//! RAIL launch; guest woła `LogonUserW` (LOGON32_LOGON_NETWORK — najtańsze,
//! nie tworzy desktopu) i odpowiada strukturyzowanym statusem. Host gate'uje
//! spawn FreeRDP na `STATUS_OK`; przy FAIL surface'uje wskazówkę
//! `crossdesk vm credentials repair`.
//!
//! Cfg gating: real impl `LogonUserW` tylko gdy `target_os = "windows"` i
//! brak feature'u `mock`. Wszystkie inne ścieżki (Mac dev, Linux integration
//! harness, `cargo test --features mock` na Windows) używają deterministic
//! mock'a poniżej.

use proto::crossdesk::v1::verify_credentials_result::Status;
use proto::crossdesk::v1::{VerifyCredentialsRequest, VerifyCredentialsResult};

/// Entry point: rozsyła do real lub mock w zależności od cfg.
pub fn handle_verify_credentials(req: &VerifyCredentialsRequest) -> VerifyCredentialsResult {
    #[cfg(all(target_os = "windows", not(feature = "mock")))]
    {
        windows_impl::verify(req)
    }
    #[cfg(any(not(target_os = "windows"), feature = "mock"))]
    {
        mock_impl::verify(req)
    }
}

fn make_result(
    req: &VerifyCredentialsRequest,
    status: Status,
    detail: &str,
    win32: u32,
) -> VerifyCredentialsResult {
    VerifyCredentialsResult {
        request_id: req.request_id.clone(),
        status: status as i32,
        detail: detail.to_string(),
        win32_error: win32,
    }
}

#[cfg(any(not(target_os = "windows"), feature = "mock"))]
mod mock_impl {
    //! Deterministyczna mapa cred → status. Hooks do failure-injection
    //! przez username prefix `__inject_<status>__` (zgodnie z wzorcem
    //! `MockTransport`/`MockFreeRDPInvocation`).

    use super::{make_result, Status};
    use proto::crossdesk::v1::{VerifyCredentialsRequest, VerifyCredentialsResult};

    pub fn verify(req: &VerifyCredentialsRequest) -> VerifyCredentialsResult {
        if let Some(injected) = parse_inject_username(&req.username) {
            return injected_response(req, injected);
        }
        match (req.username.as_str(), req.password.as_str()) {
            ("crossdesk", "test123") => make_result(req, Status::Ok, "logon succeeded (mock)", 0),
            ("crossdesk", "expired") => make_result(
                req,
                Status::FailPasswordExpired,
                "password expired (mock)",
                1907, // ERROR_PASSWORD_EXPIRED
            ),
            ("crossdesk", "locked") => make_result(
                req,
                Status::FailAccountLocked,
                "account locked out (mock)",
                1909, // ERROR_ACCOUNT_LOCKED_OUT
            ),
            _ => make_result(
                req,
                Status::FailBadCredentials,
                "username/password mismatch (mock)",
                1326, // ERROR_LOGON_FAILURE
            ),
        }
    }

    fn parse_inject_username(s: &str) -> Option<&'static str> {
        let stripped = s.strip_prefix("__inject_")?.strip_suffix("__")?;
        match stripped {
            "ok" | "bad" | "locked" | "expired" | "unavailable" => Some(match stripped {
                "ok" => "ok",
                "bad" => "bad",
                "locked" => "locked",
                "expired" => "expired",
                "unavailable" => "unavailable",
                _ => unreachable!(),
            }),
            _ => None,
        }
    }

    fn injected_response(req: &VerifyCredentialsRequest, kind: &str) -> VerifyCredentialsResult {
        let (status, detail, err) = match kind {
            "ok" => (Status::Ok, "injected ok", 0),
            "bad" => (Status::FailBadCredentials, "injected bad creds", 1326),
            "locked" => (Status::FailAccountLocked, "injected lockout", 1909),
            "expired" => (Status::FailPasswordExpired, "injected expiry", 1907),
            "unavailable" => (Status::Unavailable, "injected agent error", 0),
            _ => (Status::Unspecified, "unknown injection", 0),
        };
        make_result(req, status, detail, err)
    }
}

#[cfg(all(target_os = "windows", not(feature = "mock")))]
mod windows_impl {
    //! Real `LogonUserW` impl (Stage 4). LOGON32_LOGON_NETWORK +
    //! LOGON32_PROVIDER_DEFAULT — cheapest mode: no desktop allocated,
    //! no roaming profile loaded, runs entirely in LSA. The returned
    //! handle is closed immediately (we only care whether the logon
    //! would have succeeded). GetLastError is mapped to the proto
    //! Status enum; unknown codes fall through to Unavailable so the
    //! host can fail closed and surface a repair hint.
    //!
    //! Why we don't use `windows::Result` for the Win32 error: the
    //! crate wraps BOOL returns into `Result<(), windows::core::Error>`
    //! whose `.code()` is a HRESULT, not a raw Win32 code. To keep the
    //! proto contract (`win32_error: uint32`) faithful we call
    //! `GetLastError()` directly after the unsuccessful logon.
    use super::{make_result, Status};
    use proto::crossdesk::v1::{VerifyCredentialsRequest, VerifyCredentialsResult};
    use std::iter::once;
    use std::os::windows::ffi::OsStrExt;
    use std::ffi::OsStr;
    use windows::core::PCWSTR;
    use windows::Win32::Foundation::{CloseHandle, GetLastError, HANDLE};
    use windows::Win32::Security::{
        LogonUserW, LOGON32_LOGON_NETWORK, LOGON32_PROVIDER_DEFAULT,
    };

    pub fn verify(req: &VerifyCredentialsRequest) -> VerifyCredentialsResult {
        let username = to_wide(&req.username);
        let password = to_wide(&req.password);
        // Empty domain → local account; pass NULL pointer so LSA
        // resolves "username" against the machine SAM database.
        let domain_buf: Option<Vec<u16>> = if req.domain.is_empty() {
            None
        } else {
            Some(to_wide(&req.domain))
        };
        let domain_pcwstr = match &domain_buf {
            Some(buf) => PCWSTR(buf.as_ptr()),
            None => PCWSTR::null(),
        };

        let mut token = HANDLE::default();
        // Safety: LogonUserW writes to `token` (out-param) and reads
        // null-terminated UTF-16 strings from `username`/`password`/
        // `domain`. All buffers outlive the call.
        let result = unsafe {
            LogonUserW(
                PCWSTR(username.as_ptr()),
                domain_pcwstr,
                PCWSTR(password.as_ptr()),
                LOGON32_LOGON_NETWORK,
                LOGON32_PROVIDER_DEFAULT,
                &mut token,
            )
        };

        if result.is_ok() {
            if !token.is_invalid() {
                // Safety: token was obtained from a successful
                // LogonUserW call above; we own it and close it now.
                let _ = unsafe { CloseHandle(token) };
            }
            return make_result(req, Status::Ok, "logon succeeded", 0);
        }

        // Safety: trivial FFI call, no preconditions.
        let err = unsafe { GetLastError() }.0;
        let (status, detail) = match err {
            1326 => (Status::FailBadCredentials, "invalid username or password"),
            1909 => (Status::FailAccountLocked, "account locked out"),
            1907 => (Status::FailPasswordExpired, "password expired"),
            _ => (Status::Unavailable, "logon failed"),
        };
        make_result(req, status, detail, err)
    }

    fn to_wide(s: &str) -> Vec<u16> {
        OsStr::new(s).encode_wide().chain(once(0)).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn req(username: &str, password: &str) -> VerifyCredentialsRequest {
        VerifyCredentialsRequest {
            request_id: "test-id".to_string(),
            username: username.to_string(),
            password: password.to_string(),
            domain: String::new(),
        }
    }

    #[test]
    fn happy_path_returns_ok() {
        let result = handle_verify_credentials(&req("crossdesk", "test123"));
        assert_eq!(result.status, Status::Ok as i32);
        assert_eq!(result.request_id, "test-id");
        assert_eq!(result.win32_error, 0);
    }

    #[test]
    fn bad_credentials_returns_fail_bad() {
        let result = handle_verify_credentials(&req("crossdesk", "wrong"));
        assert_eq!(result.status, Status::FailBadCredentials as i32);
        assert_eq!(result.win32_error, 1326);
    }

    #[test]
    fn expired_password_returns_fail_expired() {
        let result = handle_verify_credentials(&req("crossdesk", "expired"));
        assert_eq!(result.status, Status::FailPasswordExpired as i32);
        assert_eq!(result.win32_error, 1907);
    }

    #[test]
    fn locked_account_returns_fail_locked() {
        let result = handle_verify_credentials(&req("crossdesk", "locked"));
        assert_eq!(result.status, Status::FailAccountLocked as i32);
        assert_eq!(result.win32_error, 1909);
    }

    #[test]
    fn unknown_user_returns_fail_bad() {
        let result = handle_verify_credentials(&req("nobody", "whatever"));
        assert_eq!(result.status, Status::FailBadCredentials as i32);
    }

    #[test]
    fn injection_unavailable() {
        let result = handle_verify_credentials(&req("__inject_unavailable__", "anything"));
        assert_eq!(result.status, Status::Unavailable as i32);
    }

    #[test]
    fn injection_ok_overrides_password() {
        let result = handle_verify_credentials(&req("__inject_ok__", "ignored"));
        assert_eq!(result.status, Status::Ok as i32);
    }

    #[test]
    fn request_id_is_echoed() {
        let mut r = req("crossdesk", "test123");
        r.request_id = "abc-123".to_string();
        assert_eq!(handle_verify_credentials(&r).request_id, "abc-123");
    }
}
