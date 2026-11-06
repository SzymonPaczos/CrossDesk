#!/usr/bin/env python3
"""Check a single acceptance-stage list; evidence contents still need review."""
import argparse
import hashlib
from pathlib import Path
import posixpath
import re
import subprocess
import sys


def stages(path, task=None, *, reader=None, sources=None, select_optional=False):
    """Read only the selected task and its explicit acceptance section."""
    lines = (reader(str(path)) if reader else Path(path).read_text(encoding="utf-8")).splitlines()
    if sources is not None and reader is None:
        sources.add(Path(path).resolve())
    visible = []
    fence = None
    comment = False
    for line in lines:
        # Examples inside comments and fenced code are not executable plans.
        if fence is not None:
            closing = re.fullmatch(r"\s*(`{3,}|~{3,})\s*", line)
            if closing and closing[1][0] == fence[0] and len(closing[1]) >= len(fence):
                fence = None
            continue
        remainder = line
        clean = ""
        while remainder:
            if comment:
                _, end, remainder = remainder.partition("-->")
                if not end:
                    break
                comment = False
            else:
                before, start, remainder = remainder.partition("<!--")
                clean += before
                if not start:
                    break
                comment = True
        line = clean
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            fence = marker.group(1)
            continue
        visible.append(line)
    if fence or comment:
        raise ValueError("unclosed code fence or comment")
    if task:
        found = []
        selected = False
        matches = 0
        for line in visible:
            heading = re.match(r"^(#{1,3})\s+(.*)$", line)
            if heading:
                selected = bool(re.match(rf"^{re.escape(task)}(?:\s|$)", heading[2]))
                matches += selected
            if selected:
                found.append(line)
        if matches == 0 and select_optional and not any(re.match(r"^### [A-Z][A-Z0-9]*-\d{4}-\d{2}-\d{2}-\d+", line) for line in visible):
            return stages(path, reader=reader, sources=sources)
        if matches != 1:
            raise ValueError("task ID must occur in exactly one heading")
        visible = found
        brief = next((line.removeprefix("BRIEF:").strip() for line in visible if line.startswith("BRIEF:")), "")
        if brief and brief not in {"—", "-"}:
            if reader:
                linked = posixpath.normpath(posixpath.join(posixpath.dirname(str(path)), brief))
                parent = posixpath.dirname(str(path))
                if linked.startswith("/") or linked == ".." or linked.startswith("../") or (parent and not linked.startswith(parent + "/")):
                    raise ValueError("snapshot brief must remain inside the backlog directory")
            else:
                linked = (Path(path).parent / brief).resolve()
                if not linked.is_relative_to(Path(path).parent.resolve()):
                    raise ValueError("brief must remain inside the backlog directory")
            if any(re.match(r"^#{1,6}\s+Etapy odbioru\s*$", line) for line in visible):
                raise ValueError("stage list and BRIEF are both present; keep one acceptance source")
            return stages(linked, reader=reader, sources=sources)
    section = False
    level = 0
    sections = 0
    result = {}
    for line in visible:
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            if heading[2] == "Etapy odbioru":
                sections += 1
                level = len(heading[1])
                section = True
            elif section and len(heading[1]) <= level:
                section = False
            continue
        if not section or not line.strip():
            continue
        match = re.fullmatch(r"\s*- \[([ xX])\] ([A-Za-z0-9_-]+) [—–-] (.+?)\s*", line)
        if not match:
            raise ValueError("stage section must contain only stage checklist rows")
        checked, ident, body = match.groups()
        title, *metadata = body.split(" | ")
        if ident in result:
            raise ValueError(f"duplicate stage: {ident}")
        proof = next((m.removeprefix("DOWOD:").strip() for m in metadata if m.startswith("DOWOD:")), "")
        result[ident] = (title, checked.lower() == "x", proof)
    if sections != 1 or not result:
        raise ValueError("exactly one nonempty acceptance-stage section is required")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan")
    parser.add_argument("--task", help="select a task ID inside a backlog")
    base = parser.add_mutually_exclusive_group()
    base.add_argument("--baseline", help="previously accepted single-plan file, not a fresh copy")
    base.add_argument("--baseline-ref", help="accepted Git revision:path of the stage plan")
    args = parser.parse_args()
    try:
        sources = set()
        current = stages(args.plan, args.task, sources=sources)
        baseline = None
        origin = "not_provided"
        if args.baseline:
            if any(Path(args.baseline).samefile(path) for path in sources):
                raise ValueError("baseline cannot be the working plan itself")
            baseline_sources = set()
            baseline = stages(args.baseline, args.task, sources=baseline_sources, select_optional=True)
            if any(a.samefile(b) for a in sources for b in baseline_sources):
                raise ValueError("baseline links to the working acceptance plan")
            origin = "file-sha256:" + hashlib.sha256(Path(args.baseline).read_bytes()).hexdigest()
        elif args.baseline_ref:
            revision, separator, name = args.baseline_ref.partition(":")
            if not separator or not revision or not name:
                raise ValueError("baseline ref must be revision:path")
            sha = subprocess.run(["git", "rev-parse", "--verify", "--end-of-options", revision + "^{commit}"], capture_output=True, text=True, check=True).stdout.strip()
            def read_snapshot(path):
                return subprocess.run(["git", "show", sha + ":" + path], capture_output=True, text=True, check=True).stdout
            baseline = stages(name, args.task, reader=read_snapshot, select_optional=True)
            origin = sha + ":" + name
        if baseline is not None and {k: v[0] for k, v in current.items()} != {k: v[0] for k, v in baseline.items()}:
            raise ValueError("stage scope differs from baseline; reconcile the authorized scope change")
        pending = [k for k, v in current.items() if not v[1]]
        missing = [k for k, v in current.items() if v[1] and (not v[2] or v[2].lower() in {"—", "-", "n/a"} or "<" in v[2] or "TODO" in v[2])]
        print(f"TASK_STAGES_TOTAL: {len(current)}")
        print(f"TASK_STAGES_PENDING: {', '.join(pending) or 'none'}")
        print(f"TASK_EVIDENCE_MISSING: {', '.join(missing) or 'none'}")
        print(f"TASK_SCOPE_COMPARISON: {'matched' if baseline is not None else 'not_checked'}")
        print(f"TASK_BASELINE: {origin}")
        ready = not pending and not missing and baseline is not None
        status = "READY_FOR_REVIEW" if ready else "INCOMPLETE" if pending or missing else "SCOPE_UNVERIFIED"
        print(f"TASK_COMPLETION: {status}")
        return 0 if ready else 1
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"TASK_COMPLETION: INVALID ({exc})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
