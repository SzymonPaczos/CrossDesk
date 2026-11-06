#!/usr/bin/env python3
"""Offline protocol fixture; no model, network, or production access."""
import json
import os
from pathlib import Path
import sys
import time


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def flag(name, default=""):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def tool(ident, name, args, content="created", error=False):
    emit({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": ident, "name": name, "input": args}]}})
    emit({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": ident, "content": content, "is_error": error}]}})


def main():
    if "--version" in sys.argv:
        print("0.0.0-offline-fixture")
        return
    model = flag("--model", "fixture-model")
    tools = flag("--tools", "Read,Glob,Grep").split(",")
    mode = os.environ.get("WORKFLOW_EVAL_FAKE_MODE", "normal")
    if mode == "extra_tool":
        tools.append("mcp__fixture__network")
    emit({"type": "system", "subtype": "init", "model": model, "tools": tools})
    emit({"type": "system", "subtype": "fixture-notice", "message": "string-valued system notice"})
    cost, turns = 0, 0
    for line in sys.stdin:
        message = json.loads(line)
        prompt = message["message"]["content"]
        turns += 1
        if mode == "hang" or mode == "hang_later" and turns > 1:
            time.sleep(30)
        if mode == "bad_stream":
            print("not-json", flush=True)
            continue
        if mode == "error":
            emit({"type": "result", "subtype": "error_fixture", "is_error": True, "result": "fixture error", "total_cost_usd": 0.12})
            continue
        notifications = False
        if "product/X1.txt" in prompt:
            if mode == "permission":
                tool("denied", "Write", {"file_path": "state/backlog.md"}, "Permission to use Write has been denied", True)
            else:
                for stage, value in [(1, "odczyt"), (2, "walidacja")]:
                    if mode == "missing_artifact" and stage == 2:
                        continue
                    Path(f"product/X{stage}.txt").write_text(value)
                    tool(f"write{stage}", "Write", {"file_path": f"product/X{stage}.txt"})
                if mode == "alias":
                    state = "### TASK-A — X3 remaining\nSTATUS: otwarte\n### TASK-B — X4 remaining\nSTATUS: otwarte\n"
                else:
                    state = "## Etapy odbioru\n- [x] X1 — odczyt\n- [x] X2 — walidacja\n- [ ] X3 — zapis\n- [ ] X4 — odbior\n"
                with Path("state/backlog.md").open("a") as stream:
                    stream.write(state)
            answer = "OK"
        elif "remaining_stage_ids" in prompt:
            answer = json.dumps({"completed": mode == "false_complete", "remaining_stage_ids": [] if mode == "false_complete" else ["TASK-A", "TASK-B"] if mode == "alias" else ["X3", "X4"], "next_action": "continue accepted remaining stages"})
        elif "product/a.txt" in prompt:
            for index, scope in enumerate(["product/a.txt", "product/b.txt"]):
                text = (f"Async agent launched successfully. agentId: worker-{index}" if mode.startswith("async") else "[Subagent hand-back] fixture finding")
                tool(f"worker{index}", "Agent", {"prompt": "Review only " + scope}, text)
            answer = "Two synthetic risks."
            notifications = mode == "async"
        elif "evidence.json" in prompt:
            evidence = json.loads(Path("evidence.json").read_text())
            if evidence["goal"].startswith("Brak"):
                delivery, drift = "unverified", None
            elif "Sandbox" in evidence["timeline"]:
                delivery, drift = "blocked", False
            elif "21 dni" in evidence["timeline"]:
                delivery, drift = "incomplete", True
            else:
                delivery, drift = "complete", False
            answer = json.dumps({"delivery": delivery, "process_drift": drift, "reason": "synthetic fixture premises"})
        elif "product/denied.txt" in prompt:
            if mode == "violate_readonly":
                Path("product/denied.txt").write_text("probe")
            answer = json.dumps({"completed": mode == "violate_readonly"})
        else:
            answer = "56" if "7 razy 8" in prompt else "CSV is a table; JSON is structured."
        cost += 0.01
        emit({"type": "result", "subtype": "success", "is_error": False, "result": answer,
              "total_cost_usd": cost, "modelUsage": {model: {}}})
        if notifications:
            for index in range(2):
                emit({"type": "system", "subtype": "task_notification", "task_id": f"worker-{index}",
                      "tool_use_id": f"worker{index}", "status": "completed", "summary": "fixture result"})


if __name__ == "__main__":
    main()
