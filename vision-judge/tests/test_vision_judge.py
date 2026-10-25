"""No network: the judge, the parsing, the corpus and the scoring, with a fake vision model."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import corpus  # noqa: E402
import vision_judge as vj  # noqa: E402

SPEC = {"title": "Checkout", "fields": ["Email", "Card number"], "button": "Pay now",
        "items": ["Lids", "Sugar", "Oat milk"]}
GOOD = {"title": "Checkout", "labels": ["Email", "Card number"], "button": "Pay now", "button_fully_visible": True,
        "list_items": ["• Lids", "Sugar", "Oat milk"], "problems_seen": []}


class Judge(unittest.TestCase):
    def test_a_faithful_description_passes(self):
        self.assertEqual(vj.judge(SPEC, GOOD), ("PASS", []))

    def test_every_planted_break_has_a_reason(self):
        cases = {"title": "Chekcout", "button": None, "list_items": ["Lids", "Sugar"],
                 "button_fully_visible": False, "problems_seen": ["two list items overlap"]}
        for key, val in cases.items():
            with self.subTest(key=key):
                v, why = vj.judge(SPEC, {**GOOD, key: val})
                self.assertEqual(v, "FAIL")
                self.assertTrue(why)

    def test_a_cut_label_is_not_the_label(self):
        v, why = vj.judge(SPEC, {**GOOD, "button": "Pay no"})
        self.assertEqual(v, "FAIL")
        self.assertIn("Pay no", why[0])


class Parsing(unittest.TestCase):
    def test_verdict_from_free_text(self):
        self.assertEqual(vj.verdict_of("PASS\nlooks fine"), "PASS")
        self.assertEqual(vj.verdict_of("Verdict: fail - the button is cut"), "FAIL")
        self.assertEqual(vj.verdict_of("looks ok to me"), "UNCLEAR")

    def test_json_inside_prose_and_fences(self):
        self.assertEqual(vj.parse_inventory("Here:\n```json\n" + json.dumps(GOOD) + "\n```")["title"], "Checkout")
        with self.assertRaises(ValueError):
            vj.parse_inventory("I see a checkout screen.")


class Corpus(unittest.TestCase):
    def test_a_third_intact_and_every_break_used_reproducibly(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            a, b = corpus.build(d1, 24), corpus.build(d2, 24)
            self.assertEqual(a, b)
            self.assertEqual(list(a.values()).count("intact"), 8)
            self.assertEqual(set(a.values()) - {"intact"}, set(corpus.BREAKS))
            self.assertTrue(os.path.exists(os.path.join(d1, "00.png")))


class Isolation(unittest.TestCase):
    def test_the_vision_call_inherits_no_settings_hooks_memory_or_config_dir(self):
        # measured 25.10: without this the model under test loaded the author's own CLAUDE.md, hooks and memory and
        # answered "all six files read" instead of describing the screen - and every earlier result was contaminated
        import subprocess
        from unittest import mock
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"], seen["env"] = argv, kw.get("env")
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({"result": "PASS"}), stderr="")
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": r"C:\warm", "ANTHROPIC_API_KEY": "x"}), \
                mock.patch.object(vj.subprocess, "run", fake_run):
            vj.ask("p", "screen.png", "m")
        i = seen["argv"].index("--setting-sources")
        self.assertEqual(seen["argv"][i + 1], "")
        self.assertIn("--strict-mcp-config", seen["argv"])
        self.assertNotIn("CLAUDE_CONFIG_DIR", seen["env"])
        self.assertNotIn("ANTHROPIC_API_KEY", seen["env"])


class Subtle(unittest.TestCase):
    def test_subtle_breaks_differ_from_the_intact_screen_but_less(self):
        # the first run (obvious breaks, neutral prompt): eyes with the spec caught 16/16, so the complaint did not
        # reproduce; real PASS-on-broken needs smaller breaks. Each subtle break must still change pixels.
        import random
        from PIL import ImageChops
        spec = corpus.make_spec(random.Random(1))
        base = corpus.draw(spec, None)
        for brk in corpus.BREAKS:
            loud = ImageChops.difference(base, corpus.draw(spec, brk, random.Random(2))).getbbox()
            soft = ImageChops.difference(base, corpus.draw(spec, brk, random.Random(2), subtle=True)).getbbox()
            self.assertIsNotNone(soft, brk)                          # still broken
            if loud and brk in ("overlap", "offscreen", "cut_text"):
                area = lambda b: (b[2] - b[0]) * (b[3] - b[1])
                self.assertLessEqual(area(soft), area(loud), brk)    # and smaller

    def test_the_agent_framing_arm_exists(self):
        self.assertIn("you built", vj.EYES_AGENT.lower())
        self.assertIn("tests pass", vj.EYES_AGENT.lower())


class RunAndScore(unittest.TestCase):
    def test_a_fake_model_runs_every_arm_once_and_is_scored(self):
        calls = []

        def fake(prompt, image, model):
            calls.append(prompt[:20])
            name = os.path.basename(image)[:-4]
            spec = json.load(open(image[:-4] + ".json", encoding="utf-8"))
            if prompt.startswith("Describe"):                       # a perfect describer
                brk = json.load(open(os.path.join(os.path.dirname(image), "answers.json")))[name]
                inv = {"title": spec["title"], "labels": spec["fields"], "button": spec["button"],
                       "button_fully_visible": True, "list_items": spec["items"], "problems_seen": []}
                if brk != "intact":
                    inv["problems_seen"] = [brk]
                return json.dumps(inv)
            return "PASS - looks finished"                           # the lazy eyes of the complaint
        with tempfile.TemporaryDirectory() as d:
            corpus.build(d, 12)
            vj.run(d, "fake", asker=fake)
            n = len(calls)
            vj.run(d, "fake", asker=fake)                            # cached: nothing is paid twice
            self.assertEqual(len(calls), n)
            sc = vj.score(d)
            self.assertEqual(sc["eyes (fake)"]["caught"], 0)
            self.assertEqual(sc["compile (fake)"]["caught"], sc["compile (fake)"]["broken"])
            self.assertEqual(sc["compile (fake)"]["false_alarm"], 0)


if __name__ == "__main__":
    unittest.main()
