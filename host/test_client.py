import asyncio
import logging
from pathlib import Path

import grpc
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

from crossdesk_host.proto.crossdesk.v1 import control_pb2, control_pb2_grpc
from crossdesk_host.proto.crossdesk.v1 import filesystem_pb2, filesystem_pb2_grpc
from crossdesk_host.proto.crossdesk.v1 import common_pb2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _sha256_fingerprint(cert_pem: bytes) -> str:
    """SHA-256 of the leaf cert, lowercase hex — matches what AuthValidator
    extracts from the live TLS session server-side."""
    cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
    return cert.fingerprint(hashes.SHA256()).hex().lower()


async def run() -> None:
    # Ustaw ścieżki certyfikatów z infra/
    base_dir = Path(__file__).resolve().parent.parent
    ca_cert = (base_dir / "infra/certs/pki/ca.crt").read_bytes()
    client_cert = (base_dir / "infra/certs/pki/guest.crt").read_bytes()
    client_key = (base_dir / "infra/certs/pki/guest.key").read_bytes()
    guest_fp = _sha256_fingerprint(client_cert)

    credentials = grpc.ssl_channel_credentials(
        root_certificates=ca_cert,
        private_key=client_key,
        certificate_chain=client_cert,
    )

    logger.info("Connecting to Host Server on 127.0.0.1:50051...")
    
    # Przez to, że certyfikat ma domyślnie przypisany CN, 
    # my omijamy weryfikację nazwy domeny ustawiając odpowiednie opcje w gRPC
    options = (('grpc.ssl_target_name_override', 'crossdesk-host'),)

    async with grpc.aio.secure_channel('127.0.0.1:50051', credentials, options=options) as channel:
        logger.info("Connected!")
        
        # 1. Test ControlService
        control_stub = control_pb2_grpc.ControlServiceStub(channel)
        
        nonce = b"manual-test-001!"  # 16 bytes

        async def control_stream():
            # 1. Wysyłamy ClientHello aby przejść z HANDSHAKE do READY
            yield control_pb2.ClientFrame(
                auth=common_pb2.AuthContext(
                    peer_cert_fingerprint=guest_fp,
                    stream_nonce=nonce,
                    sequence=1,
                ),
                hello=control_pb2.ClientHello(
                    host_version="manual-test-client",
                ),
            )
            # Uśpienie, żeby dać serwerowi czas na przeprocesowanie
            await asyncio.sleep(1)

            # 2. Wysyłamy zdarzenie okna
            yield control_pb2.ClientFrame(
                auth=common_pb2.AuthContext(
                    peer_cert_fingerprint=guest_fp,
                    stream_nonce=nonce,
                    sequence=2,
                ),
                rail_event=control_pb2.RailWindowEvent(
                    window_id=101,
                    kind=control_pb2.RailWindowEvent.Kind.KIND_CREATED,
                    title="Mock Parallels Word",
                ),
            )
            # Uśpienie, by utrzymać połączenie
            await asyncio.sleep(2)
            
        logger.info("Sending RailWindowEvent (App Spawn) to Host...")
        try:
            async for host_response in control_stub.OpenSession(control_stream()):
                logger.info(f"Received from Host (Control): {host_response}")
                break # Zamykamy po pierwszej odpowiedzi (jeśli jest)
        except asyncio.CancelledError:
            logger.info("Control stream cancelled gracefully.")
        except Exception as e:
            logger.error(f"Control stream closed: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
