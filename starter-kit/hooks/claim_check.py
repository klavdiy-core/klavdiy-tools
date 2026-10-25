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
    r"|\bbuild\s+(is\s+)?green\b|\bshould\s+(now\s+)?work\b"
    r"|\b(i|we)('ve|\s+have)?\s+verified\b|\bverified\s+(it|that|the\s+fix)\b"     # not «verified by the schema»
    r"|тест\w*\s+(теперь\s+)?(проход\w*|зел[её]н\w*)|\bпочинил\w*|\bисправил\w*|\bвс[её]\s+работает|\bработает\b"
    r"|\bвс[её]\s+зел[её]н\w*",
    re.I)
HONEST = re.compile(
    # about MY run: «I haven't run», «we did not test» — not «the test is not run by CI»
    r"\b(i|we)('ve|'d|\s+have|\s+had)?\s+(yet\s+)?(not|never|haven'?t|didn'?t|did\s+not|couldn'?t|could\s+not|"
    r"wasn'?t\s+able\s+to|weren'?t\s+able\s+to)\s+(yet\s+)?(run|ran|test|tested|verify|verified|check|checked)\b"
    r"|\b(haven'?t|didn'?t)\s+(yet\s+)?(run|ran|test|tested|verify|verified|check|checked)\b"
    r"|\buntested\b|\bwithout\s+(running\s+)?(the\s+)?tests\b"
    r"|не\s+(запускал\w*|проверял\w*|прогонял\w*|гонял\w*)|без\s+тест\w*",
    re.I)
# A test RUNNER at the start of a command (after wrappers like `npx`, `uv run`, `python -m` are taken off).
# Mentioning a test file or a runner's name elsewhere (`cat test_x.py`, `pip install pytest`) is not running tests.
RUNNER = re.compile(
    r"^((pytest|py\.test|unittest|nose2|tox|nox|jest|vitest|mocha|ava|karma|rspec|phpunit|pest|ctest)\b"
    r"|playwright\s+test\b|(npm|yarn|pnpm|bun)\s+(run\s+)?test\b|go\s+test\b|cargo\s+(test|nextest)\b"
    r"|(\S*[/\\])?(mvn|mvnw|gradle|gradlew)(\.bat|\.cmd)?\b.*\btest\b|dotnet\s+test\b|mix\s+test\b|--test\b"
    r"|make\s+(check|test)\b|deno\s+test\b|swift\s+test\b"
    r"|\S+\s.*--selftest\b|\S+\s+--selftest\b"
    r"|(\S*[/\\])?(test_\w+|\w+_test|\w+\.(test|spec))\.(py|[cm]?[jt]sx?|rb)\b)",                # a test file run directly
    re.I)
WRAPPERS = {"sudo", "env", "time", "npx", "bunx", "pnpx", "exec"}
TWO_WORD = {("uv", "run"), ("poetry", "run"), ("pipenv", "run"), ("pdm", "run"), ("hatch", "run"), ("bundle", "exec"),
            ("pnpm", "exec"), ("yarn", "exec")}
INTERPRETER = re.compile(r"^(\S*[/\\])?(python[\d.]*|py|pypy[\d.]*|node|ts-node|ruby)(\.exe)?$", re.I)
WITH_VALUE = {"-X", "-W", "-r", "--require", "--loader", "--import"}


def _command_start(segment):
    words = segment.split()
    while words:
        w = words[0]
        if re.match(r"^\w+=", w) or w.lower() in WRAPPERS:
            words = words[1:]
        elif len(words) > 1 and (w.lower(), words[1].lower()) in TWO_WORD:
            words = words[2:]
        elif INTERPRETER.match(w):
            words = words[1:]
            while words and words[0].startswith("-") and words[0] not in ("-m", "--test"):
                words = words[2:] if words[0] in WITH_VALUE else words[1:]
            if words and words[0] == "-m":
                words = words[1:]
        else:
            break
    return " ".join(words)


class _TestCmd:
    """TEST_CMD.search(command): True when some segment of the command line starts with a test runner."""
    def search(self, command):
        return any(RUNNER.search(_command_start(seg)) for seg in re.split(r"&&|\|\||[;|\n&]", command or ""))


TEST_CMD = _TestCmd()
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


def project_root(event):
    return event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or None


def in_project(path, root):
    """True when the edited file is inside the project; a throwaway script elsewhere is not the project's code.
    Unknown root: everything counts (the old behaviour). Found by running these hooks on a real session."""
    if not root or not path:
        return True
    if not os.path.isabs(path):
        path = os.path.join(root, path)          # a relative path is relative to the project
    p, r = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
    return p == r or p.startswith(r.rstrip("\\/") + os.sep)


# Shell commands that may change code. A heuristic by the shape of the command, not file fingerprints: a script that
# rewrites files was not a «last code edit», and a success claim after it with no test run went through (external
# review, 25.10). Running a script (not a test) counts: it may write anything.
# edits that need no file check: in-place editors, tree-rewriting git commands, formatters
IN_PLACE = re.compile(
    r"^(sed\s+(-[\w]+\s+)*(-\w*i\w*|--in-place)\b|perl\s+(-\w+\s+)*-\w*i|patch\b"
    r"|git\s+(apply|am|merge|pull|rebase|cherry-pick|stash(\s+(pop|apply|push))?\s*$|reset\s+--hard|checkout\s+(?!-[bB]\b)|"
    r"restore\s+(?!.*--staged))"
    r"|black\b|isort\b|ruff\s+(format|check\s+.*--fix)|prettier\s+.*--write|eslint\s+.*--fix|gofmt\s+(-\w+\s+)*-w|"
    r"rustfmt\b|cargo\s+fmt\b|clang-format\s+.*-i\b)", re.I)
# commands that write a file named in their arguments: an edit only if one of those files is code
WRITES_ARG = re.compile(r"^(cp|mv|copy|move|tee|rm|del|git\s+rm|Copy-Item|Move-Item|Remove-Item|Set-Content|Add-Content"
                        r"|Out-File|curl|wget)\b", re.I)
REDIRECT_TO = re.compile(r">>?\s*['\"]?([^\s'\";&|]+)")
SCRIPT = re.compile(r"^(bash|sh|zsh|pwsh|powershell)(\.exe)?\s+(-\w+\s+)*\S+\.(sh|ps1|bash)\b", re.I)
NOT_A_SCRIPT = re.compile(r"^(-V|--version|-h|--help|-m\b|-c\b)|runserver|\bserve\b|http\.server", re.I)


def _edit_in(seg):
    """The code file a segment may change ('' when unknown but likely), or None when it changes no code."""
    for m in REDIRECT_TO.finditer(seg):
        t = m.group(1)
        if is_code(t) and not t.startswith("/dev/") and t.lower() != "nul":
            return t
    if IN_PLACE.search(seg) or SCRIPT.search(seg):
        return ""
    if WRITES_ARG.search(seg):
        args = [a.strip("'\"") for a in seg.split()[1:] if not a.startswith("-") and "://" not in a]
        code = [a for a in args if is_code(a) and "." in os.path.basename(a)]
        return code[-1] if code else None             # cp logo.png ..., ls | tee list.txt: no code touched
    words = seg.split()
    if words and INTERPRETER.match(words[0]) and len(words) > 1 and not NOT_A_SCRIPT.search(" ".join(words[1:])):
        return ""                                     # a script run: it may write anything
    return None


def shell_edit(command):
    """(code file a shell command may have changed or '' if unknown, tested after it in the same command?), or
    (None, False) when it changes no code. A pipe's later part is its own segment (`ls | tee x`)."""
    edit, tested = None, False
    for seg in re.split(r"&&|\|\||[;\n&|]", command or ""):
        seg = seg.strip()
        if not seg:
            continue
        if TEST_CMD.search(seg):
            tested = edit is not None or tested
            continue
        f = _edit_in(seg)
        if f is not None:
            edit, tested = f, False                   # an edit after a test: the test no longer covers it
    return edit, (tested and edit is not None)


def verdict(evts, root=None):
    """None if fine, else a sentence saying what is missing."""
    results = {d["id"]: d for k, d in evts if k == "result"}
    last_edit, last_edit_file, self_tested = -1, None, False
    for i, (k, d) in enumerate(evts):
        if k == "use" and d["name"] in EDIT_TOOLS:
            f = d["input"].get("file_path") or d["input"].get("notebook_path")
            if is_code(f) and in_project(f, root):
                last_edit, last_edit_file, self_tested = i, f, False
        elif k == "use" and d["name"] in SHELL_TOOLS:
            cmd = str(d["input"].get("command", ""))
            f, tested = shell_edit(cmd)
            if f is not None and (not f or in_project(f, root)):
                last_edit, last_edit_file, self_tested = i, (f or f"a shell command: `{cmd[:80]}`"), tested
    if last_edit < 0:
        return None
    # `sed -i ... && pytest -q`: the same command edited and then tested; its run counts (Tsaplya)
    start = last_edit if self_tested else last_edit + 1
    runs = [d for k, d in evts[start:] if k == "use" and d["name"] in SHELL_TOOLS
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
        why = verdict(events(path), project_root(event))
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
