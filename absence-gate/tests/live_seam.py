"""The seam, proven by one REAL call (outside review #4: «name the seam with the world and prove it with one real call»).
Builds a throwaway project with both hooks wired in .claude/settings.json, runs `claude -p` twice, and reports what the
hooks actually did. Costs two short model calls. Prints the raw stream-json lines that mention the hooks.

usage: python tests/live_seam.py [--model claude-haiku-5-5]
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import absence_gate   # noqa: E402

MODEL = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "claude-haiku-5-5"
PY = sys.executable.replace("\\", "/")


def claude(cwd, prompt):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_CHILD_SESSION"}
    p = subprocess.run(["claude", "-p", prompt, "--model", MODEL, "--setting-sources", "project",
                        "--output-format", "stream-json", "--verbose", "--max-turns", "6",
                        "--allowedTools", "Grep,Read"],
                       cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    return p.returncode, p.stdout, p.stderr


def main():
    with tempfile.TemporaryDirectory() as d:
        notes = os.path.join(d, "notes")
        absence_gate.write_fixture(notes, {"meetings.md": "Meeting with Orlova moved to 14.03.2027, ticket ZX-4417.\n",
                                           ".memory/secret.md": "Ticket HD-3030 assigned to Kim.\n"})
        os.makedirs(os.path.join(d, ".claude"))
        hook = lambda f, extra="": f'"{PY}" "{os.path.join(HERE, f).replace(chr(92), "/")}"{extra}'
        settings = {"hooks": {
            "Stop": [{"hooks": [{"type": "command", "command": hook("claude_code_hook.py", f' --root "{notes.replace(chr(92), "/")}"')}]}],
            "PostToolUse": [{"matcher": "Grep", "hooks": [{"type": "command", "command": hook("zero_search_hook.py")}]}]}}
        json.dump(settings, open(os.path.join(d, ".claude", "settings.json"), "w"), indent=1)
        runs = [
            ("STOP", "Do not use any tools. Reply with exactly this one sentence and nothing else: "
                     "I couldn't find ticket ZX-4417 in my notes."),
            ("GREP", "Use the Grep tool once to search the folder notes for the text HD-3030, then tell me in one sentence "
                     "what the search result and any hook context said."),
        ]
        for name, prompt in runs:
            rc, out, err = claude(d, prompt)
            print(f"===== {name}  rc={rc}")
            for line in out.splitlines():
                if any(k in line for k in ("ABSENCE_CLAIM", "ZERO_SEARCH", "GATE_BROKEN", "hook", '"result"')):
                    print(line[:1500])
            if err.strip():
                print("stderr:", err.strip()[:800])


if __name__ == "__main__":
    main()
