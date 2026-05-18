//! End-to-end behaviours of `MockTransport`. The real transport flows the
//! same code path on TCP loopback today; what we test here are the
//! mock-only hooks (failure injection, call counting) so callers can rely
//! on them when scripting deterministic test scenarios.

#![cfg(feature = "mock")]

use std::io;
use std::str::FromStr;

use ipc_vsock::MockTransport;
use tonic::transport::Uri;
use tower::Service;

#[tokio::test]
async fn fail_next_connect_returns_injected_error_and_clears() {
    let mut transport = MockTransport::new();
    transport
        .hooks
        .fail_next_connect_with(io::ErrorKind::ConnectionRefused);

    let uri = Uri::from_str("http://127.0.0.1:1").expect("static URI parses");

    let err = transport
        .call(uri.clone())
        .await
        .expect_err("hook should turn the call into an error");
    assert_eq!(err.kind(), io::ErrorKind::ConnectionRefused);

    // The hook is one-shot; calling again hits the network. We can't dial a
    // real listener from a unit test without setting one up, so just assert
    // the queued failure was consumed.
    assert!(
        transport.hooks.fail_next_connect.lock().unwrap().is_none(),
        "hook should clear after firing"
    );
}

#[tokio::test]
async fn successful_call_records_in_call_count() {
    // Spin up an ephemeral TCP listener so the mock has somewhere to land.
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
        .await
        .expect("ephemeral TCP listener");
    let port = listener.local_addr().expect("addr").port();
    tokio::spawn(async move {
        // Accept-and-drop is enough — `MockTransport::call` only needs the
        // connect to succeed.
        let _ = listener.accept().await;
    });

    let mut transport = MockTransport::new();
    let uri = Uri::from_str(&format!("http://127.0.0.1:{port}")).expect("URI");

    transport.call(uri).await.expect("connect succeeds");
    assert_eq!(transport.hooks.call_count(), 1);
}
