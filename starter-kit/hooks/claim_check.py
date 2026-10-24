#!/usr/bin/env python3
"""claim_check.py — a Stop hook: "it works / tests pass" must stand on a test run made after the last code edit.

The most common lie an agent tells is not malicious: it edits code, feels done, and says "fixed, tests pass" without
running them, or after a run it didn't read (`pytest | tail` exits 0 whatever pytest said). A rule "always run the
tests" in CLAUDE.md doesn't fire. This check does, at the moment the reply is finished:

  the reply claims success (EN / RU phrasings)            and
  the session edited a code file                          and
  no test command ran after that edit, or the last one failed (by exit code OR by its own output)
  -> exit 2: the reply is held back and the model is told what is missing.

Saying it plainly ("I haven't run the tests") passes: honesty is the way out, not a skip flag.
Exit 2 blocks in Claude Code and only stderr reaches the model; any failure of this hook is exit 2 GATE_BROKEN,
except when Claude Code is already continuing from a Stop hook (stop_hook_active) — then it lets go, once.

settings.json:
  {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python /path/to/claim_check.py"}]}]}}
"""
import json
import os
import re
import sys

CLAIM = re.compile(
    r"\b(all\s+)?(the\s+)?tests?\s+(now\s+)?(pass|passes|passed|passing|are\s+(passing|green))\b"
    r"|\b(fixed|solved)\s+(it|now|the\s+(bug|issue|problem|test))\b|\bit\s+(now\s+)?works\b|\bworks\s+now\b"
    r"|\bis\s+(now\s+)?(fixed|working|green|passing)\b|\beverything\s+(works|passes)\b|\ball\s+green\b"
    r"|\bbuild\s+(is\s+)?green\b|\bshould\s+(now\s+)?work\b|\bverified\b"
    r"|тест\w*\s+(теперь\s+)?(проход\w*|зел[её]н\w*)|\bпочинил\w*|\bисправил\w*|\bвс[её]\s+работает|\bработает\b"
    r"|\bвс[её]\s+зел[её]н\w*",
    re.I)
HONEST = re.compile(
    r"\b(not|haven'?t|have\s+not|didn'?t|did\s+not|couldn'?t|could\s+not|wasn'?t\s+able\s+to)\s+(yet\s+)?"
    r"(run|ran|test|tested|verify|verified|check|checked)\b|\buntested\b|\bwithout\s+(running\s+)?(the\s+)?tests\b"
    r"|не\s+(запускал\w*|проверял\w*|прогонял\w*|гонял\w*)|без\s+тест\w*",
    re.I)
TEST_CMD = re.compile(
    r"\b(pytest|py\.test|unittest|nose2|tox|nox|jest|vitest|mocha|ava|karma|rspec|phpunit|pest|ctest)\b"
    r"|\bplaywright\s+test\b|\b(npm|yarn|pnpm|bun)\s+(run\s+)?test\b|\bgo\s+test\b|\bcargo\s+(test|nextest)\b"
    r"|\b(mvn|mvnw|gradle|gradlew)\b.*\btest\b|\bdotnet\s+test\b|\bmix\s+test\b|\bnode\s+--test\b"
    r"|\bmake\s+(check|test)\b|\bdeno\s+test\b|\bswift\s+test\b"
    r"|--selftest\b|(^|[\s/\\])(test_\w+|\w+_test|\w+\.(test|spec))\.(py|[cm]?[jt]sx?|rb)\b",   # a test file run directly
    re.I)
FAILED_OUTPUT = re.compile(
    r"\bFAILED\b|\b[1-9]\d*\s+(failed|failing|failures?|errors?)\b|^FAIL\b|^not ok \d|✖|\bpanicked\b"
    r"|\bAssertionError\b|^Traceback \(most recent call last\)",
    re.M)
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
NOT_CODE = {".md", ".markdown", ".txt", ".rst", ".adoc", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv",
            ".lock", ".png", ".jpg", ".svg", ".gif"}


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def events(path):
    """Ordered (kind, data) from a Claude Code transcript: ("use", {id,name,input}) and ("result", {id,error,text})."""
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") not in ("assistant", "user"):
                continue
            content = (e.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    out.append(("use", {"id": b.get("id"), "name": b.get("name"), "input": b.get("input") or {}}))
                elif b.get("type") == "tool_result":
                    out.append(("result", {"id": b.get("tool_use_id"), "error": bool(b.get("is_error")),
                                           "text": _text(b.get("content"))}))
    return out


def is_code(path):
    p = (path or "").replace("\\", "/").lower()
    return bool(p) and os.path.splitext(p)[1] not in NOT_CODE and "/docs/" not in "/" + p


def verdict(evts):
    """None if fine, else a sentence saying what is missing."""
    results = {d["id"]: d for k, d in evts if k == "result"}
    last_edit, last_edit_file = -1, None
    for i, (k, d) in enumerate(evts):
        if k == "use" and d["name"] in EDIT_TOOLS:
            f = d["input"].get("file_path") or d["input"].get("notebook_path")
            if is_code(f):
                last_edit, last_edit_file = i, f
    if last_edit < 0:
        return None
    runs = [d for k, d in evts[last_edit + 1:] if k == "use" and d["name"] in SHELL_TOOLS
            and TEST_CMD.search(str(d["input"].get("command", "")))]
    if not runs:
        return (f"The reply says it works / tests pass, but no test command ran after the last code edit "
                f"({last_edit_file}). Run the tests and read their output, or say plainly that you haven't.")
    last = runs[-1]
    r = results.get(last["id"])
    if r is None:
        return f"The last test run (`{last['input'].get('command')}`) has no result yet. Read it before claiming success."
    if r["error"] or FAILED_OUTPUT.search(r["text"]):
        tail = " ".join(r["text"].strip().splitlines()[-3:])[:300]
        return (f"The reply says it works / tests pass, but the last test run after the edit failed: "
                f"`{last['input'].get('command')}` -> {tail!r}. Fix it, or report the failure as it is.")
    return None


def run(argv, stdin_text):
    """Returns (exit_code, stderr_text). Pure, so the tests can call it without a process."""
    try:
        event = json.loads(stdin_text or "{}")
        if event.get("stop_hook_active"):
            return 0, ""
        msg = event.get("last_assistant_message")
        if msg is None:
            return 2, "GATE_BROKEN: claim_check: Stop hook input has no last_assistant_message"
        if not CLAIM.search(msg) or HONEST.search(msg):
            return 0, ""
        path = event.get("transcript_path")
        if not path or not os.path.exists(path):
            return 2, "GATE_BROKEN: claim_check: no transcript to check the claim against"
        why = verdict(events(path))
        return (2, "CLAIM_UNCHECKED: " + why) if why else (0, "")
    except Exception as e:                                       # noqa: BLE001 — every failure must be loud
        return 2, f"GATE_BROKEN: claim_check: {type(e).__name__}: {e}"


def main():
    try:
        code, err = run(sys.argv[1:], sys.stdin.buffer.read().decode("utf-8"))
    except Exception as e:                                       # noqa: BLE001
        code, err = 2, f"GATE_BROKEN: claim_check: {type(e).__name__}: {e}"
    if err:
        sys.stderr.buffer.write((err + "\n").encode("utf-8"))
        sys.stderr.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
