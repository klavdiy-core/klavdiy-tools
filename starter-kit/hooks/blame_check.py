#!/usr/bin/env python3
"""blame_check.py — a Stop hook: before you blame the network, SSH or the environment, check your own last change.

Agents spend a lot of effort on their own trivial mistakes and then say "looks like a network issue". This check
fires at the moment the reply is finished:

  the reply blames something outside the code (network, SSH, permissions, environment, server, flaky, "your machine")
  and the session edited a code file
  and after that edit nothing looked at the change itself (no `git diff` / `git show`, no re-read of an edited file)
  -> exit 2: the reply is held back; the model is told to look at its own change first.

Saying it plainly ("I haven't ruled out my own change") passes. Failures are loud (GATE_BROKEN); stop_hook_active
lets go once. Same transcript reading as claim_check.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claim_check import EDIT_TOOLS, FAILED_OUTPUT, SHELL_TOOLS, events, in_project, is_code, project_root  # noqa: E402

# A blame is either an explicit exoneration of the code, or, in one sentence, something outside the code + a cause
# + a failure. Measured on a blind corpus written by another model (the first, phrase-list version caught 4 of 25).
EXONERATE = re.compile(
    r"\bnot\s+(in|from|because\s+of|due\s+to|caused\s+by)\s+(our|my|the)\s+(code|change|edit|diff)\b"
    r"|\b(our|my|the)\s+(code|change|edit)\s+(is|was|looks)\s+(fine|correct|ok|okay|not\s+the\s+(problem|cause))\b"
    r"|\bnothing\s+(i|we)\s+(changed|did|touched)\b|\bnot\s+my\s+(change|fault|code|edit)\b"
    r"|\b(can'?t|cannot)\s+(fix|do\s+anything\s+about)\s+(that|it|this)\s+from\s+(our|my|this)\s+side\b"
    r"|\bon\s+(their|your)\s+(end|side|machine|box|system)\b|\b(works|passes)\s+(for\s+me\s+)?locally\b"
    r"|\b(before|without)\s+my\s+code\s+(even\s+)?(runs|running)\b|\bthat'?s\s+not\s+in\s+(our|my|the)\s+code\b"
    # "ни при чём" only about MY code / change: "шейдер ни при чём, медленная страница" blamed my own other code
    r"|(мо[йяеи]|наш\w*)\s+(код|правк|изменени|дифф?)\w*(\s+\w+){0,2}\s+ни\s+при\s+ч[её]м"
    r"|ни\s+при\s+ч[её]м\s+(мо[йяеи]|наш\w*)\s+(код|правк|изменени)\w*"
    r"|не\s+в\s+(моём\s+|нашем\s+)?коде|не\s+из-за\s+(моего|моей|моих|кода|правк)"
    r"|у\s+меня\s+локально\s+(вс[её]\s+)?(проходит|работает)|на\s+(их|вашей)\s+стороне"
    r"|\b(pass(es)?|works?)\s+on\s+my\s+machine\b|у\s+меня\s+(вс[её]\s+)?(работает|проходит)",
    re.I)
OUTSIDE_WORD = (r"network|connection|ssh|dns|proxy|firewall|vpn|server|staging|remote|permissions?|environment|env|"
                r"setup|config(uration)?|machine|cache|caching|cdn|upstream|third[\s-]party|ci|runner|infra(structure)?|"
                r"platform|timing|race")
ATTRIBUTION = re.compile(
    rf"\b({OUTSIDE_WORD})([\s-]+side)?[\s-]+(issue|problem|error|glitch|hiccup|bug|failure|outage|thing)\b"
    r"|проблем\w*\s+(в|с|на)\s+(сет\w*|окружени\w*|ssh|прокси|сервер\w*|сторон\w*|кэш\w*|ci)"
    r"|дело\s+в\s+(сет\w*|окружени\w*|ssh|сервер\w*|кэш\w*|прокси)",
    re.I)
STRONG_CAUSE = re.compile(r"\b(culprit|at\s+fault|to\s+blame|blame)\b|виноват\w*", re.I)
OUTSIDE = re.compile(
    r"\b(network|connection|ssh|host\s+key|dns|proxy|firewall|vpn|server|staging|production|remote|cluster|"
    r"permissions?|environment(\s+variable)?|env\s+var|shell|python\s+install|node\s+version|clock|machine|setup|"
    r"cache|cdn|registry|mirror|upstream|third[\s-]party|api|library|dependency|package|linter\s+version|"
    r"ci|runner|pipeline|disk|quota|rate\s+limit|certificate|cert|timeout|instance|their\s+(side|end|service))\b"
    r"|сет[ьи]|прокси|прав\w*\s+на|стейджинг\w*|сервер\w*|окружени\w*|ci\b",
    re.I)
CAUSE = re.compile(
    r"\b(because|due\s+to|caused\s+by|comes?\s+from|coming\s+from|is\s+why|which\s+is\s+why|so\s+(the|nothing|it)|"
    r"culprit|at\s+fault|is\s+the\s+(problem|cause|issue)|the\s+(problem|cause|issue)\s+is|it'?s\s+the|blame|"
    r"which\s+(breaks|causes|makes))\b"
    r"|из-за|поэтому|виноват\w*|причина",
    re.I)
FAILURE = re.compile(
    r"\b(fail\w*|error\w*|red|broke\w*|blocked|blocking|blocks|time[sd]?\s+out|timing\s+out|refuses|refused|down|"
    r"drop(s|ped)?|dropping|can'?t\s+connect|doesn'?t\s+resolve|not\s+resolve|crash\w*|5\d\d|4\d\d|corrupt\w*|"
    r"blew\s+up|reject\w*|denied|never\s+arrives|doesn'?t\s+(work|arrive)|break\w*|wrong|stale|old\s+bundle)\b"
    r"|пада\w*|ошибк\w*|не\s+доход\w*|режет|отказ\w*|не\s+работает",
    re.I)
SENTENCE = re.compile(r"(?<=[.!?;])\s+|\n+")


class _Blame:
    """BLAME.search(text): truthy when the reply blames something outside the code."""

    @staticmethod
    def search(text):
        for s in SENTENCE.split(text or ""):
            if (EXONERATE.search(s) or ATTRIBUTION.search(s) or (OUTSIDE.search(s) and STRONG_CAUSE.search(s))
                    or (OUTSIDE.search(s) and CAUSE.search(s) and FAILURE.search(s))):
                return s
        return None


BLAME = _Blame()
HONEST = re.compile(
    r"\b(haven'?t|have\s+not|didn'?t|did\s+not|not\s+yet)\s+(ruled\s+out|checked|reviewed|looked\s+at)\s+(my|the)\s+"
    r"(own\s+)?(last\s+)?(change|edit|code|diff)\b|\b(may|might|could)\s+(still\s+)?be\s+my\s+(own\s+)?(change|edit|code)\b"
    r"|не\s+(исключил|проверил|смотрел)\w*\s+(сво\w+\s+)?(правк\w*|изменени\w*|код\w*)",
    re.I)
SELF_CHECK_CMD = re.compile(r"\bgit\s+(diff|show|log\s+-p)\b|(^|\s)diff\s", re.I)


def verdict(evts, blamed, root=None):
    """None if fine. Main trigger: the last run after the last code edit failed and nothing looked at the change.
    Fallback: the reply blames something outside the code (wording is a weak signal, see README) with no look."""
    edited, last_edit = [], -1
    for i, (k, d) in enumerate(evts):
        if k == "use" and d["name"] in EDIT_TOOLS:
            f = d["input"].get("file_path") or d["input"].get("notebook_path")
            if is_code(f) and in_project(f, root):
                edited.append(f.replace("\\", "/"))
                last_edit = i
    if last_edit < 0:
        return None
    results = {d["id"]: d for k, d in evts if k == "result"}
    runs = []
    for k, d in evts[last_edit + 1:]:
        if k != "use":
            continue
        if d["name"] in SHELL_TOOLS and SELF_CHECK_CMD.search(str(d["input"].get("command", ""))):
            return None
        if d["name"] == "Read" and str(d["input"].get("file_path", "")).replace("\\", "/") in edited:
            return None
        if d["name"] in SHELL_TOOLS:
            runs.append(d)
    failed = False
    if runs:
        r = results.get(runs[-1]["id"])
        failed = r is not None and (r["error"] or bool(FAILED_OUTPUT.search(r["text"])))
    if not (failed or blamed):
        return None
    files = ", ".join(sorted(set(edited))[-3:])
    what = ("the last run after your edit failed" if failed else "the reply blames something outside the code")
    return (f"Before you explain it: {what}, and nothing after your last edit looked at the change itself ({files}). "
            f"Run `git diff` (or re-read the file), check whether your edit causes this, and say what you found. "
            f"If you haven't, say so plainly.")


def run(argv, stdin_text):
    """Returns (exit_code, stderr_text)."""
    try:
        event = json.loads(stdin_text or "{}")
        if event.get("stop_hook_active"):
            return 0, ""
        msg = event.get("last_assistant_message")
        if msg is None:
            return 2, "GATE_BROKEN: blame_check: Stop hook input has no last_assistant_message"
        if HONEST.search(msg):
            return 0, ""
        blamed = bool(BLAME.search(msg))
        path = event.get("transcript_path")
        if not path or not os.path.exists(path):
            # without a transcript the failure trigger cannot be checked; a blame still must not pass silently
            return (2, "GATE_BROKEN: blame_check: no transcript to check the reply against") if blamed else (0, "")
        why = verdict(events(path), blamed, project_root(event))
        return (2, "BLAME_UNCHECKED: " + why) if why else (0, "")
    except Exception as e:                                       # noqa: BLE001 — every failure must be loud
        return 2, f"GATE_BROKEN: blame_check: {type(e).__name__}: {e}"


def main():
    try:
        code, err = run(sys.argv[1:], sys.stdin.buffer.read().decode("utf-8"))
    except Exception as e:                                       # noqa: BLE001
        code, err = 2, f"GATE_BROKEN: blame_check: {type(e).__name__}: {e}"
    if err:
        sys.stderr.buffer.write((err + "\n").encode("utf-8"))
        sys.stderr.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
