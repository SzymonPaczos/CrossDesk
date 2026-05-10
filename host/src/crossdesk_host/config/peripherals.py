"""Typed configuration schema for peripheral redirection.

Validates ``~/.config/crossdesk/peripherals.toml`` at startup and maps
each enabled peripheral to the FreeRDP flags and libvirt XML adjustments
required at VM start.

Default stance: **opt-in for everything that crosses the trust boundary**.
Audio defaults to playback-only; clipboard defaults to text-only; all
other peripherals default off.  The user must consciously enable each
one, and the trust implication is documented in ``docs/PERIPHERALS.md``
and ``docs/THREAT_MODEL.md``.

Why a separate file rather than expanding the ``PeripheralsConfig`` that
lives in ``crossdesk_host.config``?  The top-level config carries
operator-facing infrastructure knobs (ports, cert paths, FSM timing);
it embeds a *minimal* ``PeripheralsConfig`` for the fields that appear
in ``~/.config/crossdesk/config.toml``.  This module is the richer
peripheral-specific schema, loaded from its own ``peripherals.toml``
sidecar, and is the source of truth for the FreeRDP flag mapping logic.
They coexist without conflict: the top-level config carries the small
intersection of fields that the daemon core needs; this module carries
the full schema.

FreeRDP flag syntax targets FreeRDP 3.x (the version in scope per
``docs/TECH_STACK.md``).  Flag names are verified against the FreeRDP 3.x
``--help`` output and the upstream source at
``client/common/cmdline.c``.  Key references:

- ``/sound:sys:<backend>``          — audio playback (pipewire / pulse / sdl)
- ``/microphone:sys:<backend>``     — audio capture (pulse / pipewire)
- ``+clipboard``                    — enable clipboard channel
- ``/clipboard-redirect-type:text`` — restrict to text formats (3.x only)
- ``/printer``                      — redirect all CUPS printers
- ``/printer:<name>``               — redirect named printer
- ``/smartcard``                    — PCSC-Lite passthrough
- ``/usb:id,<vendorid>:<productid>`` — USB device by vendor:product
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

if sys.version_info >= (3, 11):
    import tomllib as _tomllib  # type: ignore[import-not-found,unused-ignore]
else:  # pragma: no cover — Python <3.11 fallback
    import tomli as _tomllib  # type: ignore[import-not-found]


_FROZEN = ConfigDict(frozen=True, extra="forbid")

_USB_PATTERN = re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{4}$")
"""Vendor:product ID pattern for USB allow-list entries.

Format: ``<vendor_id>:<product_id>`` where each ID is exactly four
hexadecimal digits, e.g. ``0403:6001`` (FTDI USB-serial converter).
"""

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class PeripheralsConfig(BaseModel):
    """Peripheral redirection policy for a CrossDesk VM.

    Loaded from ``~/.config/crossdesk/peripherals.toml`` (or the path
    passed to :func:`load_peripherals_config`).  All fields have safe
    defaults so a missing file still produces a working, minimal config.

    Call :meth:`to_freerdp_flags` to get the ``freerdp`` command-line
    flags that correspond to the enabled options, and
    :meth:`to_libvirt_xml_fragments` to get the ``<hostdev>`` XML blocks
    for USB passthrough that need to be injected into the libvirt domain
    XML at VM start.

    Example ``peripherals.toml``::

        audio_enabled = true
        audio_mode = "bidirectional"
        clipboard_mode = "rich"
        usb_devices = ["0403:6001", "046d:c534"]
    """

    model_config = _FROZEN

    # --- Audio ---------------------------------------------------------------

    audio_enabled: bool = True
    """Enable audio forwarding.  Playback-only by default; see
    ``audio_mode`` to add microphone capture."""

    audio_mode: Literal["playback", "bidirectional"] = "playback"
    """``playback`` — guest-to-host only (speakers); ``bidirectional`` —
    adds microphone capture (host mic input to guest).  Bidirectional
    implies ``microphone_enabled = True``; the explicit field is still
    honoured when ``audio_enabled = False``."""

    # --- Clipboard -----------------------------------------------------------

    clipboard_mode: Literal["off", "text-only", "rich"] = "text-only"
    """``off`` — no clipboard sharing; ``text-only`` — plain text both
    directions (default, safe); ``rich`` — HTML, RTF, images, file
    references (FORMAT_FILELIST) with path translation."""

    # --- Microphone ----------------------------------------------------------

    microphone_enabled: bool = False
    """Enable microphone capture independently of ``audio_mode``.  Set
    this to ``True`` when ``audio_enabled = False`` but mic is still
    wanted (rare; e.g. push-to-talk with silent playback)."""

    # --- Printer -------------------------------------------------------------

    printer_mode: Literal["off", "auto", "named"] = "off"
    """``off`` — no printer redirection; ``auto`` — forward all CUPS
    printers; ``named`` — forward only the printer named in
    ``printer_name``."""

    printer_name: str = ""
    """Printer name forwarded when ``printer_mode = "named"``.  Ignored
    for other modes.  Must be a valid CUPS queue name (no validation
    beyond non-empty when ``printer_mode = "named"``)."""

    # --- Smart card ----------------------------------------------------------

    smartcard_enabled: bool = False
    """Enable PCSC-Lite smart-card passthrough.  Requires ``pcscd`` +
    ``libccid`` on the host; see ``docs/PERIPHERALS.md``."""

    # --- USB devices ---------------------------------------------------------

    usb_devices: List[str] = Field(default_factory=list)
    """Vendor:product allow-list for USB passthrough, e.g.
    ``["0403:6001", "046d:c534"]``.  Each entry must match
    ``<4-hex>:<4-hex>``; validated at parse time."""

    # --- Validators ----------------------------------------------------------

    @field_validator("usb_devices", mode="before")
    @classmethod
    def _usb_entries_valid(cls, v: object) -> object:
        if not isinstance(v, list):
            raise ValueError(f"usb_devices must be a list, got {type(v).__name__}")
        for entry in v:
            if not isinstance(entry, str) or not _USB_PATTERN.match(entry):
                raise ValueError(
                    f"usb_devices entries must be 4-hex:4-hex (vendor:product), "
                    f"got {entry!r}"
                )
        return v

    def model_post_init(self, __context: object) -> None:
        # Cross-field validation: printer_name must be non-empty when mode is
        # "named".  Cannot use @field_validator for this because both fields
        # must be resolved before the check is meaningful.
        if self.printer_mode == "named" and not self.printer_name.strip():
            raise ValueError(
                'printer_name must be non-empty when printer_mode = "named"'
            )

    # --- FreeRDP flag mapping ------------------------------------------------

    def to_freerdp_flags(self) -> List[str]:
        """Return the FreeRDP 3.x command-line flags for enabled peripherals.

        The list is ready to be appended to the ``freerdp`` (or ``xfreerdp``)
        argument list.  Order is deterministic (same order every call) so
        tests can assert on exact flag presence.

        Mapping:

        - Audio playback: ``/sound:sys:pipewire``
        - Microphone (bidirectional or explicit): ``/microphone:sys:pulse``
        - Clipboard text-only: ``+clipboard /clipboard-redirect-type:text``
        - Clipboard rich: ``+clipboard``
        - Printer auto: ``/printer``
        - Printer named: ``/printer:<name>``
        - Smart card: ``/smartcard``
        - USB device: ``/usb:id,<vendor>:<product>`` (one per device)
        """
        flags: List[str] = []

        # Audio
        if self.audio_enabled:
            flags.append("/sound:sys:pipewire")
        if self.audio_enabled and self.audio_mode == "bidirectional":
            flags.append("/microphone:sys:pulse")
        elif self.microphone_enabled:
            # Explicit mic without bidirectional audio (rare but valid).
            flags.append("/microphone:sys:pulse")

        # Clipboard
        if self.clipboard_mode == "text-only":
            flags.append("+clipboard")
            flags.append("/clipboard-redirect-type:text")
        elif self.clipboard_mode == "rich":
            flags.append("+clipboard")

        # Printer
        if self.printer_mode == "auto":
            flags.append("/printer")
        elif self.printer_mode == "named":
            flags.append(f"/printer:{self.printer_name}")

        # Smart card
        if self.smartcard_enabled:
            flags.append("/smartcard")

        # USB devices
        for device in self.usb_devices:
            flags.append(f"/usb:id,{device}")

        return flags

    # --- libvirt XML mapping -------------------------------------------------

    def to_libvirt_xml_fragments(self) -> List[str]:
        """Return libvirt ``<hostdev>`` XML blocks for USB passthrough.

        Each fragment is a self-contained ``<hostdev>`` element suitable for
        insertion into the ``<devices>`` section of a libvirt domain XML.
        Returns an empty list when ``usb_devices`` is empty.

        The ``<address>`` element is omitted intentionally: libvirt assigns
        a guest USB port automatically when the address is absent, which is
        correct for dynamic attach/detach via ``virsh attach-device``.

        Example output for ``usb_devices = ["0403:6001"]``::

            <hostdev mode="subsystem" type="usb" managed="yes">
              <source>
                <vendor id="0x0403"/>
                <product id="0x6001"/>
              </source>
            </hostdev>
        """
        fragments: List[str] = []
        for device in self.usb_devices:
            vendor, product = device.split(":")
            fragment = (
                '<hostdev mode="subsystem" type="usb" managed="yes">\n'
                "  <source>\n"
                f'    <vendor id="0x{vendor.lower()}"/>\n'
                f'    <product id="0x{product.lower()}"/>\n'
                "  </source>\n"
                "</hostdev>"
            )
            fragments.append(fragment)
        return fragments


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _default_peripherals_path() -> Path:
    """``~/.config/crossdesk/peripherals.toml`` — resolved at call time.

    Resolved lazily (not at import) so tests that monkeypatch ``HOME``
    see the redirected path.
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config) if xdg_config else Path.home() / ".config"
    return base / "crossdesk" / "peripherals.toml"


def load_peripherals_config(path: Path | None = None) -> PeripheralsConfig:
    """Load and validate the peripherals config.

    Discovery order:

    1. ``path`` argument, if provided.
    2. ``~/.config/crossdesk/peripherals.toml`` (XDG-aware; honours
       ``$XDG_CONFIG_HOME``).

    If the resolved file does not exist, an all-defaults
    :class:`PeripheralsConfig` is returned — a bare install with no
    ``peripherals.toml`` gets the safe defaults (playback audio,
    text-only clipboard, everything else off).

    Raises:
        pydantic.ValidationError: TOML parses but a field violates its
            validator (e.g. malformed USB ID, invalid mode string).
        tomllib.TOMLDecodeError: the file exists but contains invalid TOML.
    """
    resolved = path if path is not None else _default_peripherals_path()
    if not resolved.exists():
        return PeripheralsConfig()
    with resolved.open("rb") as fh:
        raw = _tomllib.load(fh)
    return PeripheralsConfig.model_validate(raw)
