"""Render the guest-side logon script that maps the shared folder to a
drive letter and redirects Windows shell folders at it.

Stage A of the A→B filesystem direction (owner decision 2026-06-12; plan
``handoff.md`` §2.7). The host already redirects one scoped directory into
the guest as ``\\\\tsclient\\<name>`` (FreeRDP ``/drive:``), but Windows
will not honour a UNC path as a process working directory — a RemoteApp
launched with ``workdir:\\\\tsclient\\CrossDesk`` silently falls back to
``C:\\Windows\\System32`` (verified live 2026-06-09). The fix is a drive
*letter*: this script runs at logon, maps ``<letter>:`` to the share, and
points the user's *Documents* (and optionally *Desktop*) shell folder at the
drive root so a launched app's Save/Open dialog defaults to the
Linux-visible folder.

The script is **idempotent** and **self-correcting**: every run checks
whether the rdpdr share is actually present in the session and either
(re)establishes the mapping + redirect, or — when the share is absent
(shared folder disabled, or a session that launched without ``/drive:``) —
restores the default shell-folder paths and drops any stale mapping, so the
profile never ends up pointing at a dead drive (the failure mode that makes
Explorer hang).

The mapping is created **persistent** (``net use … /persistent:yes``). Live
finding 2026-06-12 (``handoff.md`` §2.7): a persistent mapping is restored
automatically by the Windows MPR at every subsequent logon — *including a
RemoteApp/RAIL logon* — whereas HKCU/HKLM ``Run`` keys do **not** fire in a
RAIL logon (``rdpinit.exe`` is the RemoteApp shell and skips the
Explorer/userinit Run-key processing). So the persistent flag is what keeps
the drive available across logons; running this script once in a session
that has the share is enough to establish it, and the agent re-running it on
session-connect is belt-and-suspenders plus the absent-branch cleanup.

Why a batch ``.cmd`` rather than PowerShell: it matches the existing
provisioning artifact style (``run-agent.cmd``), needs no execution-policy
handling, and the operations here (``net use`` / ``reg add`` / ``if
exist``) are exactly what ``cmd`` does cleanly. The rendered text is data,
not a template the guest fills in — the host bakes the drive letter, share
name and redirect choices from :class:`PeripheralsConfig` at provision time
(no new RPC, no proto change).

The mechanism that *runs* this script (an agent-driven
``CreateProcessAsUser`` on session-connect, or a one-time provisioning
step — **not** a ``Run`` key, which a RAIL logon ignores) is a provisioning
concern handled by the caller; this module only renders the script body.
"""

from __future__ import annotations

from crossdesk_host.config.peripherals import PeripheralsConfig

# The User Shell Folders key whose values Explorer reads to locate the
# per-user Documents / Desktop folders. REG_EXPAND_SZ so the restore values
# can carry %USERPROFILE%.
_USER_SHELL_FOLDERS = (
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
)

# Stock defaults Windows ships for these shell folders — restored verbatim
# when the share is absent so we never leave the profile pointing at a drive
# that isn't mapped.
_DEFAULT_DOCUMENTS = r"%USERPROFILE%\Documents"
_DEFAULT_DESKTOP = r"%USERPROFILE%\Desktop"


def render_drive_map_script(cfg: PeripheralsConfig) -> str:
    """Return the ``.cmd`` body that maps the shared folder to
    ``<cfg.shared_folder_drive_letter>:`` and redirects shell folders.

    The script is safe to run even when the shared folder is disabled at
    runtime: it keys every action on whether ``\\\\tsclient\\<name>`` is
    present in the current session, so a launch without the ``/drive:``
    redirect simply restores defaults.

    Determinism: the output depends only on *cfg*, so the same config always
    renders byte-identical text (a provisioning artifact a test can pin).
    """
    drive = cfg.shared_folder_drive_letter  # already upper-normalised + validated
    share = f"\\\\tsclient\\{cfg.shared_folder_name}"
    root = f"{drive}:\\"

    # Map-and-redirect branch (share present). /persistent:yes so the Windows
    # MPR restores the drive at every later logon (verified to work for RAIL
    # logons, where Run keys do not fire — see module docstring).
    set_lines = [
        f'    net use {drive}: /delete /y >nul 2>&1',
        f'    net use {drive}: "{share}" /persistent:yes >nul 2>&1',
    ]
    if cfg.shared_folder_redirect_documents:
        set_lines.append(
            f'    reg add "{_USER_SHELL_FOLDERS}" /v Personal '
            f'/t REG_EXPAND_SZ /d "{root}" /f >nul'
        )
    if cfg.shared_folder_redirect_desktop:
        set_lines.append(
            f'    reg add "{_USER_SHELL_FOLDERS}" /v Desktop '
            f'/t REG_EXPAND_SZ /d "{root}" /f >nul'
        )

    # Restore branch (share absent). Mirror exactly the redirects we set, so
    # a profile that was pointed at the drive is returned to its defaults.
    restore_lines = []
    if cfg.shared_folder_redirect_documents:
        restore_lines.append(
            f'    reg add "{_USER_SHELL_FOLDERS}" /v Personal '
            f'/t REG_EXPAND_SZ /d "{_DEFAULT_DOCUMENTS}" /f >nul'
        )
    if cfg.shared_folder_redirect_desktop:
        restore_lines.append(
            f'    reg add "{_USER_SHELL_FOLDERS}" /v Desktop '
            f'/t REG_EXPAND_SZ /d "{_DEFAULT_DESKTOP}" /f >nul'
        )
    restore_lines.append(f'    net use {drive}: /delete /y >nul 2>&1')

    body = "\n".join(
        [
            "@echo off",
            "REM CrossDesk shared-folder drive map + shell-folder redirect.",
            "REM Generated by crossdesk_host.installer.drive_map — do not edit by hand.",
            "REM Runs per interactive logon; idempotent; restores defaults when the",
            "REM share is absent so the profile never points at a dead drive.",
            "",
            # `if exist <unc>\` tests the rdpdr share's presence in this session.
            # The trailing backslash forces a directory test (not a file).
            f'if exist "{share}\\" (',
            *set_lines,
            ") else (",
            *restore_lines,
            ")",
            "",
        ]
    )
    return body
