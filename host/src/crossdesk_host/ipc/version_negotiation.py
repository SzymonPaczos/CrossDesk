"""ClientHello / ServerAccept version compatibility (DEC-0007).

Compatibility window: same major, |minorH - minorG| <= 1 ("N-1 minor").
A client/server pair within that window must complete the handshake;
anything outside is rejected with a structured AuthFailure naming the
exact code so the install pipeline can surface a meaningful message.

Feature negotiation: the server intersects its own advertised feature
set with the client's ``supported_features``. The result lands in
``ServerAccept.negotiated_features`` so each side knows what's safe
to reach for.

Domain UUID: the client (host) sends ``host_domain_uuid`` from libvirt;
the guest echoes its own SMBIOS-injected UUID in ``guest_smbios_uuid``
so a live-migration / host-swap is detected. Mismatch is non-fatal at
this layer (the FSM will fail-close anyway), but we log it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Set

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


class VersionParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, raw: str) -> "ParsedVersion":
        m = _SEMVER_RE.match(raw.strip())
        if m is None:
            raise VersionParseError(f"not a semver: {raw!r}")
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))


@dataclass(frozen=True)
class CompatibilityResult:
    accepted: bool
    reason: str = ""


def is_compatible(host_raw: str, guest_raw: str) -> CompatibilityResult:
    try:
        h = ParsedVersion.parse(host_raw)
        g = ParsedVersion.parse(guest_raw)
    except VersionParseError as exc:
        return CompatibilityResult(accepted=False, reason=str(exc))
    if h.major != g.major:
        return CompatibilityResult(
            accepted=False,
            reason=f"major mismatch: host {h.major} vs guest {g.major}",
        )
    if abs(h.minor - g.minor) > 1:
        return CompatibilityResult(
            accepted=False,
            reason=(f"minor outside N-1 window: host {h.minor} vs guest {g.minor}"),
        )
    return CompatibilityResult(accepted=True)


def negotiate_features(
    host_supported: Iterable[str], client_advertised: Iterable[str]
) -> List[str]:
    host_set: Set[str] = set(host_supported)
    return sorted(host_set.intersection(client_advertised))
