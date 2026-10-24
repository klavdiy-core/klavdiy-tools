#!/usr/bin/env python3
"""done_check.py — a Stop hook: "done" means every command in TASK.md's Definition of done ran green after the last edit.

Write the definition of done once, in the project's TASK.md, with the checks as commands in backticks:

  ## Definition of done
  - [ ] `pytest -q tests/test_sync.py` passes
  - [ ] `ruff check deploy` is clean

When a reply says done / fixed / works and the project has such a section, each of those commands must appear as a
shell run after the last code edit, and must not have failed (exit code or output). Otherwise exit 2, with the list
of what is missing. No TASK.md, no section: nothing to check. Saying "I haven't run the checks" passes.
Failures are loud (GATE_BROKEN); stop_hook_active lets go once.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claim_check import CLAIM, EDIT_TOOLS, FAILED_OUTPUT, HONEST, SHELL_TOOLS, events, is_code  # noqa: E402

DONE = re.compile(r"\b(done|completed?|finished|ready)\b|\bготов\w*|\bсделан\w*|\bзакончил\w*", re.I)
SECTION = re.compile(r"^#{1,6}\s*definition\s+of\s+done\b.*$|^#{1,6}\s*критери\w*\s+готовности\b.*$", re.I | re.M)


def dod_commands(task_text):
    m = SECTION.search(task_text)
    if not m:
        return []
    rest = task_text[m.end():]
    nxt = re.search(r"^#{1,6}\s", rest, re.M)
    body = rest[:nxt.start()] if nxt else rest
    return [c.strip() for c in re.findall(r"`([^`\n]+)`", body) if c.strip()]


def _norm(s):
    return " ".join(str(s).split())


def verdict(evts, commands):
    results = {d["id"]: d for k, d in evts if k == "result"}
    last_edit = max([i for i, (k, d) in enumerate(evts) if k == "use" and d["name"] in EDIT_TOOLS
                     and is_code(d["input"].get("file_path") or d["input"].get("notebook_path"))], default=-1)
    runs = [d for k, d in evts[last_edit + 1:] if k == "use" and d["name"] in SHELL_TOOLS]
    missing = []
    for cmd in commands:
        mine = [r for r in runs if _norm(cmd) in _norm(r["input"].get("command", ""))]
        if not mine:
            missing.append(f"`{cmd}` (not run after the last edit)")
            continue
        res = results.get(mine[-1]["id"])
        if res is None or res["error"] or FAILED_OUTPUT.search(res["text"]):
            missing.append(f"`{cmd}` (its last run failed or has no result)")
    if not missing:
        return None
    return ("The reply says it is done, but the Definition of done in TASK.md is not met: " + "; ".join(missing)
            + ". Run them and read the output, or say plainly what is not done.")


def run(argv, stdin_text):
    """Returns (exit_code, stderr_text)."""
    try:
        event = json.loads(stdin_text or "{}")
        if event.get("stop_hook_active"):
            return 0, ""
        msg = event.get("last_assistant_message")
        if msg is None:
            return 2, "GATE_BROKEN: done_check: Stop hook input has no last_assistant_message"
        if not (DONE.search(msg) or CLAIM.search(msg)) or HONEST.search(msg):
            return 0, ""
        task = os.path.join(event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or ".", "TASK.md")
        if not os.path.exists(task):
            return 0, ""
        with open(task, encoding="utf-8", errors="replace") as f:
            commands = dod_commands(f.read())
        if not commands:
            return 0, ""
        path = event.get("transcript_path")
        if not path or not os.path.exists(path):
            return 2, "GATE_BROKEN: done_check: no transcript to check the claim against"
        why = verdict(events(path), commands)
        return (2, "DONE_UNCHECKED: " + why) if why else (0, "")
    except Exception as e:                                       # noqa: BLE001 — every failure must be loud
        return 2, f"GATE_BROKEN: done_check: {type(e).__name__}: {e}"


def main():
    try:
        code, err = run(sys.argv[1:], sys.stdin.buffer.read().decode("utf-8"))
    except Exception as e:                                       # noqa: BLE001
        code, err = 2, f"GATE_BROKEN: done_check: {type(e).__name__}: {e}"
    if err:
        sys.stderr.buffer.write((err + "\n").encode("utf-8"))
        sys.stderr.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
