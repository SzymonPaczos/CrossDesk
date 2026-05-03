use proto::crossdesk::v1::{LockReport, ReleaseAck, TimingMark};
use tracing::debug;

/// Phase 5 placeholder — emits a clean LockReport (no open handles, no
/// pending writes) without inspecting the actual virtiofs state.
pub async fn mock_generate_lock_report(share_id: &str, token: &[u8]) -> LockReport {
    debug!(share = %share_id, "[mock] generating LockReport");
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

/// Phase 5 placeholder — emits a ReleaseAck with hard-coded byte counts.
pub async fn mock_generate_release_ack(share_id: &str, token: &[u8]) -> ReleaseAck {
    debug!(share = %share_id, "[mock] preparing ReleaseAck");
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
