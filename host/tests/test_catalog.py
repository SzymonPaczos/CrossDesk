"""App catalog tests (Phase 8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crossdesk_host.catalog import (
    CuratedApp,
    Rating,
    UserApp,
    average_rating,
    load_curated,
    load_ratings,
    load_user_apps,
    save_user_app,
)

# ---------------------------------------------------------------------------
# Curated tier
# ---------------------------------------------------------------------------


def test_load_curated_from_bundled_file_returns_real_entries() -> None:
    """The repo ships infra/apps/curated.toml; loader must find it."""
    apps = load_curated()
    assert len(apps) >= 20
    ids = {a.id for a in apps}
    # Spot-check a handful of expected apps.
    assert "notepad" in ids
    assert "word" in ids
    assert "excel" in ids
    assert "photoshop" in ids


def test_load_curated_returns_empty_when_missing(tmp_path: Path) -> None:
    apps = load_curated(tmp_path / "nope.toml")
    assert apps == []


def test_load_curated_parses_optional_fields(tmp_path: Path) -> None:
    target = tmp_path / "curated.toml"
    target.write_text(
        """
[[app]]
id = "test-app"
display_name = "Test App"
display_name_pl = "Aplikacja testowa"
executable = "C:\\\\test.exe"
category = "Office"
stars = 4
known_issues = "It's a test."
mime_types = ["text/plain", "application/test"]
""",
        encoding="utf-8",
    )
    apps = load_curated(target)
    assert len(apps) == 1
    a = apps[0]
    assert a.id == "test-app"
    assert a.display_name_pl == "Aplikacja testowa"
    assert a.stars == 4
    assert a.known_issues == "It's a test."
    assert a.mime_types == ["text/plain", "application/test"]


def test_localized_name_picks_polish_when_available() -> None:
    a = CuratedApp(
        id="x",
        display_name="Hello",
        display_name_pl="Witaj",
        executable="C:\\x.exe",
    )
    assert a.localized_name("pl") == "Witaj"
    assert a.localized_name("pl_PL") == "Witaj"
    assert a.localized_name("en_US") == "Hello"


def test_localized_name_falls_back_to_english_when_polish_missing() -> None:
    a = CuratedApp(
        id="x",
        display_name="Hello",
        display_name_pl=None,
        executable="C:\\x.exe",
    )
    assert a.localized_name("pl") == "Hello"


def test_load_curated_skips_malformed_entries(tmp_path: Path) -> None:
    target = tmp_path / "curated.toml"
    target.write_text(
        """
[[app]]
display_name = "no-id"
executable = "C:\\\\nope.exe"

[[app]]
id = "good-id"
display_name = "Good"
executable = "C:\\\\good.exe"
""",
        encoding="utf-8",
    )
    apps = load_curated(target)
    assert len(apps) == 1
    assert apps[0].id == "good-id"


# ---------------------------------------------------------------------------
# User tier
# ---------------------------------------------------------------------------


def test_save_and_load_user_app_round_trip(tmp_path: Path) -> None:
    a = UserApp(
        id="custom-test",
        display_name="My Test App",
        executable="C:\\test.exe",
        mime_types=["text/plain"],
        category="User",
    )
    target_dir = tmp_path / "user"
    saved = save_user_app(a, target_dir)
    assert saved.exists()
    loaded = load_user_apps(target_dir)
    assert len(loaded) == 1
    assert loaded[0].display_name == "My Test App"


def test_load_user_apps_returns_empty_when_dir_missing(tmp_path: Path) -> None:
    assert load_user_apps(tmp_path / "absent") == []


def test_load_user_apps_skips_malformed_json(tmp_path: Path) -> None:
    target_dir = tmp_path / "user"
    target_dir.mkdir()
    (target_dir / "broken.json").write_text("{not valid")
    (target_dir / "missing-id.json").write_text(json.dumps({"display_name": "x"}))
    save_user_app(
        UserApp(id="ok", display_name="OK", executable="C:\\ok.exe"),
        target_dir,
    )
    loaded = load_user_apps(target_dir)
    assert {a.id for a in loaded} == {"ok"}


def test_save_user_app_no_tmp_leak(tmp_path: Path) -> None:
    target_dir = tmp_path / "user"
    save_user_app(UserApp(id="a", display_name="A", executable="C:\\a.exe"), target_dir)
    leftover = list(target_dir.glob("a.json.*.tmp"))
    assert leftover == []


# ---------------------------------------------------------------------------
# Ratings
# ---------------------------------------------------------------------------


def test_load_ratings_missing_returns_empty(tmp_path: Path) -> None:
    assert load_ratings(tmp_path / "nope.json") == {}


def test_load_ratings_parses_valid(tmp_path: Path) -> None:
    target = tmp_path / "ratings.json"
    target.write_text(
        json.dumps(
            {
                "word": {"stars": 4.2, "sample_size": 47, "notes": "good"},
                "photoshop": {"stars": 3.8, "sample_size": 12},
            }
        ),
        encoding="utf-8",
    )
    out = load_ratings(target)
    assert out["word"].stars == pytest.approx(4.2)
    assert out["word"].sample_size == 47
    assert out["photoshop"].notes == ""


def test_load_ratings_skips_garbage_entries(tmp_path: Path) -> None:
    target = tmp_path / "ratings.json"
    target.write_text(
        json.dumps(
            {
                "ok": {"stars": 4.0, "sample_size": 10},
                "broken": "not a dict",
                "bad-stars": {"stars": "five", "sample_size": 1},
            }
        )
    )
    out = load_ratings(target)
    assert "ok" in out
    assert "broken" not in out


def test_load_ratings_invalid_json_returns_empty(tmp_path: Path) -> None:
    target = tmp_path / "ratings.json"
    target.write_text("not json at all")
    assert load_ratings(target) == {}


def test_average_rating_no_community_returns_curated() -> None:
    assert average_rating(4, None) == 4.0


def test_average_rating_zero_sample_returns_curated() -> None:
    assert average_rating(4, Rating("x", 1.0, 0)) == 4.0


def test_average_rating_blends_with_community() -> None:
    rating = Rating("x", 5.0, 9)  # 9 community samples averaging 5
    blended = average_rating(2, rating)
    # (2 + 5*9) / (1+9) = 47/10
    assert blended == pytest.approx(4.7)
