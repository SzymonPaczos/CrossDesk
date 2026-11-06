#!/usr/bin/env python3
"""Durable, provider-neutral execution of an explicitly authorized work graph.

The JSON plan is trusted configuration. This runner is NOT a permission sandbox.
See agent-runtime/README.md for the result and cleanup contracts.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

VERSION = 1
TERMINAL = {"complete", "failed", "blocked"}
STOP = False
REVIEW_ROLES = {"reviewer", "security-reviewer", "red-team"}


class ControllerBusy(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def git(repo, *args, check=True):
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.quotePath=false", "-c", "core.hooksPath=" + os.devnull, "-C", str(repo), *args], env=environment,
                          capture_output=True, text=True, check=check)


def common_dir(repo):
    return (Path(repo) / git(repo, "rev-parse", "--git-common-dir").stdout.strip()).resolve()


def fingerprint(pid):
    """Unknown liveness is an error, never permission to start a duplicate."""
    result = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)],
                            env={**os.environ, "LC_ALL": "C"}, capture_output=True, text=True)
    if result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip():
        return None
    if result.returncode or not result.stdout.strip():
        raise RuntimeError("cannot establish process identity using ps")
    return result.stdout.strip()


def live(receipt):
    if type(receipt.get("pid")) is not int or receipt["pid"] < 1 or not isinstance(receipt.get("process_started"), str) or not receipt["process_started"]:
        raise ValueError("invalid process identity receipt")
    return fingerprint(receipt["pid"]) == receipt["process_started"]


def read_object(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError(Path(path).name + " must contain an object")
    return value


def emit_event(database, kind, identity, payload):
    """Durable metadata only: raw worker output remains in its private files."""
    with contextlib.closing(sqlite3.connect(database, timeout=5)) as connection:
        with connection:
            connection.execute("INSERT OR IGNORE INTO outbox(kind,node_id,run_id,payload,created_at) VALUES(?,?,?,?,?)",
                               (kind, identity["node_id"], identity["run_id"], canonical(payload).decode(), time.time()))


def result_event(directory, outcome):
    return {"reported_state": outcome.get("state", "unverified"), "head": outcome.get("head"),
            "reviewed_sha": outcome.get("reviewed_sha"),
            "receipt": directory.parent.parent.name + "/runs/" + directory.name + "/result.json"}


def path_scope(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("scope must contain nonempty POSIX relative paths")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or ".git" in path.parts:
        raise ValueError("scope cannot escape the worktree or include .git")
    return str(path).rstrip("/")


def overlap(a, b):
    return a == "." or b == "." or a == b or a.startswith(b + "/") or b.startswith(a + "/")


def argv(value):
    return isinstance(value, list) and bool(value) and all(isinstance(x, str) and x and "\0" not in x for x in value)


def load_plan(path):
    plan = json.loads(Path(path).read_text())
    if not isinstance(plan, dict) or plan.get("schema_version") != VERSION:
        raise ValueError("plan requires schema_version: 1")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", plan.get("id", "")):
        raise ValueError("invalid plan id")
    if type(plan.get("capacity")) is not int or not 1 <= plan["capacity"] <= 32:
        raise ValueError("capacity must be an integer from 1 to 32")
    target = plan.get("integration_branch")
    if not isinstance(target, str) or not target or git(Path.cwd(), "check-ref-format", "--branch", target, check=False).returncode:
        raise ValueError("integration_branch must be an explicit local branch name")
    nodes = plan.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("nodes must be a nonempty list")
    by_id = {}
    for node in nodes:
        if not isinstance(node, dict) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", node.get("id", "")):
            raise ValueError("invalid node id")
        ident = node["id"]
        if ident in by_id or type(node.get("authorized")) is not bool:
            raise ValueError("duplicate id or missing explicit authorized boolean")
        if node.get("role") not in {"builder", "scout", "reviewer", "security-reviewer", "red-team"}:
            raise ValueError("unsupported role")
        bindings = [key for key in ("review_of", "review_sha") if key in node]
        if node["role"] in REVIEW_ROLES:
            if len(bindings) != 1:
                raise ValueError("review requires exactly one of review_of or review_sha")
            if "review_sha" in node and (not isinstance(node["review_sha"], str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", node["review_sha"])):
                raise ValueError("review_sha must be a full commit SHA")
            if "review_of" in node and not isinstance(node["review_of"], str):
                raise ValueError("review_of must identify a Builder dependency")
        elif bindings:
            raise ValueError("only review roles may carry review artifact bindings")
        if not argv(node.get("argv")) or not isinstance(node.get("cwd"), str) or not node["cwd"]:
            raise ValueError("node requires argv list and cwd")
        checks = node.get("acceptance")
        if not isinstance(checks, list) or not checks or not all(argv(x) for x in checks):
            raise ValueError("node requires nonempty independently executed acceptance commands")
        if not isinstance(node.get("scope"), list) or not node["scope"]:
            raise ValueError("node requires nonempty scope")
        if any(path_scope(x) != x for x in node["scope"]):
            raise ValueError("scope paths must be normalized")
        if type(node.get("timeout_seconds")) not in {int, float} or not 0 < node["timeout_seconds"] <= 86400:
            raise ValueError("timeout_seconds must be positive and <=86400")
        if type(node.get("max_attempts")) is not int or not 1 <= node["max_attempts"] <= 3:
            raise ValueError("max_attempts must be 1..3")
        blocked_codes = node.get("blocked_exit_codes", [2, 78])
        if not isinstance(blocked_codes, list) or any(type(x) is not int or not 1 <= x <= 255 for x in blocked_codes):
            raise ValueError("blocked_exit_codes must contain nonzero exit codes")
        if not isinstance(node.get("depends_on"), list) or not all(isinstance(x, str) for x in node["depends_on"]):
            raise ValueError("depends_on must be a list")
        by_id[ident] = node
    visiting, visited = set(), set()
    def visit(ident):
        if ident not in by_id or ident in visiting:
            raise ValueError("unknown dependency or cycle")
        if ident in visited:
            return
        visiting.add(ident)
        for dependency in by_id[ident]["depends_on"]:
            visit(dependency)
        visiting.remove(ident)
        visited.add(ident)
    for ident in by_id:
        visit(ident)
    for node in nodes:
        if "review_of" in node:
            reviewed = node["review_of"]
            if reviewed not in node["depends_on"] or reviewed not in by_id or by_id[reviewed]["role"] != "builder":
                raise ValueError("review_of must be a direct Builder dependency")
    builders = [x for x in nodes if x["authorized"] and x["role"] == "builder"]
    for i, first in enumerate(builders):
        for second in builders[i + 1:]:
            if any(overlap(a, b) for a in first["scope"] for b in second["scope"]):
                raise ValueError("builder scopes overlap; split ownership or use a separate plan")
    return plan


class Runtime:
    def __init__(self, repo, plan):
        self.repo = Path(repo).resolve()
        self.common = common_dir(self.repo)
        self.root = self.common / "agent-coordination" / "runtime"
        self.directory = self.root / plan["id"]
        for path in (self.root, self.directory):
            if path.is_symlink():
                raise ValueError("runtime directory cannot be a symlink")
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        builder_paths = [(self.repo / n["cwd"]).resolve() for n in plan["nodes"] if n["authorized"] and n["role"] == "builder"]
        if len(set(builder_paths)) != len(builder_paths):
            raise ValueError("each builder requires a distinct checkout")
        self.plan = plan
        self.plan_hash = digest(plan)
        self.db = sqlite3.connect(self.directory / "state.sqlite", timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, state TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0, run_id TEXT, reason TEXT, head TEXT,
            uncertain INTEGER NOT NULL DEFAULT 0, initial_head TEXT, initial_branch TEXT,
            retry_allowed INTEGER NOT NULL DEFAULT 1);
          CREATE TABLE IF NOT EXISTS worktrees (node TEXT PRIMARY KEY, path TEXT UNIQUE NOT NULL,
            branch TEXT NOT NULL, integrated_head TEXT, integration_sha TEXT, removed INTEGER DEFAULT 0);
          CREATE TABLE IF NOT EXISTS outbox (sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL, node_id TEXT NOT NULL, run_id TEXT, payload TEXT NOT NULL,
            created_at REAL NOT NULL, UNIQUE(kind,run_id));
          CREATE TABLE IF NOT EXISTS consumers (name TEXT PRIMARY KEY, ack_cursor INTEGER NOT NULL DEFAULT 0,
            delivered_cursor INTEGER NOT NULL DEFAULT 0, last_seen REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS task_bindings (run_id TEXT PRIMARY KEY, node_id TEXT NOT NULL,
            native_task_id TEXT NOT NULL UNIQUE);
          CREATE TABLE IF NOT EXISTS attempts (run_id TEXT PRIMARY KEY, node_id TEXT NOT NULL);
        """)
        # Pre-dispatch notices describe a node, not an invented worker attempt.
        if next(r for r in self.db.execute("PRAGMA table_info(outbox)") if r[1] == "run_id")[3]:
            self.db.execute("BEGIN IMMEDIATE")
            if next(r for r in self.db.execute("PRAGMA table_info(outbox)") if r[1] == "run_id")[3]:
                sequence = self.db.execute("SELECT seq FROM sqlite_sequence WHERE name='outbox'").fetchone()
                self.db.execute("ALTER TABLE outbox RENAME TO outbox_previous")
                self.db.execute("CREATE TABLE outbox(sequence INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,node_id TEXT NOT NULL,run_id TEXT,payload TEXT NOT NULL,created_at REAL NOT NULL,UNIQUE(kind,run_id))")
                self.db.execute("INSERT INTO outbox SELECT * FROM outbox_previous")
                self.db.execute("DROP TABLE outbox_previous")
                if sequence:
                    self.db.execute("INSERT INTO sqlite_sequence(name,seq) SELECT 'outbox',? WHERE NOT EXISTS(SELECT 1 FROM sqlite_sequence WHERE name='outbox')", (sequence[0],))
                    self.db.execute("UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name='outbox'", (sequence[0],))
            self.db.commit()
        self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS outbox_preflight_notice ON outbox(node_id,payload) WHERE kind='pre-dispatch-blocked'")
        if "uncertain" not in {r[1] for r in self.db.execute("PRAGMA table_info(nodes)")}:
            self.db.execute("ALTER TABLE nodes ADD COLUMN uncertain INTEGER NOT NULL DEFAULT 0")
        for column, definition in (("initial_head", "TEXT"), ("initial_branch", "TEXT"), ("retry_allowed", "INTEGER NOT NULL DEFAULT 1"), ("expected_review_sha", "TEXT")):
            if column not in {r[1] for r in self.db.execute("PRAGMA table_info(nodes)")}:
                self.db.execute("ALTER TABLE nodes ADD COLUMN " + column + " " + definition)
        self.db.execute("BEGIN IMMEDIATE")
        existing = self.db.execute("SELECT value FROM metadata WHERE key='plan_hash'").fetchone()
        if existing and existing[0] != self.plan_hash:
            raise ValueError("plan hash changed: reconcile authorized scope using a new explicit plan id")
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('plan_hash', ?)", (self.plan_hash,))
        for node in plan["nodes"]:
            self.db.execute("INSERT OR IGNORE INTO nodes (id,state) VALUES (?, 'pending')", (node["id"],))
        self.db.execute("INSERT OR IGNORE INTO attempts SELECT run_id,id FROM nodes WHERE run_id IS NOT NULL")
        self.db.commit()

    @contextlib.contextmanager
    def lock(self):
        path = self.root / "controller.lock"
        if path.is_symlink():
            raise ValueError("runtime lock cannot be a symlink")
        with path.open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ControllerBusy("another controller is active; dispatch/cleanup was not repeated") from None
            yield

    def rows(self):
        return {r["id"]: dict(r) for r in self.db.execute("SELECT * FROM nodes")}

    def update(self, ident, **fields):
        self.db.execute("UPDATE nodes SET " + ",".join(k + "=?" for k in fields) + " WHERE id=?", (*fields.values(), ident))
        self.db.commit()
        if fields.get("state") == "blocked":
            row = self.rows()[ident]
            if not row["run_id"]:
                emit_event(self.directory / "state.sqlite", "pre-dispatch-blocked", {"node_id": ident, "run_id": None},
                           {"reported_state": "blocked", "result_available": False, "attempt_started": False, "reason": row["reason"],
                            "notice_id": digest({"plan_hash": self.plan_hash, "node_id": ident, "reason": row["reason"], "attempts": row["attempts"]})})
            elif not (self.attempt(row) / "result.json").exists():
                emit_event(self.directory / "state.sqlite", "attention-required", {"node_id": ident, "run_id": row["run_id"]},
                           {"reported_state": "unverified", "result_available": False, "reason": row["reason"]})

    def node(self, ident):
        return next(n for n in self.plan["nodes"] if n["id"] == ident)

    def review_sha(self, node):
        if node["role"] not in REVIEW_ROLES:
            return None
        if "review_of" in node:
            source = self.rows()[node["review_of"]]
            if source["state"] != "complete" or not source["head"]:
                raise ValueError("reviewed Builder result is not available")
            expected = source["head"]
        else:
            expected = node["review_sha"]
        git(self.repo, "cat-file", "-e", expected + "^{commit}")
        for dependency in node["depends_on"]:
            if self.node(dependency)["role"] == "builder":
                source = self.rows()[dependency]
                if source["state"] != "complete" or git(self.repo, "merge-base", "--is-ancestor", source["head"], expected, check=False).returncode:
                    raise ValueError("review artifact does not include dependency Builder " + dependency)
        return expected

    def workspace(self, node):
        path = (self.repo / node["cwd"]).resolve()
        if not path.is_dir() or common_dir(path) != self.common:
            raise ValueError("node cwd must be an existing checkout of this repository")
        if node["role"] == "builder":
            top = Path(git(path, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
            branch = git(path, "branch", "--show-current").stdout.strip()
            if path == self.repo or path != top or not branch or branch == self.plan["integration_branch"]:
                raise ValueError("builder needs a dedicated feature checkout, never the integration checkout")
            if git(self.repo, "worktree", "list", "--porcelain", "-z").stdout.split("\0").count("branch refs/heads/" + branch) > 1:
                raise ValueError("builder branch is checked out more than once")
            if git(path, "status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
                raise ValueError("builder checkout has pre-existing uncommitted changes")
        elif node["role"] in REVIEW_ROLES:
            if git(path, "status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
                raise ValueError("review requires a clean checkout of the evaluated commit")
            if git(path, "rev-parse", "HEAD").stdout.strip() != self.review_sha(node):
                raise ValueError("review checkout HEAD does not match the expected reviewed artifact")
        return path

    def attempt(self, row):
        return self.directory / "runs" / row["run_id"]

    def reconcile(self):
        for ident, row in self.rows().items():
            if row["state"] not in {"launching", "running"}:
                continue
            try:
                self.reconcile_attempt(ident, row)
            except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, subprocess.CalledProcessError) as error:
                self.update(ident, state="blocked", uncertain=1, reason="unverified execution receipts: " + str(error))

    def reconcile_attempt(self, ident, row):
        directory = self.attempt(row)
        result = directory / "result.json"
        launch = directory / "launch.json"
        if result.exists():
            outcome = read_object(result)
            config = read_object(directory / "config.json")
            checks = outcome.get("checks", [])
            if outcome.get("state") not in {"complete", "failed", "blocked"} or not isinstance(checks, list) or any(not isinstance(c, dict) for c in checks):
                raise ValueError("invalid result state or checks collection")
            if outcome.get("reason") is not None and not isinstance(outcome["reason"], str):
                raise ValueError("invalid result reason")
            if any(type(c.get("exit_code")) is not int or type(c.get("timed_out")) is not bool or not isinstance(c.get("argv_sha256"), str) for c in checks):
                raise ValueError("invalid acceptance check receipt")
            identity = (outcome.get("plan_hash") == self.plan_hash and outcome.get("node_id") == ident
                        and outcome.get("run_id") == row["run_id"] and config.get("node") == self.node(ident)
                        and config.get("plan_hash") == self.plan_hash and config.get("run_id") == row["run_id"]
                        and config.get("cwd") == str((self.repo / self.node(ident)["cwd"]).resolve())
                        and config.get("initial_head") == row["initial_head"] and config.get("initial_branch") == row["initial_branch"]
                        and config.get("expected_review_sha") == row["expected_review_sha"])
            accepted_node = self.node(ident)
            expected = [digest(x) for x in [accepted_node["argv"], *accepted_node["acceptance"]]]
            actual = [c.get("argv_sha256") for c in checks]
            complete = identity and outcome.get("state") == "complete" and actual == expected and all(c.get("exit_code") == 0 and c.get("timed_out") is False for c in checks)
            if not identity:
                self.update(ident, state="blocked", uncertain=1, reason="receipt identity mismatch")
            elif complete and (not isinstance(outcome.get("head"), str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", outcome["head"])):
                self.update(ident, state="blocked", uncertain=1, reason="result is missing a full evaluated commit SHA")
            elif complete:
                git(self.repo, "cat-file", "-e", outcome["head"] + "^{commit}")
                if accepted_node["role"] == "builder":
                    if (outcome.get("initial_head") != row["initial_head"] or outcome.get("initial_branch") != row["initial_branch"]
                            or outcome.get("branch") != row["initial_branch"] or outcome["head"] == row["initial_head"]):
                        raise ValueError("builder receipt requires unchanged branch and a new commit")
                    if git(self.repo, "merge-base", "--is-ancestor", row["initial_head"], outcome["head"], check=False).returncode:
                        raise ValueError("builder result does not descend from its initial commit")
                elif accepted_node["role"] in REVIEW_ROLES:
                    if outcome.get("reviewed_sha") != row["expected_review_sha"] or outcome["head"] != row["expected_review_sha"]:
                        raise ValueError("review receipt does not match the host-bound reviewed artifact")
                self.update(ident, state="complete", uncertain=0, reason=None, head=outcome.get("head"))
            elif outcome.get("state") == "complete":
                self.update(ident, state="blocked", uncertain=1, reason="incomplete or invalid acceptance receipt")
            else:
                self.update(ident, state="blocked" if outcome.get("state") == "blocked" else "failed", uncertain=0, reason=outcome.get("reason", "worker/check failed"))
        elif launch.exists():
            receipt = read_object(launch)
            if receipt.get("run_id") != row["run_id"] or receipt.get("plan_hash") != self.plan_hash or receipt.get("node_id") != ident:
                self.update(ident, state="blocked", uncertain=1, reason="invalid launch identity")
            elif live(receipt):
                self.update(ident, state="running", reason=None)
            else:
                self.update(ident, state="blocked", uncertain=1, reason="worker ended without result; audit side effects before explicit resolve")
        else:
            spawned = directory / "spawn.json"
            if spawned.exists():
                hint = read_object(spawned)
                if hint.get("run_id") != row["run_id"] or hint.get("plan_hash") != self.plan_hash or hint.get("node_id") != ident:
                    raise ValueError("invalid spawn identity")
                if hint.get("process_started") and live(hint):
                    return
            # A crash between reserving an attempt and recording Popen is ambiguous.
            self.update(ident, state="blocked", uncertain=1, reason="launch receipt missing; audit side effects before explicit resolve")

    def ensure_events(self):
        """Recover only missing delivery records, never repeat worker commands."""
        known = {r[0] for r in self.db.execute("SELECT run_id FROM outbox WHERE kind='result-ready'")}
        attempts = {r["run_id"]: r["node_id"] for r in self.db.execute("SELECT * FROM attempts")}
        for receipt in (self.directory / "runs").glob("*/result.json"):
            if receipt.parent.name in known:
                continue
            ident = attempts.get(receipt.parent.name)
            if not ident:
                continue
            identity = {"run_id": receipt.parent.name, "node_id": ident}
            try:
                config = read_object(receipt.parent / "config.json")
                if config.get("plan_hash") != self.plan_hash or config.get("run_id") != receipt.parent.name or config.get("node", {}).get("id") != ident:
                    raise ValueError("cannot recover event from an unrelated attempt")
                outcome = read_object(receipt)
                payload = result_event(receipt.parent, outcome)
            except (OSError, ValueError, TypeError, AttributeError) as error:
                payload = {"reported_state": "unverified", "receipt_error": str(error)}
            emit_event(self.directory / "state.sqlite", "result-ready", identity, payload)

    def consumer_status(self, consumer, stale_after=None):
        row = self.db.execute("SELECT * FROM consumers WHERE name=?", (consumer,)).fetchone()
        cursor = row["ack_cursor"] if row else 0
        oldest = self.db.execute("SELECT MIN(created_at) FROM outbox WHERE sequence>?", (cursor,)).fetchone()[0]
        pending = self.db.execute("SELECT COUNT(*) FROM outbox WHERE sequence>?", (cursor,)).fetchone()[0]
        age = max(0, time.time() - oldest) if oldest is not None else None
        stale = None if stale_after is None else (not row or time.time() - row["last_seen"] > stale_after or (age is not None and age > stale_after))
        return {"name": consumer, "registered": bool(row), "ack_cursor": cursor,
                "delivered_cursor": row["delivered_cursor"] if row else 0,
                "pending_events": pending, "oldest_unacked_age_seconds": age, "stale": stale}

    def events(self, consumer, limit):
        try:
            with self.lock():
                self.reconcile()
        except ControllerBusy:
            pass
        self.ensure_events()
        self.db.execute("INSERT OR IGNORE INTO consumers(name,last_seen) VALUES(?,?)", (consumer, time.time()))
        cursor = self.consumer_status(consumer)["ack_cursor"]
        rows = self.db.execute("""SELECT e.*,b.native_task_id FROM outbox e
          LEFT JOIN task_bindings b ON b.run_id=e.run_id
          WHERE e.sequence>? ORDER BY e.sequence LIMIT ?""", (cursor, limit)).fetchall()
        end = rows[-1]["sequence"] if rows else cursor
        self.db.execute("UPDATE consumers SET delivered_cursor=MAX(delivered_cursor,?),last_seen=? WHERE name=?", (end, time.time(), consumer))
        self.db.commit()
        states = self.rows()
        return {"plan_id": self.plan["id"], "consumer": consumer, "ack_cursor": cursor, "next_cursor": end,
                "events": [{**dict(row), "payload": json.loads(row["payload"]), "execution_state": states.get(row["node_id"], {}).get("state", "unverified")} for row in rows]}

    def ack(self, consumer, through):
        with self.db:
            row = self.db.execute("SELECT * FROM consumers WHERE name=?", (consumer,)).fetchone()
            if not row or through > row["delivered_cursor"]:
                raise ValueError("cannot acknowledge events that this consumer has not polled")
            if through > row["ack_cursor"] and not self.db.execute("SELECT 1 FROM outbox WHERE sequence=?", (through,)).fetchone():
                raise ValueError("ack cursor must identify a delivered event")
            self.db.execute("UPDATE consumers SET ack_cursor=MAX(ack_cursor,?),last_seen=? WHERE name=?", (through, time.time(), consumer))
        return self.consumer_status(consumer)

    def bind_task(self, ident, run_id, native_task_id):
        if not re.fullmatch(r"[0-9a-f]{32}", run_id) or not native_task_id or len(native_task_id) > 256 or any(c in native_task_id for c in "\n\r\0"):
            raise ValueError("invalid run id or native task id")
        config = read_object(self.directory / "runs" / run_id / "config.json")
        if config.get("plan_hash") != self.plan_hash or config.get("node") != self.node(ident):
            raise ValueError("native task mapping does not match this attempt")
        with self.db:
            previous = self.db.execute("SELECT native_task_id FROM task_bindings WHERE run_id=?", (run_id,)).fetchone()
            if previous and previous[0] != native_task_id:
                raise ValueError("native task id is already bound")
            self.db.execute("INSERT OR IGNORE INTO task_bindings VALUES(?,?,?)", (run_id, ident, native_task_id))
        return {"node_id": ident, "run_id": run_id, "native_task_id": native_task_id}

    def status(self, consumer="main", stale_after=None):
        self.ensure_events()
        rows = self.rows()
        cursor = self.consumer_status(consumer, stale_after)
        notices = self.db.execute("SELECT sequence,node_id,run_id,kind FROM outbox ORDER BY sequence").fetchall()
        available = {r["run_id"]: r for r in notices if r["run_id"]}
        preflight = {r["node_id"]: r for r in notices if r["kind"] == "pre-dispatch-blocked"}
        native_tasks = {r["run_id"]: r["native_task_id"] for r in self.db.execute("SELECT * FROM task_bindings")}
        accepted = [n for n in self.plan["nodes"] if n["authorized"]]
        output = []
        for node in self.plan["nodes"]:
            row = rows[node["id"]]
            if not node["authorized"]:
                reason = "not authorized"
            elif row["state"] == "pending":
                unauthorized = [x for x in node["depends_on"] if not self.node(x)["authorized"]]
                dependencies = [x for x in node["depends_on"] if rows[x]["state"] != "complete"]
                reason = ("unauthorized dependencies: " + ",".join(unauthorized) if unauthorized
                          else "dependencies: " + ",".join(dependencies) if dependencies else "ready for dispatch")
            else:
                reason = row["reason"]
            notice = available.get(row["run_id"]) if row["run_id"] else preflight.get(node["id"]) if row["state"] == "blocked" else None
            if notice is not None:
                received = notice["sequence"] <= cursor["ack_cursor"]
                delivery = ("received" if received else "result-ready") if notice["kind"] == "result-ready" else "received-attention" if received else "attention-required"
            else:
                delivery = "running" if row["run_id"] else "not-started"
            output.append({**row, "authorized": node["authorized"], "role": node["role"], "reason": reason, "delivery_state": delivery,
                           "native_task_id": native_tasks.get(row["run_id"]),
                           "receipt": f"{self.plan['id']}/runs/{row['run_id']}/result.json" if row["run_id"] else None})
        deliveries = {r["id"]: r["delivery_state"] for r in output}
        return {"plan_id": self.plan["id"], "plan_hash": self.plan_hash,
                "complete": bool(accepted) and all(rows[n["id"]]["state"] == "complete" for n in accepted),
                "results_received": bool(accepted) and not cursor["pending_events"] and all(deliveries[n["id"]] == "received" for n in accepted),
                "consumer": cursor, "nodes": output}

    def run(self):
        lease = self.root / "active-plan.json"
        children = {}
        with self.lock():
            if lease.exists():
                owner = json.loads(lease.read_text())
                if owner != {"id": self.plan["id"], "hash": self.plan_hash}:
                    raise RuntimeError("another plan has unfinished execution; resume it before starting a new plan")
            atomic_json(lease, {"id": self.plan["id"], "hash": self.plan_hash})
            # No new process may be launched before old receipts are reconciled.
            self.reconcile()
            while not STOP:
                rows = self.rows()
                running = sum(r["state"] in {"launching", "running"} for r in rows.values())
                occupied = running + sum(r["uncertain"] for r in rows.values() if r["state"] not in {"launching", "running"})
                for node in self.plan["nodes"]:
                    if STOP:
                        break
                    row = rows[node["id"]]
                    retry = row["state"] == "failed" and row["retry_allowed"] and row["attempts"] < node["max_attempts"]
                    ready = row["state"] == "pending" or retry
                    if not node["authorized"] or not ready or occupied >= self.plan["capacity"]:
                        continue
                    if any(not self.node(x)["authorized"] or rows[x]["state"] != "complete" for x in node["depends_on"]):
                        continue
                    try:
                        cwd = self.workspace(node)
                        expected_review_sha = self.review_sha(node)
                    except (ValueError, subprocess.CalledProcessError) as error:
                        self.update(node["id"], state="blocked", run_id=None, reason=str(error))
                        continue
                    if STOP:
                        break
                    run_id = uuid.uuid4().hex
                    directory = self.directory / "runs" / run_id
                    directory.mkdir(parents=True, mode=0o700)
                    initial_head = git(cwd, "rev-parse", "HEAD").stdout.strip()
                    initial_branch = git(cwd, "branch", "--show-current").stdout.strip()
                    atomic_json(directory / "config.json", {"plan_hash": self.plan_hash, "node": node, "cwd": str(cwd), "run_id": run_id,
                                                           "initial_head": initial_head, "initial_branch": initial_branch, "expected_review_sha": expected_review_sha})
                    self.db.execute("INSERT INTO attempts VALUES(?,?)", (run_id, node["id"]))
                    self.update(node["id"], state="launching", run_id=run_id, attempts=row["attempts"] + 1, reason=None,
                                initial_head=initial_head, initial_branch=initial_branch, expected_review_sha=expected_review_sha)
                    with (directory / "wrapper.log").open("wb") as log:
                        if STOP:
                            self.db.execute("DELETE FROM attempts WHERE run_id=?", (run_id,))
                            self.update(node["id"], state=row["state"], run_id=row["run_id"], attempts=row["attempts"],
                                        initial_head=row["initial_head"], initial_branch=row["initial_branch"], expected_review_sha=row["expected_review_sha"], reason="dispatch cancelled before launch")
                            break
                        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "worker", str(directory)], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
                        children[run_id] = process
                    # Only the worker records its own launch identity. Retain the PID as a hint,
                    # never as proof of successful launch or completion.
                    atomic_json(directory / "spawn.json", {"pid": process.pid, "process_started": fingerprint(process.pid),
                                                          "node_id": node["id"], "run_id": run_id, "plan_hash": self.plan_hash})
                    running += 1
                    occupied += 1
                if running:
                    time.sleep(0.1)
                    self.reconcile()
                    continue
                break
            if STOP:
                # Own Popen handles remain authoritative even before launch.json exists.
                # TERM lets a started wrapper stop its separately grouped command first.
                for process in children.values():
                    if process.poll() is None:
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGTERM)
                for row in self.rows().values():
                    if row["state"] in {"launching", "running"} and row["run_id"] not in children:
                        receipt = self.attempt(row) / "launch.json"
                        if receipt.exists():
                            try:
                                info = read_object(receipt)
                                if live(info):
                                    os.kill(info["pid"], signal.SIGTERM)
                            except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
                                self.update(row["id"], state="blocked", uncertain=1, reason="cannot verify cancellation target: " + str(error))
                deadline = time.monotonic() + 2
                for process in children.values():
                    try:
                        process.wait(timeout=max(0, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=1)
                self.reconcile()
            final = self.status()
            ambiguous = any(r["state"] in {"launching", "running"} or r["uncertain"] for r in self.rows().values())
            if not ambiguous and lease.exists():
                lease.unlink()
            return final

    def resolve(self, ident, decision, reason):
        with self.lock():
            self.reconcile()
            row = self.rows()[ident]
            if row["state"] != "blocked":
                raise ValueError("only a blocked ambiguous attempt may be explicitly resolved")
            if row["run_id"]:
                known_identity = None
                for name in ("launch.json", "spawn.json"):
                    try:
                        receipt = read_object(self.attempt(row) / name)
                        if receipt.get("run_id") != row["run_id"] or receipt.get("plan_hash") != self.plan_hash or receipt.get("node_id") != ident:
                            continue
                        alive = live(receipt)
                    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
                        continue
                    if alive:
                        raise ValueError("worker is still alive; do not replay it")
                    known_identity = receipt
                    break
                if known_identity is None:
                    raise ValueError("cannot establish worker identity; audit and repair identity evidence before resolve")
            if decision == "retry" and row["attempts"] >= self.node(ident)["max_attempts"]:
                raise ValueError("attempt budget exhausted")
            self.update(ident, state="pending" if decision == "retry" else "failed", retry_allowed=int(decision == "retry"),
                        uncertain=0, reason="operator audited side effects: " + reason)

    def worktree_add(self, ident, branch, start):
        with self.lock():
            node = self.node(ident)
            path = (self.repo / node["cwd"]).resolve()
            if not node["authorized"] or node["role"] != "builder" or path.exists() or path == self.common or self.common in path.parents:
                raise ValueError("only an authorized builder can create a fresh dedicated checkout")
            if self.repo in path.parents and git(self.repo, "check-ignore", "-q", "--", str(path.relative_to(self.repo)), check=False).returncode:
                raise ValueError("worktree directory inside the repository must be ignored before creation")
            if branch == self.plan["integration_branch"] or git(self.repo, "check-ref-format", "--branch", branch, check=False).returncode:
                raise ValueError("invalid feature branch")
            if self.db.execute("SELECT 1 FROM worktrees WHERE node=?", (ident,)).fetchone():
                raise ValueError("node already owns a worktree")
            git(self.repo, "worktree", "add", "-b", branch, str(path), start)
            self.db.execute("INSERT INTO worktrees(node,path,branch) VALUES(?,?,?)", (ident, str(path), branch))
            self.db.commit()

    def integrated(self, ident, commit):
        with self.lock():
            self.reconcile()
            row = self.rows()[ident]
            owned = self.db.execute("SELECT * FROM worktrees WHERE node=? AND removed=0", (ident,)).fetchone()
            if row["state"] != "complete" or not owned:
                raise ValueError("integration requires completed node and runtime-owned worktree")
            head = git(owned["path"], "rev-parse", "HEAD").stdout.strip()
            target = git(self.repo, "rev-parse", "--verify", "--end-of-options", "refs/heads/" + self.plan["integration_branch"] + "^{commit}").stdout.strip()
            if not re.fullmatch(r"[0-9a-f]{40,64}", commit) or target != commit or head != row["head"]:
                raise ValueError("integration SHA must be current target tip and worktree head must match accepted result")
            if git(self.repo, "merge-base", "--is-ancestor", head, commit, check=False).returncode:
                raise ValueError("node commits are not integrated into target")
            self.db.execute("UPDATE worktrees SET integrated_head=?,integration_sha=? WHERE node=?", (head, commit, ident))
            self.db.commit()

    def cleanup(self):
        output = []
        with self.lock():
            self.reconcile()
            records = {}
            record = None
            for field in git(self.repo, "worktree", "list", "--porcelain", "-z").stdout.split("\0"):
                if field.startswith("worktree "):
                    record = {}
                    records[str(Path(field[9:]).resolve())] = record
                elif field and record is not None:
                    key, _, value = field.partition(" ")
                    record[key] = value
            for row in self.db.execute("SELECT * FROM worktrees WHERE removed=0").fetchall():
                reason = None
                path = Path(row["path"])
                metadata = records.get(str(path))
                state = self.rows()[row["node"]]["state"]
                if not row["integration_sha"]:
                    reason = "no confirmed integration event"
                elif path == self.repo or path == Path.cwd().resolve() or path in Path.cwd().resolve().parents:
                    reason = "current checkout"
                elif metadata is None or "locked" in metadata or "prunable" in metadata:
                    reason = "missing, locked or prunable checkout"
                elif state != "complete":
                    reason = "execution is incomplete or ambiguous"
                elif metadata.get("branch") != "refs/heads/" + row["branch"] or metadata.get("HEAD") != row["integrated_head"]:
                    reason = "branch/head changed after integration"
                elif git(self.repo, "merge-base", "--is-ancestor", row["integrated_head"], "refs/heads/" + self.plan["integration_branch"], check=False).returncode:
                    reason = "accepted commit no longer reachable from integration branch"
                elif git(path, "status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching").stdout.strip():
                    reason = "dirty checkout including untracked/ignored files"
                if reason:
                    output.append({"node": row["node"], "removed": False, "reason": reason})
                    continue
                # Git provides a final independent dirty/locked check. Never force, prune or delete branches.
                result = git(self.repo, "worktree", "remove", str(path), check=False)
                if result.returncode:
                    output.append({"node": row["node"], "removed": False, "reason": "git refused removal"})
                else:
                    self.db.execute("UPDATE worktrees SET removed=1 WHERE node=?", (row["node"],))
                    self.db.commit()
                    output.append({"node": row["node"], "removed": True})
        return {"post_integration": output}


def request_stop(signum, frame):
    global STOP
    STOP = True


def execute(command, cwd, directory, number, deadline, environment):
    started = time.monotonic()
    if STOP or started >= deadline:
        return {"argv_sha256": digest(command), "exit_code": 130 if STOP else 124, "timed_out": not STOP, "duration_seconds": 0}
    with (directory / f"command-{number}.stdout").open("wb") as stdout, (directory / f"command-{number}.stderr").open("wb") as stderr:
        child = subprocess.Popen(command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, start_new_session=True)
        timed_out = False
        while child.poll() is None:
            if STOP or time.monotonic() >= deadline:
                timed_out = not STOP
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                # Descendants can keep running after their leader exits on TERM.
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                break
            time.sleep(0.025)
        lingering = False
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            pass
        else:
            lingering = True
            os.killpg(child.pid, signal.SIGKILL)
    return {"argv_sha256": digest(command), "exit_code": 130 if STOP else 124 if timed_out else child.returncode if child.returncode else 125 if lingering else 0,
            "timed_out": timed_out, "duration_seconds": round(time.monotonic() - started, 4)}


def worker(directory):
    directory = Path(directory)
    config = json.loads((directory / "config.json").read_text())
    node = config["node"]
    identity = {"plan_hash": config["plan_hash"], "run_id": config["run_id"], "node_id": node["id"]}
    outcome = {**identity, "state": "failed", "checks": [], "reason": "worker initialization failed"}
    try:
        atomic_json(directory / "launch.json", {**identity, "pid": os.getpid(), "process_started": fingerprint(os.getpid())})
        initial_head = git(config["cwd"], "rev-parse", "HEAD").stdout.strip()
        initial_branch = git(config["cwd"], "branch", "--show-current").stdout.strip()
        if initial_head != config["initial_head"] or initial_branch != config["initial_branch"]:
            raise ValueError("workspace changed after dispatch")
        environment = {k: v for k, v in os.environ.items() if not k.startswith("TOOLKIT_")}
        environment.update(TOOLKIT_NODE_ID=node["id"], TOOLKIT_RUN_ID=config["run_id"])
        expected_review_sha = config.get("expected_review_sha")
        if node["role"] in REVIEW_ROLES:
            if not expected_review_sha or initial_head != expected_review_sha:
                raise ValueError("initial checkout does not match the host-bound reviewed artifact")
            environment["TOOLKIT_REVIEW_SHA"] = expected_review_sha
            if "review_of" in node:
                environment["TOOLKIT_REVIEW_OF"] = node["review_of"]
        deadline = time.monotonic() + node["timeout_seconds"]
        for number, command in enumerate([node["argv"], *node["acceptance"]]):
            check = execute(command, config["cwd"], directory, number, deadline, environment)
            outcome["checks"].append(check)
            if check["exit_code"] != 0:
                if check["exit_code"] in node.get("blocked_exit_codes", [2, 78]):
                    outcome["state"] = "blocked"
                outcome["reason"] = "cancelled" if STOP else "timeout" if check["timed_out"] else "worker command failed" if number == 0 else "acceptance failed"
                break
        else:
            head = git(config["cwd"], "rev-parse", "HEAD").stdout.strip()
            branch = git(config["cwd"], "branch", "--show-current").stdout.strip()
            if node["role"] == "builder":
                if git(config["cwd"], "status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
                    raise ValueError("builder result has uncommitted changes")
                if branch != initial_branch:
                    raise ValueError("builder changed its assigned branch")
                if head == initial_head:
                    raise ValueError("builder did not deliver a new commit")
                if git(config["cwd"], "merge-base", "--is-ancestor", initial_head, head, check=False).returncode:
                    raise ValueError("builder rewrote its initial history")
                changed = set(git(config["cwd"], "diff", "--no-renames", "--name-only", "-z", initial_head, head, "--").stdout.split("\0"))
                for commit in git(config["cwd"], "rev-list", initial_head + ".." + head, "--").stdout.splitlines():
                    changed.update(git(config["cwd"], "diff-tree", "-r", "-m", "--root", "--no-renames", "--no-commit-id", "--name-only", "-z", commit, "--").stdout.split("\0"))
                if any(path and not any(scope == "." or path == scope or path.startswith(scope + "/") for scope in node["scope"]) for path in changed):
                    raise ValueError("builder committed outside the accepted scope")
            elif node["role"] in REVIEW_ROLES:
                if head != expected_review_sha or git(config["cwd"], "status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
                    raise ValueError("evaluated source changed during review")
            outcome.update(state="complete", reason=None, head=head, branch=branch, initial_head=initial_head, initial_branch=initial_branch,
                           reviewed_sha=expected_review_sha)
    except (OSError, ValueError) as error:
        outcome.update(state="blocked", reason=type(error).__name__ + ": " + str(error))
    except Exception as error:
        outcome["reason"] = type(error).__name__ + ": " + str(error)
    atomic_json(directory / "result.json", outcome)
    emit_event(directory.parent.parent / "state.sqlite", "result-ready", identity, result_event(directory, outcome))
    return 0 if outcome["state"] == "complete" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "run", "resume", "status", "events", "watch", "ack", "bind-task", "resolve", "worktree-add", "integrated", "cleanup", "worker"])
    parser.add_argument("plan")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--node")
    parser.add_argument("--branch")
    parser.add_argument("--start-point", default="HEAD")
    parser.add_argument("--commit")
    parser.add_argument("--decision", choices=["retry", "failed"])
    parser.add_argument("--reason")
    parser.add_argument("--acknowledge-side-effects", action="store_true")
    parser.add_argument("--consumer", default="main")
    parser.add_argument("--through", type=int)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument("--shortest-worker-seconds", type=float)
    parser.add_argument("--max-wait", type=float)
    parser.add_argument("--stale-after-seconds", type=float)
    parser.add_argument("--run-id")
    parser.add_argument("--native-task-id")
    args = parser.parse_args()
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    try:
        if args.command == "worker":
            return worker(args.plan)
        plan = load_plan(args.plan)
        if args.command == "validate":
            print(json.dumps({"valid": True, "plan_hash": digest(plan)}))
            return 0
        runtime = Runtime(args.repo, plan)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", args.consumer) or not 1 <= args.limit <= 1000:
            raise ValueError("invalid consumer name or event batch limit")
        if args.stale_after_seconds is not None and not 0 < args.stale_after_seconds <= 86400:
            raise ValueError("stale-after-seconds must be positive and <=86400")
        if args.command in {"run", "resume"}:
            result = runtime.run()
        elif args.command in {"events", "watch"}:
            if args.command == "watch":
                if (args.poll_seconds is None or args.shortest_worker_seconds is None or args.max_wait is None
                        or not 0 < args.poll_seconds <= args.shortest_worker_seconds <= 86400 or not 0 < args.max_wait <= 60):
                    raise ValueError("watch requires explicit poll-seconds <= shortest-worker-seconds and max-wait (0..60 seconds)")
                deadline = time.monotonic() + args.max_wait
            else:
                deadline = time.monotonic()
            while True:
                result = runtime.events(args.consumer, args.limit)
                if result["events"] or args.command == "events" or time.monotonic() >= deadline or STOP:
                    result["timed_out"] = not result["events"] and args.command == "watch"
                    break
                time.sleep(min(args.poll_seconds, max(0, deadline - time.monotonic())))
        elif args.command == "ack":
            if args.through is None or args.through < 0:
                raise ValueError("ack requires a nonnegative --through sequence")
            result = runtime.ack(args.consumer, args.through)
        elif args.command == "bind-task":
            if not args.node or not args.run_id or not args.native_task_id:
                raise ValueError("bind-task requires node, run-id and native-task-id")
            result = runtime.bind_task(args.node, args.run_id, args.native_task_id)
        elif args.command == "status":
            try:
                with runtime.lock():
                    runtime.reconcile()
            except ControllerBusy:
                result = {**runtime.status(args.consumer, args.stale_after_seconds), "reconciliation": "active controller; database snapshot"}
            else:
                result = runtime.status(args.consumer, args.stale_after_seconds)
        elif args.command == "resolve":
            if not args.node or not args.decision or not args.reason or not args.acknowledge_side_effects:
                raise ValueError("resolve requires node, decision, reason and --acknowledge-side-effects")
            runtime.resolve(args.node, args.decision, args.reason)
            result = runtime.status()
        elif args.command == "worktree-add":
            if not args.node or not args.branch:
                raise ValueError("worktree-add requires node and branch")
            runtime.worktree_add(args.node, args.branch, args.start_point)
            result = {"created": args.node}
        elif args.command == "integrated":
            if not args.node or not args.commit:
                raise ValueError("integrated requires node and full target commit SHA")
            runtime.integrated(args.node, args.commit)
            result = {"integration_recorded": args.node, "commit": args.commit, **runtime.cleanup()}
        else:
            result = runtime.cleanup()
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0 if result.get("complete", True) else 1
    except (OSError, ValueError, KeyError, TypeError, StopIteration, RuntimeError, sqlite3.Error, subprocess.CalledProcessError) as error:
        print(json.dumps({"blocked": True, "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
