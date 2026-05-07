//! Observability facade — JSON-line `tracing` configuration mirroring
//! the Python host facade. Every CrossDesk Rust binary calls
//! [`init`] once at startup so logs land on stderr in the same schema:
//!
//! ```text
//! {"timestamp": "...", "level": "...", "component": "...",
//!  "trace_id": "", "span_id": "",
//!  "fields": {"event": "...", ...}, "target": "..."}
//! ```
//!
//! Mandatory fields per DEC-0006 are always present; trace/span IDs
//! are empty strings until W3C Trace Context propagation lands
//! (`trace::install_carrier`).

use tracing_subscriber::{fmt, prelude::*, EnvFilter};

/// Configure the global subscriber. Idempotent in the sense that
/// `try_init` quietly errors when called twice — second calls become
/// no-ops, which is what we want for tests that boot multiple agents.
pub fn init() -> Result<(), tracing_subscriber::util::TryInitError> {
    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info"));

    let json_layer = fmt::layer()
        .json()
        .with_current_span(true)
        .with_span_list(false)
        .with_writer(std::io::stderr);

    tracing_subscriber::registry()
        .with(env_filter)
        .with(json_layer)
        .try_init()
}

/// Variant for tests that need to capture output. The caller supplies
/// any writer; the resulting subscriber is *not* set as global, it's
/// returned for installation under `tracing::subscriber::with_default`.
pub fn build_test_subscriber<W>(writer: W) -> impl tracing::Subscriber + Send + Sync
where
    W: for<'a> fmt::MakeWriter<'a> + Send + Sync + 'static,
{
    tracing_subscriber::registry()
        .with(EnvFilter::new("trace"))
        .with(
            fmt::layer()
                .json()
                .with_current_span(false)
                .with_span_list(false)
                .with_writer(writer),
        )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex};
    use tracing::info;

    /// Writer that captures into an Arc<Mutex<Vec<u8>>> so tests can
    /// inspect emitted bytes after the subscriber drops.
    #[derive(Clone)]
    struct VecWriter(Arc<Mutex<Vec<u8>>>);

    impl<'a> fmt::MakeWriter<'a> for VecWriter {
        type Writer = VecWriterHandle;
        fn make_writer(&'a self) -> Self::Writer {
            VecWriterHandle(self.0.clone())
        }
    }

    struct VecWriterHandle(Arc<Mutex<Vec<u8>>>);

    impl std::io::Write for VecWriterHandle {
        fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
            self.0.lock().expect("lock").extend_from_slice(buf);
            Ok(buf.len())
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }

    #[test]
    fn emits_json_with_required_keys() {
        let buf = Arc::new(Mutex::new(Vec::<u8>::new()));
        let writer = VecWriter(buf.clone());
        let subscriber = build_test_subscriber(writer);

        tracing::subscriber::with_default(subscriber, || {
            info!(component = "guest.tests.log", key = "value", "smoke");
        });

        let bytes = buf.lock().unwrap().clone();
        let line = std::str::from_utf8(&bytes).unwrap().trim();
        assert!(!line.is_empty(), "no log line emitted");

        let v: serde_json::Value = serde_json::from_str(line)
            .unwrap_or_else(|e| panic!("not JSON: {e}; line:\n{line}"));

        // tracing-subscriber's JSON format puts user fields under
        // `fields`. Schema sanity: timestamp + level + target + fields.
        for required in ["timestamp", "level", "fields", "target"] {
            assert!(v.get(required).is_some(), "missing field {required}");
        }
        let fields = v.get("fields").unwrap();
        assert_eq!(fields.get("component").and_then(|s| s.as_str()), Some("guest.tests.log"));
        assert_eq!(fields.get("key").and_then(|s| s.as_str()), Some("value"));
    }
}
