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

fn make_result(req: &VerifyCredentialsRequest, status: Status, detail: &str, win32: u32) -> VerifyCredentialsResult {
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
    //! Real `LogonUserW` impl. Stage 4 (post-hardware) — placeholder
    //! zwracający `STATUS_UNAVAILABLE` żeby ścieżka kompilowała się
    //! cross-compile na Mac dla x86_64-pc-windows-gnu, ale nigdy nie
    //! wprowadziła hosta w błąd że credentials są OK. Real wiring:
    //! `windows::Win32::Security::LogonUserW` z LOGON32_LOGON_NETWORK
    //! + LOGON32_PROVIDER_DEFAULT, mapowanie GetLastError na enum.

    use super::{make_result, Status};
    use proto::crossdesk::v1::{VerifyCredentialsRequest, VerifyCredentialsResult};

    pub fn verify(req: &VerifyCredentialsRequest) -> VerifyCredentialsResult {
        make_result(
            req,
            Status::Unavailable,
            "real LogonUserW not yet wired — Stage 4 / post-hardware",
            0,
        )
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
