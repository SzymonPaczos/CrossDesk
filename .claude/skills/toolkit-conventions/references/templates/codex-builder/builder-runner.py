#!/usr/bin/env python3
"""Run one bounded Codex builder; verify Git identity and execute owner-specified gates."""
import argparse
import fnmatch
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid

sys.dont_write_bytecode = True
from watchdog import run_process  # noqa: E402

HERE = Path(__file__).resolve().parent
REPORT_KEYS = {"status", "assessed_sha", "commits", "changed_files", "gates", "skipped", "blockers"}
SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def git(root, *args, raw=False):
    output = subprocess.run(["git", "-c", "core.quotePath=false", "-c", "core.fsmonitor=false", "-C", str(root), *args], check=True,
                            capture_output=True, text=True,
                            env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")}).stdout
    return output if raw else output.strip()


def _strings(value, name):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError(f"{name} must be an array of nonempty strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{name} contains duplicate values")


def validate_spec(spec):
    if not isinstance(spec, dict) or not {"base_sha", "expected_branch", "scope", "gates"} <= spec.keys():
        raise ValueError("gate spec requires base_sha, expected_branch, scope and gates")
    if not isinstance(spec["base_sha"], str) or not SHA.fullmatch(spec["base_sha"]):
        raise ValueError("base_sha must be a full accepted commit SHA")
    if not isinstance(spec["expected_branch"], str) or not spec["expected_branch"].strip():
        raise ValueError("expected_branch is required")
    _strings(spec["scope"], "scope")
    if not spec["scope"] or any(x.startswith("/") or ".." in PurePosixPath(x).parts for x in spec["scope"]):
        raise ValueError("scope must contain safe relative paths or globs")
    if not isinstance(spec["gates"], list) or (not spec["gates"] and spec.get("allow_empty_gates") is not True):
        raise ValueError("gates cannot be empty without explicit allow_empty_gates=true")
    names = []
    for gate in spec["gates"]:
        if not isinstance(gate, dict) or set(gate) != {"name", "argv", "timeout_seconds"}:
            raise ValueError("each gate requires only name, argv and timeout_seconds")
        if not isinstance(gate["name"], str) or not re.fullmatch(r"[A-Za-z0-9_-]+", gate["name"]):
            raise ValueError("gate name must be a portable identifier")
        if (not isinstance(gate["argv"], list) or not gate["argv"]
                or any(not isinstance(x, str) or not x for x in gate["argv"])):
            raise ValueError("gate argv must be a nonempty argument vector")
        timeout = gate["timeout_seconds"]
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("gate timeout_seconds must be finite and positive")
        names.append(gate["name"])
    if len(names) != len(set(names)):
        raise ValueError("duplicate gate name")


def _in_scope(name, scope):
    return any(fnmatch.fnmatchcase(name, entry) or (entry.endswith("/") and name.startswith(entry)) for entry in scope)


def validate_report(report, *, root, spec):
    """Validate declarations against accepted scope and real Git; do not trust declared test results."""
    if not isinstance(report, dict) or set(report) != REPORT_KEYS:
        raise ValueError("report fields do not match report.schema.json")
    if not isinstance(report["status"], str) or report["status"] not in {"ready_for_checks", "completed", "blocked"}:
        raise ValueError("unknown builder status")
    for name in ["commits", "changed_files", "skipped", "blockers"]:
        _strings(report[name], name)
    if not isinstance(report["assessed_sha"], str) or not SHA.fullmatch(report["assessed_sha"]):
        raise ValueError("assessed_sha must be a full commit SHA")
    if report["assessed_sha"] != git(root, "rev-parse", "HEAD"):
        raise ValueError("report SHA differs from actual HEAD")
    if not isinstance(report["gates"], list):
        raise ValueError("gates must be an array")
    declared = {}
    for gate in report["gates"]:
        if not isinstance(gate, dict) or set(gate) != {"name", "exit_code", "evidence_ref"}:
            raise ValueError("malformed gate declaration")
        if not isinstance(gate["name"], str) or gate["name"] in declared:
            raise ValueError("duplicate or malformed gate declaration name")
        code = gate["exit_code"]
        if code is not None and (isinstance(code, bool) or not isinstance(code, int)):
            raise ValueError("gate exit_code must be an integer or null")
        if not isinstance(gate["evidence_ref"], str):
            raise ValueError("gate evidence_ref must be text")
        declared[gate["name"]] = gate
    expected = {g["name"] for g in spec["gates"]}
    if report["status"] == "blocked":
        if not report["blockers"]:
            raise ValueError("blocked report requires an explicit blocker")
        return {"status": "BLOCKED", "reason": "builder reported a blocker"}
    if report["blockers"] or report["skipped"]:
        raise ValueError("completed report has blockers or skipped checks")
    allowed_codes = {0, None} if report["status"] == "ready_for_checks" else {0}
    if set(declared) != expected or any(g["exit_code"] not in allowed_codes or (g["exit_code"] == 0 and not g["evidence_ref"].strip()) for g in declared.values()):
        raise ValueError("completed report omits/fails required gates or evidence references")
    if git(root, "branch", "--show-current") != spec["expected_branch"]:
        raise ValueError("builder changed the accepted branch")
    git(root, "merge-base", "--is-ancestor", spec["base_sha"], "HEAD")
    actual_commits = git(root, "rev-list", "--reverse", spec["base_sha"] + "..HEAD").splitlines()
    if not actual_commits or report["commits"] != actual_commits:
        raise ValueError("reported commits differ from actual delivered commits")
    if git(root, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("uncommitted or untracked work cannot be delivered as completed")
    for commit in actual_commits:
        # -m checks each merge parent; --root covers introduced orphan roots.
        # Disable rename inference so both old and new names remain in scope.
        history_paths = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "-m",
                            "--root", "--no-renames", "-z", commit, raw=True).split("\0")
        if any(name and not _in_scope(name, spec["scope"]) for name in history_paths):
            raise ValueError("introduced commit history exceeds accepted scope: " + commit)
    actual_files = [name for name in git(root, "diff", "--name-only", "-z", spec["base_sha"], "HEAD", raw=True).split("\0") if name]
    if sorted(report["changed_files"]) != sorted(actual_files):
        raise ValueError("changed_files differs from actual Git diff")
    if any(not _in_scope(name, spec["scope"]) for name in actual_files):
        raise ValueError("delivered files exceed accepted scope")
    return {"status": "READY_FOR_HOST_CHECKS", "assessed_sha": report["assessed_sha"]}


def execute_gates(root, spec, directory):
    """Only host-executed gate receipts can support verified completion."""
    receipts = []
    for gate in spec["gates"]:
        with (directory / (gate["name"] + ".stdout")).open("wb") as stdout, (directory / (gate["name"] + ".stderr")).open("wb") as stderr:
            result = run_process(gate["argv"], cwd=root, timeout=gate["timeout_seconds"], stdout=stdout, stderr=stderr)
        receipts.append({"name": gate["name"], "argv_sha256": hashlib.sha256(json.dumps(gate["argv"]).encode()).hexdigest(), **result})
        if result["exit_code"]:
            break
    return receipts


def extra_arguments(arguments):
    """Model/color selection is allowed; callers cannot replace the sandbox or report contract."""
    index = 0
    while index < len(arguments):
        item = arguments[index]
        if item in {"-m", "--model", "--color"}:
            index += 1
            if index == len(arguments) or arguments[index].startswith("-"):
                raise ValueError(f"missing value for {item}")
        elif not (item in {"--ephemeral", "--strict-config"} or item.startswith(("--model=", "--color="))):
            raise ValueError(f"unsupported Codex override: {item}")
        index += 1
    return arguments


def read_final_report(stream):
    """Read the final agent message, never a tool result masquerading as completion."""
    stream.seek(0)
    final = None
    consumed = 0
    while True:
        line = stream.readline(1024 * 1024 + 1)
        if not line:
            break
        consumed += len(line)
        if len(line) > 1024 * 1024 or consumed > 64 * 1024 * 1024:
            raise ValueError("Codex JSONL output exceeded the report parser limit")
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError("Codex event must be an object")
        item = event.get("item")
        if event.get("type") == "item.completed" and isinstance(item, dict) and item.get("type") == "agent_message":
            final = item.get("text")
    if not isinstance(final, str):
        raise ValueError("Codex did not emit a final agent message")
    return json.loads(final)


def write_json_at(directory_fd, name, payload):
    """Atomic write anchored to an open directory; a worker-created symlink is replaced, not followed."""
    temporary = "." + name + "." + uuid.uuid4().hex
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worktree")
    parser.add_argument("brief")
    parser.add_argument("report")
    parser.add_argument("codex_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    receipt = {"status": "BLOCKED", "reason": "run not started", "gates": []}
    target = Path(args.report).absolute()
    try:
        root = Path(args.worktree).resolve(strict=True)
        target.resolve().relative_to(root)
    except ValueError:
        pass
    except OSError as exc:
        print(f"BUILDER: INVALID ({type(exc).__name__})", file=sys.stderr)
        return 2
    else:
        print("BUILDER: INVALID (report must be outside the working tree)", file=sys.stderr)
        return 2
    directory_fd = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        directory_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for name in [target.name, target.name + ".receipt.json"]:
            try:
                if stat.S_ISLNK(os.stat(name, dir_fd=directory_fd, follow_symlinks=False).st_mode):
                    raise ValueError("report and receipt paths cannot be symlinks")
            except FileNotFoundError:
                pass
        spec_path = os.environ.get("CODEX_GATE_SPEC")
        if not spec_path:
            raise ValueError("CODEX_GATE_SPEC must name an owner-provided gate spec")
        spec = json.loads(Path(spec_path).read_text())
        validate_spec(spec)
        if git(root, "rev-parse", "HEAD") != spec["base_sha"] or git(root, "branch", "--show-current") != spec["expected_branch"]:
            raise ValueError("baseline or branch differs from accepted gate spec")
        if git(root, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError("builder baseline must be clean")
        preamble = Path(os.environ.get("CODEX_PREAMBLE", str(HERE / "preamble.md")))
        prompt = preamble.read_text() + "\n" + Path(args.brief).read_text()
        prompt += "\nReturn only report.schema.json JSON. Required gate names: " + ", ".join(g["name"] for g in spec["gates"]) + ". If a commit or gate is denied, report blocked with the reason; do not weaken the sandbox.\n"
        codex = shutil.which("codex")
        if not codex:
            raise ValueError("codex is not installed")
        help_result = subprocess.run([codex, "exec", "--help"], capture_output=True, text=True, timeout=10)
        if help_result.returncode or any(flag not in help_result.stdout for flag in ["--output-schema", "--json"]):
            raise ValueError("installed Codex must support exec --output-schema and --json")
        if "--strict-config" in args.codex_args and "--strict-config" not in help_result.stdout:
            raise ValueError("installed Codex does not support --strict-config")
        timeout = float(os.environ.get("CODEX_TIMEOUT_SECONDS", "1800"))
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("CODEX_TIMEOUT_SECONDS must be finite and positive")
        effort = os.environ.get("CODEX_EFFORT", "medium")
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", effort):
            raise ValueError("CODEX_EFFORT must name a reasoning level")
        command = [codex, "exec", "-C", str(root), "-s", "workspace-write",
                   "-c", 'model_reasoning_effort="' + effort + '"',
                   "-c", "tool_output_token_limit=2000", "-c", 'approval_policy="never"',
                   "--output-schema", str(HERE / "report.schema.json"), "--json"]
        if os.environ.get("CODEX_SCRATCH"):
            command += ["--add-dir", os.environ["CODEX_SCRATCH"]]
        command += extra_arguments(args.codex_args) + ["-"]
        try:
            os.unlink(target.name, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        runtime = Path(tempfile.mkdtemp(prefix="builder-", dir=target.parent))
        receipt["runtime_directory"] = str(runtime)
        with (runtime / "events.jsonl").open("wb+") as events, (runtime / "stderr.log").open("wb") as stderr:
            with (runtime / "prompt").open("wb+") as stdin:
                stdin.write(prompt.encode())
                stdin.seek(0)
                result = run_process(command, cwd=root, timeout=timeout, stdin=stdin, stdout=events, stderr=stderr)
            receipt["builder_process"] = result
            if result["exit_code"]:
                receipt["reason"] = "builder process failed, timed out or was cancelled"
                return result["exit_code"]
            report = read_final_report(events)
            write_json_at(directory_fd, target.name, report)
            checked = validate_report(report, root=root, spec=spec)
            if checked["status"] == "BLOCKED":
                receipt.update(checked)
                return 3
            receipts = execute_gates(root, spec, runtime)
            receipt["gates"] = receipts
            unchanged = git(root, "rev-parse", "HEAD") == checked["assessed_sha"] and not git(root, "status", "--porcelain", "--untracked-files=all")
            if len(receipts) != len(spec["gates"]) or any(g["exit_code"] for g in receipts) or not unchanged:
                receipt["reason"] = "independent gates failed or changed the assessed artifact"
                return next((g["exit_code"] for g in receipts if g["exit_code"]), 3)
            receipt.update(status="VERIFIED_COMPLETE", reason="host gates passed", assessed_sha=checked["assessed_sha"])
            return 0
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        receipt["reason"] = str(exc)
        print(f"BUILDER: INVALID ({exc})", file=sys.stderr)
        return 2
    finally:
        if directory_fd is not None:
            try:
                write_json_at(directory_fd, target.name + ".receipt.json", receipt)
            finally:
                os.close(directory_fd)
        print("BUILDER: " + receipt["status"], file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
