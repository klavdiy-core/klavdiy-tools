"""Unit tests for the two Claude Code wrappers (pure run() functions; no Claude Code needed).
usage: python tests/test_hooks.py      (from the absence-gate folder; needs rg)"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import absence_gate, claude_code_hook, zero_search_hook   # noqa: E402

ok = True


def expect(name, got, want):
    global ok
    good = got == want
    ok &= good
    print(("ok  " if good else "FAIL") + f"  {name}: got {got!r}, want {want!r}")


with tempfile.TemporaryDirectory() as d:
    absence_gate.write_fixture(d, {"notes.md": "Meeting with Orlova moved to 14.03.2027, ticket ZX-4417.\n",
                                   ".memory/secret.md": "Ticket HD-3030 assigned to Kim.\n",
                                   "ignored/x.md": "Ticket IG-4040 lives here.\n",
                                   ".gitignore": "ignored/\n",
                                   "mixed.md": "Carol called about the budget.\nPR-301 belongs to the migration.\n"})
    os.makedirs(os.path.join(d, ".git"), exist_ok=True)      # makes rg honour .gitignore, like a real repo
    R = ["--root", d]

    def stop(msg, active=False):
        return json.dumps({"hook_event_name": "Stop", "stop_hook_active": active, "last_assistant_message": msg})

    expect("Stop: contradicted claim blocks (exit 2)", claude_code_hook.run(R, stop("I couldn't find ZX-4417 in my notes."))[0], 2)
    expect("Stop: report goes to stderr text", "ZX-4417" in claude_code_hook.run(R, stop("I couldn't find ZX-4417 in my notes."))[1], True)
    review = "I couldn't find the document for Carol about project PR-301 in my files."
    expect("Stop: REVIEW asks to look (exit 2)", claude_code_hook.run(R, stop(review))[0], 2)
    expect("Stop: REVIEW passes once already continuing", claude_code_hook.run(R, stop(review, True))[0], 0)
    expect("Stop: --block-only lets REVIEW pass", claude_code_hook.run(R + ["--block-only"], stop(review))[0], 0)
    expect("Stop: BLOCK still blocks while continuing", claude_code_hook.run(R, stop("I couldn't find ZX-4417 in my notes.", True))[0], 2)
    expect("Stop: no claim passes", claude_code_hook.run(R, stop("The build is green."))[0], 0)
    expect("Stop: missing field is GATE_BROKEN", claude_code_hook.run(R, json.dumps({"hook_event_name": "Stop"}))[0], 2)
    expect("no roots is GATE_BROKEN", claude_code_hook.run([], stop("I couldn't find ZX-4417 in my notes."))[0], 2)
    pre = json.dumps({"hook_event_name": "PreToolUse", "tool_input": {"chat_id": 1, "text": "There is no record of HD-3030 in my files."}})
    expect("PreToolUse: tool text is checked (hidden dir found)", claude_code_hook.run(R, pre)[0], 2)
    saved = os.environ["PATH"]
    os.environ["PATH"] = ""                                    # no rg -> must not read as a pass
    try:
        code, err = claude_code_hook.run(R, stop("I couldn't find ZX-4417 in my notes."))
        expect("broken search is GATE_BROKEN, exit 2", (code, err.startswith("GATE_BROKEN")), (2, True))
    finally:
        os.environ["PATH"] = saved

    def grep(pattern):
        return zero_search_hook.run(json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Grep", "cwd": d,
                                                "tool_input": {"pattern": pattern, "path": d}}))
    expect("zero search: hidden-only hit is reported", "ZERO_SEARCH_WAS_BLIND" in grep("HD-3030"), True)
    expect("zero search: gitignored-only hit is reported", "ZERO_SEARCH_WAS_BLIND" in grep("IG-4040"), True)
    expect("zero search: a visible hit says nothing", grep("ZX-4417"), "")
    expect("zero search: a true zero says nothing", grep("QQ-0000"), "")
    expect("zero search: other tools ignored", zero_search_hook.run(json.dumps({"tool_name": "Bash"})), "")

    # The REAL Grep tool_response shapes, captured from Claude Code on 23.10.2026 (live seam test). Its Grep sees hidden
    # files but obeys .gitignore — the first version of this hook re-ran a default rg instead and cried «blind» on a hit.
    def real(pattern, resp):
        return zero_search_hook.run(json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Grep", "cwd": d,
                                                "tool_input": {"pattern": pattern, "path": d, "output_mode": "content"},
                                                "tool_response": resp}))
    hit = {"mode": "content", "numFiles": 0, "filenames": [], "numLines": 1, "totalLines": 1,
           "content": ".memory/secret.md:1:Ticket HD-3030 assigned to Kim."}
    empty = {"mode": "content", "numFiles": 0, "filenames": [], "content": "", "numLines": 0, "totalLines": 0}
    expect("real response: the tool found the hidden file -> silent", real("HD-3030", hit), "")
    expect("real response: tool zero, gitignored file has it -> reported", "ZERO_SEARCH_WAS_BLIND" in real("IG-4040", empty), True)
    expect("real response: tool zero, true zero -> silent", real("QQ-0000", empty), "")
    expect("real response: files mode hit -> silent", real("ZX-4417", {"mode": "files_with_matches", "numFiles": 1,
                                                                       "filenames": ["notes.md"]}), "")

print("TEST_HOOKS", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
