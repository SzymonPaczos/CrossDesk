//! Production transport. Two distinct call paths share a single
//! `RealTransport` type:
//!
//! - **Windows** (`cfg(target_os = "windows")`): When the URI scheme
//!   is `vsock`, dial **AF_VSOCK** (virtio-vsock via the virtio-win
//!   `viosock` driver) to the host's integer CID — `VMADDR_CID_HOST = 2`
//!   (DEC-0017). When the scheme is `https` (dev path), fall back to TCP.
//! - **Non-Windows**: the guest is Windows in production; the macOS /
//!   Linux compile path is the integration harness, which always speaks
//!   `https://` over TCP loopback.
//!
//! NOT AF_HYPERV: CrossDesk runs the guest under QEMU/KVM, not Hyper-V
//! (DEC-0003). The earlier AF_HYPERV/`SOCKADDR_HV`/GUID model was wrong
//! for a virtio-vsock device; see DEC-0017 for the retarget + the
//! still-pending socket FFI / Response-boxing work (hardware-gated).
//!
//! Mock counterpart lives in `super::mock`. Both implementations
//! satisfy `tower::Service<Uri, Response = TokioIo<TcpStream>>`,
//! which is the abstraction tonic 0.12 requires.

use hyper_util::rt::TokioIo;
use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};
use tokio::net::TcpStream;
use tonic::transport::Uri;
use tower::Service;

#[derive(Clone, Debug, Default)]
pub struct RealTransport;

impl Service<Uri> for RealTransport {
    type Response = TokioIo<TcpStream>;
    type Error = std::io::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>> + Send>>;

    fn poll_ready(&mut self, _cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        Poll::Ready(Ok(()))
    }

    fn call(&mut self, uri: Uri) -> Self::Future {
        let scheme = uri.scheme_str().unwrap_or("https").to_string();
        let host = uri.host().unwrap_or("127.0.0.1").to_string();
        let port = uri.port_u16().unwrap_or(50051);
        Box::pin(async move { dial(&scheme, &host, port).await })
    }
}

#[cfg(target_os = "windows")]
async fn dial(scheme: &str, host: &str, port: u16) -> std::io::Result<TokioIo<TcpStream>> {
    if scheme == "vsock" {
        return dial_af_vsock(host, port).await;
    }
    let addr = format!("{host}:{port}");
    tracing::info!(target = %addr, "real transport dialing TCP loopback");
    Ok(TokioIo::new(TcpStream::connect(addr).await?))
}

#[cfg(not(target_os = "windows"))]
async fn dial(_scheme: &str, host: &str, port: u16) -> std::io::Result<TokioIo<TcpStream>> {
    // AF_HYPERV is Windows-kernel-only. Production builds for the
    // guest target Windows; the macOS/Linux compile path exists for
    // the integration harness, which always speaks `https://` over
    // TCP loopback.
    let addr = format!("{host}:{port}");
    tracing::info!(target = %addr, "real transport dialing TCP loopback");
    Ok(TokioIo::new(TcpStream::connect(addr).await?))
}

/// Parse a `vsock://CID:port` target into `(cid, port)`.
///
/// The CID is an **integer** (AF_VSOCK) — e.g. `2` for `VMADDR_CID_HOST` —
/// NOT a GUID (that was the AF_HYPERV model retargeted in DEC-0017).
/// Defined for the Windows build (used by `dial_af_vsock`) and under
/// `test` so the parsing is exercised on any platform without a Windows
/// kernel.
#[cfg(any(target_os = "windows", test))]
fn parse_vsock_target(host: &str, port: u16) -> std::io::Result<(u32, u32)> {
    let cid: u32 = host.parse().map_err(|_| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            format!("vsock CID must be an integer, got {host:?}"),
        )
    })?;
    Ok((cid, u32::from(port)))
}

/// virtio-vsock `sockaddr_vm` (the viosock provider uses the same layout as
/// the Linux `sockaddr_vm`). windows-rs has no binding for it — it's not a
/// Microsoft struct — so we declare it. DEC-0017.
#[cfg(target_os = "windows")]
#[repr(C)]
struct SockaddrVm {
    svm_family: u16,
    svm_reserved1: u16,
    svm_port: u32,
    svm_cid: u32,
    svm_zero: [u8; 4],
}

/// AF_VSOCK connector (virtio-vsock via the viosock driver) — Windows only.
///
/// Retargeted from AF_HYPERV per DEC-0017. Creates an AF_VSOCK stream socket,
/// connects to `cid:port`, and wraps the connected SOCKET for tokio.
///
/// HARDWARE-UNVERIFIED: this compiles for the windows-gnu target but has not
/// been run against a live guest — it needs the virtio-win `viosock` driver
/// installed in the VM. The `AF_VSOCK` family value (40) is the viosock
/// convention; confirm via `WSAEnumProtocols` on the real guest if it fails.
/// AF_VSOCK is `SOCK_STREAM`, so wrapping the SOCKET in a `std::net::TcpStream`
/// is just a generic stream-socket handle (bytes flow identically); we never
/// invoke TCP-specific options on it.
#[cfg(target_os = "windows")]
async fn dial_af_vsock(host: &str, port: u16) -> std::io::Result<TokioIo<TcpStream>> {
    use std::os::windows::io::FromRawSocket;

    use windows::Win32::Networking::WinSock::{
        closesocket, connect, WSAGetLastError, WSASocketW, WSAStartup, SOCKADDR, SOCK_STREAM,
        WSADATA, WSA_FLAG_OVERLAPPED,
    };

    // viosock registers AF_VSOCK as this family value (matches Linux).
    const AF_VSOCK: u16 = 40;

    let (cid, port) = parse_vsock_target(host, port)?;

    // WSAStartup is refcounted; a per-dial call is safe.
    let mut wsadata = WSADATA::default();
    // Safety: wsadata is a valid out-param; 0x0202 requests Winsock 2.2.
    let rc = unsafe { WSAStartup(0x0202, &mut wsadata) };
    if rc != 0 {
        return Err(std::io::Error::other(format!("WSAStartup failed: {rc}")));
    }

    // Safety: standard WSASocketW call for an AF_VSOCK stream socket.
    let sock = unsafe {
        WSASocketW(
            i32::from(AF_VSOCK),
            SOCK_STREAM.0,
            0,
            None,
            0,
            WSA_FLAG_OVERLAPPED,
        )
    }
    .map_err(|e| {
        std::io::Error::new(
            std::io::ErrorKind::Unsupported,
            format!(
                "WSASocketW(AF_VSOCK) failed ({e}): is the viosock driver \
                 installed in the guest?"
            ),
        )
    })?;

    let addr = SockaddrVm {
        svm_family: AF_VSOCK,
        svm_reserved1: 0,
        svm_port: u32::from(port as u16),
        svm_cid: cid,
        svm_zero: [0; 4],
    };
    // Safety: addr is a valid #[repr(C)] sockaddr_vm; the length matches.
    let rc = unsafe {
        connect(
            sock,
            std::ptr::addr_of!(addr) as *const SOCKADDR,
            std::mem::size_of::<SockaddrVm>() as i32,
        )
    };
    if rc != 0 {
        let err = unsafe { WSAGetLastError() };
        // Safety: sock is a valid socket we opened above.
        unsafe {
            let _ = closesocket(sock);
        }
        return Err(std::io::Error::new(
            std::io::ErrorKind::ConnectionRefused,
            format!("connect AF_VSOCK cid={cid} port={port} failed (WSA {})", err.0),
        ));
    }

    // Safety: sock is a valid connected socket whose ownership we transfer
    // into the std wrapper (which closes it on drop).
    let std_stream = unsafe { std::net::TcpStream::from_raw_socket(sock.0 as _) };
    std_stream.set_nonblocking(true)?;
    let stream = TcpStream::from_std(std_stream)?;
    tracing::info!(cid, port, "AF_VSOCK connected to host");
    Ok(TokioIo::new(stream))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::str::FromStr;

    #[tokio::test]
    async fn https_uri_dials_tcp_on_any_platform() {
        // Spin up a TCP listener and verify RealTransport's `https`
        // path lands on it.
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();
        tokio::spawn(async move {
            let _ = listener.accept().await;
        });

        let mut transport = RealTransport;
        let uri = Uri::from_str(&format!("https://127.0.0.1:{port}")).unwrap();
        transport.call(uri).await.expect("https dial");
    }

    #[cfg(target_os = "windows")]
    #[tokio::test]
    async fn vsock_uri_returns_unsupported_until_implemented() {
        // Integer CID 2 = VMADDR_CID_HOST (AF_VSOCK, not a GUID — DEC-0017).
        let mut transport = RealTransport;
        let uri = Uri::from_str("vsock://2:50051").unwrap();
        let err = transport.call(uri).await.expect_err("vsock should fail");
        assert_eq!(err.kind(), std::io::ErrorKind::Unsupported);
    }

    #[test]
    fn parse_vsock_target_extracts_integer_cid_and_port() {
        let (cid, port) = parse_vsock_target("2", 50051).expect("valid CID");
        assert_eq!((cid, port), (2u32, 50051u32));
    }

    #[test]
    fn parse_vsock_target_rejects_non_integer_cid() {
        // A GUID (the old AF_HYPERV form) is no longer a valid vsock CID.
        let err = parse_vsock_target("00000000-0000-0000-0000-000000000000", 50051)
            .expect_err("GUID is not a valid integer CID");
        assert_eq!(err.kind(), std::io::ErrorKind::InvalidInput);
    }
}
