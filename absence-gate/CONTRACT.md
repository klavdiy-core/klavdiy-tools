# absence-gate — contract between evidence, policy and cost (draft for v0.6)

Proposed by the second reviewer after v0.5.1: separate **Evidence** (what was found, where, in what context),
**Policy** (which evidence is enough for BLOCK / REVIEW / ALLOW) and **Cost** (what happens when the verdict is wrong).
This file is the contract, written before the code — so the layers can be checked for independence first.

## 1. Evidence — facts only, no judgment

Input: one claim sentence + search roots. Output: a record, the same for every policy.

```json
{
  "claim": "I couldn't find the document for Alice about project X-918 in my files.",
  "about_disk": true,
  "fact_tokens": ["Alice", "X-918"],
  "content_words": ["document", "project"],
  "per_token_files": {"Alice": 3, "X-918": 1},
  "files_with_all_tokens": ["notes.md"],
  "lines_with_all_tokens": [
    {"file": "notes.md", "line": 14, "text": "...", "has_absence": false, "has_negation": false,
     "has_modality": true, "has_all_content_words": true}
  ]
}
```

Rule: evidence never says BLOCK. It only labels what is on the line. A new marker (a new kind of negation, a new tense)
is an evidence change — and must not change any verdict until a policy uses it.

## 2. Policy — a table over evidence, nothing else

A policy is an ordered list of `(condition over evidence fields) -> verdict`, first match wins. v0.5.1 as data:

| # | condition | verdict |
|---|---|---|
| 1 | some line: all tokens, all content words, no absence, no negation, no modality | BLOCK |
| 2 | some line with all tokens has absence or negation | REVIEW |
| 3 | some line with all tokens has modality | REVIEW |
| 4 | some line has all tokens (but not all content words) | REVIEW |
| 5 | some file has all tokens | REVIEW |
| 6 | some token exists anywhere | REVIEW |
| 7 | otherwise | ALLOW |

Rule: a policy reads only evidence fields; it never searches. Two policies over the same evidence record must be
runnable side by side, so a change of policy is a diff of verdicts on a fixed evidence corpus.

## 3. Cost — chosen per use, not hidden in the code

| verdict wrong as | cost | who pays |
|---|---|---|
| false BLOCK | a true claim is stopped; the agent is accused of an error it did not make; trust in the gate drops | the agent, then the person |
| false REVIEW | one extra look | whoever opens the files |
| false ALLOW | the original failure: "I don't have it" while the disk has it | the person who believed it |

A deployment picks a **cost profile**. ~~A profile selects which rows BLOCK~~ — that was wrong in the first draft
(caught by the reviewer): making rule 2 (a line with a negation) BLOCK under a "strict" profile turns weak evidence into
strong, which this contract itself forbids. Two decisions are kept apart:

- **verdict** — BLOCK / REVIEW / ALLOW — comes from evidence and policy only, the same in every deployment;
- **action** — `send` / `hold for a look` / `stop` — is what a deployment does with a verdict; this is where cost lives.

| profile | BLOCK | REVIEW | ALLOW |
|---|---|---|---|
| `strict` (an agent that must never deny memory) | stop | hold for a look | send |
| `gentle` (a chat) | stop | send, with the evidence attached | send |

A held REVIEW is reported as **"held by cost, not by evidence"** — the verdict stays REVIEW. Cost may move the action
threshold; it may never pretend to be evidence.

## What each layer has no right to decide

| layer | may | may NOT |
|---|---|---|
| Evidence | find, quote and label lines | turn a match into a verdict; drop a line because it "looks irrelevant"; guess meaning beyond its labels |
| Policy | map evidence fields to BLOCK / REVIEW / ALLOW | search or read files; hide uncertainty (every verdict ships with the evidence and the row number that fired); round a REVIEW up to BLOCK |
| Cost | choose which policy a deployment runs | change facts, labels or the evidence record; make an error invisible by making it cheaper |

**ALLOW is not "true".** It means only "this policy found no ground to stop the claim". A caller that reads ALLOW
as "the agent was right" returns to the original failure from the other side. The same holds for every verdict: it
answers "what may be concluded from what was observed", never "what is so".

In short: evidence answers *what was observed*; policy answers *what may be concluded from it*; cost answers *which
threshold is justified here* — and no layer may forge another's answer.

The aim (in the reviewer's words): not a gate that never errs, but a gate whose errors stay **visible, explainable and
correctable**.

## Independence checks (to pass before v0.6 code is trusted)

1. **Evidence is stable under policy change.** Same claim + roots -> byte-identical evidence record for every policy.
2. **Policy is pure.** Given a saved evidence record, the verdict is reproducible with no filesystem access.
3. **Known costs stay pinned.** Every accepted false verdict (e.g. "was created yesterday and remains" -> REVIEW) is a
   test in the evidence corpus; a policy change that flips it must show up as a verdict diff, not pass silently.
4. **Adding a marker is not a policy change.** A new evidence label alone flips zero verdicts in the corpus.
5. **Cost never changes a verdict.** For one evidence record, every profile reports the same verdict; only the action differs.

Each check counts only if it can catch a planted violation: a policy that opens a file must fail check 2; a profile
that rewrites a verdict must fail check 5; a marker that silently flips a verdict must fail check 4. A green check that
was never red is evidence, not absolution.

## Blind corpus (held-out examples the author never saw)

1. The corpus author writes each case — claim, files, **expected verdict and a short reason** — before the gate runs.
2. Mismatches between expected and actual are published as they are, not smoothed.
3. After results are revealed, cases are not edited in place; a correction is a separate change with its reason.
4. The corpus holds expected `REVIEW` and `ALLOW` cases too, not only `BLOCK` — otherwise a gate that blocks everything
   would look perfect.
