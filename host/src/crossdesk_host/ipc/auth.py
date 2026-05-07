import logging
from typing import Dict, Optional

import grpc
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

from crossdesk_host.observability.metrics import REGISTRY, MetricNames
from crossdesk_host.proto.crossdesk.v1 import common_pb2

logger = logging.getLogger(__name__)
_REJECTIONS = REGISTRY.counter(MetricNames.AUTH_CONTEXT_REJECTIONS_TOTAL)


class AuthValidator:
    """Per-frame AuthContext validator: pins TLS fingerprint, enforces monotonic sequence per stream nonce."""

    def __init__(self) -> None:
        self._active_streams: Dict[bytes, int] = {}

    def extract_peer_fingerprint(self, context: grpc.ServicerContext) -> Optional[str]:
        auth_context = context.auth_context()
        if not auth_context:
            return None

        peer_certs = auth_context.get("x509_pem_cert")
        if not peer_certs:
            return None

        try:
            cert_pem = peer_certs[0]
            cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
            fingerprint = cert.fingerprint(hashes.SHA256())
            return fingerprint.hex().lower()
        except Exception as e:
            logger.error(f"Failed to parse peer certificate: {e}")
            return None

    async def verify_auth_context(
        self,
        context: grpc.aio.ServicerContext,
        request_auth_context: common_pb2.AuthContext,
    ) -> None:
        """
        Async: grpc.aio.ServicerContext.abort is a coroutine — the whole call
        chain must be awaitable, otherwise abort() returns an unawaited
        coroutine and the offending request silently passes through.
        """
        if not request_auth_context:
            _REJECTIONS.inc()
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing AuthContext")

        # 1. Weryfikacja Fingerprintu
        tls_fingerprint = self.extract_peer_fingerprint(context)
        if not tls_fingerprint:
            _REJECTIONS.inc()
            await context.abort(
                grpc.StatusCode.UNAUTHENTICATED,
                "No valid mTLS client certificate found",
            )

        if tls_fingerprint != request_auth_context.peer_cert_fingerprint.lower():
            logger.error(
                f"CID Collision/Spoofing detected! TLS: {tls_fingerprint}, "
                f"Msg: {request_auth_context.peer_cert_fingerprint}"
            )
            _REJECTIONS.inc()
            await context.abort(
                grpc.StatusCode.UNAUTHENTICATED,
                "Peer certificate fingerprint mismatch",
            )

        # 2. Weryfikacja Nonce i Sequence
        nonce = request_auth_context.stream_nonce
        seq = request_auth_context.sequence

        if not nonce:
            _REJECTIONS.inc()
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "Missing stream_nonce in AuthContext",
            )

        expected_seq = self._active_streams.get(nonce)
        if expected_seq is None:
            self._active_streams[nonce] = seq + 1
        else:
            if seq != expected_seq:
                logger.error(
                    f"Replay attack / Sequence mismatch! Expected: {expected_seq}, Got: {seq}"
                )
                del self._active_streams[nonce]
                _REJECTIONS.inc()
                await context.abort(
                    grpc.StatusCode.ABORTED,
                    "Sequence mismatch (possible replay attack)",
                )

            self._active_streams[nonce] = seq + 1

    def remove_stream(self, nonce: bytes) -> None:
        self._active_streams.pop(nonce, None)
