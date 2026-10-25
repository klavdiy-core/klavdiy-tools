"""examples/motion.png: for each planted motion bug, what a frame-by-frame look says vs what the rules say."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import motion_check as mc  # noqa: E402

f = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 21)
fb = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 26)
rows = [("none",) + ("-",) * 0] + [(b,) for b in mc.BUGS]
im = Image.new("RGB", (1000, 150 + 54 * 6), (18, 20, 26))
d = ImageDraw.Draw(im)
d.text((30, 22), "Every frame looks fine. The motion is broken.", font=fb, fill=(235, 235, 240))
d.text((30, 80), f"{'planted bug':<18}{'screenshot says':<20}rule over time (first frame)", font=f, fill=(140, 146, 160))
for i, bug in enumerate(("none",) + mc.BUGS):
    t = mc.play(mc.SCRIPT, bugs=set() if bug == "none" else {bug})
    looks_bad = len(mc.frame_looks_fine(t))
    found = mc.check(t)
    y = 125 + i * 54
    d.text((30, y), f"{bug:<18}", font=f, fill=(235, 235, 240))
    d.text((30 + 18 * 11.6, y), "looks fine" if not looks_bad else f"{looks_bad} odd frames", font=f,
           fill=(230, 200, 90) if bug != "none" else (110, 210, 130))
    txt = "; ".join(f"{v['rule']} @frame {v['frame']}" for v in found) or "no rule broken"
    d.text((30 + 38 * 11.6, y), txt, font=f, fill=(230, 90, 90) if found else (110, 210, 130))
im.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "motion.png"))
print("ok")
