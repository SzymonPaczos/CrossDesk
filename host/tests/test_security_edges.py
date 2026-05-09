"""Security edge cases not covered by the existing per-validator tests.

Phase 2 SPOF (ROADMAP): a single bypass of AuthContext lets a peer
push frames that defeat mTLS' protections. These tests probe the
non-obvious corners — sequence wraparound, nonce reuse across
streams, fingerprint case folding — that a casual review might miss.
"""

from __future__ import annotations

import pytest

from crossdesk_host.ipc.auth import AuthValidator
from crossdesk_host.proto.crossdesk.v1 import common_pb2
from tests.conftest import AbortError, context_with_cert


def _auth(fp: str, nonce: bytes, sequence: int) -> common_pb2.AuthContext:
    return common_pb2.AuthContext(
        peer_cert_fingerprint=fp, stream_nonce=nonce, sequence=sequence
    )


# ---------------------------------------------------------------------------
# Concurrent streams
# ---------------------------------------------------------------------------


async def test_two_streams_with_distinct_nonces_track_independent_sequences(
    make_cert,
) -> None:
    """A peer holding two streams must have its sequence state tracked
    per-nonce; a stale nonce in one stream must NOT corrupt the other."""
    pem, fp = make_cert("guest")
    ctx = context_with_cert(pem)
    v = AuthValidator()

    await v.verify_auth_context(ctx, _auth(fp, b"stream-A", 1))
    await v.verify_auth_context(ctx, _auth(fp, b"stream-B", 1))
    await v.verify_auth_context(ctx, _auth(fp, b"stream-A", 2))
    await v.verify_auth_context(ctx, _auth(fp, b"stream-B", 2))
    # No abort — each stream advanced its own counter.


async def test_nonce_reuse_after_close_re_initialises(make_cert) -> None:
    """If a stream legitimately closes (remove_stream), a later stream
    can reuse the same nonce starting from sequence 1 again. We're
    relying on stream uniqueness from the TLS handshake nonce — the
    reuse here would only happen if the remote side mints a colliding
    nonce, which is OK as long as the previous state was cleared."""
    pem, fp = make_cert("guest")
    ctx = context_with_cert(pem)
    v = AuthValidator()
    await v.verify_auth_context(ctx, _auth(fp, b"reused", 1))
    await v.verify_auth_context(ctx, _auth(fp, b"reused", 2))
    v.remove_stream(b"reused")
    # Fresh state: 1 is again accepted.
    await v.verify_auth_context(ctx, _auth(fp, b"reused", 1))


# ---------------------------------------------------------------------------
# Sequence corner cases
# ---------------------------------------------------------------------------


async def test_zero_sequence_is_a_first_frame_legitimately(make_cert) -> None:
    """The proto field is uint64; 0 is a valid initial value. Treat it
    the same as any other first sequence number — bind nonce, expect
    next=1."""
    pem, fp = make_cert("guest")
    ctx = context_with_cert(pem)
    v = AuthValidator()
    await v.verify_auth_context(ctx, _auth(fp, b"n", 0))
    await v.verify_auth_context(ctx, _auth(fp, b"n", 1))


async def test_sequence_huge_jump_forward_rejected(make_cert) -> None:
    """A peer sending seq=1 then seq=10**18 must be rejected — the
    expected next is 2, anything else is suspicious."""
    pem, fp = make_cert("guest")
    ctx = context_with_cert(pem)
    v = AuthValidator()
    await v.verify_auth_context(ctx, _auth(fp, b"n", 1))
    with pytest.raises(AbortError):
        await v.verify_auth_context(ctx, _auth(fp, b"n", 10**18))


async def test_sequence_replay_after_advance_rejected(make_cert) -> None:
    pem, fp = make_cert("guest")
    ctx = context_with_cert(pem)
    v = AuthValidator()
    await v.verify_auth_context(ctx, _auth(fp, b"n", 5))
    await v.verify_auth_context(ctx, _auth(fp, b"n", 6))
    with pytest.raises(AbortError):
        await v.verify_auth_context(ctx, _auth(fp, b"n", 5))


async def test_sequence_state_cleared_on_first_failure(make_cert) -> None:
    """When sequence mismatch fires, the validator deletes the nonce's
    state. A retry with the original sequence must therefore work as
    a fresh stream — confirming the cleanup behaviour."""
    pem, fp = make_cert("guest")
    ctx = context_with_cert(pem)
    v = AuthValidator()
    await v.verify_auth_context(ctx, _auth(fp, b"n", 1))
    with pytest.raises(AbortError):
        await v.verify_auth_context(ctx, _auth(fp, b"n", 99))
    # State for nonce "n" is gone; sequence 1 is now a "first frame".
    await v.verify_auth_context(ctx, _auth(fp, b"n", 1))


# ---------------------------------------------------------------------------
# Fingerprint formats
# ---------------------------------------------------------------------------


async def test_uppercase_fingerprint_in_auth_context_accepted(make_cert) -> None:
    """The validator lower-cases the message-side fingerprint before
    comparison; an uppercase hex string from a careless guest must
    still match."""
    pem, fp = make_cert("guest")
    ctx = context_with_cert(pem)
    v = AuthValidator()
    await v.verify_auth_context(ctx, _auth(fp.upper(), b"n", 1))


async def test_mixed_case_fingerprint_accepted(make_cert) -> None:
    pem, fp = make_cert("guest")
    ctx = context_with_cert(pem)
    v = AuthValidator()
    # Alternate-case version of the fingerprint
    mixed = "".join(c.upper() if i % 2 == 0 else c for i, c in enumerate(fp))
    await v.verify_auth_context(ctx, _auth(mixed, b"n", 1))


async def test_short_fingerprint_rejected(make_cert) -> None:
    """A truncated fingerprint cannot match the SHA-256 of any real
    cert; the validator's lower-case-then-equal check rejects it."""
    pem, _ = make_cert("guest")
    ctx = context_with_cert(pem)
    v = AuthValidator()
    with pytest.raises(AbortError):
        await v.verify_auth_context(ctx, _auth("abcd", b"n", 1))


# ---------------------------------------------------------------------------
# Empty / missing fields
# ---------------------------------------------------------------------------


async def test_zero_byte_nonce_rejected(make_cert) -> None:
    pem, fp = make_cert("guest")
    ctx = context_with_cert(pem)
    v = AuthValidator()
    with pytest.raises(AbortError):
        await v.verify_auth_context(ctx, _auth(fp, b"", 1))
