"""hook-doctor --unattended: before an autonomous run, list what will stop it.
Complaint (25.10): x.com/mahyarm8/status/2114161206999023818 - an unattended run stalls on a prompt nobody answers."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hook_doctor as hd  # noqa: E402
from test_hook_doctor import ALLOW_ALL, hook_cmd  # noqa: E402

ASK_ON_BASH = ("import sys, json; d = json.load(sys.stdin); "
               "print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': "
               "'ask' if d.get('tool_name') == 'Bash' else 'allow'}}))")


class Unattended(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def settings(self, name, data):
        p = self.dir / name
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def run_main(self, *files):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = hd.main(["--unattended", "--project", str(self.dir)] + [a for f in files for a in ("--settings", str(f))])
        return code, out.getvalue()

    def test_everything_that_would_stop_a_run_is_listed(self):
        f = self.settings("s.json", {
            "permissions": {"defaultMode": "default", "deny": ["Bash(git push:*)"], "ask": ["Write(**/*.env)"]},
            "hooks": {"PreToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": hook_cmd(ASK_ON_BASH)}]}]}})
        code, out = self.run_main(f)
        self.assertEqual(code, 1)
        self.assertIn("asks on an ordinary Bash call", out)                 # the hook, found by running it
        self.assertIn("deny rule Bash(git push:*)", out)
        self.assertIn("ask rule Write(**/*.env)", out)
        self.assertIn("defaultMode 'default'", out)
        self.assertIn("built-in", out)                                       # the honest line: not everything is visible

    def test_a_run_ready_settings_file_passes(self):
        f = self.settings("s.json", {"permissions": {"defaultMode": "acceptEdits", "allow": ["Bash(git status)"]},
                                     "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                                         {"type": "command", "command": hook_cmd(ALLOW_ALL)}]}]}})
        code, out = self.run_main(f)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing found that would stop", out)


if __name__ == "__main__":
    unittest.main()
