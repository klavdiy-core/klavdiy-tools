#!/usr/bin/env python3
"""absence_gate.py — refuse to send "I don't have it" when the disk has it.

An agent writes rules into its memory ("search before claiming something doesn't exist") and breaks them anyway:
Anthropic's own Opus 4.8 system card calls this "ignored correction". A rule in memory doesn't fire. A check at the
point of action does. This gate sits in the send path: it reads the outgoing text, finds claims of ABSENCE
("I couldn't find", "there is no record", "not saved anywhere"), runs the search itself over the roots you give it,
and exits 4 if the disk contradicts the claim. The agent then has to open the files and rewrite — not argue.

Usage:
  python absence_gate.py <textfile> --root DIR [--root DIR ...]   exit 0 pass · 4 BLOCK · 5 REVIEW · 2 usage
  python absence_gate.py --selftest                                planted red + negative control, in a temp dir

v0.2 (after an outside review, 23.10.2026): evidence gathering is separated from the decision.
  evidence: per claim — which files hold ALL of its fact tokens together, and the matching lines themselves;
  policy:   BLOCK  — one file holds every fact token, and its matching line is not itself an absence statement;
            REVIEW — tokens exist but only scattered across files, or the only matching lines say "not found"
                     themselves (a lexical gate can't tell "ZX-4417 exists" from "I could not find ZX-4417");
            PASS   — no token anywhere, or the claim is not about the disk / has no fact-shaped token.
  A token merely existing somewhere is not proof that the thing claimed absent exists.

Requires ripgrep (`rg`) on PATH. Searches with --no-ignore and case-insensitive on purpose: .gitignore silently hides
files from a default search, and a silent zero reads exactly like a real one.

Wire it into whatever sends: a Claude Code PreToolUse hook, a chat bot's send function, a commit-msg hook.
Fail-closed: any hit blocks. False blocks are fixed in the gate (with a regression test), never by a skip flag.
"""
import re
import subprocess
import sys
import tempfile
import os

# --- what counts as a claim of absence (EN + RU). Broad on purpose: a false positive costs one search,
# a false negative costs a lie. A list of phrasings is blind to synonyms it lacks — add the new ones as tests.
ABSENCE = re.compile(
    r"(couldn'?t find|could not find|can'?t find|not found|no (record|entry|file|note|mention)s?\b|"
    r"nothing (recorded|found|saved|anywhere)|there is nothing|never (saved|recorded|written)|"
    r"not (saved|recorded|written down|stored)|doesn'?t exist|does not exist|i don'?t have|no such|"
    r"нигде не (запис|найд|встреч|сохран)|не сохран(ил|ён|ен|ены|ено)|не найден|не нашёл|не нашел|ничего нет|"
    r"нет нигде|нет записи|не записан|не существует|у меня (этого )?нет)",
    re.I)

# --- a claim is checkable by the disk only if it is ABOUT the disk (names a carrier). "The meeting doesn't exist
# yet" is a claim about the world; no search can confirm it, and blocking it with unrelated hits is worse than silence.
DISK_ANCHOR = re.compile(
    r"file|folder|director|archive|record|note|log\b|memory|index|saved|stored|search|found|disk|repo|"
    r"[\\/][\w.\-]+|\.(md|txt|json|py|ps1|jsonl|csv|pdf|png|jpg)\b|"
    r"файл|папк|архив|запис|заметк|журнал|памят|индекс|сохран|нашёл|нашел|искал|поиск|диск", re.I)

# Quoted SPEECH (several words) is someone's words, not my claim — blanked. A quoted single token is a NAME
# (a file, an id: «The file "Orlova-2027" doesn't exist») and stays part of the claim (v0.1 let it escape).
QUOTED = re.compile(r"«([^«»\n]{0,300})»|“([^“”\n]{0,300})”|\"([^\"\n]{1,300})\"")


def unquote(text):
    def repl(m):
        inner = next(g for g in m.groups() if g is not None)
        return inner if not re.search(r"\s", inner.strip()) else " "
    return QUOTED.sub(repl, text)
WORD = re.compile(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_\-\.]{2,}")
STOP = set("""the a an of to in on at for and or is are was were be been it its this that these those my your his her
our their me you him us them i we there here where when what which who how not no yes do does did have has had any
и в во не на с со к ко по у о об от для из за то что это как так же бы ли или а но да нет я ты он она мы вы они""".split())
GENERIC = set("""searched search found find memory record recorded file files folder note notes saved stored anywhere
nothing really honest think know remember maybe just only very already still today yesterday
поискал искал нашёл нашел памяти память записи запись файл файла папке нигде ничего сегодня вчера""".split())


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+|\n+", text) if s.strip()]


def keywords(sentence):
    # The first word is capitalised by grammar, not because it is a name: lower it unless ALL-CAPS or has a digit.
    m = re.match(r"^[«\"'(\[_*]*([A-Za-zА-Яа-яЁё][\wЁё\-\.]*)", sentence)
    if m:
        w0 = m.group(1)
        if not (w0.isupper() or re.search(r"\d", w0)):
            sentence = sentence[:m.start(1)] + w0[:1].lower() + w0[1:] + sentence[m.end(1):]
    out, seen = [], set()
    for w in (x.strip(".-_") for x in WORD.findall(sentence)):
        if w.lower() in STOP or ABSENCE.search(w) or w.lower() in seen:
            continue
        seen.add(w.lower())
        out.append(w)
    return out


def pattern(words):
    """Only FACT-shaped tokens make a claim checkable: numbers/dates, Names, ids (T97, ZZ-9182).
    No such token -> conversational "no" -> pass with a note (guessing with common words blocks innocent text).
    ALL-CAPS longer than 6 letters is emphasis, not a name."""
    strong, plain = [], []
    for w in words:
        if w.lower() in GENERIC:
            continue
        is_id = ("-" in w or "_" in w) and (re.search(r"\d", w) or w.replace("-", "").replace("_", "").isupper())
        if w.isupper() and len(w) > 6 and not re.search(r"\d", w):
            plain.append(w.lower())
        elif re.search(r"\d", w) or w[:1].isupper() or is_id:
            strong.append(re.escape(w))
        elif len(w) >= 4:
            plain.append(w)
    if not strong:
        return None
    return strong   # only fact-shaped tokens are evidence; a common noun beside them proves nothing


def evidence(tokens, roots):
    """Three strengths of evidence, kept apart (v0.3, after the second review: one file is not one record):
      per_token — how many files hold each token;
      together  — files that hold all tokens, with the lines that hold any of them;
      same_line — lines that hold ALL tokens at once: the strongest lexical link a gate can see.
    Returns (together: {file: [line, ...]}, same_line: [(file, line), ...], per_token: {token: count})."""
    per = {t: search(t, roots)[0] for t in tokens}
    together, same_line = {}, []
    for f in search(tokens[0], roots)[1]:
        try:
            text = open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if all(re.search(t, text, re.I) for t in tokens[1:]):
            together[f] = [ln.strip() for ln in text.splitlines() if any(re.search(t, ln, re.I) for t in tokens)][:5]
            same_line += [(f, ln.strip()) for ln in text.splitlines() if all(re.search(t, ln, re.I) for t in tokens)]
    return together, same_line, per


def search(query, roots):
    """ripgrep, --no-ignore, case-insensitive, files-with-matches. Returns (count, files)."""
    p = subprocess.run(["rg", "--no-ignore", "-i", "-l", "-e", query, *roots],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode not in (0, 1):
        raise RuntimeError("search failed: " + p.stderr.strip()[:200])   # a broken search must not read as zero
    files = [l for l in p.stdout.splitlines() if l.strip()]
    return len(files), files


def decide(tokens, together, same_line, per):
    """Policy over the evidence. Kept apart from gathering, so the rule is readable and replaceable.
    BLOCK needs one LINE holding every fact token that is not itself an absence statement ("could not find X")."""
    positive = [(f, ln) for f, ln in same_line if not ABSENCE.search(ln)]
    if positive:
        return "BLOCK", "one line holds every fact token"
    if same_line:
        return "REVIEW", "the only lines holding all tokens say 'not found' themselves"
    if together:
        return "REVIEW", "one file holds the tokens, but on different lines — co-stored is not linked"
    if any(per.values()):
        return "REVIEW", "tokens exist, but never together in one file"
    return "PASS", "no token anywhere"


def check(text, roots):
    claims = [s for s in sentences(unquote(text)) if ABSENCE.search(s)]
    if not claims:
        return 0, "ABSENCE_GATE_OK: no absence claim"
    report, worst = [], "PASS"
    for s in claims:
        if not DISK_ANCHOR.search(s):
            report.append(f"  not checkable (about the world, not the disk): «{s[:100]}»")
            continue
        toks = pattern(keywords(s))
        if toks is None:
            report.append(f"  not checkable (no date/number/name/id): «{s[:100]}»")
            continue
        together, same_line, per = evidence(toks, roots)
        verdict, why = decide(toks, together, same_line, per)
        per_s = " · ".join(f"{t}: {n}" for t, n in per.items())
        lines = "".join(f"\n    {f}\n      " + "\n      ".join(ls) for f, ls in list(together.items())[:5])
        report.append(f"  {verdict}: «{s[:140]}»\n    why: {why}\n    per token (files): {per_s}{lines}")
        if verdict == "BLOCK" or (verdict == "REVIEW" and worst == "PASS"):
            worst = verdict
    if worst == "BLOCK":
        return 4, "ABSENCE_CLAIM_CONTRADICTED — the disk has what the text says is absent. Open the files, rewrite.\n" + "\n".join(report)
    if worst == "REVIEW":
        return 5, "ABSENCE_CLAIM_REVIEW — evidence is partial; a person (or the agent, by opening the files) decides.\n" + "\n".join(report)
    return 0, f"ABSENCE_GATE_OK: {len(claims)} claim(s), none contradicted\n" + "\n".join(report)


def selftest():
    import secrets
    ok = True
    with tempfile.TemporaryDirectory() as d:
        files = {
            "notes.md": "Meeting with Orlova moved to 14.03.2027, ticket ZX-4417.\n",
            "people.md": "Alice called about the budget.\n",                   # Alice here …
            "projects.md": "Spec for X-918 is in review.\n",                   # … X-918 elsewhere
            "contracts.md": "Signed: Bob, project QB-77, 02.02.2027.\n",       # both, one file
            "log.md": "I could not find ticket TK-5150 anywhere.\n",           # the token, in an absence line
            "files.md": "Orlova-2027 draft lives in /drafts.\n",
            "mixed.md": "Carol called about the budget.\nPR-301 belongs to the unrelated migration project.\n",   # one file, two records
            "ids.md": "Ticket ZQ-7788 assigned to Petrov.\n",
        }
        for name, body in files.items():
            with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                f.write(body)
        cases = [
            # v0.2, from an outside review — each of these answered wrongly in v0.1
            ("scattered tokens -> review, not block", "I couldn't find the document for Alice about project X-918 in my files.", 5),
            ("same file -> block", "I couldn't find any record of Bob and QB-77 in my files.", 4),
            ("only an absence line -> review", "Ticket TK-5150 was never saved in my files.", 5),
            ("quoted name is a claim", 'The file "Orlova-2027" does not exist in my folder.', 4),
            # v0.3, second review: one file is not one record
            ("same file, different lines -> review", "I couldn't find the document for Carol about project PR-301 in my files.", 5),
            # quotes, as a class (so the v0.1 hole can't come back): name / id / person stay; speech goes
            ("quoted id", 'There is no record of "ZQ-7788" in my notes.', 4),
            ("quoted person + id", 'I couldn\'t find "Petrov" with ZQ-7788 in my files.', 4),
            ("quoted sentence is speech", 'He wrote "there is no record of ZQ-7788 in my files" yesterday.', 0),
            ("nested quotation is speech", 'She said «he wrote "no record of ZQ-7788 in my files" again».', 0),
            ("planted red", "I searched my notes for the Orlova meeting on 14.03.2027 and there is no record anywhere.", 4),
            ("synonym still red", "Ticket ZX-4417 was never saved in my files.", 4),
            ("negative control", f"There is no record of {'q' + secrets.token_hex(6)} in my files.", 0),  # generated: can't find itself
            ("no claim", "The tests are green and the build is done.", 0),
            ("quoted negation", "Her line in the song is «not found anywhere, Orlova 14.03.2027».", 0),
            ("about the world", "The Orlova meeting does not exist yet, she hasn't scheduled it.", 0),
            ("first word is grammar", "There is nothing I could add, I searched and it is not saved.", 0),
        ]
        for name, text, want in cases:
            got, msg = check(text, [d])
            print(f"[{name}] exit {got} | expect {want}")
            ok &= (got == want)
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv):
    if len(argv) >= 2 and argv[1] == "--selftest":
        return selftest()
    roots = [argv[i + 1] for i, a in enumerate(argv) if a == "--root" and i + 1 < len(argv)]
    if len(argv) < 2 or not roots:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        code, msg = check(f.read(), roots)
    print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
