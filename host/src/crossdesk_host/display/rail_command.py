"""xfreerdp RAIL command builder.

Assembles the full argv we hand to :class:`FreeRDPInvocation.spawn_rail`.
Pure logic — no subprocess, no I/O. The reference template lives in
``docs/COMPARISON_WINAPPS.md`` §2.2 (winapps' ``bin/winapps:855-865``).

Flag rationale (each in the comment near the line that emits it):

- ``/v:`` — guest-side hostname/IP. Always ``localhost`` because we
  tunnel through gRPC over AF_VSOCK and a local stunnel-style port-forward.
- ``/u:`` / ``/p:`` — Windows credentials from
  ``~/.config/crossdesk/vm.toml``. Per-app health check (Week 6 P0,
  blocked on proto edit) will gate launches before we get here.
- ``/cert:tofu`` — Trust on first use; we manage our own PKI in
  ``infra/certs/``. RDP layer's TLS is independent of mTLS on the
  gRPC channel.
- ``/app:program:`` — the actual Windows binary to run as a RAIL app.
  ``hidef:on`` enables high-quality glyphs; ``cmd:`` carries argv
  forwarded from the Linux invocation.
- ``+auto-reconnect`` — we WANT auto-reconnect because heartbeat FSM's
  HARD_DESTROY path restarts the VM and we'd like the existing RAIL
  windows to come back when the agent does.
- ``/scale:`` — discrete 100/140/180 (FreeRDP limit). HiDPI
  auto-detect (P2 follow-up, Week 10) replaces the static value.
- ``/wm-class:`` — what the Linux compositor groups the windows under.
  Matches the app catalog name so .desktop files can target it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence


@dataclass(frozen=True)
class AppLaunchSpec:
    """Inputs for one RAIL command. The caller (rail_manager) builds
    one of these per :class:`AppLaunchRequest` it receives off the
    Control plane."""

    app_id: str
    """Stable identifier ('notepad', 'word', etc.). Drives ``/wm-class:``."""

    executable_guest_path: str
    """Windows path to the executable (e.g. ``C:\\Windows\\notepad.exe``)."""

    argv: Sequence[str] = field(default_factory=tuple)
    """Translated arguments to forward; usually a single guest-path
    file from :class:`PathTranslator`."""

    display_name: str = ""
    """Human-readable app name. Becomes the WM_CLASS instance name."""

    icon_path: Optional[str] = None
    """Optional Windows path to an icon resource. ``ExtractIconExW``
    (P1 Phase 4 follow-up) feeds this when the guest emits CREATED
    with ``icon_png`` populated."""


@dataclass(frozen=True)
class FreeRDPConnectionSpec:
    """Per-host connection knobs, separate from the app spec because
    they're configured once per session, not per launch."""

    host: str = "localhost"
    port: int = 3389
    username: str = ""
    password: str = ""
    scale: int = 100
    """FreeRDP-supported discrete scale: 100, 140, 180."""

    cert_policy: str = "tofu"
    """Trust on first use. Production deployments may swap to
    ``ignore`` during the install handshake."""


def build_rail_argv(app: AppLaunchSpec, conn: FreeRDPConnectionSpec) -> list[str]:
    """Construct the full xfreerdp RAIL argv (excluding the binary
    itself; :class:`RealFreeRDPInvocation` resolves and prepends it)."""

    if conn.scale not in (100, 140, 180):
        raise ValueError(f"FreeRDP only supports scale 100/140/180; got {conn.scale}")

    cmd_arg = " ".join(app.argv) if app.argv else ""
    program_clause = f"||{app.executable_guest_path}"
    if cmd_arg:
        program_clause += f',cmd:"{cmd_arg}"'
    if app.icon_path:
        program_clause += f",icon:{app.icon_path}"

    argv: list[str] = [
        f"/v:{conn.host}:{conn.port}",
        f"/u:{conn.username}",
        f"/p:{conn.password}",
        f"/cert:{conn.cert_policy}",
        f"/scale:{conn.scale}",
        "/dynamic-resolution",
        "+auto-reconnect",
        f"/app:program:{program_clause},hidef:on,name:{app.display_name or app.app_id}",
        f"/wm-class:{app.app_id}",
    ]
    return argv
