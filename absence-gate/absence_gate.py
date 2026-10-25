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

Requires ripgrep (`rg`) on PATH, built with PCRE2. Searches with -uu (no ignore files, hidden folders too), whole words,
case-insensitive on purpose: .gitignore and dot-folders silently hide files from a default search, and a silent zero
reads exactly like a real one.

Wire it into whatever sends. In Claude Code use claude_code_hook.py (Claude Code blocks only on exit 2 — v0.6);
elsewhere — a chat bot's send function, a commit-msg hook — call this directly.
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
    # v0.6.2: a word boundary in front (no «casino file»), and «missing» only as a state («is missing», «missing from»),
    # not as an adjective in a status line («fixed the missing import»)
    r"\b(couldn'?t find|could not find|can'?t find|didn'?t find|did not find|haven'?t found|have not found|not found|"
    r"found nothing|no (record|entry|file|note|mention|trace)s?\b|(is|are|was|were|went|go|goes) missing|"
    r"missing (from|in)\b|"
    r"nothing (recorded|found|saved|anywhere)|there is nothing|there'?s nothing|never (saved|recorded|written)|"
    r"not (saved|recorded|written down|stored)|isn'?t (saved|recorded|stored|written)|doesn'?t exist|does not exist|"
    r"i don'?t have|no such|"
    # v0.6.1 (breakers): «unable to locate», «absent from», «came up empty»…
    r"unable to (locate|find)|(could not|couldn'?t|can'?t|cannot) locate|found no\b|found none|no sign of|"
    r"nothing (about|on)\b|is absent|absent from|(is not|isn'?t) in\b|never wrote down|nothing was found|"
    r"came up empty|zero results|no hits|lack any|"
    r"нигде не (запис|найд|встреч|сохран)|не сохран(ил|ён|ен|ены|ено)|не найден|не нашёл|не нашел|не нашл(а|и)|"
    r"ничего нет|нет нигде|нет записи|нет такого|не записан|не существует|отсутству\w*|у меня (этого )?нет|"
    r"не (могу|смог|смогла|удалось) найти|не вижу|нет информации|пусто)",
    re.I)

# --- a claim is checkable by the disk only if it is ABOUT the disk (names a carrier). "The meeting doesn't exist
# yet" is a claim about the world; no search can confirm it, and blocking it with unrelated hits is worse than silence.
DISK_ANCHOR = re.compile(
    r"file|folder|director|archive|record|note|log\b|memory|index|saved|stored|search|found|find|locate|anywhere|"
    r"database|vault|docs?\b|table|disk|repo|"
    r"[\\/][\w.\-]+|\.(md|txt|json|py|ps1|jsonl|csv|pdf|png|jpg)\b|"
    r"файл|папк|архив|запис|заметк|журнал|памят|индекс|сохран|нашёл|нашел|искал|поиск|диск", re.I)

# Quoted SPEECH (several words) is someone's words, not my claim — blanked. A quoted single token is a NAME
# (a file, an id: «The file "Orlova-2027" doesn't exist») and stays part of the claim (v0.1 let it escape).
QUOTED = re.compile(r"«([^«»\n]{0,300})»|“([^“”\n]{0,300})”|\"([^\"\n]{1,300})\"")


def unquote(text):
    def repl(m):
        inner = next(g for g in m.groups() if g is not None)
        name = inner.strip()
        # v0.6.2: a quoted FILE name keeps its spaces («"Quarterly plan Z9.docx"») — it is a name, not speech
        is_file = "," not in name and (re.search(r"\.[A-Za-z][A-Za-z0-9]{0,4}$", name) or re.search(r"[\\/]", name))
        return inner if not re.search(r"\s", name) or is_file else " "
    return QUOTED.sub(repl, text)
# v0.6: two-character ids («Q3», «7B») were dropped by the 3+ rule.
WORD = re.compile(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_\-\.]{2,}|(?<![\w-])(?:[A-Za-z]\d|\d[A-Za-z])(?![\w-])")
STOP = set("""the a an of to in on at for and or is are was were be been it its this that these those my your his her
our their me you him us them i we there here where when what which who how not no yes do does did have has had any
about with from into over under onto upon exist exists existed""".split()) | set("""
и в во не на с со к ко по у о об от для из за то что это как так же бы ли или а но да нет я ты он она мы вы они
мой моя моё мое мои моих моём моем моей моим своих свой своя свои своём своем про""".split())
GENERIC = set("""searched search found find memory record recorded file files folder note notes saved stored anywhere
nothing really honest think know remember maybe just only very already still today yesterday
couldn cannot never don doesn didn haven hasn wasn isn aren weren won wouldn shouldn mine
поискал искал нашёл нашел памяти память записи запись файл файла папке нигде ничего сегодня вчера""".split())


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+|\n+", text) if s.strip()]


def keywords(sentence):
    # The first word is capitalised by grammar, not because it is a name: lower it unless ALL-CAPS or has a digit.
    m = re.match(r"^[«\"'(\[_*]*([A-Za-zА-Яа-яЁё][\wЁё\-\.]*)", sentence)
    if m:
        w0 = m.group(1)
        possessive = re.match(r"['’]s\b", sentence[m.end(1):])      # v0.6: «Petrov's contract…» — a name, not grammar
        if not (w0.isupper() or re.search(r"\d", w0) or possessive):
            sentence = sentence[:m.start(1)] + w0[:1].lower() + w0[1:] + sentence[m.end(1):]
    # v0.6.1: the words OF the absence phrase («unable to locate», «came up empty», «нет информации») are not what the
    # claim says is missing — blank the phrase before picking tokens, or «locate» becomes a content word no line holds.
    sentence = ABSENCE.sub(" ", sentence)
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
            strong.append(w)
        elif len(w) >= 4:
            plain.append(w)
    if not strong:
        return None
    return strong   # only fact-shaped tokens find the evidence; content words judge it (see content_words)


CYR = re.compile(r"^[А-Яа-яЁё]+$")
DASHES = "‐‑‒–—―−"            # ‐ ‑ ‒ – — ― −  (v0.6.1: LLM and word-processor output)
HYPHEN = "[-" + DASHES + "]"


def normalize(text):
    """v0.6.1: «couldn’t» (curly apostrophe) slipped every phrasing; «ZX‑4417» (U+2011) split the id in two."""
    text = text.replace("’", "'").replace("‘", "'")
    return re.sub("[" + DASHES + "]", "-", text)


def tok_re(t, strict=True):
    """v0.6 (outside review #3): a token is a WORD, not a substring — «Ivo» is not in «pivot», «ZT-55» not in «ZT-550».
    Same boundaries on both sides (rg -P and Python), so the two can't disagree. Russian names decline: «Орлову» must find
    «Орлова» — a crude stem (drop the ending, allow up to 3 letters back). A false hit costs one look; a false PASS, a lie.
    v0.6.1 (breakers): two tiers. STRICT also refuses a dot glued to a letter or digit — «2.0» is not inside «1.2.0», «ZT-56»
    not inside «ZT-56.draft», a year not inside a date; only strict hits can BLOCK. NEAR (the v0.6 boundary) still counts, as
    REVIEW: a near match is worth a look, never a verdict. Any dash on disk matches a hyphen in the token."""
    if CYR.match(t) and len(t) >= 5:
        core = re.escape(t[:-2] if len(t) >= 6 else t[:-1]) + r"\w{0,3}"
    else:
        core = re.escape(t).replace(r"\-", HYPHEN)
    if strict:
        return r"(?<![\w.-])" + core + r"(?![\w-]|\.\w)"
    return r"(?<![\w-])" + core + r"(?![\w-])"


def read_text(path):
    """v0.6.1: a UTF-16 file (PowerShell's '>' writes one) was read as UTF-8 garbage — rg found it, the line proof was lost."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8-sig", errors="replace")


def has_digit_or_id(t):
    return bool(re.search(r"\d", t)) or (("-" in t or "_" in t) and t.replace("-", "").replace("_", "").isupper())


def content_words(words):
    """The claim's common content words ("document", "contract", "ticket"): what the claim says is ABSENT, roughly.
    v0.4: a line naming Alice and X-918 but not "document" shows they were mentioned together, not that a document exists."""
    out = []
    for w in words:
        lw = w.lower()
        if lw in GENERIC or len(w) < 4 or re.search(r"\d", w) or w[:1].isupper() or "-" in w or "_" in w:
            continue
        if DISK_ANCHOR.search(lw):      # v0.6.1: «файлах», «notes», «vault» name the carrier, not the thing missing
            continue
        out.append(lw)
    return out


NEGATION = re.compile(r"(?i)(?<![\w-])(not|no|never|none|without|isn'?t|aren'?t|wasn'?t|weren'?t|не|нет|ни|без)(?![\w-])")
# v0.5, the sixth hole (tense and modality): «will be created tomorrow», «may exist», «was deleted yesterday» name the thing
# but don't say it exists NOW. Kept deliberately narrow — a short list, not a grammar.
MODALITY = re.compile(r"(?i)(?<![\w-])(will|shall|going to|may|might|could|would|should|maybe|perhaps|possibly|planned|"
                      r"tomorrow|later|soon|deleted|removed|erased|lost|was|were|будет|будут|может|возможно|наверное|"
                      r"завтра|потом|позже|удал\w*|стёр\w*|стер\w*|был|была|было|были)(?![\w-])")


def evidence(tokens, roots):
    """Three strengths of evidence, kept apart (v0.3, after the second review: one file is not one record):
      per_token — how many files hold each token;
      together  — files that hold all tokens, with the lines that hold any of them;
      same_line — lines that hold ALL tokens at once: the strongest lexical link a gate can see.
    Returns (together: {file: [line, ...]}, same_line: [(file, line), ...], per_token: {token: count})."""
    res = [tok_re(t) for t in tokens]
    per = {t: search(tok_re(t, strict=False), roots)[0] for t in tokens}     # near hits count — as a reason to look
    together, same_line = {}, []
    for f in search(res[0], roots)[1]:
        try:
            text = read_text(f)
        except OSError:
            continue
        if all(re.search(r, text, re.I) for r in res[1:]):
            lines = text.splitlines()
            together[f] = [(i + 1, ln.strip()) for i, ln in enumerate(lines) if any(re.search(r, ln, re.I) for r in res)][:5]
            same_line += [(f, i + 1, ln.strip()) for i, ln in enumerate(lines) if all(re.search(r, ln, re.I) for r in res)]
    # v0.6 (outside review #1): the NAME of a file is evidence too. «I don't have budget-2027.xlsx» with that file in the
    # root used to PASS — a binary file has no line to match, and nothing else on disk spells its name.
    # v0.6.1 (breakers): a FOLDER named «ZX-5555» holding unrelated files is not the file — only the file's own name
    # can BLOCK; a path that holds the tokens only in its folders is a reason to look.
    listed = list_files(roots)
    file_paths = [p for p in listed if all(re.search(r, os.path.basename(p), re.I) for r in res)]
    dir_paths = [p for p in listed if p not in file_paths and all(re.search(r, p, re.I) for r in res)]
    return together, same_line, per, (file_paths, dir_paths)


RG = ["rg", "-uu", "-P"]   # v0.6 (outside review #2): --no-ignore alone still skips dot-dirs (.claude/, .obsidian/) — -uu


def search(query, roots):
    """ripgrep: no ignore files, hidden files too, PCRE2 (for word boundaries), case-insensitive. Returns (count, files)."""
    p = subprocess.run([*RG, "-i", "-l", "-e", query, *roots],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode not in (0, 1):
        raise RuntimeError("search failed: " + p.stderr.strip()[:200])   # a broken search must not read as zero
    files = [l for l in p.stdout.splitlines() if l.strip()]
    return len(files), files


def list_files(roots):
    """Every file path under the roots, relative to its root (so a token can't match the root's own folder name)."""
    out = []
    for root in roots:
        p = subprocess.run(["rg", "--files", "-uu", root], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode not in (0, 1):
            raise RuntimeError("file listing failed: " + p.stderr.strip()[:200])
        out += [os.path.relpath(l, root) for l in p.stdout.splitlines() if l.strip()]
    return out


def decide(tokens, together, same_line, per, content=(), paths=(), names_file=False):
    """Policy over the evidence. Kept apart from gathering, so the rule is readable and replaceable.
    BLOCK (v0.4) needs ONE LINE that holds every fact token AND every content word of the claim, with no negation in it.
    Anything weaker is REVIEW: a dumb gate errs toward «go look», never toward «forbidden».
    v0.6: a file whose path holds every token, when the claim is about a file, is BLOCK too; a clean line next to a
    negated or ended one is a CONFLICT -> REVIEW; and a capitalised word alone («Python», «March») never convicts — BLOCK
    needs at least one token with a digit or an id shape."""
    def clean(ln):
        return (not ABSENCE.search(ln) and not NEGATION.search(ln) and not MODALITY.search(ln)
                and all(re.search(r"(?i)(?<![\w-])" + re.escape(c), ln) for c in content))
    convicting = any(has_digit_or_id(t) for t in tokens)
    plain = [x for x in same_line if clean(x[2])]
    dirty = [x for x in same_line if ABSENCE.search(x[2]) or NEGATION.search(x[2]) or MODALITY.search(x[2])]
    file_paths, dir_paths = paths if isinstance(paths, tuple) else (list(paths), [])
    if file_paths and names_file and convicting:
        return "BLOCK", f"a file whose name holds every fact token exists: {file_paths[0]}"
    paths = file_paths + dir_paths
    if plain and dirty:
        return "REVIEW", "evidence conflicts: a plain line says it exists, another line negates it or says it ended"
    if plain and convicting:
        return "BLOCK", "one line holds every fact token and every content word, plain present, no negation"
    if plain:
        return "REVIEW", "a plain line matches, but only on capitalised words — a name alone doesn't convict"
    if paths:
        return "REVIEW", f"a path holds every fact token: {paths[0]}"
    if [x for x in same_line if ABSENCE.search(x[2]) or NEGATION.search(x[2])]:
        return "REVIEW", "the lines holding all tokens carry a negation — mention is not existence"
    if [x for x in same_line if MODALITY.search(x[2])]:
        return "REVIEW", "the lines holding all tokens speak of future, possibility or a past that ended — not 'exists now'"
    if same_line:
        return "REVIEW", f"the tokens are mentioned together, but not the thing claimed absent ({', '.join(content)})"
    if together:
        return "REVIEW", "one file holds the tokens, but on different lines — co-stored is not linked"
    if any(per.values()):
        return "REVIEW", "tokens exist, but never together in one file"
    return "PASS", "no token anywhere"


NAMES_FILE = re.compile(r"(?i)file|файл|\.[a-z][a-z0-9]{1,4}\b")   # «.xlsx» names a file; «14.03.2027» does not


def check(text, roots):
    sents = sentences(unquote(normalize(text)))
    claims = [(i, s) for i, s in enumerate(sents) if ABSENCE.search(s)]
    if not claims:
        # blind run 1: ALLOW on a positive claim meant «not looked at», and read like «checked and fine». Two states now.
        return 0, "ABSENCE_GATE_NOT_APPLICABLE: no absence claim — this text was not evaluated (ALLOW is not 'true')"
    report, worst, checked = [], "PASS", 0
    for i, s in claims:
        # v0.6: «Searched my notes for Orlova. Nothing found.» — the facts sit one or two sentences back.
        ctx = " ".join(sents[max(0, i - 2):i + 1])
        if not DISK_ANCHOR.search(ctx):
            report.append(f"  not checkable (about the world, not the disk): «{s[:100]}»")
            continue
        kw = keywords(s)
        toks = pattern(kw)
        if toks is None and i > 0:
            kw = [w for p in sents[max(0, i - 2):i] for w in keywords(p)] + kw
            toks = pattern(kw)
        if toks is None:
            report.append(f"  not checkable (no date/number/name/id): «{s[:100]}»")
            continue
        checked += 1
        together, same_line, per, paths = evidence(toks, roots)
        verdict, why = decide(toks, together, same_line, per, content_words(kw), paths, bool(NAMES_FILE.search(ctx)))
        per_s = " · ".join(f"{t}: {n}" for t, n in per.items())
        # the deciding lines first (all tokens on one line), with line numbers; then paths; then what shares a file
        decisive = "".join(f"\n    {f}:{n}: {ln}" for f, n, ln in same_line[:5])
        path_s = "".join(f"\n    path: {p}" for p in (paths[0] + paths[1])[:5])
        rest = "".join(f"\n    {f}" + "".join(f"\n      {n}: {ln}" for n, ln in ls)
                       for f, ls in list(together.items())[:5] if f not in {x[0] for x in same_line[:5]})
        report.append(f"  {verdict}: «{s[:140]}»\n    why: {why}\n    per token (files): {per_s}{decisive}{path_s}{rest}")
        if verdict == "BLOCK" or (verdict == "REVIEW" and worst == "PASS"):
            worst = verdict
    if worst == "BLOCK":
        return 4, "ABSENCE_CLAIM_CONTRADICTED — the disk has what the text says is absent. Open the files, rewrite.\n" + "\n".join(report)
    if worst == "REVIEW":
        return 5, "ABSENCE_CLAIM_REVIEW — evidence is partial; a person (or the agent, by opening the files) decides.\n" + "\n".join(report)
    if checked == 0:
        return 0, (f"ABSENCE_GATE_NOT_APPLICABLE: {len(claims)} absence claim(s), none checkable against the disk "
                   "(about the world, or no fact-shaped token)\n" + "\n".join(report))
    return 0, f"ABSENCE_GATE_OK: {checked} claim(s) checked against the disk, none contradicted\n" + "\n".join(report)


# v0.6, outside review #3 (Fable 5.1, 23.10.2026). Module-level, so an older version of check() can be run against the
# same fixture to prove each new case is RED on it (tests/red_on_previous.py).
FIXTURE_V06 = {
    "budget-2027.xlsx": b"PK\x03\x04\x00binary",                                   # a binary file: its name is the only evidence
    ".memory/secret.md": "Ticket HD-3030 assigned to Kim.\n",                         # a dot-dir — where agent memory lives
    "cola.md": "Cola sales went up.\n",                                               # «Ola» is a substring here, not a word
    "ru.md": "Договор с Сидоровой RT-7 лежит в /contracts.\n",                        # Russian declension
    "q.md": "Report Q3 lives in /reports.\n",                                         # a two-character id
    "kai.md": "Document for Kai about project ZT-90 is in /contracts.\n"
              "Document for Kai about project ZT-90 was deleted.\n",                  # conflicting evidence
}
CASES_V06 = [
    ("#1 file name is evidence", "I don't have the file budget-2027.xlsx in my folder.", 4),
    ("#2 dot-dirs are searched", "There is no record of HD-3030 in my files.", 4),
    ("#3 a word, not a substring", "There is no note about Ola in my files.", 0),
    ("#3 near id is not the id", "I couldn't find ticket ZT-5 in my files.", 0),
    ("#3 Russian declension", "Не нашёл договор с Сидоровым RT-7 в памяти.", 4),
    ("facts one sentence back", "I searched my notes for ticket ZX-4417. Nothing found.", 4),
    ("possessive name at the start", "Petrov's ticket is not saved anywhere.", 5),
    ("a name alone doesn't convict", "I couldn't find the ticket for Petrov in my files.", 5),
    ("conflicting evidence -> review", "I couldn't find the document for Kai about project ZT-90 in my files.", 5),
    ("two-character id", "There is no record of the Q3 report in my files.", 4),
    ("new phrasing: didn't find", "I didn't find ZX-4417 in my notes.", 4),
]


# v0.6.1 — three look-only breaker agents on v0.6 (23.10.2026), each finding reproduced by hand before it became a case.
FIXTURE_V061 = {
    "ZX-5555/about.md": "Unrelated grocery list.\n",                                  # a FOLDER named like the id
    "rel.md": "Version 1.2.0 released, release notes attached.\n",                     # «2.0» lives inside «1.2.0»
    "cfg.md": "Config for ZT-56.draft is pending review.\n",                           # the id with a dot-suffix
    "nh.md": "Ticket NH‑8888 assigned to Kim.\n",                                 # a non-ASCII hyphen on disk
    "u16.md": "Ticket QW-9003 assigned to Kim.\n".encode("utf-16"),                    # UTF-16 with a BOM
}
CASES_V061 = [
    ("a folder named like the id is a look, not proof", "I couldn't find the ticket ZX-5555 in my files.", 5),
    ("2.0 is not 1.2.0 — a near match is a look", "I couldn't find the release notes for version 2.0 in my files.", 5),
    ("ZT-56.draft is a near match, not the id", "I couldn't find the config for ZT-56 in my files.", 5),
    ("curly apostrophe", "I couldn’t find ZX-4417 in my files.", 4),
    ("non-ASCII hyphen in the claim", "I couldn't find ZX‑4417 in my files.", 4),
    ("non-ASCII hyphen on disk", "There is no record of NH-8888 in my files.", 4),
    ("phrasing: unable to locate", "Unable to locate ticket ZX-4417 in my files.", 4),
    ("phrasing: absent from", "ZX-4417 is absent from my notes.", 4),
    ("phrasing: came up empty", "Searched my files for ZX-4417. Came up empty.", 4),
    ("phrasing: не могу найти", "Не могу найти ZX-4417 в файлах.", 4),
    ("phrasing: нет информации", "Нет информации про ZX-4417 в моих файлах.", 4),
    ("anywhere is a search", "I couldn't find ZX-4417 anywhere.", 4),
    ("UTF-16 file with a BOM", "I did not find ticket QW-9003 in my notes.", 4),
]


# v0.6.2 — an outside look-only review (25.10.2026), each finding reproduced before it became a case.
FIXTURE_V062 = {
    "Quarterly plan Z9.docx": b"PK\x03\x04\x00binary",                               # a file name with spaces
    "build/app.cpython-311.pyc": b"\x00binary",                                       # a build artefact
}
CASES_V062 = [
    ("a quoted file name with spaces is a claim", 'I couldn\'t find "Quarterly plan Z9.docx" in my files.', 4),
    ("'missing' in a status line is not an absence claim", "Fixed the missing import in file app.cpython-311.pyc.", 0),
    ("'no file' inside a word is not 'no file'", "The casino file ZX-4417 opened fine.", 0),
    ("'is missing' still is", "Ticket ZX-4417 is missing from my notes.", 4),
]


def write_fixture(d, files):
    for name, body in files.items():
        path = os.path.join(d, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb" if isinstance(body, bytes) else "w", **({} if isinstance(body, bytes) else {"encoding": "utf-8"})) as f:
            f.write(body)


def selftest():
    import secrets
    ok = True
    with tempfile.TemporaryDirectory() as d:
        write_fixture(d, FIXTURE_V06)
        write_fixture(d, FIXTURE_V061)
        write_fixture(d, FIXTURE_V062)
        files = {
            "notes.md": "Meeting with Orlova moved to 14.03.2027, ticket ZX-4417.\n",
            "people.md": "Alice called about the budget.\n",                   # Alice here …
            "projects.md": "Spec for X-918 is in review.\n",                   # … X-918 elsewhere
            "contracts.md": "Signed: Bob, project QB-77, 02.02.2027.\n",       # both, one file
            "log.md": "I could not find ticket TK-5150 anywhere.\n",           # the token, in an absence line
            "files.md": "Orlova-2027 draft lives in /drafts.\n",
            "mixed.md": "Carol called about the budget.\nPR-301 belongs to the unrelated migration project.\n",   # one file, two records
            "ids.md": "Ticket ZQ-7788 assigned to Petrov.\n",
            "minutes.md": "Dana and project ZT-55 were discussed at the meeting.\n"      # co-mentioned, no document
                          "Evan is not associated with project ZT-66.\n"                 # a negated link
                          "Document for Fay about project ZT-77 is in /contracts.\n"     # the thing itself
                          "The document for Gil about project ZT-81 will be created tomorrow.\n"   # future
                          "The document for Hana about project ZT-82 may exist.\n"                 # possibility
                          "The document for Ivo about project ZT-83 was deleted yesterday.\n"      # existed, then gone
                          "The document for Jun about project ZT-84 was created yesterday and remains in /contracts.\n",  # exists — but past tense
        }
        write_fixture(d, files)
        cases = CASES_V06 + CASES_V061 + CASES_V062 + [
            # v0.2, from an outside review — each of these answered wrongly in v0.1
            ("scattered tokens -> review, not block", "I couldn't find the document for Alice about project X-918 in my files.", 5),
            ("same file -> block", "I couldn't find any record of Bob and QB-77 in my files.", 4),
            ("only an absence line -> review", "Ticket TK-5150 was never saved in my files.", 5),
            ("quoted name is a claim", 'The file "Orlova-2027" does not exist in my folder.', 4),
            # v0.3, second review: one file is not one record
            ("same file, different lines -> review", "I couldn't find the document for Carol about project PR-301 in my files.", 5),
            # v0.4, the fifth hole (second reviewer): mention is not existence
            ("co-mention, no document -> review", "I couldn't find the document for Dana about project ZT-55 in my files.", 5),
            ("negated link -> review", "I couldn't find the contract for Evan about project ZT-66 in my files.", 5),
            ("the thing itself -> block", "I couldn't find the document for Fay about project ZT-77 in my files.", 4),
            # v0.5, the sixth hole: tense and modality
            ("future -> review", "I couldn't find the document for Gil about project ZT-81 in my files.", 5),
            ("possibility -> review", "I couldn't find the document for Hana about project ZT-82 in my files.", 5),
            ("deleted -> review", "I couldn't find the document for Ivo about project ZT-83 in my files.", 5),
            # a KNOWN, ACCEPTED false REVIEW (pinned so it is visible, not hidden): the file exists, but the line is past
            # tense, and the narrow marker list can't tell «was created and remains» from «was deleted». A REVIEW costs one
            # look; a false BLOCK costs a false accusation. If this ever turns into 4, the policy changed — on purpose or not.
            ("past tense that still exists -> review (accepted cost)", "I couldn't find the document for Jun about project ZT-84 in my files.", 5),
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
        # blind run 1 (closed): «checked and allowed» and «not applicable» must be told apart, both exit 0
        for name, text, label in [
            ("positive claim is NOT evaluated", "The document for Fay about project ZT-77 exists.", "ABSENCE_GATE_NOT_APPLICABLE"),
            ("world claim is NOT evaluated", "The Orlova meeting does not exist yet, she hasn't scheduled it.", "ABSENCE_GATE_NOT_APPLICABLE"),
            ("checked and held", f"There is no record of {'q' + secrets.token_hex(6).upper()}-7 in my files.", "ABSENCE_GATE_OK"),
        ]:
            got, msg = check(text, [d])
            print(f"[{name}] {msg.split(':')[0]} | expect {label}")
            ok &= (got == 0 and msg.startswith(label + ":"))
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
