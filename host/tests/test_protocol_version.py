"""Tests for protocol_version wiring (FOLLOWUPS: Versioning P0).

Covers:
1. StatusFrame proto has agent_version field (field 7).
2. ClientHello proto has protocol_version field (field 4).
3. ControlServiceServicer stamps CROSSDESK_PROTOCOL_VERSION in ServerAccept.
4. ControlServiceServicer warns + rejects when ClientHello.protocol_version
   major digit differs from CROSSDESK_PROTOCOL_VERSION.
5. on_agent_version callback fires with the correct version on handshake.
6. MgmtState.agent_version appears in StatusFrame via ManagementServiceServicer.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from crossdesk_host.ipc.control import (
    CROSSDESK_PROTOCOL_VERSION,
    ControlServiceServicer,
)
from crossdesk_host.ipc.management import ManagementServiceServicer, MgmtState
from crossdesk_host.libvirt_ctl.mock import LibvirtControllerMock
from crossdesk_host.proto.crossdesk.v1 import common_pb2, control_pb2, mgmt_pb2
from tests.conftest import AbortError, FakeServicerContext


# ---------------------------------------------------------------------------
# Proto field presence
# ---------------------------------------------------------------------------


def test_status_frame_has_agent_version_field() -> None:
    """StatusFrame proto carries agent_version (field 7)."""
    frame = mgmt_pb2.StatusFrame(agent_version="0.9.1")
    assert frame.agent_version == "0.9.1"


def test_protocol_version_in_clienthello() -> None:
    """ClientHello proto carries protocol_version (field 4)."""
    hello = control_pb2.ClientHello(protocol_version="1")
    assert hello.protocol_version == "1"


def test_protocol_version_in_serveraccept() -> None:
    """ServerAccept proto carries protocol_version (field 4)."""
    accept = control_pb2.ServerAccept(protocol_version="1")
    assert accept.protocol_version == "1"


# ---------------------------------------------------------------------------
# Helpers shared by servicer tests
# ---------------------------------------------------------------------------


def _auth() -> common_pb2.AuthContext:
    return common_pb2.AuthContext(
        peer_cert_fingerprint="ff" * 32, stream_nonce=b"n", sequence=1
    )


def _hello(protocol_version: str = "1") -> control_pb2.ClientFrame:
    return control_pb2.ClientFrame(
        auth=_auth(),
        hello=control_pb2.ClientHello(
            host_version="v0.1.0",
            supported_features=["rail.v1"],
            protocol_version=protocol_version,
        ),
    )


async def _async_iter(
    frames: List[control_pb2.ClientFrame],
) -> AsyncIterator[control_pb2.ClientFrame]:
    for f in frames:
        yield f


async def _drive(
    frames: List[control_pb2.ClientFrame],
    **kwargs: object,
) -> tuple[list[control_pb2.ServerFrame], FakeServicerContext]:
    auth_validator = MagicMock()
    auth_validator.verify_auth_context = AsyncMock()
    servicer = ControlServiceServicer(auth_validator, **kwargs)  # type: ignore[arg-type]
    ctx = FakeServicerContext()
    out: list[control_pb2.ServerFrame] = []
    try:
        async for sf in servicer.OpenSession(_async_iter(frames), ctx):
            out.append(sf)
    except AbortError:
        pass
    return out, ctx


# ---------------------------------------------------------------------------
# ServerAccept stamps protocol_version
# ---------------------------------------------------------------------------


async def test_clienthello_stamps_protocol_version() -> None:
    """ServerAccept carries CROSSDESK_PROTOCOL_VERSION after a successful handshake."""
    out, _ = await _drive([_hello()])
    assert len(out) == 1
    assert out[0].WhichOneof("payload") == "accept"
    assert out[0].accept.protocol_version == CROSSDESK_PROTOCOL_VERSION


# ---------------------------------------------------------------------------
# Major mismatch rejection
# ---------------------------------------------------------------------------


async def test_serveraccept_major_mismatch_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ClientHello with a different major digit triggers WARNING + abort."""
    with caplog.at_level(logging.WARNING, logger="crossdesk_host.ipc.control"):
        out, ctx = await _drive([_hello(protocol_version="99")])

    # The stream is aborted — no ServerAccept should be yielded.
    assert ctx.aborted
    warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("protocol major mismatch" in r.message for r in warning_records)


async def test_empty_protocol_version_passes_without_rejection() -> None:
    """A ClientHello with an empty protocol_version (old agent) is still accepted."""
    out, ctx = await _drive([_hello(protocol_version="")])
    assert not ctx.aborted
    assert len(out) == 1
    assert out[0].WhichOneof("payload") == "accept"


# ---------------------------------------------------------------------------
# on_agent_version callback
# ---------------------------------------------------------------------------


async def test_on_agent_version_called_on_successful_handshake() -> None:
    """on_agent_version callback fires with the guest's version string."""
    captured: list[str] = []
    await _drive([_hello()], on_agent_version=captured.append)
    assert captured == ["v0.1.0"]


async def test_on_agent_version_not_called_on_rejected_handshake() -> None:
    """on_agent_version must NOT fire when the handshake is rejected."""
    captured: list[str] = []
    out, ctx = await _drive(
        [_hello(protocol_version="99")],
        on_agent_version=captured.append,
    )
    assert ctx.aborted
    assert captured == []


# ---------------------------------------------------------------------------
# MgmtState.agent_version surfaced in StatusFrame
# ---------------------------------------------------------------------------


async def test_status_frame_includes_agent_version_from_state() -> None:
    """ManagementServiceServicer embeds MgmtState.agent_version in every StatusFrame."""
    ctx = MagicMock()
    ctx.cancelled.return_value = False

    state = MgmtState(agent_version="1.2.3")
    libvirt = LibvirtControllerMock()
    servicer = ManagementServiceServicer(state, libvirt)

    frames: list[mgmt_pb2.StatusFrame] = []
    async for frame in servicer.Status(mgmt_pb2.Empty(), ctx):
        frames.append(frame)
        break  # only need the first frame

    assert frames[0].agent_version == "1.2.3"


async def test_status_frame_agent_version_empty_before_handshake() -> None:
    """agent_version is empty string when no handshake has occurred."""
    ctx = MagicMock()
    ctx.cancelled.return_value = False

    state = MgmtState()  # agent_version defaults to ""
    libvirt = LibvirtControllerMock()
    servicer = ManagementServiceServicer(state, libvirt)

    frames: list[mgmt_pb2.StatusFrame] = []
    async for frame in servicer.Status(mgmt_pb2.Empty(), ctx):
        frames.append(frame)
        break

    assert frames[0].agent_version == ""
