"""Unit tests for hook-doctor. Synthetic hooks only, written by hand in a temp folder."""
import contextlib
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hook_doctor as hd  # noqa: E402

DENY_EXIT2 = "import sys; sys.stdin.read(); sys.exit(2)"
DENY_JSON = (
    "import sys, json; sys.stdin.read(); "
    "print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny'}}))"
)
ALLOW_ALL = "import sys; sys.stdin.read(); sys.exit(0)"
HANG = "import time; time.sleep(60)"
CANARY = {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}, "expect": "deny"}


def hook_cmd(code):
    return f'"{Path(sys.executable).as_posix()}" -c "{code}"'


class RunCanaryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_a_exit2_is_deny_PASS(self):
        self.assertTrue(hd.run_canary(hook_cmd(DENY_EXIT2), CANARY).startswith("PASS"))

    def test_b_json_deny_is_deny_PASS(self):
        self.assertTrue(hd.run_canary(hook_cmd(DENY_JSON), CANARY).startswith("PASS"))

    def test_c_allow_all_hook_is_FAIL(self):
        self.assertTrue(hd.run_canary(hook_cmd(ALLOW_ALL), CANARY).startswith("FAIL"))

    def test_f_hook_that_did_not_start_is_ERROR_not_PASS(self):
        missing = Path(self._tmp.name) / "missing_hook.py"
        verdict = hd.run_canary(f'"{sys.executable}" "{missing}"', CANARY)
        self.assertTrue(verdict.startswith("ERROR"), verdict)

    def test_e_hang_is_ERROR_within_timeout(self):
        t0 = time.time()
        verdict = hd.run_canary(hook_cmd(HANG), CANARY, timeout=1.0)
        self.assertTrue(verdict.startswith("ERROR"), verdict)
        self.assertLess(time.time() - t0, 20)


class ScanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _settings(self, name, command):
        path = self.root / name
        path.write_text(json.dumps({"hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}]}}), encoding="utf-8")
        return path

    def test_d_hook_without_canary_is_UNTESTED(self):
        cmd = hook_cmd(ALLOW_ALL)
        settings = self._settings("settings.json", cmd)
        rows = hd.scan([("user", settings)], canaries={})
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].verdict.startswith("UNTESTED"), rows[0].verdict)

    def test_untested_does_not_fail_the_run(self):
        settings = self._settings("settings.json", hook_cmd(ALLOW_ALL))
        self.assertEqual(hd.main(["--settings", str(settings), "--canaries", str(self.root / "none.json")]), 0)

    def test_fail_makes_exit_code_1(self):
        cmd = hook_cmd(ALLOW_ALL)
        settings = self._settings("settings.json", cmd)
        canaries = self.root / "hook-doctor.canaries.json"
        canaries.write_text(json.dumps({cmd: CANARY}), encoding="utf-8")
        self.assertEqual(hd.main(["--settings", str(settings), "--canaries", str(canaries)]), 1)


class ReviewTests(unittest.TestCase):
    """Regressions from a code review (24.10.2026): each one was red before the fix."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_empty_home_and_project_is_not_an_error(self):
        # blocker 1: missing settings files are a scope that is not present, not a broken run
        home, project = self.root / "home", self.root / "project"
        home.mkdir()
        project.mkdir()
        canaries = self.root / "none.json"
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = hd.main(["--home", str(home), "--project", str(project), "--canaries", str(canaries)])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("hooks: 0  bad: 0", out.getvalue())

    def test_hook_using_claude_project_dir_denies_with_exit2(self):
        # blocker 2a: Claude Code runs hooks in Git Bash and exports CLAUDE_PROJECT_DIR
        project = self.root / "project"
        hook = project / ".claude" / "hooks" / "deny.py"
        hook.parent.mkdir(parents=True)
        hook.write_text(DENY_EXIT2, encoding="utf-8")
        command = f'"{Path(sys.executable).as_posix()}" "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/deny.py"'
        self.assertTrue(hd.run_canary(command, CANARY, project_dir=project).startswith("PASS"))

    def test_no_git_bash_is_FAIL_OPEN_and_exit_1(self):
        # blocker 2b: without Git Bash, command hooks do not run at all on Windows
        original = hd.find_bash
        hd.find_bash = lambda *a, **k: None
        self.addCleanup(setattr, hd, "find_bash", original)
        verdict = hd.run_canary(hook_cmd(ALLOW_ALL), CANARY)
        self.assertTrue(verdict.startswith("FAIL_OPEN"), verdict)

    def test_canary_outside_matcher_is_CANARY_MISMATCH(self):
        # point 3: the group matcher is Bash, the canary is a Write call, so the hook would never see it
        cmd = hook_cmd(DENY_EXIT2)
        settings = self.root / "settings.json"
        settings.write_text(json.dumps({"hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": cmd}]}]}}), encoding="utf-8")
        canaries = {cmd: {"tool_name": "Write", "tool_input": {"file_path": "x"}, "expect": "deny"}}
        rows = hd.scan([("file", settings)], canaries)
        self.assertTrue(rows[0].verdict.startswith("CANARY MISMATCH"), rows[0].verdict)

    def test_expect_ask_accepts_ask_and_deny(self):
        # reviewer: many guards ask instead of deny (test_guard, asset-seatbelt); a canary can say which it wants
        ask = ("import sys, json; sys.stdin.read(); "
               "print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'ask'}}))")
        want_ask = dict(CANARY, expect="ask")
        self.assertEqual(hd.run_canary(hook_cmd(ask), want_ask), "PASS")
        self.assertEqual(hd.run_canary(hook_cmd(DENY_EXIT2), want_ask), "PASS")
        self.assertTrue(hd.run_canary(hook_cmd(ALLOW_ALL), want_ask).startswith("FAIL"))
        self.assertTrue(hd.run_canary(hook_cmd(ask), CANARY).startswith("FAIL"))   # expect deny, got ask

    def test_matchers_follow_claude_code_rules(self):
        # letters-only matchers are exact names; anything else is an unanchored regex (Claude Code hooks docs)
        self.assertTrue(hd._matcher_hits("Edit|Write", "Write"))
        self.assertFalse(hd._matcher_hits("Edit", "NotebookEdit"))
        self.assertTrue(hd._matcher_hits("^mcp__", "mcp__mail__send"))
        self.assertTrue(hd._matcher_hits("mcp__.*", "mcp__x__y"))
        self.assertFalse(hd._matcher_hits("^(WebFetch|Bash)$", "Write"))

    def test_canary_mismatch_fails_the_run(self):
        # reviewer: a canary the hook never sees proves nothing, so the run must not end green
        cmd = hook_cmd(DENY_EXIT2)
        settings = self.root / "settings.json"
        settings.write_text(json.dumps({"hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": cmd}]}]}}), encoding="utf-8")
        canaries = self.root / "canaries.json"
        canaries.write_text(json.dumps({cmd: {"tool_name": "Write", "tool_input": {"file_path": "x"},
                                              "expect": "deny"}}), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(hd.main(["--settings", str(settings), "--canaries", str(canaries)]), 1)


if __name__ == "__main__":
    unittest.main()
