"""Render one polyglot lesson as a picture, from a lesson JSON.

    pip install pillow
    python example/make_card.py                       # both examples: pushkin_lesson.png, guitar_lesson.png
    python example/make_card.py my_lesson.json -o out.png

kind "poem": the original + word by word, sound, what a translation loses, words to keep, homework.
kind "skill" (music, code, maths): 1 one small thing, 2 how it feels / sounds / looks (what the hands do),
3 what usually breaks for a beginner and why, 4 what to keep (cards.py: tomorrow, then 2, 4, 8, 16 days),
5 homework, 15 minutes; then "tomorrow starts with review". A skill lesson's "cards" have the fields cards.py reads.
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, PAD = 1200, 44
BG, FG, DIM, ACC, GLS, RED = (20, 21, 27), (232, 230, 224), (140, 138, 130), (232, 176, 74), (150, 200, 230), (235, 120, 110)
LAST_WIDTHS = []                       # the width of every line drawn by the last render (the tests read it)


def font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            pass
    return ImageFont.load_default()


SERIF = font(["georgia.ttf", "DejaVuSerif.ttf"], 34)
SERIF_S = font(["georgia.ttf", "DejaVuSerif.ttf"], 22)
SANS = font(["segoeui.ttf", "DejaVuSans.ttf"], 21)
SANS_B = font(["segoeuib.ttf", "DejaVuSans-Bold.ttf"], 22)
MONO = font(["consola.ttf", "DejaVuSansMono.ttf"], 17)
HEAD = font(["segoeuib.ttf", "DejaVuSans-Bold.ttf"], 15)


class Pen:
    """Draws top to bottom, wraps every text to the card's width, and logs what it wrote."""

    def __init__(self, d):
        self.d, self.y, self.log = d, PAD, []

    def text(self, s, f, fill, x=PAD, dy=32, right=W - PAD):
        words, line, lines = s.split(" "), "", []
        for w in words:
            if line and self.d.textlength(line + " " + w, font=f) > right - x:
                lines.append(line)
                line = w
            else:
                line = w if not line else line + " " + w           # keeps runs of spaces (chord notation)
        lines.append(line)
        for ln in lines:
            self.d.text((x, self.y), ln, font=f, fill=fill)
            LAST_WIDTHS.append(x + self.d.textlength(ln, font=f))
            self.log.append(ln)
            self.y += dy
        return len(lines)

    def head(self, s):
        self.y += 18
        self.text(s, HEAD, DIM, dy=30)


def _top(p, lesson):
    p.d.text((PAD, p.y), lesson.get("tag", "polyglot · one lesson"), font=HEAD, fill=ACC)
    p.d.text((W - PAD, p.y), lesson.get("source", ""), font=HEAD, fill=DIM, anchor="ra")
    p.log += [lesson.get("tag", ""), lesson.get("source", "")]
    p.y += 30


def _poem(p, L):
    p.head("1  ORIGINAL + 2  WORD BY WORD")
    for line, tr in zip(L["lines"], L["translit"]):
        x = PAD
        for word, gloss in line:
            ww = max(p.d.textlength(word + " ", font=SERIF), p.d.textlength(gloss + "  ", font=MONO))
            p.d.text((x, p.y), word, font=SERIF, fill=FG)
            p.d.text((x, p.y + 44), gloss, font=MONO, fill=RED if "[" in gloss else GLS)
            x += ww + 6
        LAST_WIDTHS.append(x)
        p.log.append(" ".join(w for w, _ in line))
        p.y += 68
        p.text(tr, SANS, DIM, dy=48)
    p.head("3  SOUND")
    p.text(L["sound"][0], MONO, ACC, dy=30)
    p.text(L["sound"][1], SANS, FG)
    p.head("4  WHAT A TRANSLATION LOSES HERE")
    for word, why in L["loses"]:
        top = p.y
        p.d.text((PAD, top), word, font=SANS_B, fill=RED)
        p.text(why, SANS, FG, x=PAD + 170, dy=36)
    p.head("5  WORDS TO KEEP  (cards.py: due tomorrow, then 2, 4, 8, 16 days)")
    p.text(L["keep"], SERIF_S, GLS, dy=40)
    p.head("6  HOMEWORK, 15 MINUTES")
    for h in L["homework"]:
        p.text("·  " + h, SANS, FG)


def _skill(p, L):
    p.head("1  ONE SMALL THING")
    p.text(L["thing"], SERIF_S, FG, dy=36)
    if L.get("notation"):
        p.text(L["notation"], MONO, ACC, dy=28)
    p.head("2  HOW IT FEELS · WHAT THE HANDS DO")
    for f in L["feel"]:
        p.text("·  " + f, SANS, FG)
    p.head("3  WHAT USUALLY BREAKS, AND WHY")
    for what, why in L["breaks"]:
        p.d.text((PAD, p.y), what, font=SANS_B, fill=RED)
        p.log.append(what)
        p.text(why, SANS, FG, x=PAD + 230, dy=34)
    p.head("4  TO KEEP  (cards.py: review after 1, 2, 4, 8, 16 days)")
    for c in L["cards"]:
        p.d.text((PAD, p.y), c["word"], font=SANS_B, fill=GLS)
        p.log.append(c["word"])
        p.text(c["meaning"], SANS, FG, x=PAD + 230, dy=34)
    p.head("5  HOMEWORK, 15 MINUTES")
    for h in L["homework"]:
        p.text("·  " + h, SANS, FG)


def render(lesson):
    """(image, log of every line written). kind must be poem or skill."""
    kind = lesson.get("kind", "poem")
    if kind not in ("poem", "skill"):
        raise ValueError(f"kind must be poem or skill, not {kind!r}")
    LAST_WIDTHS.clear()
    img = Image.new("RGB", (W, 2400), BG)
    p = Pen(ImageDraw.Draw(img))
    _top(p, lesson)
    (_poem if kind == "poem" else _skill)(p, lesson)
    p.y += 24
    p.text(f"tomorrow starts with review: \"{lesson['tomorrow']}\"", SANS, DIM)
    return img.crop((0, 0, W, p.y + PAD)), p.log


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("lesson", nargs="?", help="lesson JSON (default: both examples)")
    ap.add_argument("-o", "--output")
    a = ap.parse_args(argv)
    jobs = [(a.lesson, a.output or os.path.splitext(a.lesson)[0] + ".png")] if a.lesson else [
        (os.path.join(HERE, "pushkin_card.json"), os.path.join(HERE, "pushkin_lesson.png")),
        (os.path.join(HERE, "guitar_card.json"), os.path.join(HERE, "guitar_lesson.png"))]
    for src, out in jobs:
        with open(src, encoding="utf-8") as f:
            img, _ = render(json.load(f))
        img.save(out)
        print(out, img.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
