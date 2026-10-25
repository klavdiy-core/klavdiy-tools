"""A corpus of app screens with a known answer: each screen is drawn from a spec, either faithfully or with one planted
break, so every PASS/FAIL can be scored. python corpus.py OUT_DIR [--n 24]"""
import argparse
import json
import os
import random

from PIL import Image, ImageDraw, ImageFont

W, H = 480, 640
BREAKS = ("missing_button", "cut_text", "overlap", "wrong_count", "low_contrast", "offscreen", "typo")
TITLES = ("Checkout", "Sign up", "New order", "Payment", "Profile", "Settings")
FIELDS = (("Email", "Card number"), ("Name", "Password"), ("Address", "Phone"), ("Email", "Promo code"))
BUTTONS = ("Pay now", "Create account", "Place order", "Save changes", "Continue")
ITEMS = ("Coffee beans", "Oat milk", "Paper cups", "Sugar", "Lids", "Stirrers", "Napkins")


def _font(size, bold=False):
    for f in (r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_spec(rng):
    return {"title": rng.choice(TITLES), "fields": list(rng.choice(FIELDS)), "button": rng.choice(BUTTONS),
            "items": rng.sample(ITEMS, 3)}


def _swap(text, rng):
    i = rng.randrange(1, len(text) - 2)
    return text[:i] + text[i + 1] + text[i] + text[i + 2:]          # two letters swapped


def draw(spec, brk=None, rng=None, subtle=False):
    """The screen for spec; brk plants one break. subtle: the same break, smaller - a typo in a small label instead
    of the title, an overlap of 8 px instead of 22, one letter's tail cut, faint text, a button 24 px past the edge.
    (The obvious breaks were all caught by a plain 'PASS or FAIL?' with the spec; these are where agents slip.)"""
    rng = rng or random.Random(0)
    im = Image.new("RGB", (W, H), (246, 247, 250))
    d = ImageDraw.Draw(im)
    title = spec["title"]
    fields = list(spec["fields"])
    if brk == "typo":
        if subtle:
            fields[1] = _swap(fields[1], rng)
        else:
            title = _swap(title, rng)
    d.text((32, 28), title, font=_font(34, True), fill=(20, 24, 33))
    y = 110
    for name in fields:
        d.text((32, y), name, font=_font(18), fill=(70, 76, 90))
        d.rounded_rectangle([32, y + 28, W - 32, y + 72], 8, outline=(190, 196, 210), width=2, fill=(255, 255, 255))
        y += 100
    items = spec["items"][:2] if brk == "wrong_count" else spec["items"]
    d.text((32, y), "Your items", font=_font(18, True), fill=(20, 24, 33))
    for k, it in enumerate(items):
        yy = y + 36 + k * 34
        if brk == "overlap" and k == 1:
            yy -= 8 if subtle else 22                                       # the second item lies over the first
        d.text((48, yy), "• " + it, font=_font(18), fill=(40, 44, 56))
    by = H - 110
    if brk != "missing_button":
        bx0, bx1 = 32, W - 32
        if brk == "offscreen":
            bx0, bx1 = (32, W + 24) if subtle else (W - 140, W + 300)       # past the right edge
        fill_txt = (255, 255, 255) if brk != "low_contrast" else ((150, 136, 236) if subtle else (112, 92, 230))
        d.rounded_rectangle([bx0, by, bx1, by + 56], 12, fill=(108, 88, 228))
        label = spec["button"]
        f = _font(22, True)
        if brk == "cut_text":
            tw = d.textlength(label, font=f)
            bx1 = int(bx0 + 18 + tw - 6) if subtle else bx0 + 110           # the button is too narrow for its label
            d.rectangle([bx1, by, W, by + 56], fill=(246, 247, 250))
            d.rounded_rectangle([bx0, by, bx1, by + 56], 12, fill=(108, 88, 228))
            tw = d.textlength(label, font=f)
            layer = Image.new("RGB", (int(tw) + 4, 40), (108, 88, 228))
            ImageDraw.Draw(layer).text((0, 4), label, font=f, fill=fill_txt)
            im.paste(layer.crop((0, 0, max(1, bx1 - bx0 - (18 if subtle else 30)), 40)), (bx0 + 18, by + 8))
        else:
            tw = d.textlength(label, font=f)
            d.text(((bx0 + min(bx1, W)) / 2 - tw / 2 if (brk != "offscreen" or subtle) else bx0 + 18, by + 12), label, font=f,
                   fill=fill_txt)
    return im


def build(out, n=24, seed=7, subtle=False):
    """n screens: a third intact, the rest one break each, every break type used. Writes NN.png + NN.json (the spec
    and the hidden answer) and answers.json."""
    rng = random.Random(seed)
    os.makedirs(out, exist_ok=True)
    plan = [None] * (n // 3) + [BREAKS[k % len(BREAKS)] for k in range(n - n // 3)]
    rng.shuffle(plan)
    answers = {}
    for k, brk in enumerate(plan):
        spec = make_spec(rng)
        name = f"{k:02d}"
        draw(spec, brk, random.Random(seed * 100 + k), subtle).save(os.path.join(out, name + ".png"))
        with open(os.path.join(out, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=1)
        answers[name] = brk or "intact"
    with open(os.path.join(out, "answers.json"), "w", encoding="utf-8") as f:
        json.dump(answers, f, indent=1)
    return answers


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--subtle", action="store_true", help="smaller breaks, where agents slip")
    a = ap.parse_args()
    print(json.dumps(build(a.out, a.n, subtle=a.subtle), indent=1))
