# absence-gate

**Problem.** An agent says "I searched and there's no record of X" — and X is sitting in a file it didn't open, or in a
folder its search silently skipped (`.gitignore` hides files from a default `rg`/grep with exit code 0). You can write
"always search before claiming absence" into its instructions. It will still do it. I did, many times.

**Fix.** Put the check in the send path. Before a message leaves, the gate:

1. finds sentences that claim absence (English and Russian phrasings; quoted text is ignored — that's someone's words);
2. keeps only claims about the disk (they name a carrier: file, folder, record, memory, a path). "The meeting doesn't
   exist yet" is about the world, and no search can check it;
3. pulls the fact-shaped tokens: dates, numbers, names, ids. A claim with none of them is conversation, and passes with a note;
4. **gathers evidence** with `rg -uu -P -i` (ignore files off, hidden folders on, whole words only): per token, how many
   files hold it; which files hold *all* of them together; the matching lines with their numbers; and file paths that
   hold the tokens in their names;
5. **decides by policy**, separately from the gathering:
   - `BLOCK` (exit 4) — one **line** holds every fact token, and that line is not itself an absence statement
     (v0.3: one file is co-storage, not a link — two unrelated lines in one notes file are `REVIEW`);
   - `REVIEW` (exit 5) — tokens exist but only scattered across files, or the only matching lines say "not found"
     themselves. A lexical gate can't tell "ZX-4417 exists" from "I could not find ZX-4417" — so it shows the line
     and hands the call to whoever opens the file;
   - `PASS` (exit 0) — nothing anywhere, or not a checkable claim.

A token existing somewhere is not proof that the *thing* claimed absent exists. That distinction is the whole of v0.2.

```
python absence_gate.py outgoing.txt --root ~/notes --root ~/project
python absence_gate.py --selftest
```

**Wiring.** In Claude Code use the wrappers, not the raw exit codes (Claude Code ignores 4 and 5):
```json
{"hooks": {
  "Stop": [{"hooks": [{"type": "command", "command": "python /path/absence-gate/claude_code_hook.py --root /path/to/notes"}]}],
  "PostToolUse": [{"matcher": "Grep", "hooks": [{"type": "command", "command": "python /path/absence-gate/zero_search_hook.py"}]}]
}}
```
Elsewhere — a bot's `send()`, a `commit-msg` hook — call `absence_gate.py` directly. Exit 4 means: open the files, rewrite the sentence. Never add a skip flag — a gate you skip by judgment
is not a gate. If it blocks something wrongly, fix the gate and add that sentence as a regression case.

**What it learned the hard way** (each is a case in `--selftest`):
- a negation inside quotes is a quote, not a claim;
- a capital first letter is grammar, not a name;
- ALL-CAPS emphasis is not a name either;
- a phrasing list is blind to synonyms it lacks: "never saved" slipped through once; add new phrasings as tests;
- the negative-control term is generated at runtime — a literal in the test file gets found *in the test file*.

**v0.2 — after an outside review.** A GPT model read v0.1's code (not just this README) and found three real holes:
an OR-search across the tree blocked "no document for Alice about X-918" when Alice and X-918 lived in different
files; a line saying "I could not find ticket ZX-4417" counted as proof the ticket exists; and a quoted name
(`The file "Orlova-2027" doesn't exist`) escaped the check because quotes were stripped as speech. Each is now a
self-test case, and each was confirmed wrong on v0.1 before the fix. Its main point I agree with: separate evidence from
decision, and formalise which claims a gate may block and what proof is enough — before making the extraction smarter.

**v0.3 — the second review** (another model, reading the published v0.2) found the fourth hole: "Alice called about
the budget" and "X-918 belongs to an unrelated project" in one notes file made v0.2 block "no document for Alice about
X-918". Now the strongest evidence a lexical gate can see is one line holding every token; the same file on different
lines is `REVIEW`. Quotes became a test class of their own (file name, id, person stay in the claim; a quoted sentence
and a nested quotation are speech). Per-format records (a JSONL entry, a table row) are the next rung, not this one.

**v0.4 — the fifth hole: mention is not existence.** "Alice and project X-918 were discussed at the meeting" holds both
tokens on one line, yet proves only that they were mentioned together, not that a *document* exists; "Alice is not
associated with X-918" even says the opposite. A lexical gate cannot decide existence — so `BLOCK` got narrower again.

**v0.5 — the sixth hole: tense and modality.** "will be created tomorrow", "may exist", "was deleted yesterday" name the
thing but don't say it exists *now*. A short, deliberately narrow list of markers sends such lines to `REVIEW`. In the
reviewer's words: not "become smarter" — "define more precisely when you have the right to be sure".

**What it is, and what it is not.** The gate has learned to *cut off* several known kinds of evidence that do not
support "the thing exists now" (a token alone, co-storage, co-mention, negation, future/possibility/ended past). It has
**not** learned to *prove* existence: "The document for Alice about X-918 exists" can be false, and "was created yesterday
and remains in /contracts" describes a real file yet goes to `REVIEW` because of its tense — a known false `REVIEW`, pinned
as a self-test so it stays visible. The next rung is not better negation detection; it is **calibrating the gate's
authority**: which claims it may block at all, and on what evidence. Self-test N/N means the lessons written so far are
not forgotten — not that the gate is reliable.

**v0.5.2 — after blind run 1: ALLOW has two meanings, now told apart.** The first blind corpus held 20 *positive*
claims ("The document … exists"); the gate evaluates only *absence* claims, so all 20 came back ALLOW without being
looked at ([results](blind-runs/run-1/RESULTS.md)). Both still exit 0 (so existing hooks don't break), but the first
line now says which:
- `ABSENCE_GATE_OK` — at least one claim was checked against the disk and none was contradicted;
- `ABSENCE_GATE_NOT_APPLICABLE` — nothing was evaluated (no absence claim, or none checkable). It does **not** mean
  the text is true.

**v0.6 — the third review (Fable 5.1), and the wire.** It read the code, not the README, and found what eight tiny
self-test files could never show. Graded: method 9/10, code 6/10, readiness 3/10. All eleven new cases were run against
v0.5.2 first and are red there (`tests/red_on_previous.py d68d989` → 11/11):
1. **File names are evidence.** "I don't have budget-2027.xlsx" with that file in the root passed — a binary file has no
   line to match. Now the file list (`rg --files -uu`) is searched too; a path holding every fact token, in a claim about a
   file, is `BLOCK`.
2. **Dot-folders.** `--no-ignore` still skips `.claude/`, `.obsidian/`, `.memory/` — exactly where agent memory lives.
   Now `-uu`.
3. **Words, not substrings.** "Ola" was found in "Cola" and v0.5.2 *blocked* — a false accusation; "ZT-5" matched
   "ZT-55". Tokens now have word boundaries on both sides (rg `-P` and Python share one regex). Russian names decline:
   "Сидоровым" finds "Сидоровой" through a crude stem.
4. **The wire was cut.** Claude Code blocks only on exit 2 and shows the model only stderr. Exit 4/5 stopped nothing, and a
   crash (no `rg`) failed *open*. → [`claude_code_hook.py`](claude_code_hook.py): Stop or PreToolUse, `BLOCK`→2,
   `REVIEW`→2 with "open these lines, then rewrite or say why they don't count" (once — not again while already continuing),
   any error → 2 `GATE_BROKEN`. The Stop hook reads `last_assistant_message`: it checks Claude Code's own replies.

Smaller ones, also cases now: facts one or two sentences back ("Searched my notes for ZX-4417. Nothing found."); a
possessive name at the start ("Petrov's ticket…"); more phrasings ("didn't find", "missing", "отсутствует"…); a
capitalised word alone never convicts (BLOCK needs a digit or an id); a clean line next to a "was deleted" line is a
**conflict** → `REVIEW`; two-character ids ("Q3"); the deciding lines are printed first, **with line numbers**.

**And the cause, not the sentence.** The reviewer's main point: the bug isn't the wording, it's a search that returned a
silent zero. [`zero_search_hook.py`](zero_search_hook.py) is a `PostToolUse` hook on Grep: it re-runs the pattern itself,
default and `-uu`; if only the second finds something, the model is told *next to the tool result* — before any
sentence is written, and no synonym gets around it. absence-gate stays the second line. Both wrappers: `tests/test_hooks.py`.

## What the gate may block (the policy, written down)

| evidence | verdict |
|---|---|
| a file whose **path** holds every fact token, when the claim is about a file, and a token has a digit or id shape | `BLOCK` (v0.6) |
| one line holds every fact token **and** every content word of the claim ("document", "ticket"), in plain present, with no negation — and at least one token has a digit or id shape | `BLOCK` |
| such a plain line **and** another line that negates it or says it ended | `REVIEW` — conflict (v0.6) |
| such a plain line, but the tokens are only capitalised words ("Python", "Petrov") | `REVIEW` — a name alone doesn't convict (v0.6) |
| one line holds every fact token, but carries a negation or an absence phrase | `REVIEW` |
| one line holds every fact token, but speaks of the future, a possibility, or a past that ended ("will be created", "may exist", "was deleted") | `REVIEW` (v0.5) |
| one line holds every fact token, but not the thing the claim says is absent | `REVIEW` |
| one file holds the tokens on different lines | `REVIEW` — co-stored is not linked |
| the tokens exist only scattered across files | `REVIEW` |
| no token anywhere, or the claim is about the world / has no fact-shaped token | `PASS` |

The asymmetry is on purpose: a dumb gate errs toward "go and look", never toward "forbidden". `BLOCK` is rare by
design; `REVIEW` is its normal answer when the evidence is partial — and the evidence is always printed.

**Limits.** It checks presence of tokens, not meaning. It will not catch "I don't remember how this works" (no
fact-shaped token), and it can be fooled by a claim that names no carrier. It's a floor, not a judge.
