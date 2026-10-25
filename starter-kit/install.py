#!/usr/bin/env python3
"""install.py — put the starter kit into a project: hooks into .claude/hooks/starter-kit/, wiring into
.claude/settings.json (merged, never replaced; a .bak is left), and CLAUDE.md only if the project has none.

    python install.py /path/to/project            # everything; absence-gate only if ripgrep (rg) is on PATH
    python install.py /path/to/project --no-absence-gate

Running it twice changes nothing the second time.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(os.path.dirname(HERE), "absence-gate")
PY = "python" if os.name == "nt" else "python3"


def _cmd(name, extra=""):
    return f'{PY} "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/starter-kit/{name}"{extra}'


def _add(hooks, event, matcher, command, marker):
    entries = hooks.setdefault(event, [])
    if any(marker in c.get("command", "") for h in entries for c in h.get("hooks", [])):
        return False
    entry = {"hooks": [{"type": "command", "command": command}]}
    if matcher:
        entry = {"matcher": matcher, **entry}
    entries.append(entry)
    return True


def install(project, with_absence_gate=True):
    project = os.path.abspath(project)
    dest = os.path.join(project, ".claude", "hooks", "starter-kit")
    os.makedirs(dest, exist_ok=True)
    for f in ("claim_check.py", "test_guard.py", "blame_check.py", "done_check.py"):
        shutil.copy2(os.path.join(HERE, "hooks", f), dest)
    gate = with_absence_gate and shutil.which("rg") is not None and os.path.isdir(GATE)
    if gate:
        for f in ("absence_gate.py", "claude_code_hook.py", "zero_search_hook.py"):
            shutil.copy2(os.path.join(GATE, f), dest)

    settings = os.path.join(project, ".claude", "settings.json")
    data = {}
    if os.path.exists(settings):
        with open(settings, encoding="utf-8") as f:
            data = json.load(f)
    hooks = data.setdefault("hooks", {})
    added = []
    if _add(hooks, "Stop", None, _cmd("claim_check.py"), "claim_check.py"):
        added.append("Stop: claim_check")
    if _add(hooks, "Stop", None, _cmd("blame_check.py"), "blame_check.py"):
        added.append("Stop: blame_check")
    if _add(hooks, "Stop", None, _cmd("done_check.py"), "done_check.py"):
        added.append("Stop: done_check")
    if _add(hooks, "PreToolUse", "Edit|MultiEdit|Write", _cmd("test_guard.py"), "test_guard.py"):
        added.append("PreToolUse(Edit|MultiEdit|Write): test_guard")
    if gate:
        if _add(hooks, "Stop", None, _cmd("claude_code_hook.py", ' --root "${CLAUDE_PROJECT_DIR}"'), "claude_code_hook.py"):
            added.append("Stop: absence-gate")
        if _add(hooks, "PostToolUse", "Grep", _cmd("zero_search_hook.py"), "zero_search_hook.py"):
            added.append("PostToolUse(Grep): zero-search")
    if added:                              # nothing new -> the file and its .bak (the user's original) stay untouched
        if os.path.exists(settings):
            shutil.copy2(settings, settings + ".bak")
        with open(settings, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # canaries, so `python hook_doctor.py` run in the project proves the hooks fire (a Stop hook is out of its reach)
    shutil.copy2(os.path.join(HERE, "hook_doctor.py"), dest)
    canaries_path = os.path.join(project, "hook-doctor.canaries.json")
    canaries = {}
    if os.path.exists(canaries_path):
        with open(canaries_path, encoding="utf-8") as f:
            canaries = json.load(f)
    canaries.setdefault(_cmd("test_guard.py"), {
        "tool_name": "Edit",
        "tool_input": {"file_path": "tests/test_canary.py", "old_string": "assert total == 3\n", "new_string": "pass\n"},
        "expect": "ask"})
    with open(canaries_path, "w", encoding="utf-8") as f:
        json.dump(canaries, f, indent=2)

    claude_md = os.path.join(project, "CLAUDE.md")
    wrote_md = False
    if not os.path.exists(claude_md):
        shutil.copy2(os.path.join(HERE, "CLAUDE.md"), claude_md)
        wrote_md = True
    return {"settings": settings, "added": added, "absence_gate": gate, "claude_md": wrote_md}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    r = install(argv[0], with_absence_gate="--no-absence-gate" not in argv)
    print(f"settings: {r['settings']}")
    for a in r["added"] or ["(already installed)"]:
        print(f"  + {a}")
    if not r["absence_gate"] and "--no-absence-gate" not in argv:
        print("  absence-gate skipped: it needs ripgrep (rg) on PATH")
    print("CLAUDE.md: " + ("written from the template, edit it" if r["claude_md"] else "kept yours as it is"))
    print("check the hooks fire: cd into the project and run  python .claude/hooks/starter-kit/hook_doctor.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
