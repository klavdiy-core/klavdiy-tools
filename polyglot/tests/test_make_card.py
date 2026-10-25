"""make_card: one lesson picture from a lesson JSON, kind poem or skill (music, code, maths). Red before 'kind'."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(os.path.dirname(HERE), "example")
sys.path.insert(0, EX)
import make_card as mc  # noqa: E402


def load(name):
    with open(os.path.join(EX, name), encoding="utf-8") as f:
        return json.load(f)


class Card(unittest.TestCase):
    def test_a_skill_lesson_has_the_five_blocks_in_order_and_tomorrows_review(self):
        img, log = mc.render(load("guitar_card.json"))
        heads = [t for t in log if t[:2] in ("1 ", "2 ", "3 ", "4 ", "5 ")]
        self.assertEqual([h[:1] for h in heads], ["1", "2", "3", "4", "5"])
        self.assertIn("ONE SMALL THING", heads[0])
        self.assertIn("BREAKS", heads[2])
        self.assertIn("1, 2, 4, 8, 16", heads[3])
        self.assertTrue(any(t.startswith("tomorrow starts with review") for t in log))
        self.assertGreater(img.size[1], 400)

    def test_the_poem_lesson_still_renders_from_its_json(self):
        img, log = mc.render(load("pushkin_card.json"))
        self.assertTrue(any("WORD BY WORD" in t for t in log))
        self.assertTrue(any("WHAT A TRANSLATION LOSES" in t for t in log))

    def test_long_text_wraps_inside_the_card(self):
        lesson = load("guitar_card.json")
        lesson["breaks"][0][1] = "a very long reason " * 30
        img, log = mc.render(lesson)
        self.assertTrue(all(w <= mc.W - mc.PAD for w in mc.LAST_WIDTHS), max(mc.LAST_WIDTHS))

    def test_an_unknown_kind_is_an_error(self):
        with self.assertRaises(ValueError):
            mc.render({"kind": "dance"})

    def test_the_cards_of_a_skill_lesson_feed_cards_py(self):
        lesson = load("guitar_card.json")
        for c in lesson["cards"]:
            self.assertTrue({"word", "lemma", "meaning", "line"} <= set(c))

    def test_the_command_line_writes_the_png(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "card.png")
            r = subprocess.run([sys.executable, os.path.join(EX, "make_card.py"), os.path.join(EX, "guitar_card.json"),
                                "-o", out], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.getsize(out) > 1000)


if __name__ == "__main__":
    unittest.main()
