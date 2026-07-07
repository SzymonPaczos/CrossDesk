"""WindowIconStore — applies the agent's extracted .exe icon to the launched
app's .desktop / icon theme via the expect()/offer() launch correlation.

mime.install_app and the icon-cache refresh are stubbed so the unit tests
write only into a tmp icon dir and never touch the real desktop/icon caches.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import List, Tuple

import pytest

from crossdesk_host.display import window_icon
from crossdesk_host.display.window_icon import WindowIconStore

_PNG = b"\x89PNG\r\n\x1a\n" + b"fake-icon-bytes"


@pytest.fixture
def store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Tuple[WindowIconStore, List[dict]]:
    """A store writing icons under tmp_path, with install_app + cache refresh
    stubbed. Returns the store and the list of install_app call kwargs."""
    calls: List[dict] = []
    monkeypatch.setattr(
        window_icon.mime,
        "install_app",
        lambda **kw: calls.append(kw) or (tmp_path / f"crossdesk-{kw['app_id']}.desktop"),
    )
    # No icon-cache subprocesses in tests.
    monkeypatch.setattr(window_icon.shutil, "which", lambda _name: None)
    clock = {"t": 1000.0}
    s = WindowIconStore(icon_dir=tmp_path / "apps", now=lambda: clock["t"])
    s._clock = clock  # type: ignore[attr-defined]  # test handle to advance time
    return s, calls


def test_offer_without_expect_is_noop(store: Tuple[WindowIconStore, List[dict]]) -> None:
    s, calls = store
    assert s.offer(_PNG) is None
    assert calls == []


def test_expect_then_offer_writes_icon_and_desktop(
    store: Tuple[WindowIconStore, List[dict]], tmp_path: Path
) -> None:
    s, calls = store
    s.expect("notepad", "Notepad")
    assert s.offer(_PNG) == "notepad"
    # Icon PNG written verbatim into the theme under crossdesk-<app_id>.png.
    icon_file = tmp_path / "apps" / "crossdesk-notepad.png"
    assert icon_file.read_bytes() == _PNG
    # .desktop (re)written with the matching icon name.
    assert len(calls) == 1
    assert calls[0]["app_id"] == "notepad"
    assert calls[0]["icon"] == "crossdesk-notepad"
    assert calls[0]["display_name"] == "Notepad"


def test_empty_icon_is_ignored(store: Tuple[WindowIconStore, List[dict]]) -> None:
    s, calls = store
    s.expect("notepad", "Notepad")
    assert s.offer(b"") is None
    assert calls == []
    # The expectation survives an empty offer so a later real icon still lands.
    assert s.offer(_PNG) == "notepad"


def test_non_png_icon_rejected_preserves_expectation(
    store: Tuple[WindowIconStore, List[dict]]
) -> None:
    s, calls = store
    s.expect("notepad", "Notepad")
    # An MZ (PE/exe) header is not a PNG — reject at the boundary, write nothing.
    assert s.offer(b"MZ\x90\x00\x03\x00\x00\x00") is None
    assert calls == []
    # Validation runs before the pending lookup, so the expectation survives a
    # bogus offer and the real icon still lands.
    assert s.offer(_PNG) == "notepad"


def test_oversize_icon_rejected(store: Tuple[WindowIconStore, List[dict]]) -> None:
    s, calls = store
    s.expect("notepad", "Notepad")
    huge = window_icon._PNG_MAGIC + b"\x00" * (1 << 20)  # magic ok, but > 1 MiB
    assert s.offer(huge) is None
    assert calls == []
    # A valid-sized icon still applies afterwards.
    assert s.offer(_PNG) == "notepad"


def test_expectation_consumed_after_one_offer(
    store: Tuple[WindowIconStore, List[dict]]
) -> None:
    s, _ = store
    s.expect("notepad", "Notepad")
    assert s.offer(_PNG) == "notepad"
    # A second window's icon has no pending launch to attach to.
    assert s.offer(_PNG) is None


def test_expired_expectation_is_dropped(
    store: Tuple[WindowIconStore, List[dict]]
) -> None:
    s, calls = store
    s.expect("notepad", "Notepad")
    s._clock["t"] += 120.0  # type: ignore[attr-defined]  # past the 60s TTL
    assert s.offer(_PNG) is None
    assert calls == []


def test_most_recent_launch_wins(
    store: Tuple[WindowIconStore, List[dict]]
) -> None:
    s, calls = store
    s.expect("word", "Word")
    s.expect("excel", "Excel")  # second launch overwrites the first
    assert s.offer(_PNG) == "excel"
    assert calls[0]["app_id"] == "excel"


def test_refresh_caches_offloaded_off_the_event_loop(
    store: Tuple[WindowIconStore, List[dict]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """On the daemon's asyncio loop the cache-tool subprocesses must run on a
    worker thread, not inline — otherwise a window-create stalls the loop
    (heartbeat FSM + every gRPC stream) for up to ~30s."""
    s, _ = store
    # Make the cache tools "present" so _run_cache_refresh reaches subprocess.run.
    monkeypatch.setattr(window_icon.shutil, "which", lambda name: f"/usr/bin/{name}")
    main_thread = threading.get_ident()
    ran_on: List[int] = []
    monkeypatch.setattr(
        window_icon.subprocess,
        "run",
        lambda argv, **kw: ran_on.append(threading.get_ident()),
    )

    async def drive() -> None:
        fut = s._refresh_caches()
        assert fut is not None  # offloaded → returns the executor future
        await fut

    asyncio.run(drive())
    assert ran_on, "cache tools should have been invoked"
    assert all(tid != main_thread for tid in ran_on)  # never on the loop thread


def test_refresh_caches_runs_inline_without_a_loop(
    store: Tuple[WindowIconStore, List[dict]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Outside an event loop (CLI / tests) it runs synchronously, no future."""
    s, _ = store
    monkeypatch.setattr(window_icon.shutil, "which", lambda name: f"/usr/bin/{name}")
    calls: List[Tuple[str, ...]] = []
    monkeypatch.setattr(
        window_icon.subprocess, "run", lambda argv, **kw: calls.append(tuple(argv))
    )
    assert s._refresh_caches() is None
    assert calls  # both cache tools invoked inline
