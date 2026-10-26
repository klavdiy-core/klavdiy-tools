"""An external review (25.10): a description with a missing button_fully_visible, or "false" as a string, gave PASS -
only the bool False was noticed. Red on 0.1.0."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import vision_judge as vj  # noqa: E402

SPEC = {"title": "Checkout", "fields": ["Name"], "button": "Buy", "items": ["A"]}


def inv(**over):
    d = {"title": "Checkout", "labels": ["Name"], "button": "Buy", "button_fully_visible": True,
         "list_items": ["A"], "problems_seen": []}
    d.update(over)
    return {k: v for k, v in d.items() if v is not ...}


class Schema(unittest.TestCase):
    def test_a_complete_matching_description_passes(self):
        self.assertEqual(vj.judge(SPEC, inv())[0], "PASS")

    def test_a_missing_visibility_flag_is_not_a_pass(self):
        v, why = vj.judge(SPEC, inv(button_fully_visible=...))
        self.assertEqual(v, "REVIEW")
        self.assertTrue(any("button_fully_visible" in w for w in why), why)

    def test_false_as_a_string_is_not_a_pass(self):
        v, why = vj.judge(SPEC, inv(button_fully_visible="false"))
        self.assertEqual(v, "REVIEW")

    def test_wrong_types_and_missing_keys_are_review(self):
        for bad in (inv(labels="Name"), inv(list_items=...), inv(problems_seen=None), inv(title=7),
                    inv(problems_seen="none")):
            with self.subTest(bad=bad):
                self.assertEqual(vj.judge(SPEC, bad)[0], "REVIEW")

    def test_a_real_difference_still_fails(self):
        self.assertEqual(vj.judge(SPEC, inv(button="Pay"))[0], "FAIL")
        self.assertEqual(vj.judge(SPEC, inv(button_fully_visible=False))[0], "FAIL")


class ReviewEverywhere(unittest.TestCase):
    """Notes from a second review of 989ad09."""

    def test_an_unreadable_description_is_review_not_fail(self):
        v, why, _ = vj.check_one("x.png", SPEC, "m", asker=lambda *a: "I could not see the screen")
        self.assertEqual(v, "REVIEW")

    def test_score_counts_reviews_apart(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "answers.json"), "w", encoding="utf-8") as f:
                json.dump({"s1": "intact", "s2": "cut_button"}, f)
            with open(os.path.join(d, "results.jsonl"), "w", encoding="utf-8") as f:
                for s, v in (("s1", "REVIEW"), ("s2", "REVIEW")):
                    f.write(json.dumps({"screen": s, "arm": "compile", "model": "m", "verdict": v}) + "\n")
            sc = vj.score(d)["compile (m)"]
            self.assertEqual(sc["review"], 2)
            self.assertEqual(sc["false_alarm"], 0)


if __name__ == "__main__":
    unittest.main()
