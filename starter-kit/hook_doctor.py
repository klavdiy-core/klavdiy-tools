"""hook-doctor: checks that every PreToolUse hook in your Claude Code settings actually denies a known-bad input.

A hook that silently never runs looks the same as a hook that works. This tool feeds each hook a canary
(a JSON tool call that the hook must deny) and reports PASS / FAIL / UNTESTED / ERROR / FAIL_OPEN / CANARY MISMATCH
per hook. Hooks run the way Claude Code runs them: through bash (Git Bash on Windows), with CLAUDE_PROJECT_DIR set.
Stdlib only, no network.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

# stderr of a command that never ran: python's missing file (exit 2), cmd/sh missing command
NOT_STARTED = re.compile(r"can't open file|No such file or directory|is not recognized as an internal|command not found")
GIT_BASH = (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe")


@dataclass
class Row:
    scope: str
    command: str
    verdict: str


def find_bash(env=None, fallbacks=GIT_BASH):
    """The bash Claude Code itself uses. On Windows that is Git Bash, never the WSL stubs in System32 or
    WindowsApps: inside WSL a Windows path does not exist. Taken as is from limit-forecast."""
    env = os.environ if env is None else env
    if os.name != "nt":
        return shutil.which("bash", path=env.get("PATH"))
    if env.get("CLAUDE_CODE_GIT_BASH_PATH"):
        return env["CLAUDE_CODE_GIT_BASH_PATH"]
    for d in (env.get("PATH") or "").split(os.pathsep):
        low = d.lower().replace("/", "\\").rstrip("\\")
        if low.endswith("\\windows\\system32") or low.endswith("\\windowsapps") or low.endswith("\\sysnative"):
            continue
        p = os.path.join(d, "bash.exe")
        if os.path.isfile(p):
            return p
    return next((p for p in fallbacks if os.path.isfile(p)), None)


def _json_decision(text):
    """The PreToolUse permissionDecision printed on stdout ("deny", "ask", "allow", ...), or None."""
    candidates = [text.strip()] + [line.strip() for line in text.splitlines()[-1:]]
    for raw in candidates:
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        if isinstance(data, dict):
            spec = data.get("hookSpecificOutput") or {}
            if isinstance(spec, dict) and spec.get("permissionDecision"):
                return spec["permissionDecision"]
    return None


def _json_deny(text):
    return _json_decision(text) == "deny"


def _kill_tree(proc):
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        try:
            os.killpg(proc.pid, 9)
        except OSError:
            pass


def _run_hook(command, payload, timeout, project_dir):
    """Run one hook with payload on stdin, through bash, the way Claude Code runs it, in a fresh temporary folder with
    CLAUDE_PROJECT_DIR set. Returns (decision or None, returncode, stderr text), or an ERROR/FAIL_OPEN string."""
    bash = find_bash()
    if bash is None:
        return "FAIL_OPEN (Git Bash not found: Claude Code cannot run command hooks here)"
    project = Path(project_dir) if project_dir else Path.cwd()
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project.as_posix())
    with tempfile.TemporaryDirectory() as work_dir:
        proc = subprocess.Popen(
            [bash, "-c", command], cwd=work_dir, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=(os.name != "nt"),
        )
        try:
            out, err = proc.communicate(json.dumps(payload).encode("utf-8"), timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            return f"ERROR (timeout {timeout:g} s)"
    err_text = err.decode("utf-8", "replace")
    decision = _json_decision(out.decode("utf-8", "replace"))
    if decision is None and not NOT_STARTED.search(err_text) and proc.returncode == 2:
        decision = "deny"
    return decision, proc.returncode, err_text


def run_canary(command, canary, timeout=10.0, project_dir=None):
    """Run one hook with the canary on stdin. Deny = exit code 2, or JSON permissionDecision deny on stdout."""
    got = _run_hook(command, canary, timeout, project_dir)
    if isinstance(got, str):
        return got
    decision, returncode, err_text = got
    expect = canary.get("expect", "deny")          # "deny", or "ask" (a deny is stricter, so it passes too)
    if decision == "deny" or (decision == "ask" and expect == "ask"):
        return "PASS"
    if decision == "ask":
        return "FAIL (asked where it should deny)"
    if NOT_STARTED.search(err_text):
        return "ERROR (hook did not start: exit 2 here is not a deny)"
    if returncode in (0, 2) or decision == "allow":
        return f"FAIL (allowed what it should {expect})"
    return f"ERROR (crashed, exit {returncode})"


# ---------- unattended: what stops a run nobody watches ----------

# ordinary work an autonomous run does; a hook that asks or denies on these stalls it (an ask has nobody to answer)
PROBES = (("Bash", {"command": "git status"}), ("Read", {"file_path": "{p}/README.md"}),
          ("Edit", {"file_path": "{p}/src/app.py", "old_string": "a", "new_string": "b"}),
          ("Write", {"file_path": "{p}/notes.txt", "content": "x"}),
          ("WebFetch", {"url": "https://example.com", "prompt": "summary"}))
RUN_READY_MODES = {"acceptEdits", "bypassPermissions", "dontAsk"}


def unattended(scopes, timeout=10.0, project_dir=None):
    """Lines naming each thing that would stop an unattended run: hooks that ask or deny on ordinary tool calls (found
    by running them), ask and deny rules, and a defaultMode under which anything not allowed asks."""
    project = Path(project_dir) if project_dir else Path.cwd()
    found, mode = [], None
    for label, path in scopes:
        try:
            entries = hook_entries(path)
            data = json.loads(Path(path).read_text(encoding="utf-8")) if entries is not None else {}
        except (ValueError, OSError) as err:
            found.append(f"[{label}] {path}: unreadable ({err}); what it holds is unknown")
            continue
        perms = (data or {}).get("permissions") or {}
        mode = perms.get("defaultMode", mode)
        for rule in perms.get("deny") or []:
            found.append(f"[{label}] deny rule {rule}: a run that needs it stops there")
        for rule in perms.get("ask") or []:
            found.append(f"[{label}] ask rule {rule}: asks, and an unattended run has nobody to answer")
        for matcher, command in entries or []:
            for tool, inp in PROBES:
                if not _matcher_hits(matcher, tool):
                    continue
                payload = {"hook_event_name": "PreToolUse", "tool_name": tool,
                           "tool_input": {k: v.replace("{p}", project.as_posix()) for k, v in inp.items()}}
                got = _run_hook(command, payload, timeout, project)
                if isinstance(got, str):
                    found.append(f"[{label}] hook {_label(command)}: {got} on an ordinary {tool} call")
                elif got[0] in ("ask", "deny"):
                    verb = "asks" if got[0] == "ask" else "denies"
                    found.append(f"[{label}] hook {_label(command)} {verb} on an ordinary {tool} call")
    if mode not in RUN_READY_MODES:
        found.append(f"permissions: defaultMode {mode or 'default'!r}: every edit and command not in an allow rule asks "
                     f"(acceptEdits, dontAsk or bypassPermissions do not)")
    return found


def _matcher_hits(matcher, tool_name):
    """Claude Code matchers (hooks docs): empty or '*' is every tool; only letters, digits, _ - spaces , | is an exact
    name or a list of names; anything else is a regex tested unanchored, like JavaScript's RegExp.test."""
    if matcher in ("", "*", None):
        return True
    if re.fullmatch(r"[A-Za-z0-9_\-\s,|]+", matcher):
        return tool_name in [m.strip() for m in re.split(r"[|,]", matcher) if m.strip()]
    try:
        return re.search(matcher, tool_name) is not None
    except re.error:
        return False


def hook_entries(settings_path):
    """(matcher, command) for each PreToolUse command hook in one settings file or plugin hooks.json.

    Returns None when the file is not there (that scope is simply not present). Raises ValueError if unreadable.
    """
    path = Path(settings_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ValueError(f"unreadable: {type(err).__name__}") from err
    entries = []
    groups = ((data or {}).get("hooks") or {}).get("PreToolUse") or []
    for group in groups:
        matcher = (group or {}).get("matcher", "")
        for hook in (group or {}).get("hooks") or []:
            if hook.get("type", "command") == "command" and hook.get("command"):
                entries.append((matcher, hook["command"]))
    return entries


def scan(scopes, canaries, timeout=10.0, project_dir=None):
    """scopes: list of (label, settings path). canaries: {command: canary dict}. Returns one Row per hook.

    A settings file that is not there adds no rows. An unreadable one adds one ERROR row.
    """
    rows = []
    for label, path in scopes:
        try:
            entries = hook_entries(path)
        except ValueError as err:
            rows.append(Row(label, str(path), f"ERROR ({err})"))
            continue
        for matcher, command in entries or []:
            if command not in canaries:
                rows.append(Row(label, command, "UNTESTED (no canary)"))
                continue
            canary = canaries[command]
            if not _matcher_hits(matcher, canary.get("tool_name", "")):
                rows.append(Row(label, command, f"CANARY MISMATCH (matcher {matcher!r} does not see tool "
                                                f"{canary.get('tool_name')!r})"))
                continue
            rows.append(Row(label, command, run_canary(command, canary, timeout, project_dir)))
    return rows


def _label(command):
    """Show only a script name: settings can hold inline secrets, so no full command in output."""
    tokens = [t.strip("\"'") for t in command.split()]
    scripts = [t for t in tokens if t.lower().endswith((".py", ".js", ".sh", ".ps1", ".exe", ".json"))]
    return os.path.basename((scripts or tokens or [command])[0])


def _default_scopes(home, project):
    scopes = [
        ("user", home / ".claude" / "settings.json"),
        ("project", project / ".claude" / "settings.json"),
        ("local", project / ".claude" / "settings.local.json"),
    ]
    if sys.platform == "win32":
        managed = Path(r"C:\Program Files\ClaudeCode\managed-settings.json")
    elif sys.platform == "darwin":
        managed = Path("/Library/Application Support/ClaudeCode/managed-settings.json")
    else:
        managed = Path("/etc/claude-code/managed-settings.json")
    scopes.append(("managed", managed))
    plugin_files = sorted(glob.glob(str(home / ".claude" / "plugins" / "**" / "hooks" / "hooks.json"), recursive=True))
    for found in plugin_files:
        scopes.append(("plugin", Path(found)))
    return scopes, bool(plugin_files)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hook_doctor.py", description="Check PreToolUse hooks with canaries.")
    parser.add_argument("--settings", action="append", default=[], help="check only these settings files")
    parser.add_argument("--canaries", default=None, help="canary file (default: ./hook-doctor.canaries.json)")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--home", default=None, help="home folder for user and plugin scopes (default: your home)")
    parser.add_argument("--project", default=None, help="project folder (default: current folder)")
    parser.add_argument("--unattended", action="store_true",
                        help="before an autonomous run: list the hooks, rules and mode that would stop it")
    args = parser.parse_args(argv)

    notes = []
    project = Path(args.project) if args.project else Path.cwd()
    if args.settings:
        scopes = [("file", Path(p)) for p in args.settings]
    else:
        home = Path(args.home) if args.home else Path.home()
        scopes, plugins_found = _default_scopes(home, project)
        if not plugins_found:
            notes.append("plugins: NOT CHECKED (no plugin hooks.json found under the plugins folder)")

    if args.unattended:
        stops = unattended(scopes, args.timeout, project_dir=project)
        for line in stops:
            print(f"STOPS  {line}")
        if not stops:
            print("unattended: nothing found that would stop the run")
        print("not listed: Claude Code's built-in safety checks (they cannot be read from settings or switched off; "
              "they show only when they fire)")
        return 1 if stops else 0

    canary_path = Path(args.canaries) if args.canaries else Path.cwd() / "hook-doctor.canaries.json"
    try:
        canaries = json.loads(canary_path.read_text(encoding="utf-8")) if canary_path.exists() else {}
    except ValueError:
        print("canaries: ERROR (file is not valid JSON)")
        return 1

    rows = scan(scopes, canaries, args.timeout, project_dir=project)
    for row in rows:
        print(f"{row.verdict:<36} [{row.scope}] {_label(row.command)}")
    for note in notes:
        print(note)

    bad = [r for r in rows if r.verdict.startswith(("FAIL", "ERROR", "CANARY MISMATCH"))]
    print(f"hooks: {len(rows)}  bad: {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
