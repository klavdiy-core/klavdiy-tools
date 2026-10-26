"""vision-judge: why "Visual QA: PASS" passes broken screens, measured, and a check that does not.

Three ways to check a screenshot against its spec, run on the same screens:
  eyes        one call: "here is the screen and the spec - PASS or FAIL?" (what coding agents do today)
  eyes-blind  the same without the spec (the control)
  compile     the vision model only DESCRIBES what it sees, letter by letter, without the spec (the vision compiler);
              plain code then compares that description with the spec (the judge). The model never decides PASS.

python vision_judge.py run CORPUS_DIR [--model claude-sonnet-5-5]   # runs every arm on every screen, cached
python vision_judge.py score CORPUS_DIR [--png chart.png]            # caught / false alarms per arm and per break
python vision_judge.py check SCREEN.png SPEC.json                    # the compile arm on one screen
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

__version__ = "0.1.1"

EYES = ("You are the visual QA step of a coding agent. This screenshot shows the app screen it just built.{spec} "
        "Does the screen look correct and finished? Answer PASS or FAIL on the first line, then one short reason.")
# the framing of the complaint: the agent that built the screen, tests green, wanting to finish
EYES_AGENT = ("You built this app screen from the spec below, and the tests pass. This is the final visual QA "
              "step before you report the task as done. The spec: {spec} Answer PASS or FAIL on the first line, "
              "then one short reason.")
COMPILE = ("Describe exactly what is visible in this screenshot. You have not seen any spec; do not guess what it "
           "should say. Copy every text exactly as it appears, letter by letter, and do not correct spelling. "
           "Answer with JSON only, no prose: {\"title\": text, \"labels\": [the label texts above input boxes], "
           "\"button\": the main button's text or null, \"button_fully_visible\": true/false, \"list_items\": [list "
           "item texts], \"problems_seen\": [anything overlapping, cut off, unreadable or outside the screen]}")


ENV_ALLOW = {"PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "TMPDIR", "HOME",
             "USERPROFILE", "APPDATA", "LOCALAPPDATA", "LANG", "LC_ALL"}


def ask(prompt, image, model, timeout=240):
    """One vision call through Claude Code: it reads the image with its Read tool. Returns the answer text.
    Isolated like a stranger's fresh install: no settings, hooks, MCP servers or config dir of whoever runs this
    (measured: without it the model loaded its runner's own memory and answered about that instead of the screen)."""
    exe = shutil.which("claude") or "claude"
    full = prompt + f"\n\nThe screenshot is the image file {os.path.abspath(image)}. Read it, then answer."
    env = {k: v for k, v in os.environ.items() if k.upper() in ENV_ALLOW}
    p = subprocess.run([exe, "-p", full, "--model", model, "--output-format", "json", "--allowedTools", "Read",
                        "--max-turns", "4", "--setting-sources", "", "--strict-mcp-config"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                       cwd=os.path.dirname(os.path.abspath(image)), env=env)
    try:
        return str(json.loads(p.stdout).get("result") or "")
    except ValueError:
        raise RuntimeError(f"claude returned no JSON (exit {p.returncode}): {p.stderr.strip()[:200]}")


def verdict_of(text):
    """PASS / FAIL from a free-text answer: the first of the two words that appears."""
    m = re.search(r"\b(PASS|FAIL)\b", text.upper())
    return m.group(1) if m else "UNCLEAR"


def parse_inventory(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in the description")
    return json.loads(m.group(0))


def _norm(s):
    return re.sub(r"[\s•·*\-]+", " ", str(s or "")).strip().lower()


SCHEMA = {"title": str, "labels": list, "button": (str, type(None)), "button_fully_visible": bool,
          "list_items": list, "problems_seen": list}


def schema_problems(inv):
    """What is missing or of the wrong type in a description. Only a description that is complete can be judged:
    a missing button_fully_visible, or "false" as a string, used to read as PASS (external review, 25.10)."""
    if not isinstance(inv, dict):
        return [f"the description is {type(inv).__name__}, not an object"]
    out = []
    for key, want in SCHEMA.items():
        if key not in inv:
            out.append(f"{key} is missing")
        elif not isinstance(inv[key], want) or (want is bool and not isinstance(inv[key], bool)):
            out.append(f"{key} is {type(inv[key]).__name__} ({inv[key]!r}), not {getattr(want, '__name__', 'str or null')}")
        elif want is list and not all(isinstance(x, str) for x in inv[key]):
            out.append(f"{key} holds something other than text")
    return out


def judge(spec, inv):
    """The judge is code: every difference between the description and the spec is a reason to fail. A
    description that is incomplete or mistyped is not judged at all: REVIEW, never PASS."""
    bad = schema_problems(inv)
    if bad:
        return "REVIEW", bad
    why = []
    if _norm(inv.get("title")) != _norm(spec["title"]):
        why.append(f"title reads {inv.get('title')!r}, spec says {spec['title']!r}")
    if [_norm(x) for x in inv.get("labels") or []] != [_norm(x) for x in spec["fields"]]:
        why.append(f"field labels {inv.get('labels')} differ from {spec['fields']}")
    if not inv.get("button"):
        why.append("no main button visible")
    elif _norm(inv.get("button")) != _norm(spec["button"]):
        why.append(f"button reads {inv.get('button')!r}, spec says {spec['button']!r}")
    if inv.get("button") and inv.get("button_fully_visible") is False:
        why.append("the button is not fully visible")
    items = [_norm(x) for x in inv.get("list_items") or []]
    if sorted(items) != sorted(_norm(x) for x in spec["items"]):
        why.append(f"list shows {len(items)} item(s) {inv.get('list_items')}, spec has {spec['items']}")
    for p in inv.get("problems_seen") or []:
        why.append(f"seen: {p}")
    return ("FAIL" if why else "PASS"), why


def check_one(image, spec, model, asker=ask):
    """The compile arm: describe without the spec, then the code judge."""
    text = asker(COMPILE, image, model)
    try:
        inv = parse_inventory(text)
    except ValueError as e:
        return "REVIEW", [f"the description was not readable JSON ({e}): not judged"], text   # cannot judge = REVIEW (a second review)
    v, why = judge(spec, inv)
    return v, why, inv


def run(corpus, model, asker=ask, arms=("eyes", "eyes-blind", "eyes-agent", "compile"), jobs=1):
    """Every arm on every screen; results.jsonl caches, so a rerun only pays for what is missing."""
    path = os.path.join(corpus, "results.jsonl")
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                done.add((r["screen"], r["arm"], r["model"]))
    names = sorted(n[:-4] for n in os.listdir(corpus) if n.endswith(".png") and not n.startswith("_"))
    todo = [(n, a) for n in names for a in arms if (n, a, model) not in done]
    lock = threading.Lock()
    with open(path, "a", encoding="utf-8") as out:
        def one(job):
            name, arm = job
            img = os.path.join(corpus, name + ".png")
            with open(os.path.join(corpus, name + ".json"), encoding="utf-8") as f:
                spec = json.load(f)
            try:
                if arm == "compile":
                    v, why, raw = check_one(img, spec, model, asker)
                elif arm == "eyes-agent":
                    raw = asker(EYES_AGENT.format(spec=json.dumps(spec)), img, model)
                    v, why = verdict_of(raw), []
                else:
                    raw = asker(EYES.format(spec=(" The spec it was built from: " + json.dumps(spec))
                                            if arm == "eyes" else ""), img, model)
                    v, why = verdict_of(raw), []
            except Exception as e:  # noqa: BLE001 - a failed call is recorded, not a crashed run
                v, why, raw = "ERROR", [str(e)[:200]], ""
            with lock:                                     # one line per result, whole, whichever thread finishes
                out.write(json.dumps({"screen": name, "arm": arm, "model": model, "verdict": v, "why": why,
                                      "raw": raw if isinstance(raw, str) else json.dumps(raw)},
                                     ensure_ascii=False) + "\n")
                out.flush()
                print(f"{name} {arm:<10} {v}", flush=True)
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            list(pool.map(one, todo))


def score(corpus):
    with open(os.path.join(corpus, "answers.json"), encoding="utf-8") as f:
        truth = json.load(f)
    rows = [json.loads(l) for l in open(os.path.join(corpus, "results.jsonl"), encoding="utf-8")]
    out = {}
    for r in rows:
        a = out.setdefault((r["arm"], r["model"]), {"caught": 0, "broken": 0, "false_alarm": 0, "intact": 0, "review": 0,
                                                   "missed": [], "by_break": {}})
        broken = truth[r["screen"]] != "intact"
        fail = r["verdict"] == "FAIL"
        a["review"] += r["verdict"] == "REVIEW"           # said apart: a model full of REVIEWs is not just a weak catcher
        if broken:
            a["broken"] += 1
            a["caught"] += fail
            b = a["by_break"].setdefault(truth[r["screen"]], [0, 0])
            b[0] += fail
            b[1] += 1
            if not fail:
                a["missed"].append(f"{r['screen']}:{truth[r['screen']]}")
        else:
            a["intact"] += 1
            a["false_alarm"] += fail
    return {f"{k[0]} ({k[1]})": v for k, v in out.items()}


def chart(sc, path):
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 22)
    fb = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 26)
    im = Image.new("RGB", (980, 120 + 110 * len(sc)), (18, 20, 26))
    d = ImageDraw.Draw(im)
    d.text((30, 24), "Broken screens caught (green) and intact screens failed (red)", font=fb, fill=(235, 235, 240))
    for i, (name, a) in enumerate(sc.items()):
        y = 90 + i * 110
        d.text((30, y), name, font=f, fill=(235, 235, 240))
        cr = a["caught"] / max(a["broken"], 1)
        fa = a["false_alarm"] / max(a["intact"], 1)
        d.rectangle([330, y, 330 + 520 * cr, y + 34], fill=(110, 210, 130))
        d.text((340 + 520 * cr, y + 2), f"{a['caught']}/{a['broken']} caught", font=f, fill=(235, 235, 240))
        d.rectangle([330, y + 44, 330 + 520 * fa, y + 70], fill=(230, 90, 90))
        d.text((340 + 520 * fa, y + 42), f"{a['false_alarm']}/{a['intact']} false alarms", font=f, fill=(200, 200, 210))
    im.save(path)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="vision-judge", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("corpus")
    r.add_argument("--model", default="claude-sonnet-5-5")
    r.add_argument("--arms", default="eyes,eyes-blind,eyes-agent,compile")
    r.add_argument("--jobs", type=int, default=4, help="vision calls at once (default 4)")
    s = sub.add_parser("score")
    s.add_argument("corpus")
    s.add_argument("--png")
    c = sub.add_parser("check")
    c.add_argument("screen")
    c.add_argument("spec")
    c.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run(a.corpus, a.model, arms=tuple(a.arms.split(",")), jobs=a.jobs)
    elif a.cmd == "score":
        sc = score(a.corpus)
        for name, v in sc.items():
            print(f"{name:<34} caught {v['caught']}/{v['broken']}  false alarms {v['false_alarm']}/{v['intact']}"
                  f"  review {v['review']}  missed {', '.join(v['missed']) or '-'}")
        if a.png:
            chart(sc, a.png)
    else:
        with open(a.spec, encoding="utf-8") as f:
            v, why, _ = check_one(a.screen, json.load(f), a.model)
        print(v)
        for w in why:
            print(" -", w)
        return {"PASS": 0, "FAIL": 1}.get(v, 2)        # REVIEW / anything unknown: 2, never a pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
