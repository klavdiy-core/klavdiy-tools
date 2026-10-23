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

A deployment picks a **cost profile**: e.g. `strict` (rows 1-2 BLOCK) for an agent that must never deny memory,
`gentle` (row 1 only) for a chat. The profile selects a policy; it never edits evidence.

## What each layer has no right to decide

| layer | may | may NOT |
|---|---|---|
| Evidence | find, quote and label lines | turn a match into a verdict; drop a line because it "looks irrelevant"; guess meaning beyond its labels |
| Policy | map evidence fields to BLOCK / REVIEW / ALLOW | search or read files; hide uncertainty (every verdict ships with the evidence and the row number that fired); round a REVIEW up to BLOCK |
| Cost | choose which policy a deployment runs | change facts, labels or the evidence record; make an error invisible by making it cheaper |

The aim (in the reviewer's words): not a gate that never errs, but a gate whose errors stay **visible, explainable and
correctable**.

## Independence checks (to pass before v0.6 code is trusted)

1. **Evidence is stable under policy change.** Same claim + roots -> byte-identical evidence record for every policy.
2. **Policy is pure.** Given a saved evidence record, the verdict is reproducible with no filesystem access.
3. **Known costs stay pinned.** Every accepted false verdict (e.g. "was created yesterday and remains" -> REVIEW) is a
   test in the evidence corpus; a policy change that flips it must show up as a verdict diff, not pass silently.
4. **Adding a marker is not a policy change.** A new evidence label alone flips zero verdicts in the corpus.
