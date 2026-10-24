# CLAUDE.md

Short on purpose. A rule written here does not fire by itself; each rule below names the hook that checks it at the
moment of action. Add your project's facts under "This project". Keep the rest short.

## This project

- What it is, in one line:
- How to run it:
- How to run the tests (the exact command):
- Where notes and decisions live (e.g. `NOTES.md`, `DECISIONS.md`):

## Memory lives in files

- Anything that must survive this session goes into a file in the repo, during the work, not after it.
  The chat is not a carrier.
- Before you say "there is no X" / "I don't have it" / "not found": search the disk, including ignored and hidden
  folders. *Checked by:* `absence-gate` (Stop) and `zero_search_hook` (after Grep) — a claim of absence that the
  disk contradicts is held back.

## Verify before you claim

- "Fixed", "works", "tests pass" need a test run **after your last code edit**, and you read its output (a pipe like
  `| tail` hides the exit code). If you didn't run them, say so; that is an acceptable answer.
  *Checked by:* `claim_check` (Stop).
- A failing test gets a fix in the code, not a weaker test. If you believe the test is wrong, say so and why.
  *Checked by:* `test_guard` (before Edit / Write) — removing an assertion, adding a skip or deleting a test asks the human.
- Write the test first and watch it fail for the right reason before you write the fix. A test that was never red
  proves nothing.
- When something fails after your edit, look at your own change (`git diff`) before you blame the network, SSH, the
  environment or the tool. *Checked by:* `blame_check` (Stop).
- "Done" means the Definition of done in `TASK.md` is met: each command listed there ran green after your last edit.
  *Checked by:* `done_check` (Stop).

## When unsure

- Say "I don't know, I'll check" instead of a smooth guess. Then check.
- Name what you did not do. A skipped step said out loud costs less than one found later.
