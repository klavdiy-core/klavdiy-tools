"""examples/chart.png from two runs on the SAME screens (the corpus is deterministic): one where the model under test
inherited its runner's crowded session (settings, hooks, memory files), and one isolated.
python make_chart.py CROWDED_DIR CLEAN_DIR"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import vision_judge as vj  # noqa: E402

crowded, clean = vj.score(sys.argv[1]), vj.score(sys.argv[2])
rows = [("haiku, agent's QA step, crowded session", crowded["eyes-agent (claude-haiku-5-5)"]),
        ("haiku, same prompt, fresh isolated call", clean["eyes-agent (claude-haiku-5-5)"]),
        ("sonnet, same prompt, fresh isolated call", clean["eyes-agent (claude-sonnet-5-5)"]),
        ("haiku describes, code judges (isolated)", clean["compile (claude-haiku-5-5)"])]
f = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 21)
fb = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 26)
im = Image.new("RGB", (1100, 150 + 92 * len(rows)), (18, 20, 26))
d = ImageDraw.Draw(im)
d.text((30, 20), "Same 24 screens, same model, same question. Only the context changed.", font=fb, fill=(235, 235, 240))
d.text((30, 60), "Broken screens caught (green) / intact screens failed (red). 16 broken, 8 intact, subtle breaks.",
       font=f, fill=(150, 156, 170))
for i, (name, a) in enumerate(rows):
    y = 110 + i * 92
    d.text((30, y + 4), name, font=f, fill=(235, 235, 240))
    cr = a["caught"] / max(a["broken"], 1)
    d.rectangle([470, y, 470 + 460 * cr, y + 32], fill=(110, 210, 130) if cr == 1 else (230, 190, 80))
    d.text((480 + 460 * cr, y + 2), f"{a['caught']}/{a['broken']}", font=f, fill=(235, 235, 240))
    fa = a["false_alarm"] / max(a["intact"], 1)
    d.rectangle([470, y + 40, 470 + 460 * fa + 2, y + 62], fill=(230, 90, 90))
    d.text((480 + 460 * fa, y + 38), f"{a['false_alarm']}/{a['intact']} false alarms", font=f, fill=(190, 190, 200))
im.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chart.png"))
print("ok")
