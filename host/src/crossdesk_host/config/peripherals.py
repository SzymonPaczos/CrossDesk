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

    audio_enabled: bool = False
    """Enable audio forwarding (``/sound``).  OFF by default: adding the audio
    channel to the RAIL/RemoteApp connection caused FreeRDP 3.24
    ``ERRCONNECT_POST_CONNECT_FAILED`` in live testing (observed under the
    console-agent harness, where ``crossdesk launch`` reconnects to the
    session the agent already holds — plausibly a session-takeover channel
    renegotiation issue rather than a product defect). Until it's validated
    against a production NT-service agent (which holds no RDP session), audio
    is opt-in so the default launch always renders. Playback-only when
    enabled; see ``audio_mode`` for microphone."""

    audio_mode: Literal["playback", "bidirectional"] = "playback"
    """``playback`` — guest-to-host only (speakers); ``bidirectional`` —
    adds microphone capture (host mic input to guest).  Bidirectional
    implies ``microphone_enabled = True``; the explicit field is still
    honoured when ``audio_enabled = False``."""

    # --- Clipboard -----------------------------------------------------------

    clipboard_mode: Literal["off", "text-only", "rich"] = "off"
    """``off`` (default) — no clipboard sharing; ``text-only`` — plain text
    both directions; ``rich`` — HTML, RTF, images, file references
    (FORMAT_FILELIST) with path translation.

    OFF by default for the same reason as ``audio_enabled``: enabling
    ``+clipboard`` on the RAIL connection caused FreeRDP 3.24
    ``ERRCONNECT_POST_CONNECT_FAILED`` (and a ``cliprdr_file_context_uninit``
    SIGSEGV during the failed-connect cleanup) in the console-agent test
    harness. Opt-in until validated against a production NT-service agent."""

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

    # --- Shared folder -------------------------------------------------------

    shared_folder_enabled: bool = False
    """Expose a host directory to the guest as a redirected drive
    (``\\\\tsclient\\<shared_folder_name>``) so a Windows app can open and
    save files the user reaches from Linux, and so the user can drop an
    installer into it and run it inside the guest.

    OPT-IN (OFF by default).  :attr:`shared_folder_scope` chooses *what* is
    exposed once enabled; the owner-confirmed default (2026-06-29) is the whole
    ``$HOME`` R/W for maximum usefulness — a deliberate widening from the
    earlier single-scoped-folder stance (which rejected the static
    ``\\\\tsclient\\home`` mount in ``docs/COMPARISON_WINAPPS.md`` §7 /
    DEC-META-005).

    SECURITY: the ``home`` scope gives the Windows guest R/W to *everything*
    under ``$HOME`` — including ``~/.ssh`` and ``~/.config/crossdesk`` (the
    host mTLS private key and the VM password). A compromised Windows app
    could read or overwrite them. This is the owner's accepted trade-off for
    the default; set ``shared_folder_scope = "documents"`` (or ``custom``) to
    keep those out of the guest. The matching ``docs/THREAT_MODEL.md`` /
    DECISIONS rows are drafted for owner sign-off (``.claude/needs-owner.md``)."""

    shared_folder_scope: Literal["home", "documents", "custom"] = "home"
    """What the shared folder exposes once :attr:`shared_folder_enabled`:

    - ``home`` (default) — the whole ``$HOME`` R/W.  The Windows app's
      Open/Save dialog reaches anything the user has, no hunting for a
      special folder.  Owner-confirmed default (2026-06-29). Exposes secrets
      under ``$HOME`` to the guest — see :attr:`shared_folder_enabled`.
    - ``documents`` — only ``~/Documents`` R/W (covers the common
      open-here / save-here path without exposing the rest of ``$HOME``).
    - ``custom`` — the explicit :attr:`shared_folder_path` directory."""

    shared_folder_path: str = "~/CrossDesk-Shared"
    """Host directory shared when :attr:`shared_folder_scope` = ``custom``.
    Tilde- and env-expanded; created on demand by the launcher.  Ignored for
    the ``home`` / ``documents`` scopes.

    Defaults to ``~/CrossDesk-Shared`` — NOT ``~/CrossDesk``: on a dev
    checkout that path is the git repository root, and exposing the source
    tree read-write to the guest would be a footgun."""

    shared_folder_name: str = "CrossDesk"
    """Redirect name — the guest sees the share as
    ``\\\\tsclient\\<shared_folder_name>``."""

    shared_folder_drive_letter: str = "Z"
    """Drive letter the guest logon step maps the share to (``net use
    <letter>: \\\\tsclient\\<name>``).

    Why a drive letter at all when the rdpdr redirect already exposes
    ``\\\\tsclient\\<name>``?  Because Windows does **not** honour a UNC
    path as a process working directory — a RemoteApp launched with
    ``workdir:\\\\tsclient\\CrossDesk`` silently falls back to
    ``C:\\Windows\\System32`` (verified live 2026-06-09).  A drive letter
    *is* a valid CWD, so the launcher points the app's working directory
    at ``<letter>:\\`` instead, and the Save/Open dialog defaults to the
    Linux-visible folder.

    Constrained to ``D``–``Z``: ``A``/``B`` are legacy floppy slots and
    ``C`` is the system drive."""

    shared_folder_redirect_documents: bool = True
    """Point the guest user's *Documents* shell folder at the mapped
    drive so apps that default their Save dialog to Documents land on the
    Linux-visible folder.  Effective only when ``shared_folder_enabled``;
    the guest logon step restores the default Documents path whenever the
    share is absent so the profile never points at a dead drive."""

    shared_folder_redirect_desktop: bool = False
    """Also point the guest user's *Desktop* at the mapped drive.  Off by
    default: redirecting the Desktop is more visually invasive (every icon
    on the Windows desktop becomes the Linux folder's contents) than
    redirecting Documents, so it's opt-in."""

    # --- Validators ----------------------------------------------------------

    @field_validator("shared_folder_drive_letter")
    @classmethod
    def _drive_letter_valid(cls, v: str) -> str:
        up = v.strip().upper()
        if not re.fullmatch(r"[D-Z]", up):
            raise ValueError(
                "shared_folder_drive_letter must be a single letter D-Z "
                "(A/B are legacy floppy slots, C is the system drive), "
                f"got {v!r}"
            )
        return up

    @field_validator("shared_folder_name")
    @classmethod
    def _share_name_safe(cls, v: str) -> str:
        # The name becomes a UNC path component the guest navigates to; keep
        # it to a simple token so it can't smuggle path separators.
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", v):
            raise ValueError(
                f"shared_folder_name must be 1-32 chars of [A-Za-z0-9_-], got {v!r}"
            )
        return v

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

    def model_post_init(self, _context: object) -> None:
        # Single underscore (not dunder) so vulture's "unused variable"
        # detector accepts the intentional ignore. Pydantic's introspection
        # binds to position, not name, so the rename is safe.
        # Cross-field validation: printer_name must be non-empty when mode
        # is "named".  Cannot use @field_validator for this because both
        # fields must be resolved before the check is meaningful.
        if self.printer_mode == "named" and not self.printer_name.strip():
            raise ValueError(
                'printer_name must be non-empty when printer_mode = "named"'
            )
        # Same cross-field shape for the shared folder, but only for the
        # ``custom`` scope: an empty/whitespace path there is a footgun — it
        # expands to "" (so ``to_freerdp_flags`` emits a malformed
        # ``/drive:<name>,`` with no host path) and ``Path("").mkdir`` silently
        # resolves to the daemon's CWD, defeating the launcher's "only mount a
        # real directory" guard. The ``home``/``documents`` scopes derive the
        # path from ``$HOME`` and ignore ``shared_folder_path`` entirely.
        if (
            self.shared_folder_enabled
            and self.shared_folder_scope == "custom"
            and not self.shared_folder_path.strip()
        ):
            raise ValueError(
                "shared_folder_path must be non-empty when shared_folder_enabled "
                'and shared_folder_scope = "custom"'
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

        # Audio. Use the PulseAudio backend, not pipewire: FreeRDP 3.24's
        # rdpsnd failed to load the pipewire subsystem (error 1359) and that
        # failure aborts the whole RAIL connect (ERRCONNECT_POST_CONNECT_FAILED).
        # pulse is the broadly-available backend (PipeWire ships a pulse shim),
        # so /sound:sys:pulse works whether the host runs PulseAudio or PipeWire.
        if self.audio_enabled:
            flags.append("/sound:sys:pulse")
        if self.audio_enabled and self.audio_mode == "bidirectional":
            flags.append("/microphone:sys:pulse")
        elif self.microphone_enabled:
            # Explicit mic without bidirectional audio (rare but valid).
            flags.append("/microphone:sys:pulse")

        # Clipboard. FreeRDP 3.x has no "/clipboard-redirect-type" flag — the
        # parser rejects it ("Unexpected keyword"), which fails the whole RAIL
        # spawn. `+clipboard` enables the channel; finer control (direction /
        # selection) is via `/clipboard:` sub-options and the text-only vs rich
        # *format* filtering is handled host-side at the FORMAT_FILELIST seam,
        # not by a FreeRDP flag. So both enabled modes map to `+clipboard`.
        if self.clipboard_mode in ("text-only", "rich"):
            flags.append("+clipboard")

        # Printer
        if self.printer_mode == "auto":
            flags.append("/printer")
        elif self.printer_mode == "named":
            flags.append(f"/printer:{self.printer_name}")

        # Smart card
        if self.smartcard_enabled:
            flags.append("/smartcard")

        # USB devices. FreeRDP 3.x syntax is /usb:id:<vid>:<pid> (a colon after
        # `id`, per `xfreerdp3 /help`), not `id,`.
        for device in self.usb_devices:
            flags.append(f"/usb:id:{device}")

        # Shared folder (opt-in host directory redirect). FreeRDP auto-enables
        # the rdpdr channel; the guest sees it as \\tsclient\<name>. The host
        # path is resolved from the exposure scope (default: whole $HOME).
        if self.shared_folder_enabled:
            flags.append(
                f"/drive:{self.shared_folder_name},{self.shared_folder_resolved_path()}"
            )

        return flags

    def shared_folder_resolved_path(self) -> str:
        """The expanded host directory the share exposes, per
        :attr:`shared_folder_scope`. Empty string when the share is off.

        - ``home`` → ``$HOME``; ``documents`` → ``$HOME/Documents``;
          ``custom`` → the tilde/env-expanded :attr:`shared_folder_path`.
        """
        if not self.shared_folder_enabled:
            return ""
        if self.shared_folder_scope == "home":
            return os.path.expanduser("~")
        if self.shared_folder_scope == "documents":
            return os.path.join(os.path.expanduser("~"), "Documents")
        return os.path.expanduser(os.path.expandvars(self.shared_folder_path))

    def shared_folder_host_path(self) -> str:
        """The expanded host directory for the shared folder (for the
        launcher to create on demand). Empty string when disabled.

        Alias of :meth:`shared_folder_resolved_path` kept as the launcher's
        existing call site."""
        return self.shared_folder_resolved_path()

    def shared_folder_drive_path(self) -> str:
        """Guest-side working directory for a launched RemoteApp: the root
        of the mapped drive, e.g. ``Z:\\``.

        The guest logon step maps ``<letter>:`` to ``\\\\tsclient\\<name>``;
        the launcher passes this as the ``/app:`` ``workdir:`` so the app's
        Save/Open dialog defaults to the Linux-visible folder.  A drive
        letter is used rather than the UNC because Windows ignores a UNC
        working directory (falls back to System32).  Empty when the shared
        folder is off."""
        if not self.shared_folder_enabled:
            return ""
        return f"{self.shared_folder_drive_letter}:\\"

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
