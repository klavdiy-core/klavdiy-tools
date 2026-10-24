#!/usr/bin/env python3
"""test_guard.py — a PreToolUse hook: an edit that weakens a test asks a human first.

"Make the tests pass" has a cheap solution an agent finds often: loosen the assertion, skip the test, delete it.
This hook reads Edit / MultiEdit / Write on test files before they happen and compares before and after:
fewer assertions, more skips (skip, xfail, xit, .only, @Disabled, t.Skip ...), or fewer test functions ->
permissionDecision "ask", with the counts, so the human sees it and decides. Anything else is silent.
If the hook cannot read its input it asks too: a broken guard must not wave an edit through.

settings.json:
  {"hooks": {"PreToolUse": [{"matcher": "Edit|MultiEdit|Write",
     "hooks": [{"type": "command", "command": "python /path/to/test_guard.py"}]}]}}
"""
import json
import os
import re
import sys

TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs)/|(^|/)test_[^/]*\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$"
    r"|Tests?\.(java|kt|cs|swift)$|_spec\.rb$")
ASSERTION = re.compile(r"\bassert\w*\b|\bexpect\s*\(|\.should\b|\bassert_\w+!|\bt\.(Error|Fatal)f?\(|\bverify\(")
SKIP = re.compile(
    r"@pytest\.mark\.(skip|xfail)|@unittest\.skip|\bpytest\.skip\(|\b(it|test|describe|context)\.(skip|todo|only)\("
    r"|\bx(it|test|describe)\(|@Disabled\b|@Ignore\b|\bt\.Skip(Now|f)?\(|#\[ignore\]|\bskip\(\s*['\"]")
TEST_FN = re.compile(
    r"^\s*(async\s+)?def\s+test\w*|(?<![.\w])(it|test)\s*\(\s*['\"`]|^\s*func\s+Test\w+|#\[test\]|@Test\b", re.M)


def counts(text):
    return (len(ASSERTION.findall(text)), len(SKIP.findall(text)), len(TEST_FN.findall(text)))


def _before_after(tool, inp, cwd):
    if tool == "Edit":
        return inp.get("old_string", ""), inp.get("new_string", "")
    if tool == "MultiEdit":
        edits = inp.get("edits") or []
        return ("\n".join(e.get("old_string", "") for e in edits), "\n".join(e.get("new_string", "") for e in edits))
    if tool == "Write":
        path = inp.get("file_path", "")
        full = path if os.path.isabs(path) else os.path.join(cwd or ".", path)
        old = ""
        if os.path.exists(full):
            with open(full, encoding="utf-8", errors="replace") as f:
                old = f.read()
        return old, inp.get("content", "")
    return None


def _ask(reason):
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                              "permissionDecisionReason": "test_guard: " + reason}})


def run(stdin_text):
    """Returns what to print on stdout ("" = no decision). Pure, so the tests can call it."""
    try:
        event = json.loads(stdin_text or "{}")
        tool = event.get("tool_name")
        if tool not in ("Edit", "MultiEdit", "Write"):
            return ""
        inp = event["tool_input"]
        path = str(inp.get("file_path", "")).replace("\\", "/")
        if not TEST_PATH.search(path):
            return ""
        before, after = _before_after(tool, inp, event.get("cwd"))
        (a0, s0, t0), (a1, s1, t1) = counts(before), counts(after)
        why = []
        if a1 < a0:
            why.append(f"assertions {a0} -> {a1}")
        if s1 > s0:
            why.append(f"skips {s0} -> {s1}")
        if t1 < t0:
            why.append(f"test functions {t0} -> {t1}")
        if not why:
            return ""
        return _ask(f"this edit weakens {os.path.basename(path)} ({', '.join(why)}). "
                    "Is the code wrong, or the test? Say which before it goes in.")
    except Exception as e:                                       # noqa: BLE001 — a broken guard asks, never passes
        return _ask(f"guard could not read this edit ({type(e).__name__}: {e}); look at it yourself.")


def main():
    try:
        out = run(sys.stdin.buffer.read().decode("utf-8"))
    except Exception as e:                                       # noqa: BLE001
        out = _ask(f"guard broken ({type(e).__name__}: {e})")
    if out:
        sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
