"""``crossdesk version`` — show host, agent, and protocol version.

Output format:

    CrossDesk host  0.1.0-dev
    Agent           1.2.3          (from last handshake; "not connected" if no session)
    Protocol        1
    Commit          abc1234        (from package metadata; "unknown" if not available)

Implementation notes:
- Host version: from ``importlib.metadata.version("crossdesk-host")`` with a
  ``dev`` fallback for editable installs that don't ship metadata.
- Agent version: calls ``ManagementService.Status()`` over the Unix socket and
  reads ``StatusFrame.agent_version``. If the daemon is unreachable, prints
  "daemon not running". If the daemon is running but no handshake has
  completed yet, prints "not connected".
- Protocol version: the ``CROSSDESK_PROTOCOL_VERSION`` constant from
  ``crossdesk_host.ipc.control`` — always "1" in the current release.
- Commit: ``importlib.metadata`` entry-point metadata if available; falls back
  to "unknown". Not set by the editable-install path.
"""

from __future__ import annotations

import argparse
import asyncio
from importlib.metadata import PackageNotFoundError, version as pkg_version
from typing import Optional

import grpc

from crossdesk_host.i18n import _
from crossdesk_host.ipc.control import CROSSDESK_PROTOCOL_VERSION
from crossdesk_host.ipc.management import mgmt_socket_path
from crossdesk_host.proto.crossdesk.v1 import mgmt_pb2, mgmt_pb2_grpc

_CONNECT_TIMEOUT_SECONDS = 2.0
_RPC_TIMEOUT_SECONDS = 5.0


def add_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    sub.add_parser("version", help="Show host, agent, and protocol version")


def run(args: argparse.Namespace) -> int:  # noqa: ARG001
    host_ver = _host_version()
    agent_ver, daemon_status = _agent_version()
    commit = _commit()

    label_w = max(len("CrossDesk host"), len("Agent"), len("Protocol"), len("Commit"))

    def row(label: str, value: str, note: str = "") -> str:
        note_part = f"  ({note})" if note else ""
        return f"  {label:<{label_w}}  {value}{note_part}"

    lines = [
        row("CrossDesk host", host_ver),
        row("Agent", agent_ver, daemon_status),
        row("Protocol", CROSSDESK_PROTOCOL_VERSION),
        row("Commit", commit),
    ]
    print("\n".join(lines))
    return 0


def _host_version() -> str:
    try:
        return pkg_version("crossdesk-host")
    except PackageNotFoundError:
        return "dev"


def _agent_version() -> tuple[str, str]:
    """Return (agent_version_string, status_note).

    status_note is empty when a live agent version is available.
    """
    sock = str(mgmt_socket_path())
    try:
        frame = asyncio.run(_fetch_status_frame(sock))
    except grpc.aio.AioRpcError:
        return "unknown", _("daemon not running")
    except asyncio.TimeoutError:
        return "unknown", _("daemon not running")

    if frame is None:
        return "unknown", _("daemon not running")

    ver = frame.agent_version
    if not ver:
        return "unknown", _("not connected")
    return ver, ""


async def _fetch_status_frame(socket: str) -> Optional[mgmt_pb2.StatusFrame]:
    target = f"unix://{socket}"
    async with grpc.aio.insecure_channel(target) as channel:
        try:
            await asyncio.wait_for(channel.channel_ready(), _CONNECT_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            return None
        stub = mgmt_pb2_grpc.ManagementServiceStub(channel)
        # Status() is a server-streaming RPC; read just the first frame.
        call = stub.Status(mgmt_pb2.Empty(), timeout=_RPC_TIMEOUT_SECONDS)
        async for frame in call:
            result: mgmt_pb2.StatusFrame = frame
            return result
    return None


def _commit() -> str:
    try:
        from importlib.metadata import metadata

        meta = metadata("crossdesk-host")
        # PackageMetadata exposes __getitem__ but not .get(); use KeyError guard.
        try:
            raw: Optional[str] = meta["X-Vcs-Revision"]
        except KeyError:
            raw = None
        commit: Optional[str] = str(raw) if raw is not None else None
        return commit if commit else "unknown"
    except (PackageNotFoundError, Exception):
        return "unknown"


__all__ = ["add_subparser", "run"]
