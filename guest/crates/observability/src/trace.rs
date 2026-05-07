//! W3C Trace Context (`traceparent`) on tonic gRPC metadata.
//!
//! Symmetric with `host/src/crossdesk_host/observability/trace_ctx.py`:
//! same wire format (`00-<trace>-<span>-<flags>`), same fall-back
//! behaviour (parse failure → return None, caller mints a fresh root).

use rand::RngCore;
use tonic::metadata::{MetadataMap, MetadataValue};

const TRACEPARENT_KEY: &str = "traceparent";
const INVALID_TRACE_ID: &str = "00000000000000000000000000000000";
const INVALID_SPAN_ID: &str = "0000000000000000";

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TraceContext {
    pub trace_id: String,
    pub span_id: String,
    pub flags: String,
}

impl TraceContext {
    pub fn to_traceparent(&self) -> String {
        format!("00-{}-{}-{}", self.trace_id, self.span_id, self.flags)
    }

    pub fn is_valid(&self) -> bool {
        self.trace_id != INVALID_TRACE_ID && self.span_id != INVALID_SPAN_ID
    }
}

fn random_hex(bytes: usize) -> String {
    let mut buf = vec![0u8; bytes];
    rand::thread_rng().fill_bytes(&mut buf);
    let mut s = String::with_capacity(bytes * 2);
    for b in buf {
        s.push_str(&format!("{b:02x}"));
    }
    s
}

pub fn generate_root() -> TraceContext {
    TraceContext {
        trace_id: random_hex(16),
        span_id: random_hex(8),
        flags: "01".to_string(),
    }
}

pub fn child_span(parent: &TraceContext) -> TraceContext {
    TraceContext {
        trace_id: parent.trace_id.clone(),
        span_id: random_hex(8),
        flags: parent.flags.clone(),
    }
}

pub fn parse_traceparent(value: &str) -> Option<TraceContext> {
    let trimmed = value.trim();
    let parts: Vec<&str> = trimmed.split('-').collect();
    if parts.len() != 4 || parts[0] != "00" {
        return None;
    }
    if parts[1].len() != 32 || parts[2].len() != 16 || parts[3].len() != 2 {
        return None;
    }
    if !parts[1].chars().all(|c| c.is_ascii_hexdigit())
        || !parts[2].chars().all(|c| c.is_ascii_hexdigit())
        || !parts[3].chars().all(|c| c.is_ascii_hexdigit())
    {
        return None;
    }
    Some(TraceContext {
        trace_id: parts[1].to_string(),
        span_id: parts[2].to_string(),
        flags: parts[3].to_string(),
    })
}

pub fn extract_from_metadata(metadata: &MetadataMap) -> Option<TraceContext> {
    metadata
        .get(TRACEPARENT_KEY)
        .and_then(|v| v.to_str().ok())
        .and_then(parse_traceparent)
}

/// Insert a `traceparent` value onto outgoing tonic metadata. Used by
/// the request interceptor — see `inject_interceptor` below.
pub fn inject_into_metadata(metadata: &mut MetadataMap, ctx: &TraceContext) {
    if let Ok(value) = MetadataValue::try_from(&ctx.to_traceparent()) {
        metadata.insert(TRACEPARENT_KEY, value);
    }
}

/// Build a tonic interceptor that stamps every outgoing request with
/// the supplied trace context. Constructed once per stream so each
/// stream has a stable trace ID for its lifetime; callers usually
/// generate the context with `generate_root()` and clone it across
/// the planes that share a single trace.
pub fn inject_interceptor(
    ctx: TraceContext,
) -> impl FnMut(tonic::Request<()>) -> Result<tonic::Request<()>, tonic::Status> + Clone {
    move |mut req| {
        inject_into_metadata(req.metadata_mut(), &ctx);
        Ok(req)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip_traceparent() {
        let ctx = generate_root();
        let serialised = ctx.to_traceparent();
        let parsed = parse_traceparent(&serialised).expect("round-trip");
        assert_eq!(parsed, ctx);
    }

    #[test]
    fn parse_rejects_wrong_version() {
        assert!(parse_traceparent("01-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01").is_none());
    }

    #[test]
    fn parse_rejects_short_hex() {
        assert!(parse_traceparent("00-tooshort-bbbbbbbbbbbbbbbb-01").is_none());
    }

    #[test]
    fn child_span_keeps_trace_id_changes_span() {
        let parent = generate_root();
        let child = child_span(&parent);
        assert_eq!(parent.trace_id, child.trace_id);
        assert_ne!(parent.span_id, child.span_id);
    }

    #[test]
    fn metadata_round_trip() {
        let ctx = generate_root();
        let mut md = MetadataMap::new();
        inject_into_metadata(&mut md, &ctx);
        let extracted = extract_from_metadata(&md).expect("extract");
        assert_eq!(extracted, ctx);
    }
}
