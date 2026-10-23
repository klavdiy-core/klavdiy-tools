#!/usr/bin/env python3
"""claude_code_hook.py — wire absence_gate into Claude Code as a Stop (or PreToolUse) hook.

v0.6, outside review #4 (Fable 5.1, 23.10.2026): "the wire in Claude Code is cut". Claude Code blocks ONLY on exit 2, and
only stderr reaches the model; any other non-zero code is a non-blocking error and the action goes ahead; stdout on exit 0
is not shown to the model at all. absence_gate.py exits 4 / 5 — as a hook it stopped nothing, and a crash (no rg) was a
traceback, exit 1, fail-open. This wrapper translates:

  BLOCK                          -> exit 2, report on stderr (the model has to open the files and rewrite)
  REVIEW                         -> exit 2, report + what to do next (open these lines; rewrite, or say why they don't count)
                                    — except on a Stop hook that is already continuing (stop_hook_active): then exit 0,
                                    the agent has had its chance and REVIEW is a cost of one look, not a wall
  OK / NOT_APPLICABLE            -> exit 0
  anything broken                -> exit 2, GATE_BROKEN (a broken gate must not read as a pass)

Stop hook: checks `last_assistant_message` — Claude Code's own reply, not only a custom send tool.
PreToolUse hook: checks every string inside `tool_input` (e.g. the text of a message-sending tool).

Roots: --root DIR (repeatable) or the env var ABSENCE_GATE_ROOTS (paths joined by os.pathsep).
Profile: --block-only makes REVIEW pass (exit 0) everywhere; only BLOCK stops.

settings.json:
  {"hooks": {"Stop": [{"hooks": [{"type": "command",
     "command": "python /path/to/claude_code_hook.py --root /path/to/notes"}]}]}}
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NEXT = ("\nWhat to do now: open the lines above. Then either rewrite the reply so it says what the disk has, "
        "or say in the reply why those lines don't count (e.g. they name a different thing).")


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


def run(argv, stdin_text):
    """Returns (exit_code, stderr_text). Pure, so the tests can call it without a process."""
    roots = [argv[i + 1] for i, a in enumerate(argv) if a == "--root" and i + 1 < len(argv)]
    roots += [r for r in os.environ.get("ABSENCE_GATE_ROOTS", "").split(os.pathsep) if r]
    block_only = "--block-only" in argv
    try:
        import absence_gate
        event = json.loads(stdin_text or "{}")
        if not roots:
            return 2, "GATE_BROKEN: no roots (--root or ABSENCE_GATE_ROOTS) — nothing to search, refusing to pass silently"
        name = event.get("hook_event_name", "")
        continuing = bool(event.get("stop_hook_active"))
        if name == "Stop":
            text = event.get("last_assistant_message")
            if text is None:
                if continuing:
                    return 0, ""
                return 2, "GATE_BROKEN: Stop hook input has no last_assistant_message — this Claude Code version can't be checked"
        elif name == "PreToolUse":
            text = "\n".join(strings(event.get("tool_input", {})))
        else:
            return 2, f"GATE_BROKEN: unsupported hook event {name!r} (use Stop or PreToolUse)"
        code, msg = absence_gate.check(text, roots)
    except Exception as e:                                       # noqa: BLE001 — every failure must be loud
        return 2, f"GATE_BROKEN: {type(e).__name__}: {e}"
    if code == 4:
        return 2, msg + NEXT
    if code == 5:
        if block_only or continuing:
            return 0, ""
        return 2, msg + NEXT
    return 0, ""


def main():
    code, err = run(sys.argv[1:], sys.stdin.read())
    if err:
        sys.stderr.write(err + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
