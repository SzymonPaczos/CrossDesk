use proto::crossdesk::v1::MountResult;
use proto::crossdesk::v1::mount_result::Status as MountStatus;
use tracing::info;

pub async fn handle_mount_request(share_id: &str, drive_letter: &str, token: &[u8]) -> MountResult {
    // Symulacja podłączania urządzenia WinFSP virtiofs.
    // Prawdziwa wersja wywołałaby np. narzędzia winfsp do zmapowania dysku z virtiofs.
    info!("[VirtioFS Mock] Zaczynam mapowanie wirtualnego dysku virtiofs z id {} pod literę {}", share_id, drive_letter);
    
    // Uśpij krótko aby udawać pracę IO
    tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
    
    info!("[VirtioFS Mock] Dysk {} zmapowany z powodzeniem.", drive_letter);
    
    MountResult {
        share_id: share_id.to_string(),
        mount_token: token.to_vec(),
        status: MountStatus::Mounted.into(),
        detail: format!("Successfully mapped drive {}", drive_letter),
    }
}
