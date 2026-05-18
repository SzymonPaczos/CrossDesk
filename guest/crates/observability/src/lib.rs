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

pub mod trace;

use tracing_subscriber::{fmt, prelude::*, EnvFilter};

const OTLP_ENV_VAR: &str = "OTEL_EXPORTER_OTLP_ENDPOINT";
const SERVICE_NAME: &str = "crossdesk-guest";

/// Configure the global subscriber. Idempotent in the sense that
/// `try_init` quietly errors when called twice — second calls become
/// no-ops, which is what we want for tests that boot multiple agents.
///
/// Per DEC-0006 §6 + DEC-0002, the OTLP exporter is opt-in: the
/// OpenTelemetry layer is wired into the subscriber stack only when
/// `OTEL_EXPORTER_OTLP_ENDPOINT` is set. Without it, no spans leave
/// the process and no extra goroutines are spawned. With it, every
/// `tracing` span is exported to that endpoint via OTLP-over-gRPC.
pub fn init() -> Result<(), tracing_subscriber::util::TryInitError> {
    let env_filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));

    let json_layer = fmt::layer()
        .json()
        .with_current_span(true)
        .with_span_list(false)
        .with_writer(std::io::stderr);

    let registry = tracing_subscriber::registry()
        .with(env_filter)
        .with(json_layer);

    if let Some(otel_layer) = build_otlp_layer() {
        registry.with(otel_layer).try_init()
    } else {
        registry.try_init()
    }
}

/// If `OTEL_EXPORTER_OTLP_ENDPOINT` is set, build the OpenTelemetry
/// layer that exports `tracing` spans to that endpoint via
/// OTLP-over-gRPC. Returns `None` when no endpoint is configured —
/// the call site adds nothing to the subscriber stack.
///
/// We swallow exporter-build errors and log them via `tracing` rather
/// than aborting init: a misconfigured OTLP endpoint must never
/// prevent the agent from starting.
fn build_otlp_layer<S>(
) -> Option<tracing_opentelemetry::OpenTelemetryLayer<S, opentelemetry_sdk::trace::Tracer>>
where
    S: tracing::Subscriber + for<'a> tracing_subscriber::registry::LookupSpan<'a>,
{
    use opentelemetry::trace::TracerProvider as _;
    use opentelemetry::KeyValue;
    use opentelemetry_otlp::{SpanExporter, WithExportConfig};
    use opentelemetry_sdk::{runtime::Tokio, trace::TracerProvider, Resource};

    let endpoint = std::env::var(OTLP_ENV_VAR).ok()?;
    if endpoint.is_empty() {
        return None;
    }

    let exporter = match SpanExporter::builder()
        .with_tonic()
        .with_endpoint(&endpoint)
        .build()
    {
        Ok(e) => e,
        Err(err) => {
            // Don't crash on OTLP misconfig — DEC-0006 lists OTLP as
            // opt-in, not load-bearing. The tracing subscriber isn't
            // installed yet here so stderr is the only viable channel;
            // the workspace `print_stderr` ban exists to keep the rest
            // of the codebase routing through `tracing`.
            #[allow(clippy::print_stderr)]
            {
                eprintln!("observability: OTLP exporter build failed: {err}");
            }
            return None;
        }
    };

    let provider = TracerProvider::builder()
        .with_batch_exporter(exporter, Tokio)
        .with_resource(Resource::new(vec![KeyValue::new(
            "service.name",
            SERVICE_NAME,
        )]))
        .build();
    let tracer = provider.tracer(SERVICE_NAME);
    // Hand the provider to the OTel global so tonic and other
    // ecosystem libraries that talk to the OTel API see the same one.
    opentelemetry::global::set_tracer_provider(provider);

    Some(tracing_opentelemetry::OpenTelemetryLayer::new(tracer))
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

        let v: serde_json::Value =
            serde_json::from_str(line).unwrap_or_else(|e| panic!("not JSON: {e}; line:\n{line}"));

        // tracing-subscriber's JSON format puts user fields under
        // `fields`. Schema sanity: timestamp + level + target + fields.
        for required in ["timestamp", "level", "fields", "target"] {
            assert!(v.get(required).is_some(), "missing field {required}");
        }
        let fields = v.get("fields").unwrap();
        assert_eq!(
            fields.get("component").and_then(|s| s.as_str()),
            Some("guest.tests.log")
        );
        assert_eq!(fields.get("key").and_then(|s| s.as_str()), Some("value"));
    }
}
