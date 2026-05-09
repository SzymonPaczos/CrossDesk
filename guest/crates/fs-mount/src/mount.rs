use proto::crossdesk::v1::MountResult;
use proto::crossdesk::v1::mount_result::Status as MountStatus;
use tracing::info;

/// Phase 5 placeholder — pretends a virtiofs share was mapped onto
/// `drive_letter`. The real implementation will drive WinFSP / virtiofs.
pub async fn mock_handle_mount_request(
    share_id: &str,
    drive_letter: &str,
    token: &[u8],
) -> MountResult {
    info!(share = %share_id, drive = %drive_letter, "[mock] mapping virtiofs share");
    tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
    info!(drive = %drive_letter, "[mock] share mapped");

    MountResult {
        share_id: share_id.to_string(),
        mount_token: token.to_vec(),
        status: MountStatus::Mounted.into(),
        detail: format!("[mock] mapped drive {drive_letter}"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn mock_returns_mounted_status() {
        let token = b"32-byte-token-12345678901234567x";
        let result = mock_handle_mount_request("share-1", "X:", token).await;
        assert_eq!(result.share_id, "share-1");
        assert_eq!(result.status, MountStatus::Mounted as i32);
        assert!(result.detail.contains("X:"));
    }

    #[tokio::test]
    async fn mock_echoes_token_verbatim() {
        // Mock must echo bytes so host-side token-mismatch tests catch
        // tampering. Token is opaque to the guest; host validates length.
        let token: &[u8] = &[
            0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c,
            0x0d, 0x0e, 0x0f, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18,
            0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f, 0x20,
        ];
        let result = mock_handle_mount_request("s", "Z:", token).await;
        assert_eq!(result.mount_token.as_slice(), token);
    }

    #[tokio::test]
    async fn mock_carries_share_id_into_detail() {
        let result = mock_handle_mount_request("abc-def", "Y:", b"t").await;
        assert_eq!(result.share_id, "abc-def");
    }

    #[tokio::test]
    async fn mock_handles_empty_token() {
        // Mock doesn't validate token length — that's the host's job at
        // MountResult ingest. Mock just round-trips bytes.
        let result = mock_handle_mount_request("s", "X:", b"").await;
        assert_eq!(result.mount_token.len(), 0);
    }

    #[tokio::test]
    async fn mock_handles_unicode_drive_letter() {
        // Defensive: the wire field is `string` (UTF-8) so any valid
        // UTF-8 round-trips. Real Windows drive letters are ASCII; the
        // proto doesn't enforce that.
        let result = mock_handle_mount_request("s", "Δ:", b"t").await;
        assert!(result.detail.contains("Δ:"));
    }
}
