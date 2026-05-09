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

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn lock_report_clean_state() {
        let report = mock_generate_lock_report("s", b"tok").await;
        assert_eq!(report.share_id, "s");
        assert_eq!(report.open_handles, 0);
        assert_eq!(report.pending_writes_bytes, 0);
        assert!(report.handles.is_empty());
        assert!(report.observed_at.is_some());
    }

    #[tokio::test]
    async fn lock_report_echoes_token() {
        let report = mock_generate_lock_report("s", b"\x01\x02\x03").await;
        assert_eq!(report.mount_token, vec![0x01, 0x02, 0x03]);
    }

    #[tokio::test]
    async fn release_ack_carries_share_id() {
        let ack = mock_generate_release_ack("share-xyz", b"t").await;
        assert_eq!(ack.share_id, "share-xyz");
    }

    #[tokio::test]
    async fn release_ack_zero_handles_invariant() {
        // ReleaseAck means "all handles closed" — the wire contract
        // says final_handle_count_observed MUST be 0. The mock pins
        // this so a future regression that bumps handles to non-zero
        // is caught immediately.
        let ack = mock_generate_release_ack("s", b"t").await;
        assert_eq!(ack.final_handle_count_observed, 0);
    }

    #[tokio::test]
    async fn release_ack_includes_timestamp() {
        let ack = mock_generate_release_ack("s", b"t").await;
        assert!(ack.released_at.is_some());
    }

    #[tokio::test]
    async fn lock_and_release_share_token_format() {
        // The token bytes must be byte-identical between LockReport
        // and ReleaseAck for the same share — the host correlates
        // them via (share_id, mount_token).
        let token = b"matching-token";
        let lock = mock_generate_lock_report("s", token).await;
        let ack = mock_generate_release_ack("s", token).await;
        assert_eq!(lock.mount_token, ack.mount_token);
    }
}
