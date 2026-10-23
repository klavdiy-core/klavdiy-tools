# absence-gate

**Problem.** An agent says "I searched and there's no record of X" — and X is sitting in a file it didn't open, or in a
folder its search silently skipped (`.gitignore` hides files from a default `rg`/grep with exit code 0). You can write
"always search before claiming absence" into its instructions. It will still do it. I did, many times.

**Fix.** Put the check in the send path. Before a message leaves, the gate:

1. finds sentences that claim absence (English and Russian phrasings; quoted text is ignored — that's someone's words);
2. keeps only claims about the disk (they name a carrier: file, folder, record, memory, a path). "The meeting doesn't
   exist yet" is about the world, and no search can check it;
3. pulls the fact-shaped tokens: dates, numbers, names, ids. A claim with none of them is conversation, and passes with a note;
4. searches your roots with `rg --no-ignore -i`;
5. any hit → exit 4, with the files and a per-token count (so you see that the *date* matched, not just "something did").

```
python absence_gate.py outgoing.txt --root ~/notes --root ~/project
python absence_gate.py --selftest
```

**Wiring.** Anywhere text leaves the agent: a Claude Code `PreToolUse` hook on your send tool, a bot's `send()`, a
`commit-msg` hook. Exit 4 means: open the files, rewrite the sentence. Never add a skip flag — a gate you skip by judgment
is not a gate. If it blocks something wrongly, fix the gate and add that sentence as a regression case.

**What it learned the hard way** (each is a case in `--selftest`):
- a negation inside quotes is a quote, not a claim;
- a capital first letter is grammar, not a name;
- ALL-CAPS emphasis is not a name either;
- a phrasing list is blind to synonyms it lacks: "never saved" slipped through once; add new phrasings as tests;
- the negative-control term is generated at runtime — a literal in the test file gets found *in the test file*.

**Limits.** It checks presence of tokens, not meaning. It will not catch "I don't remember how this works" (no
fact-shaped token), and it can be fooled by a claim that names no carrier. It's a floor, not a judge.
