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


def _run_hook(
    repo: Path, push_refs: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the hook the way git does.

    *push_refs* is the stdin git feeds a pre-push hook: one
    ``<local ref> <local sha> <remote ref> <remote sha>`` line per ref. ``None``
    means no refs at all (a manual invocation), which the hook handles by
    falling back to HEAD vs the default branch.
    """
    return subprocess.run(
        ["bash", str(HOOK)],
        cwd=repo,
        capture_output=True,
        text=True,
        input=push_refs if push_refs is not None else "",
    )


def _push_line(repo: Path, branch: str = "main") -> str:
    local_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    remote_sha = subprocess.run(
        ["git", "rev-parse", f"origin/{branch}"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return (
        f"refs/heads/{branch} {local_sha} refs/heads/{branch} {remote_sha}\n"
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


# ---------------------------------------------------------------------------
# Antipattern A1 (.claude/rules/rules-as-gates.md): the gate must check the
# commit being PUSHED, not the working tree.
#
# The old hook derived its range from HEAD and grepped files off disk. Both
# halves are wrong in the same direction: a secret that was committed and then
# edited out of the working tree — the "fix it quickly before pushing" move —
# was never read, so the push went through carrying it.
# ---------------------------------------------------------------------------


def test_secret_committed_then_removed_only_in_the_working_tree_is_caught(
    repo: Path,
) -> None:
    name = "leaky.py"
    _commit_file(repo, name, f'api_key = "{FAKE_SECRET}"\n')
    # The working tree is now clean-looking; the commit is not. This is what
    # the remote would receive.
    (repo / name).write_text("api_key = os.environ['API_KEY']\n", encoding="utf-8")

    result = _run_hook(repo, _push_line(repo))

    assert result.returncode != 0, (
        "hook passed a push whose commit carries the secret — it scanned the "
        f"working tree instead of the pushed commit. stdout:\n{result.stdout}"
    )
    assert "potential hardcoded secrets" in result.stdout
    assert name in result.stdout


def test_secret_present_only_in_the_working_tree_is_not_reported(
    repo: Path,
) -> None:
    """The mirror case, and the reason this is a fix rather than a tightening:
    an uncommitted scratch edit is not part of the push and must not fail it."""
    _commit_file(repo, "clean.py", "value = 1\n")
    (repo / "scratch.py").write_text(f'api_key = "{FAKE_SECRET}"\n', encoding="utf-8")

    result = _run_hook(repo, _push_line(repo))

    assert "potential hardcoded secrets" not in result.stdout
    assert result.returncode == 0


def test_range_comes_from_stdin_not_from_head(repo: Path) -> None:
    """Given a remote sha that already includes the secret commit, that commit
    is not part of this push and must not be re-reported.

    The old hook could not express this: its range was always
    origin/<default>...HEAD, so anything not yet on the remote branch counted,
    regardless of what the push actually advertised.
    """
    _commit_file(repo, "old-leak.py", f'api_key = "{FAKE_SECRET}"\n')
    already_pushed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _commit_file(repo, "new-clean.py", "value = 2\n")
    local_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    result = _run_hook(
        repo, f"refs/heads/main {local_sha} refs/heads/main {already_pushed}\n"
    )

    assert result.returncode == 0, result.stdout
    assert "old-leak.py" not in result.stdout


def test_new_branch_push_scans_its_own_commits(repo: Path) -> None:
    """A branch the remote has never seen reports an all-zero remote sha. The
    range is then 'commits no remote ref contains', not an empty diff."""
    _git(repo, "checkout", "-b", "feature", "-q")
    _commit_file(repo, "feature-leak.py", f'api_key = "{FAKE_SECRET}"\n')
    local_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    result = _run_hook(
        repo, f"refs/heads/feature {local_sha} refs/heads/feature {'0' * 40}\n"
    )

    assert result.returncode != 0, result.stdout
    assert "feature-leak.py" in result.stdout


def test_branch_deletion_is_not_scanned(repo: Path) -> None:
    """Deleting a remote branch pushes an all-zero LOCAL sha. There is no
    commit to check out, and treating it as one would crash the hook."""
    result = _run_hook(
        repo, f"(delete) {'0' * 40} refs/heads/gone {'0' * 40}\n"
    )

    assert result.returncode == 0, result.stdout


# ---------------------------------------------------------------------------
# The per-line `pre-push-allow-secret` marker (.claude/rules/rules-as-gates.md
# §9): a gate proving it blocks needs a fixture containing a dummy secret, and
# that fixture tripped this very layer. The exemption must stay per LINE —
# excluding the path would blind the scanner to a real secret sitting next to
# the dummy, which is the failure mode the marker exists to avoid.
# ---------------------------------------------------------------------------


def test_marked_line_does_not_block_and_is_announced(repo: Path) -> None:
    _commit_file(
        repo,
        "gate-probe.sh",
        f'api_key = "{FAKE_SECRET}"  # pre-push-allow-secret: gate fixture\n',
    )

    result = _run_hook(repo, _push_line(repo))

    assert result.returncode == 0, result.stdout
    assert "potential hardcoded secrets" not in result.stdout
    # Loud, not silent: an unannounced escape hatch is the same failure as no
    # gate (rules-as-gates.md §7).
    assert "pre-push-allow-secret" in result.stdout


def test_unmarked_secret_beside_a_marked_one_still_blocks(repo: Path) -> None:
    """Per-line, not per-file — the point of the whole design."""
    _commit_file(
        repo,
        "gate-probe.sh",
        f'api_key = "{FAKE_SECRET}"  # pre-push-allow-secret: gate fixture\n'
        f'password = "{FAKE_SECRET}"\n',
    )

    result = _run_hook(repo, _push_line(repo))

    assert result.returncode != 0, result.stdout
    assert "potential hardcoded secrets" in result.stdout
    assert "gate-probe.sh" in result.stdout
