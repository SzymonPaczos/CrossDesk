"""The pre-push secret gate must survive filenames that word-split.

Regression for the 2026-07-12 audit (P1 / Red Team): the hook iterated
``for f in $CHANGED_FILES`` unquoted. ``git diff --name-only`` prints a path
containing a space *unquoted*, so it split into tokens, every token failed the
``[ -f ]`` guard, and a file holding a real secret was never scanned — and this
grep is the only secret gate when gitleaks is not installed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / ".githooks" / "pre-push"

# Deliberately low-entropy: it must trip the hook's own regex (`api_key` =
# quoted run of 8+ chars) without reading as a live credential to gitleaks.
FAKE_SECRET = "hunter2" * 3


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _commit_file(repo: Path, name: str, body: str) -> None:
    (repo / name).write_text(body, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-m", f"add {name}")


def _run_hook(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(HOOK)], cwd=repo, capture_output=True, text=True
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A repo whose ``origin/HEAD`` resolves — the hook diffs against it."""
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(remote)],
        check=True,
        capture_output=True,
    )

    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-b", "main")
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    _commit_file(work, "README.md", "seed\n")
    _git(work, "remote", "add", "origin", str(remote))
    _git(work, "push", "-u", "origin", "main")
    _git(work, "remote", "set-head", "origin", "main")
    return work


def test_secret_in_spaced_filename_is_caught(repo: Path) -> None:
    name = "secret file.py"
    _commit_file(repo, name, f'api_key = "{FAKE_SECRET}"\n')

    result = _run_hook(repo)

    assert result.returncode != 0
    assert "potential hardcoded secrets" in result.stdout
    assert name in result.stdout


def test_clean_spaced_filename_is_not_flagged(repo: Path) -> None:
    _commit_file(repo, "clean file.py", "value = 1\n")

    result = _run_hook(repo)

    assert "potential hardcoded secrets" not in result.stdout


def test_secret_in_plain_filename_still_caught(repo: Path) -> None:
    """The array rewrite must not regress the ordinary path."""
    name = "plain.py"
    _commit_file(repo, name, f'api_key = "{FAKE_SECRET}"\n')

    result = _run_hook(repo)

    assert result.returncode != 0
    assert "potential hardcoded secrets" in result.stdout
    assert name in result.stdout
