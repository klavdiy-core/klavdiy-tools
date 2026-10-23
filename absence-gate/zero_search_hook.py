#!/usr/bin/env python3
"""zero_search_hook.py — catch the cause, not the sentence: a search that came back EMPTY because it couldn't see.

v0.6, after outside review #4 (Fable 5.1): «the cause of the bug isn't the wording — it's a search with a silent zero».
A default ripgrep (and Claude Code's Grep tool, which is ripgrep) obeys .gitignore and skips dot-folders. «data/*» in a
.gitignore made 97% of a memory folder invisible, and an empty result reads exactly like «it isn't there».

PostToolUse hook for the Grep tool. It does NOT parse the tool's output (an independent witness can't come from the thing
it checks): it re-runs the same pattern twice itself — once the default way, once with -uu (no ignore files, hidden too).
If the default search finds nothing and -uu finds something, the model is told, next to the tool result:
  "this search was blind: with --no-ignore --hidden, N files match: ..."
Nothing blocks here — the tool already ran; the point is that the false zero never reaches a sentence.
absence_gate.py stays the second line, at the moment of sending.

settings.json:
  {"hooks": {"PostToolUse": [{"matcher": "Grep", "hooks": [{"type": "command",
     "command": "python /path/to/zero_search_hook.py"}]}]}}
"""
import json
import os
import subprocess
import sys


def rg_files(args, pattern, path):
    p = subprocess.run(["rg", *args, "-l", "-e", pattern, path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode not in (0, 1):
        raise RuntimeError(p.stderr.strip()[:200])
    return [l for l in p.stdout.splitlines() if l.strip()]


def run(stdin_text):
    """Returns the JSON string to print (or "" for nothing). Pure, for the tests."""
    try:
        event = json.loads(stdin_text or "{}")
        if event.get("tool_name") != "Grep":
            return ""
        ti = event.get("tool_input", {})
        pattern = ti.get("pattern")
        if not pattern:
            return ""
        base = event.get("cwd") or os.getcwd()
        path = os.path.join(base, ti["path"]) if ti.get("path") else base   # v0.6.1: relative to the SESSION's cwd
        flags = ["-i"] if ti.get("-i") else []
        if ti.get("glob"):
            flags += ["--glob", ti["glob"]]
        if ti.get("type"):
            flags += ["--type", ti["type"]]
        # Did the TOOL find anything? Read its own result. (v0.6, caught by the live seam test: re-running a default rg as
        # a stand-in was wrong — Claude Code's Grep sees hidden files but obeys .gitignore, so the stand-in cried «blind»
        # on a search that had found the file.) The witness for «there is more» stays independent: -uu, run here.
        resp = event.get("tool_response")
        if isinstance(resp, dict):
            found = (resp.get("numFiles") or resp.get("numLines") or resp.get("numMatches") or resp.get("filenames")
                     or str(resp.get("content") or "").strip())
            if found:
                return ""
        elif rg_files(flags, pattern, path):                     # no tool_response: fall back to a default rg
            return ""
        hidden = rg_files(["-uu", *flags], pattern, path)
        if not hidden:
            return ""
        note = (f"ZERO_SEARCH_WAS_BLIND: this search returned nothing because it skips ignored and hidden files. "
                f"With --no-ignore --hidden, {len(hidden)} file(s) match: " + ", ".join(hidden[:10])
                + ("" if len(hidden) <= 10 else f" … (+{len(hidden) - 10})")
                + ". Do not report this as absent — open these files.")
    except Exception as e:                                       # noqa: BLE001
        note = f"ZERO_SEARCH_HOOK_BROKEN: {type(e).__name__}: {e} — the zero from this search is unverified."
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": note}})


def main():
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")     # v0.6.1: UTF-8, not the console codec
    if os.environ.get("ZERO_SEARCH_DUMP"):                      # debugging the real hook input; off by default
        open(os.environ["ZERO_SEARCH_DUMP"], "a", encoding="utf-8").write(raw + "\n")
    out = run(raw)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
