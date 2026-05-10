"""``crossdesk doctor`` CLI wrapper around :mod:`doctor.checks`."""

from __future__ import annotations

import argparse

from crossdesk_host.doctor import has_failures, run_all
from crossdesk_host.doctor.checks import Status
from crossdesk_host.i18n import _


def add_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    sub.add_parser("doctor", help="Run pre-flight environment checks")


# Glyphs are not translated — they are a visual status indicator and
# match a fixed legend the user expects regardless of locale.
_GLYPH = {Status.OK: "✓", Status.WARN: "!", Status.FAIL: "✗"}


def run(_args: argparse.Namespace) -> int:
    results = run_all()
    for r in results:
        glyph = _GLYPH[r.status]
        # r.name is a check identifier (e.g. "libvirt", "kvm") and stays
        # English per docs/I18N.md "Strings we don't translate". The
        # status enum value is also fixed schema — we surface the
        # human-readable status label via translation of that fixed
        # token so locales can rephrase "ok"/"warn"/"fail" if needed.
        status_label = _(r.status.value)
        line = f"  {glyph} {r.name:<16} [{status_label}]"
        if r.message:
            # The message is emitted by doctor.checks call sites; this
            # wrapper marks it as user-facing so a later pass that wraps
            # those literals in _() picks them up automatically.
            line += f" — {_(r.message)}"
        print(line)
    return 1 if has_failures(results) else 0
