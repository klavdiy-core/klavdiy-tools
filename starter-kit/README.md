# starter-kit

**Problem.** People wait for the next model to stop their agent from saying "fixed, tests pass" when it never ran the
tests, from loosening a test until it goes green, from saying "there's no such file" when there is. A bigger model
makes these mistakes less often. It still makes them. A rule in `CLAUDE.md` saying "always run the tests" doesn't fire;
I wrote rules like that for months and broke them anyway.

**Fix.** Checks at the moment of action, wired as Claude Code hooks, plus a short `CLAUDE.md` where every rule names
the hook that enforces it. Install into any project in one command.

```
python install.py /path/to/your/project
```

| hook | when | what it does |
|---|---|---|
| [`claim_check.py`](hooks/claim_check.py) | `Stop` | The reply claims success ("fixed", "works", "tests pass", «починил», «тесты проходят»…), the session edited a code file, and **no test command ran after that edit, or the last one failed**. Reply held back (exit 2), the model is told what's missing. Failure is read from the exit code **and** from the output, because `pytest \| tail` exits 0 whatever pytest said. Saying plainly "I haven't run the tests" passes: honesty is the way out, not a skip flag. |
| [`test_guard.py`](hooks/test_guard.py) | `PreToolUse` on `Edit\|MultiEdit\|Write` | An edit to a test file that drops assertions, adds a skip (`skip`, `xfail`, `xit`, `.only`, `@Disabled`, `t.Skip`…) or deletes a test function **asks the human first**, with the counts before and after. |
| [`absence_gate`](../absence-gate/) | `Stop` | "There's no X / not found" when the disk has X: held back (wired only if `rg` is installed). |
| [`zero_search_hook`](../absence-gate/zero_search_hook.py) | `PostToolUse` on `Grep` | A search that came back empty only because `.gitignore` or a dot-folder hid the file: the model is told next to the result. |

`install.py` copies the hooks into `.claude/hooks/starter-kit/`, **merges** them into `.claude/settings.json` (your
own hooks and settings stay; a `.bak` is left), and writes [`CLAUDE.md`](CLAUDE.md) only if the project has none.
Running it twice changes nothing.

**About the CLAUDE.md.** It is not mine. My own instruction files stay out of this repository, as the top README says.
This one is a skeleton: a few lines for your project's facts, and three groups of rules (memory in files, verify
before you claim, say "I don't know"), each with the hook that checks it. It is short on purpose. The hooks do the work;
the text only tells the model why it was stopped.

**Every failure is loud.** No transcript, unreadable input, a crash: `claim_check` exits 2 `GATE_BROKEN`, `test_guard`
asks. A broken check must not read as a pass. To avoid a loop, `claim_check` lets go once when Claude Code is already
continuing from a Stop hook (`stop_hook_active`).

**Tested.** `python tests/test_starter.py`: claims with no run, a green run, a red run, a red run hidden behind a pipe,
a run *before* the last edit only, docs-only edits, honest "not tested", Russian phrasings, twelve test-runner command
shapes (including a test file run directly and `--selftest`), assertion drop, a skip alone, a deleted assertion-free
test, MultiEdit, Write over an existing file, broken input, and an install into a project that already has settings, run
twice. Every check here was broken on purpose to see the test go red first (8 planted breaks; 3 of them first survived
and showed holes in the tests, fixed). `claim_check` also reads a real Claude Code transcript: on the session that wrote
it, it found the last test run red behind a `| grep`, which was true at that moment.

**Limits.** It is lexical. `claim_check` knows test commands by shape; a custom runner (`./ci.sh`) is invisible until
you add its pattern. It knows success claims by phrasing; "Shipped! 🚀" slips by. `test_guard` counts, it doesn't
understand: replacing `assert x == 1` with `assert x` keeps the count and passes. Not yet exercised in a live Claude
Code loop, only on its transcripts and hook inputs. Tell me what broke.
