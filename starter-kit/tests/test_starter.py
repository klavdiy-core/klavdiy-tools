"""Tests for the starter-kit hooks (pure run() functions; no Claude Code needed).
usage: python tests/test_starter.py      (from the starter-kit folder)"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "hooks"))
sys.path.insert(0, HERE)
import claim_check, test_guard, install   # noqa: E402

ok = True


def expect(name, got, want):
    global ok
    good = got == want
    ok &= good
    print(("ok  " if good else "FAIL") + f"  {name}: got {got!r}, want {want!r}")


# ---------- a fake Claude Code transcript ----------
_n = [0]


def use(name, **inp):
    _n[0] += 1
    tid = f"toolu_{_n[0]}"
    return tid, {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}}


def result(tid, text, error=False):
    block = {"type": "tool_result", "tool_use_id": tid, "content": text}
    if error:
        block["is_error"] = True
    return {"type": "user", "message": {"content": [block]}}


def transcript(d, steps):
    p = os.path.join(d, "t.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for s in steps:
            f.write(json.dumps(s) + "\n")
    return p


def stop(path, msg, active=False):
    return json.dumps({"hook_event_name": "Stop", "transcript_path": path, "stop_hook_active": active,
                       "last_assistant_message": msg})


def edit_step(path="src/app.py"):
    tid, s = use("Edit", file_path=path, old_string="a", new_string="b")
    return [s, result(tid, "ok")]


def bash_step(cmd, out, error=False):
    tid, s = use("Bash", command=cmd)
    return [s, result(tid, out, error)]


with tempfile.TemporaryDirectory() as d:
    claim = "Fixed it — all tests pass now."

    t = transcript(d, edit_step())
    expect("claim after an edit, no test run: blocks", claim_check.run([], stop(t, claim))[0], 2)
    expect("the reason names the edited file", "src/app.py" in claim_check.run([], stop(t, claim))[1], True)

    t = transcript(d, edit_step() + bash_step("python -m pytest -q", "12 passed in 0.4s"))
    expect("claim after a green run: passes", claim_check.run([], stop(t, claim))[0], 0)

    t = transcript(d, edit_step() + bash_step("pytest", "1 failed, 11 passed", error=True))
    expect("claim after a red run: blocks", claim_check.run([], stop(t, claim))[0], 2)

    t = transcript(d, edit_step() + bash_step("npm test 2>&1 | tail -5", "Tests: 2 failed, 40 passed"))
    expect("a pipe hides the exit code; the output still says failed: blocks", claim_check.run([], stop(t, claim))[0], 2)

    t = transcript(d, bash_step("pytest", "12 passed") + edit_step())
    expect("tests ran BEFORE the last edit only: blocks", claim_check.run([], stop(t, claim))[0], 2)

    t = transcript(d, edit_step("README.md"))
    expect("only docs were edited: passes", claim_check.run([], stop(t, claim))[0], 0)

    t = transcript(d, edit_step())
    expect("no success claim: passes", claim_check.run([], stop(t, "I changed app.py; next I'll write the test."))[0], 0)
    expect("honest 'not tested': passes", claim_check.run([], stop(t, "Fixed it, but I haven't run the tests yet."))[0], 0)
    expect("Russian claim: blocks", claim_check.run([], stop(t, "Починил, тесты проходят."))[0], 2)
    expect("'verified by the schema' is not a claim of success",
           bool(claim_check.CLAIM.search("The config is verified by the schema.")), False)
    expect("'I verified it' still is", bool(claim_check.CLAIM.search("I verified it works.")), True)
    expect("'not run by CI' is not an honest 'I did not run'",
           claim_check.run([], stop(t, "Fixed; the flaky test is not run by CI, all tests pass."))[0], 2)
    expect("'we have not run the tests' is honest",
           claim_check.run([], stop(t, "Fixed it, but we have not run the tests yet."))[0], 0)
    expect("already continuing: lets it stop", claim_check.run([], stop(t, claim, active=True))[0], 0)

    for cmd in ("go test ./...", "cargo test", "npx vitest run", "node --test", "python -m unittest discover -s tests",
                "dotnet test", "bundle exec rspec", "./gradlew test", "make test",
                "python tests/test_starter.py", "python absence_gate.py --selftest", "node test/app.test.js"):
        t = transcript(d, edit_step() + bash_step(cmd, "ok"))
        expect(f"recognises a test run: {cmd}", claim_check.run([], stop(t, claim))[0], 0)

    for cmd in ("cat tests/test_foo.py", "git diff test_a.py", "pip install pytest", "grep -n pytest setup.cfg",
                "echo pytest -q", "code tests/test_starter.py", "git add app.test.js"):
        t = transcript(d, edit_step() + bash_step(cmd, "ok"))
        expect(f"mentioning tests is not running them: {cmd}", claim_check.run([], stop(t, claim))[0], 2)
    for cmd in ("cd app && pytest -q", "CI=1 npm test", "uv run pytest", "python -X utf8 -m pytest tests",
                "poetry run python tests/test_x.py", "git diff; go test ./..."):
        t = transcript(d, edit_step() + bash_step(cmd, "ok"))
        expect(f"recognises a test run in a longer line: {cmd}", claim_check.run([], stop(t, claim))[0], 0)

    expect("no transcript: GATE_BROKEN, not a silent pass",
           claim_check.run([], json.dumps({"hook_event_name": "Stop", "last_assistant_message": claim}))[0], 2)

    # ---------- test_guard ----------
    def pre(tool, **inp):
        return json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": inp, "cwd": d})

    def decision(out):
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else None

    old = "def test_refund():\n    assert refund(10) == 10\n    assert balance() == 0\n"
    expect("Edit that drops an assertion in a test file: ask",
           decision(test_guard.run(pre("Edit", file_path=os.path.join(d, "tests", "test_pay.py"), old_string=old,
                                       new_string="def test_refund():\n    assert refund(10)\n"))), "ask")
    expect("Edit that adds a skip: ask",
           decision(test_guard.run(pre("Edit", file_path="src/pay.spec.ts", old_string="it('charges once', () => {",
                                       new_string="it.skip('charges once', () => {"))), "ask")
    expect("a skip alone (same tests, same assertions): ask",
           decision(test_guard.run(pre("Edit", file_path="tests/test_pay.py", old_string=old,
                                       new_string="@pytest.mark.skip(reason='flaky')\n" + old))), "ask")
    expect("deleting a test with no assertion in it: ask",
           decision(test_guard.run(pre("Edit", file_path="tests/test_smoke.py",
                                       old_string="def test_boots():\n    boot()\n\ndef test_runs():\n    run()\n",
                                       new_string="def test_boots():\n    boot()\n"))), "ask")
    expect("Edit that adds an assertion: silent",
           decision(test_guard.run(pre("Edit", file_path="tests/test_pay.py", old_string=old,
                                       new_string=old + "    assert fee() == 1\n"))), None)
    expect("Edit of a source file: silent",
           decision(test_guard.run(pre("Edit", file_path="src/pay.py", old_string="assert x", new_string=""))), None)
    os.makedirs(os.path.join(d, "tests"), exist_ok=True)
    with open(os.path.join(d, "tests", "test_cart.py"), "w") as f:
        f.write("def test_a():\n    assert 1\n\ndef test_b():\n    assert 2\n")
    expect("Write that deletes a test function: ask",
           decision(test_guard.run(pre("Write", file_path=os.path.join(d, "tests", "test_cart.py"),
                                       content="def test_a():\n    assert 1\n"))), "ask")
    expect("MultiEdit is read too: ask",
           decision(test_guard.run(pre("MultiEdit", file_path="tests/test_x.py", edits=[
               {"old_string": "assert a == 1", "new_string": "pass"}]))), "ask")
    expect("a broken input asks instead of passing",
           decision(test_guard.run('{"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": 7}')), "ask")

    # ---------- install ----------
    proj = os.path.join(d, "proj")
    os.makedirs(os.path.join(proj, ".claude"))
    with open(os.path.join(proj, ".claude", "settings.json"), "w", encoding="utf-8") as f:
        json.dump({"model": "x", "note": "проект", "hooks": {"Stop": [{"hooks": [{"type": "command",
                                                                                   "command": "mine.sh"}]}]}}, f,
                  ensure_ascii=False)
    install.install(proj, with_absence_gate=False)
    install.install(proj, with_absence_gate=False)
    bak = json.load(open(os.path.join(proj, ".claude", "settings.json.bak"), encoding="utf-8"))
    expect("a second install keeps the .bak of the ORIGINAL settings", "claim_check.py" in json.dumps(bak), False)
    expect("install keeps non-ASCII text readable",
           "проект" in open(os.path.join(proj, ".claude", "settings.json"), encoding="utf-8").read(), True)
    s = json.load(open(os.path.join(proj, ".claude", "settings.json"), encoding="utf-8"))
    cmds = [c["command"] for ev in s["hooks"].values() for h in ev for c in h["hooks"]]
    expect("install keeps the user's own hook", "mine.sh" in cmds, True)
    expect("install is idempotent (claim_check once)", sum("claim_check.py" in c for c in cmds), 1)
    expect("install wires test_guard on Edit|Write", any("test_guard.py" in c for h in s["hooks"]["PreToolUse"]
                                                          for c in [x["command"] for x in h["hooks"]]), True)
    expect("install keeps other settings", s["model"], "x")
    expect("install writes CLAUDE.md when there is none", os.path.exists(os.path.join(proj, "CLAUDE.md")), True)
    with open(os.path.join(proj, "CLAUDE.md"), "w") as f:
        f.write("my own rules\n")
    install.install(proj, with_absence_gate=False)
    expect("install never overwrites an existing CLAUDE.md", open(os.path.join(proj, "CLAUDE.md")).read(), "my own rules\n")

# an external review (25.10): a code change made through the shell was not a «last code edit», so a success claim
# after it, with no test run, went through
with tempfile.TemporaryDirectory() as d:
    claim = "Fixed it — all tests pass now."
    for cmd in ("python edit_project_files.py", "sed -i 's/a/b/' src/app.py", "echo 'x = 1' > src/app.py",
                "git apply fix.patch", "git checkout other-branch -- src/app.py", "perl -pi -e 's/a/b/' app.py"):
        t = transcript(d, bash_step(cmd, "updated app.py"))
        expect(f"shell edit `{cmd}`, no test run: blocks", claim_check.run([], stop(t, claim))[0], 2)
    t = transcript(d, bash_step("python edit_project_files.py", "updated app.py") + bash_step("pytest -q", "3 passed"))
    expect("shell edit then a green run: passes", claim_check.run([], stop(t, claim))[0], 0)
    for cmd in ("cat src/app.py", "ls -la", "git status", "git diff", "grep -n foo src/app.py", "echo hi > notes.md"):
        t = transcript(d, bash_step(cmd, "..."))
        expect(f"read-only or non-code shell `{cmd}`: passes", claim_check.run([], stop(t, claim))[0], 0)

# a second review of 442d78f: false blocks in ordinary work (a green run first, then ONE command, then the claim)
with tempfile.TemporaryDirectory() as d:
    claim = "Fixed it — all tests pass now."
    for cmd in ("sed -i 's/a/b/' src/app.py && pytest -q", "echo 'x=1' > src/app.py ; pytest -q",
                "python --version", "python -V", "node --version", "python -m http.server", "python manage.py runserver",
                "cp logo.png assets/logo.png", "mv notes.txt old_notes.txt", "ls | tee list.txt",
                "git checkout -b feature", "git restore --staged src/app.py"):
        t = transcript(d, bash_step("pytest -q", "3 passed") + bash_step(cmd, "3 passed" if "pytest" in cmd else "ok"))
        expect(f"not a code edit (or edited and tested) `{cmd}`: passes", claim_check.run([], stop(t, claim))[0], 0)
    t = transcript(d, bash_step("pytest -q", "3 passed") + bash_step("sed -i 's/a/b/' src/app.py && pytest -q",
                                                                     "1 failed, 2 passed"))
    expect("edited and tested in one command, red: blocks", claim_check.run([], stop(t, claim))[0], 2)
    for cmd in ("sed -ni 's/a/b/p' src/app.py", "sed --in-place 's/a/b/' src/app.py", "bash fix.sh", "black src/",
                "prettier --write src/app.js", "ruff check --fix src", "gofmt -w main.go", "cargo fmt", "rm src/app.py",
                "git rm src/app.py", "curl -o src/app.py https://example.org/app.py", "cp new.py src/app.py"):
        t = transcript(d, bash_step("pytest -q", "3 passed") + bash_step(cmd, "ok"))
        expect(f"shell edit `{cmd}` after the last run: blocks", claim_check.run([], stop(t, claim))[0], 2)

# a second review: a formatter that only checks writes nothing
with tempfile.TemporaryDirectory() as d:
    claim = "Fixed it — all tests pass now."
    for cmd in ("black --check src/", "black --diff src/", "isort --check-only src/", "isort --diff src/",
                "ruff format --check src/"):
        t = transcript(d, bash_step("pytest -q", "3 passed") + bash_step(cmd, "ok"))
        expect(f"a check-only formatter `{cmd}`: passes", claim_check.run([], stop(t, claim))[0], 0)

# a nested shell runs the same edit: `sh -c 'sed -i ...'` is an edit, `bash -c "pytest -q"` is a run
with tempfile.TemporaryDirectory() as d:
    claim = "Fixed it — all tests pass now."
    for cmd in ("sh -c 'sed -i s/a/b/ src/app.py'", 'bash -c "sed -i s/a/b/ src/app.py"',
                "zsh -c 'black src/'",
                # second review of 627b05f: flags before -c, substitutions, prefixes
                "bash -lc 'sed -i s/a/b/ src/app.py'", "bash -ec 'sed -i s/a/b/ src/app.py'",
                "bash -e -c 'sed -i s/a/b/ src/app.py'", "bash --login -c 'sed -i s/a/b/ src/app.py'",
                "echo $(sed -i s/a/b/ src/app.py)", "echo `sed -i s/a/b/ src/app.py`",
                "sudo sed -i s/a/b/ src/app.py", "env LC_ALL=C sed -i s/a/b/ src/app.py",
                "LC_ALL=C sed -i s/a/b/ src/app.py", "/bin/sed -i s/a/b/ src/app.py",
                "sudo -E /usr/bin/sed -i s/a/b/ src/app.py"):
        t = transcript(d, bash_step("pytest -q", "3 passed") + bash_step(cmd, "ok"))
        expect(f"nested shell edit `{cmd}` after the last run: blocks", claim_check.run([], stop(t, claim))[0], 2)
    for cmd in ("sh -c 'ls src'", "bash -c \"sed -i s/a/b/ src/app.py && pytest -q\""):
        t = transcript(d, bash_step("pytest -q", "3 passed") + bash_step(cmd, "3 passed"))
        expect(f"nested shell, no edit or edited and tested `{cmd}`: passes", claim_check.run([], stop(t, claim))[0], 0)

print("ALL OK" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
