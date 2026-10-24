"""Tests for blame_check and done_check (pure run() functions; no Claude Code needed).
usage: python tests/test_blame_done.py      (from the starter-kit folder)"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "hooks"))
import blame_check, done_check   # noqa: E402

ok = True


def expect(name, got, want):
    global ok
    good = got == want
    ok &= good
    print(("ok  " if good else "FAIL") + f"  {name}: got {got!r}, want {want!r}")


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


def step(name, out="ok", error=False, **inp):
    tid, s = use(name, **inp)
    return [s, result(tid, out, error)]


def transcript(d, steps):
    _n[0] += 1
    p = os.path.join(d, f"t{_n[0]}.jsonl")          # one file per transcript: a shared file let tests read the wrong one
    with open(p, "w", encoding="utf-8") as f:
        for s in steps:
            f.write(json.dumps(s) + "\n")
    return p


def stop(path, msg, cwd=None, active=False):
    return json.dumps({"hook_event_name": "Stop", "transcript_path": path, "stop_hook_active": active,
                       "last_assistant_message": msg, "cwd": cwd or os.path.dirname(path)})


EDIT = step("Edit", file_path="deploy/sync.py", old_string="a", new_string="b")

with tempfile.TemporaryDirectory() as d:
    # ---------- blame_check ----------
    blame = "The deploy still fails, but this looks like a network issue on the server side, not the code."
    t = transcript(d, EDIT + step("Bash", "ssh: connect to host x port 22: Connection timed out", True, command="./deploy.sh"))
    expect("blames the network after an edit, no self-check: blocks", blame_check.run([], stop(t, blame))[0], 2)
    expect("the reason names the edited file", "deploy/sync.py" in blame_check.run([], stop(t, blame))[1], True)

    for phr in ("It's probably an SSH problem on your machine.", "Seems to be a permissions issue in your environment.",
                "This is a flaky test, not my change.", "Скорее всего, проблема в сети, а не в коде.",
                "Похоже, дело в окружении."):
        expect(f"blame phrasing {phr[:30]!r}: blocks", blame_check.run([], stop(t, phr))[0], 2)

    t2 = transcript(d, EDIT + step("Bash", "diff --git a/deploy/sync.py ...", command="git diff deploy/sync.py")
                    + step("Bash", "timed out", True, command="./deploy.sh"))
    expect("blame after git diff of own change: passes", blame_check.run([], stop(t2, blame))[0], 0)
    t3 = transcript(d, EDIT + step("Read", "...", file_path="deploy/sync.py"))
    expect("blame after re-reading the edited file: passes", blame_check.run([], stop(t3, blame))[0], 0)
    t4 = transcript(d, step("Read", "...", file_path="deploy/sync.py") + EDIT)
    expect("a read BEFORE the edit does not count: blocks", blame_check.run([], stop(t4, blame))[0], 2)

    t5 = transcript(d, EDIT + step("Read", "...", file_path="README.md"))
    expect("re-reading some other file is not a self-check: blocks", blame_check.run([], stop(t5, blame))[0], 2)

    # the main trigger is the transcript, not the wording: a failing run after the edit + no look at the change
    neutral = "The deploy still fails with a timeout after my edit."
    expect("failing run after the edit, neutral wording, no self-check: blocks",
           blame_check.run([], stop(t, neutral))[0], 2)
    expect("failing run after the edit, but the diff was looked at: passes",
           blame_check.run([], stop(t2, neutral))[0], 0)
    t8 = transcript(d, EDIT + step("Bash", "FAILED tests/test_sync.py::test_retry", command="pytest -q | tail -3"))
    expect("a failure hidden behind a pipe (exit 0, output FAILED): blocks",
           blame_check.run([], stop(t8, neutral))[0], 2)
    t6 = transcript(d, EDIT + step("Bash", "4 passed", command="pytest -q"))
    expect("green run after the edit, neutral wording: passes", blame_check.run([], stop(t6, neutral))[0], 0)
    t7 = transcript(d, step("Bash", "timed out", True, command="./deploy.sh") + EDIT)
    expect("a failure only BEFORE the edit, no blame: passes",
           blame_check.run([], stop(t7, "Edited sync.py as asked."))[0], 0)

    honest = "This looks like a network issue, but I haven't ruled out my own change yet."
    expect("the honest phrasing really contains a blame", bool(blame_check.BLAME.search(honest)), True)
    expect("honest 'not ruled out my change': passes", blame_check.run([], stop(t, honest))[0], 0)
    expect("no code edit at all: passes", blame_check.run([], stop(transcript(d, []), blame))[0], 0)
    expect("plain mention of ssh, no blame, green run: passes",
           blame_check.run([], stop(t6, "I updated the SSH config path in sync.py."))[0], 0)
    expect("a blame with only a green run and no look at the change: blocks",
           blame_check.run([], stop(t6, blame))[0], 2)
    expect("stop_hook_active lets go once", blame_check.run([], stop(t, blame, active=True))[0], 0)
    broken = blame_check.run([], stop(os.path.join(d, "nope.jsonl"), blame))
    expect("no transcript: loud GATE_BROKEN, exit 2", (broken[0], broken[1].startswith("GATE_BROKEN")), (2, True))

    # ---------- done_check ----------
    task = os.path.join(d, "TASK.md")
    with open(task, "w", encoding="utf-8") as f:
        f.write("# Task\nMake sync retry.\n\n## Definition of done\n- [ ] `pytest -q tests/test_sync.py` passes\n"
                "- [ ] `ruff check deploy` is clean\n\n## Notes\n`not a command` here\n")
    done = "Done: sync now retries three times."
    t = transcript(d, EDIT + step("Bash", "3 passed", command="pytest -q tests/test_sync.py"))
    r = done_check.run([], stop(t, done, cwd=d))
    expect("a DoD command never run: blocks", r[0], 2)
    expect("the reason names the missing command", "ruff check deploy" in r[1], True)
    expect("commands outside the DoD section are not required", "not a command" in r[1], False)

    t = transcript(d, EDIT + step("Bash", "3 passed", command="pytest -q tests/test_sync.py")
                   + step("Bash", "All checks passed!", command="ruff check deploy"))
    expect("every DoD command ran green after the edit: passes", done_check.run([], stop(t, done, cwd=d))[0], 0)

    t = transcript(d, step("Bash", "3 passed", command="pytest -q tests/test_sync.py")
                   + step("Bash", "All checks passed!", command="ruff check deploy") + EDIT)
    expect("DoD run only BEFORE the last edit: blocks", done_check.run([], stop(t, done, cwd=d))[0], 2)

    t = transcript(d, EDIT + step("Bash", "1 failed, 2 passed", True, command="pytest -q tests/test_sync.py")
                   + step("Bash", "All checks passed!", command="ruff check deploy"))
    expect("a DoD command that failed: blocks", done_check.run([], stop(t, done, cwd=d))[0], 2)

    t = transcript(d, EDIT)
    expect("no claim of done: passes", done_check.run([], stop(t, "Still working on the retry logic.", cwd=d))[0], 0)
    expect("honest 'haven't run': passes",
           done_check.run([], stop(t, "Done with the code, but I haven't run the checks.", cwd=d))[0], 0)
    with tempfile.TemporaryDirectory() as empty:
        expect("no TASK.md: passes", done_check.run([], stop(t, done, cwd=empty))[0], 0)

sys.path.insert(0, HERE)
import install   # noqa: E402
with tempfile.TemporaryDirectory() as proj:
    install.install(proj, with_absence_gate=False)
    install.install(proj, with_absence_gate=False)
    with open(os.path.join(proj, ".claude", "settings.json")) as f:
        stops = [c["command"] for h in json.load(f)["hooks"]["Stop"] for c in h["hooks"]]
    for name in ("blame_check.py", "done_check.py"):
        expect(f"install wires {name} once", sum(name in c for c in stops), 1)
        expect(f"install copies {name}", os.path.exists(os.path.join(proj, ".claude", "hooks", "starter-kit", name)), True)

print("ALL OK" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
