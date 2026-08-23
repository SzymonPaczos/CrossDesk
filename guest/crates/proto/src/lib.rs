//! tonic-build generated stubs for crossdesk.v1 gRPC services.

// clippy 1.98 (2026-08-18) started flagging `result_large_err` on every
// streaming client method tonic-build emits: the `Err` variant is
// `tonic::Status` (176 bytes), which comes from tonic 0.12 and is not ours
// to shrink. The offending code is generated into OUT_DIR by
// `include_proto!`, so there is nowhere to put a targeted `#[allow]` — the
// allow has to sit on the crate that includes it. Scoped to this crate only,
// so hand-written guest code still gets the lint.
#![allow(clippy::result_large_err)]

pub mod crossdesk {
    pub mod v1 {
        tonic::include_proto!("crossdesk.v1");
    }
}
