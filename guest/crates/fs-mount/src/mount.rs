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
