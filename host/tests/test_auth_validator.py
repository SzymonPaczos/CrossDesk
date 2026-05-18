"""AuthValidator unit tests.

Phase 2 SPOF: per-frame fingerprint+nonce+sequence enforcement is the only
thing standing between a malicious peer and the control plane. Bugs here
silently bypass mTLS — every branch needs explicit coverage.
"""

from __future__ import annotations

import grpc
import pytest

from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.proto.crossdesk.v1 import common_pb2
from tests.conftest import AbortError, FakeServicerContext, context_with_cert


@pytest.fixture
def validator() -> AuthValidator:
    return AuthValidator()


def _auth(
    fp: str, nonce: bytes = b"nonce-1", sequence: int = 1
) -> common_pb2.AuthContext:
    return common_pb2.AuthContext(
        peer_cert_fingerprint=fp, stream_nonce=nonce, sequence=sequence
    )


# ---------------------------------------------------------------------------
# Fingerprint extraction
# ---------------------------------------------------------------------------


def test_extract_fingerprint_returns_lowercase_hex(
    validator: AuthValidator, make_cert
) -> None:
    pem, expected_fp = make_cert("guest")
    ctx = context_with_cert(pem)
    assert validator.extract_peer_fingerprint(ctx) == expected_fp


def test_extract_fingerprint_returns_none_when_no_auth_context(
    validator: AuthValidator,
) -> None:
    ctx = FakeServicerContext(auth_props=None)
    assert validator.extract_peer_fingerprint(ctx) is None


def test_extract_fingerprint_returns_none_when_no_cert(
    validator: AuthValidator,
) -> None:
    ctx = FakeServicerContext(auth_props={"some_other_key": [b"x"]})
    assert validator.extract_peer_fingerprint(ctx) is None


def test_extract_fingerprint_handles_malformed_pem(
    validator: AuthValidator,
) -> None:
    ctx = context_with_cert(b"-----BEGIN CERT-----\nnot a real PEM\n-----END CERT-----")
    assert validator.extract_peer_fingerprint(ctx) is None


# ---------------------------------------------------------------------------
# verify_auth_context — happy path & sequence bookkeeping
# ---------------------------------------------------------------------------


async def test_first_frame_initializes_sequence_state(
    validator: AuthValidator, make_cert
) -> None:
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    await validator.verify_auth_context(ctx, _auth(fp, b"nonceA", sequence=5))
    # Internal state primes itself to expect seq+1 next:
    assert validator._active_streams[b"nonceA"] == 6


async def test_consecutive_frames_with_monotonic_sequence_pass(
    validator: AuthValidator, make_cert
) -> None:
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    await validator.verify_auth_context(ctx, _auth(fp, b"n", sequence=1))
    await validator.verify_auth_context(ctx, _auth(fp, b"n", sequence=2))
    await validator.verify_auth_context(ctx, _auth(fp, b"n", sequence=3))
    assert validator._active_streams[b"n"] == 4


async def test_fingerprint_match_is_case_insensitive(
    validator: AuthValidator, make_cert
) -> None:
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    await validator.verify_auth_context(
        ctx, _auth(fp.upper(), b"nU", sequence=1)
    )  # uppercase → must still match


# ---------------------------------------------------------------------------
# verify_auth_context — rejection paths
# ---------------------------------------------------------------------------


async def test_missing_tls_cert_aborts_unauthenticated(
    validator: AuthValidator,
) -> None:
    ctx = FakeServicerContext(auth_props={})
    with pytest.raises(AbortError) as exc:
        await validator.verify_auth_context(ctx, _auth("deadbeef"))
    assert exc.value.code == grpc.StatusCode.UNAUTHENTICATED


async def test_fingerprint_mismatch_aborts_unauthenticated(
    validator: AuthValidator, make_cert
) -> None:
    pem, real_fp = make_cert()
    ctx = context_with_cert(pem)
    fake_fp = "0" * 64
    with pytest.raises(AbortError) as exc:
        await validator.verify_auth_context(ctx, _auth(fake_fp))
    assert exc.value.code == grpc.StatusCode.UNAUTHENTICATED
    assert "mismatch" in exc.value.detail.lower()


async def test_missing_nonce_aborts_invalid_argument(
    validator: AuthValidator, make_cert
) -> None:
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    with pytest.raises(AbortError) as exc:
        await validator.verify_auth_context(ctx, _auth(fp, nonce=b"", sequence=1))
    assert exc.value.code == grpc.StatusCode.INVALID_ARGUMENT


async def test_sequence_regression_aborts_and_clears_stream_state(
    validator: AuthValidator, make_cert
) -> None:
    """Replay protection: receiving the same seq twice must terminate the stream
    AND wipe its bookkeeping (so a fresh nonce-reuse attempt looks like first
    frame again rather than chaining off the corrupted state)."""
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    await validator.verify_auth_context(ctx, _auth(fp, b"replay", sequence=10))
    # State now expects seq=11. Replaying seq=10 must be rejected:
    with pytest.raises(AbortError) as exc:
        await validator.verify_auth_context(ctx, _auth(fp, b"replay", sequence=10))
    assert exc.value.code == grpc.StatusCode.ABORTED
    assert b"replay" not in validator._active_streams


async def test_sequence_skip_forward_is_also_rejected(
    validator: AuthValidator, make_cert
) -> None:
    """Strict monotonic+1 — even forward gaps must be rejected (defense against
    nonce-recycling reorder attacks)."""
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    await validator.verify_auth_context(ctx, _auth(fp, b"skip", sequence=1))
    # Expected next: 2. Sending 5 must abort.
    with pytest.raises(AbortError) as exc:
        await validator.verify_auth_context(ctx, _auth(fp, b"skip", sequence=5))
    assert exc.value.code == grpc.StatusCode.ABORTED


# ---------------------------------------------------------------------------
# Stream lifecycle
# ---------------------------------------------------------------------------


async def test_remove_stream_cleans_state(validator: AuthValidator, make_cert) -> None:
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    await validator.verify_auth_context(ctx, _auth(fp, b"clean", sequence=1))
    assert b"clean" in validator._active_streams
    validator.remove_stream(b"clean")
    assert b"clean" not in validator._active_streams


def test_remove_stream_for_unknown_nonce_is_silent(
    validator: AuthValidator,
) -> None:
    validator.remove_stream(b"never-existed")  # no exception


async def test_concurrent_streams_with_distinct_nonces_dont_interfere(
    validator: AuthValidator, make_cert
) -> None:
    pem, fp = make_cert()
    ctx = context_with_cert(pem)
    await validator.verify_auth_context(ctx, _auth(fp, b"s1", sequence=1))
    await validator.verify_auth_context(ctx, _auth(fp, b"s2", sequence=100))
    await validator.verify_auth_context(ctx, _auth(fp, b"s1", sequence=2))
    await validator.verify_auth_context(ctx, _auth(fp, b"s2", sequence=101))
    assert validator._active_streams == {b"s1": 3, b"s2": 102}
