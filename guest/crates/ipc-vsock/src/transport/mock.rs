//! Test-side transport. Identical wire path to `RealTransport` (TCP
//! loopback) but exposes failure-injection hooks that production code must
//! never carry — the rule from DEC-0005 is that mocks enforce the same
//! invariants but make their failure modes scriptable.
//!
//! Use only in tests or with `--features mock`. The cfg gate in `lib.rs`
//! prevents production binaries from accidentally linking it.

use std::future::Future;
use std::io;
use std::pin::Pin;
use std::sync::{Arc, Mutex};
use std::task::{Context, Poll};
use hyper_util::rt::TokioIo;
use tokio::net::TcpStream;
use tonic::transport::Uri;
use tower::Service;

/// Knobs flipped by tests to drive deterministic failure scenarios. Each
/// hook is exercised at most once per `MockTransport::call` so a
/// "simulate connect failure on the third attempt" pattern is achieved by
/// constructing the mock with a pre-decremented counter.
#[derive(Clone, Default, Debug)]
pub struct MockHooks {
    /// If `Some`, the next `call()` returns this error instead of dialing.
    /// Cleared after firing so subsequent calls succeed.
    pub fail_next_connect: Arc<Mutex<Option<io::ErrorKind>>>,
    /// Counts every successful `call()`. Tests inspect this to assert the
    /// transport was actually exercised by tonic.
    pub call_count: Arc<Mutex<usize>>,
}

impl MockHooks {
    pub fn fail_next_connect_with(&self, kind: io::ErrorKind) {
        *self.fail_next_connect.lock().expect("mock hooks poisoned") = Some(kind);
    }

    pub fn call_count(&self) -> usize {
        *self.call_count.lock().expect("mock hooks poisoned")
    }

    fn take_fail_next_connect(&self) -> Option<io::ErrorKind> {
        self.fail_next_connect
            .lock()
            .expect("mock hooks poisoned")
            .take()
    }

    fn record_call(&self) {
        *self.call_count.lock().expect("mock hooks poisoned") += 1;
    }
}

#[derive(Clone, Debug, Default)]
pub struct MockTransport {
    pub hooks: MockHooks,
}

impl MockTransport {
    pub fn new() -> Self {
        Self::default()
    }
}

impl Service<Uri> for MockTransport {
    type Response = TokioIo<TcpStream>;
    type Error = io::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>> + Send>>;

    fn poll_ready(&mut self, _cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        Poll::Ready(Ok(()))
    }

    fn call(&mut self, uri: Uri) -> Self::Future {
        let injected = self.hooks.take_fail_next_connect();
        let hooks = self.hooks.clone();
        let host = uri.host().unwrap_or("127.0.0.1").to_string();
        let port = uri.port_u16().unwrap_or(50051);
        Box::pin(async move {
            if let Some(kind) = injected {
                return Err(io::Error::new(kind, "mock-injected connect failure"));
            }
            let addr = format!("{host}:{port}");
            tracing::debug!(target = %addr, "mock transport dialing TCP loopback");
            let stream = TcpStream::connect(addr).await?;
            hooks.record_call();
            Ok(TokioIo::new(stream))
        })
    }
}
