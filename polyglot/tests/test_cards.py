import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import cards  # noqa: E402

D0 = date(2026, 10, 24)
LESSON = {"poem": "Pushkin, Я вас любил", "lang": "ru", "cards": [
    {"word": "любил", "lemma": "любить", "meaning": "loved (he; past, masculine)", "line": "Я вас любил: любовь ещё, быть может,"},
    {"word": "угасла", "lemma": "угаснуть", "meaning": "has died out (like a flame)", "line": "В душе моей угасла не совсем;"},
]}


class CardsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "progress.json")

    def tearDown(self):
        self.tmp.cleanup()

    def deck(self):
        return cards.Deck(self.path)

    def test_new_cards_are_due_tomorrow_not_today(self):
        d = self.deck()
        self.assertEqual(d.add_lesson(LESSON, today=D0), 2)
        self.assertEqual(d.due(D0), [])
        self.assertEqual([c["word"] for c in d.due(D0 + timedelta(days=1))], ["любил", "угасла"])

    def test_adding_the_same_word_twice_keeps_one_card(self):
        d = self.deck()
        d.add_lesson(LESSON, today=D0)
        self.assertEqual(d.add_lesson(LESSON, today=D0), 0)
        self.assertEqual(len(d.data["cards"]), 2)

    def test_a_known_card_climbs_the_boxes(self):
        d = self.deck()
        d.add_lesson(LESSON, today=D0)
        cid = d.due(D0 + timedelta(days=1))[0]["id"]
        day = D0 + timedelta(days=1)
        gaps = []
        for _ in range(5):
            c = d.grade(cid, True, today=day)
            nxt = date.fromisoformat(c["due"])
            gaps.append((nxt - day).days)
            day = nxt
        self.assertEqual(gaps, [2, 4, 8, 16, 16])     # box 5 is the top: it stays there

    def test_a_miss_goes_back_to_box_one(self):
        d = self.deck()
        d.add_lesson(LESSON, today=D0)
        cid = d.due(D0 + timedelta(days=1))[0]["id"]
        d.grade(cid, True, today=D0 + timedelta(days=1))
        c = d.grade(cid, False, today=D0 + timedelta(days=3))
        self.assertEqual(c["box"], 1)
        self.assertEqual(c["due"], (D0 + timedelta(days=4)).isoformat())

    def test_overdue_cards_are_due(self):
        d = self.deck()
        d.add_lesson(LESSON, today=D0)
        self.assertEqual(len(d.due(D0 + timedelta(days=30))), 2)

    def test_progress_survives_and_is_written_atomically(self):
        d = self.deck()
        d.add_lesson(LESSON, today=D0)
        self.assertEqual(len(cards.Deck(self.path).data["cards"]), 2)
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_a_lesson_without_words_is_an_error(self):
        with self.assertRaises(ValueError):
            self.deck().add_lesson({"poem": "x", "lang": "ru", "cards": [{"word": "", "meaning": "m"}]}, today=D0)

    def test_unknown_card_is_an_error(self):
        with self.assertRaises(KeyError):
            self.deck().grade("nope", True, today=D0)

    def test_poems_are_listed_with_their_counts(self):
        d = self.deck()
        d.add_lesson(LESSON, today=D0)
        self.assertEqual(d.poems(), {"Pushkin, Я вас любил": 2})


class CliTest(unittest.TestCase):
    def test_add_then_due(self):
        with tempfile.TemporaryDirectory() as t:
            lesson = os.path.join(t, "lesson.json")
            with open(lesson, "w", encoding="utf-8") as f:
                json.dump(LESSON, f, ensure_ascii=False)
            prog = os.path.join(t, "p.json")
            run = lambda *a: subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), "cards.py"),
                                             "--file", prog, *a], capture_output=True, text=True, encoding="utf-8",
                                            cwd=t)
            r = run("add", lesson, "--today", "2026-10-24")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("2 new", r.stdout)
            r = run("due", "--today", "2026-10-25")
            self.assertIn("любил", r.stdout)
            self.assertIn("угасла", r.stdout)
            # the progress landed exactly where --file said, nowhere else (a subcommand default once won)
            self.assertTrue(os.path.exists(prog))
            self.assertFalse(os.path.exists(os.path.join(t, "polyglot")))


if __name__ == "__main__":
    unittest.main()
