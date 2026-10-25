"""motion check: bugs that every screenshot hides and the frames-over-time telemetry shows.
@Alex_Vainshtein: the worst bugs are when the screenshots are fine and the game falls apart in motion."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import motion_check as mc  # noqa: E402


class Motion(unittest.TestCase):
    def test_a_clean_game_breaks_no_rule(self):
        t = mc.play(mc.SCRIPT)
        self.assertEqual(mc.check(t), [])

    def test_every_planted_motion_bug_is_named_by_its_rule(self):
        expect = {"camera_in_wall": "camera", "speed_unclamped": "speed", "teleport": "teleport",
                  "fall_through": "floor", "stuck": "stuck"}
        for bug, rule in expect.items():
            with self.subTest(bug=bug):
                found = mc.check(mc.play(mc.SCRIPT, bugs={bug}))
                self.assertTrue(any(v["rule"] == rule for v in found), (bug, found[:3]))

    def test_every_single_frame_still_looks_fine(self):
        # the point: a per-frame look (is the player on screen, inside the level?) passes every buggy run
        for bug in mc.BUGS:
            with self.subTest(bug=bug):
                t = mc.play(mc.SCRIPT, bugs={bug})
                self.assertEqual(mc.frame_looks_fine(t), [], bug)

    def test_the_first_violation_says_when_and_how_much(self):
        v = mc.check(mc.play(mc.SCRIPT, bugs={"teleport"}))[0]
        self.assertIn("frame", v)
        self.assertGreater(v["frame"], 0)
        self.assertIn("jump", v["detail"])


if __name__ == "__main__":
    unittest.main()
