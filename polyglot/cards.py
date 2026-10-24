#!/usr/bin/env python3
"""Homework cards for polyglot: the words of the poems you are reading, reviewed in Leitner boxes.

A new card is due tomorrow. Knew it -> next box (1, 2, 4, 8, 16 days). Missed -> back to box 1, due tomorrow.
Progress is one JSON file in your project, written atomically. Standard library only.

    python cards.py add lesson.json        # the cards block of a lesson
    python cards.py due                    # what to review today
    python cards.py grade <id> ok|miss
    python cards.py poems
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta

INTERVAL = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}


class Deck:
    def __init__(self, path):
        self.path = path
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {"cards": {}}

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def add_lesson(self, lesson, today=None):
        today = today or date.today()
        new = 0
        for c in lesson.get("cards", []):
            if not c.get("word") or not c.get("meaning"):
                raise ValueError("every card needs a word and a meaning")
            cid = f"{lesson.get('lang', '?')}:{c.get('lemma') or c['word']}"
            if cid in self.data["cards"]:
                continue
            self.data["cards"][cid] = {
                "id": cid, "word": c["word"], "lemma": c.get("lemma", ""), "meaning": c["meaning"],
                "line": c.get("line", ""), "poem": lesson.get("poem", ""), "box": 1,
                "due": (today + timedelta(days=1)).isoformat()}
            new += 1
        self._save()
        return new

    def due(self, today=None):
        today = (today or date.today()).isoformat()
        return [c for c in self.data["cards"].values() if c["due"] <= today]

    def grade(self, cid, knew, today=None):
        today = today or date.today()
        c = self.data["cards"][cid]
        c["box"] = min(5, c["box"] + 1) if knew else 1
        c["due"] = (today + timedelta(days=INTERVAL[c["box"]])).isoformat()
        self._save()
        return c

    def poems(self):
        out = {}
        for c in self.data["cards"].values():
            out[c["poem"]] = out.get(c["poem"], 0) + 1
        return out


def main(argv=None):
    # SUPPRESS: a subcommand's default must not overwrite --file/--today given before the subcommand
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--file", default=argparse.SUPPRESS)
    common.add_argument("--today", type=date.fromisoformat, default=argparse.SUPPRESS)
    ap = argparse.ArgumentParser(description="polyglot homework cards", parents=[common])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("add", parents=[common]).add_argument("lesson")
    sub.add_parser("due", parents=[common])
    g = sub.add_parser("grade", parents=[common])
    g.add_argument("id")
    g.add_argument("result", choices=["ok", "miss"])
    sub.add_parser("poems", parents=[common])
    a = ap.parse_args(argv)
    a.file = getattr(a, "file", "polyglot/progress.json")
    a.today = getattr(a, "today", None)
    if os.path.dirname(a.file):
        os.makedirs(os.path.dirname(a.file), exist_ok=True)
    d = Deck(a.file)
    if a.cmd == "add":
        with open(a.lesson, encoding="utf-8") as f:
            n = d.add_lesson(json.load(f), a.today)
        print(f"{n} new card(s); {len(d.data['cards'])} in all")
    elif a.cmd == "due":
        cs = d.due(a.today)
        print(f"{len(cs)} due")
        for c in cs:
            print(f"- [{c['id']}] {c['word']}  ({c['poem']}: \"{c['line']}\")")
    elif a.cmd == "grade":
        c = d.grade(a.id, a.result == "ok", a.today)
        print(f"{c['id']}: box {c['box']}, next {c['due']}")
    elif a.cmd == "poems":
        for p, n in d.poems().items():
            print(f"{n:4}  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
