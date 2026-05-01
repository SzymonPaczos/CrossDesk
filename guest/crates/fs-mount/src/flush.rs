use proto::crossdesk::v1::{LockReport, ReleaseAck, TimingMark};
use tracing::debug;

pub async fn generate_mock_lock_report(share_id: &str, token: &[u8]) -> LockReport {
    debug!("[VirtioFS Mock] Generowanie LockReport dla {}", share_id);
    
    LockReport {
        share_id: share_id.to_string(),
        mount_token: token.to_vec(),
        open_handles: 0,
        pending_writes_bytes: 0,
        handles: vec![],
        observed_at: Some(TimingMark {
            wall_clock: None,
            monotonic_ns: 0,
        }),
    }
}

pub async fn generate_release_ack(share_id: &str, token: &[u8]) -> ReleaseAck {
    debug!("[VirtioFS Mock] Zwalnianie zasobów i przygotowanie ReleaseAck dla {}", share_id);
    
    ReleaseAck {
        share_id: share_id.to_string(),
        mount_token: token.to_vec(),
        released_at: Some(TimingMark {
            wall_clock: None,
            monotonic_ns: 0,
        }),
        total_bytes_written: 1024,
        final_handle_count_observed: 0,
    }
}
