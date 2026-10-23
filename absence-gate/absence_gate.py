#!/usr/bin/env python3
"""absence_gate.py — refuse to send "I don't have it" when the disk has it.

An agent writes rules into its memory ("search before claiming something doesn't exist") and breaks them anyway:
Anthropic's own Opus 4.8 system card calls this "ignored correction". A rule in memory doesn't fire. A check at the
point of action does. This gate sits in the send path: it reads the outgoing text, finds claims of ABSENCE
("I couldn't find", "there is no record", "not saved anywhere"), runs the search itself over the roots you give it,
and exits 4 if the disk contradicts the claim. The agent then has to open the files and rewrite — not argue.

Usage:
  python absence_gate.py <textfile> --root DIR [--root DIR ...]   exit 0 pass · 4 contradicted · 2 usage
  python absence_gate.py --selftest                                planted red + negative control, in a temp dir

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

QUOTED = re.compile(r"«[^«»\n]{0,300}»|“[^“”\n]{0,300}”|\"[^\"\n]{1,300}\"")   # someone's words, not my claim
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
    return "|".join(strong + ([re.escape(max(plain, key=len))] if plain else []))


def search(query, roots):
    """ripgrep, --no-ignore, case-insensitive, files-with-matches. Returns (count, files)."""
    p = subprocess.run(["rg", "--no-ignore", "-i", "-l", "-e", query, *roots],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode not in (0, 1):
        raise RuntimeError("search failed: " + p.stderr.strip()[:200])   # a broken search must not read as zero
    files = [l for l in p.stdout.splitlines() if l.strip()]
    return len(files), files


def check(text, roots):
    claims = [s for s in sentences(QUOTED.sub(" ", text)) if ABSENCE.search(s)]
    if not claims:
        return 0, "ABSENCE_GATE_OK: no absence claim"
    report, blocked = [], False
    for s in claims:
        if not DISK_ANCHOR.search(s):
            report.append(f"  not checkable (about the world, not the disk): «{s[:100]}»")
            continue
        q = pattern(keywords(s))
        if q is None:
            report.append(f"  not checkable (no date/number/name/id): «{s[:100]}»")
            continue
        n, files = search(q, roots)
        if n:
            blocked = True
            # a merged pattern is not a measurement: say WHICH token hit
            per = " · ".join(f"{t}: {search(t, roots)[0]}" for t in q.split("|")[:6]) if "|" in q else ""
            report.append(f"  CONTRADICTED: «{s[:140]}»\n    query: {q}\n    files: {n}" +
                          (f"\n    per token: {per}" if per else "") + "\n    " + "\n    ".join(files[:10]))
        else:
            report.append(f"  holds (0 hits): «{s[:100]}»  query: {q}")
    if blocked:
        return 4, "ABSENCE_CLAIM_CONTRADICTED — the disk has what the text says is absent. Open the files, rewrite.\n" + "\n".join(report)
    return 0, f"ABSENCE_GATE_OK: {len(claims)} claim(s), none contradicted\n" + "\n".join(report)


def selftest():
    import secrets
    ok = True
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "notes.md"), "w", encoding="utf-8") as f:
            f.write("Meeting with Orlova moved to 14.03.2027, ticket ZX-4417.\n")
        cases = [
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
