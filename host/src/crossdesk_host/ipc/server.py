import grpc
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def create_vsock_server(ca_cert_path: Path, host_cert_path: Path, host_key_path: Path, vsock_port: int = 50051) -> grpc.aio.Server:
    """
    Tworzy asynchroniczny serwer gRPC zbindowany do AF_VSOCK i używający mTLS.
    Zakłada wsparcie dla `vsock:` przez `grpc.aio.server()`.
    W przypadku braku wsparcia z poziomu C-core, może być wymagany socat na proxy,
    ale używamy bezpośredniego bindowania.
    """
    server = grpc.aio.server()

    try:
        ca_cert = ca_cert_path.read_bytes()
        host_cert = host_cert_path.read_bytes()
        host_key = host_key_path.read_bytes()
    except Exception as e:
        logger.error(f"Failed to read mTLS credentials: {e}")
        raise

    # Konfiguracja mTLS z wymuszeniem uwierzytelnienia klienta (require_client_auth=True)
    server_credentials = grpc.ssl_server_credentials(
        [(host_key, host_cert)],
        root_certificates=ca_cert,
        require_client_auth=True
    )

    # Używamy CID: -1 (VMADDR_CID_ANY) dla serwera nasłuchującego
    # Składnia grpc dla vsock: `vsock:CID:PORT` (wiele implementacji akceptuje `vsock:-1:PORT` lub `vsock::PORT`)
    endpoint = f"vsock:-1:{vsock_port}"
    
    port = server.add_secure_port(endpoint, server_credentials)
    if port == 0:
        logger.warning(f"Failed to bind to {endpoint} natively. Fallback / proxy might be required.")
    else:
        logger.info(f"gRPC server listening securely on {endpoint}")

    return server
