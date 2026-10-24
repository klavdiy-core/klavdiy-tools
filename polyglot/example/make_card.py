"""Render example/pushkin_lesson.png: one polyglot lesson on the first stanza of Pushkin's «Я вас любил» (1829).
    pip install pillow ; python example/make_card.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, PAD = 1200, 44
BG, FG, DIM, ACC, GLS, RED = (20, 21, 27), (232, 230, 224), (140, 138, 130), (232, 176, 74), (150, 200, 230), (235, 120, 110)


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

STANZA = [
    [("Я", "I"), ("вас", "you [formal]"), ("любил:", "loved [masc.]"), ("любовь", "love"), ("ещё,", "still"),
     ("быть может,", "perhaps")],
    [("В", "in"), ("душе", "soul"), ("моей", "my"), ("угасла", "died out [fem.]"), ("не совсем;", "not quite")],
    [("Но", "but"), ("пусть", "let"), ("она", "it/she"), ("вас", "you"), ("больше не", "no longer"), ("тревожит;", "troubles")],
    [("Я", "I"), ("не хочу", "don't want"), ("печалить", "to sadden"), ("вас", "you"), ("ничем.", "with anything")],
]
TRANSLIT = ["Ya vas lyubíl: lyubóv' yeshchyó, byt' mózhet,", "V dushé moyéy ugásla ne sovsém;",
            "No pust' oná vas ból'she ne trevózhit;", "Ya ne khochú pechálit' vas nichém."]
LOSES = [
    ("любил", "masculine past: Russian tells you a man is speaking. \"I loved\" does not."),
    ("вас", "the formal \"you\" (вы), not the intimate ты: he keeps his distance even while confessing."),
    ("угасла · она", "a flame going out; and love (любовь) is feminine, so \"она\" is both \"it\" and \"she\"."),
]
CARDS = "любить · угаснуть · тревожить · печалить · душа · ещё"
HOMEWORK = ["read the stanza aloud 3×, the last time without the gloss",
            "cover the gloss, write it again for lines 1-2, check",
            "one line of your own in the same beat, about anything"]


def main():
    img = Image.new("RGB", (W, 1500), BG)
    d = ImageDraw.Draw(img)
    y = PAD
    d.text((PAD, y), "polyglot · one lesson", font=HEAD, fill=ACC)
    d.text((W - PAD, y), "Pushkin, «Я вас любил», 1829 · stanza 1", font=HEAD, fill=DIM, anchor="ra")
    y += 44
    d.text((PAD, y), "1  ORIGINAL + 2  WORD BY WORD", font=HEAD, fill=DIM)
    y += 34
    for line, tr in zip(STANZA, TRANSLIT):
        x = PAD
        for word, gloss in line:
            ww = max(d.textlength(word + " ", font=SERIF), d.textlength(gloss + "  ", font=MONO))
            d.text((x, y), word, font=SERIF, fill=FG)
            d.text((x, y + 44), gloss, font=MONO, fill=RED if "[" in gloss else GLS)
            x += ww + 6
        d.text((PAD, y + 68), tr, font=SANS, fill=DIM)
        y += 116
    y += 6
    d.text((PAD, y), "3  SOUND", font=HEAD, fill=DIM)
    y += 28
    d.text((PAD, y), "я ВАС лю-БИЛ: лю-БОВЬ е-ЩЁ, быть МО-жет", font=MONO, fill=ACC)
    y += 30
    d.text((PAD, y), "iambic pentameter: five beats on the even syllables · rhyme ABAB: может / совсем / тревожит / ничем",
           font=SANS, fill=FG)
    y += 52
    d.text((PAD, y), "4  WHAT A TRANSLATION LOSES HERE", font=HEAD, fill=DIM)
    y += 30
    for word, why in LOSES:
        d.text((PAD, y), word, font=SANS_B, fill=RED)
        d.text((PAD + 170, y), why, font=SANS, fill=FG)
        y += 36
    y += 20
    d.text((PAD, y), "5  WORDS TO KEEP  (cards.py: due tomorrow, then 2, 4, 8, 16 days)", font=HEAD, fill=DIM)
    y += 30
    d.text((PAD, y), CARDS, font=SERIF_S, fill=GLS)
    y += 50
    d.text((PAD, y), "6  HOMEWORK, 15 MINUTES", font=HEAD, fill=DIM)
    y += 30
    for h in HOMEWORK:
        d.text((PAD, y), "·  " + h, font=SANS, fill=FG)
        y += 32
    y += 24
    d.text((PAD, y), "tomorrow starts with review: \"in «В душе моей угасла не совсем», what is угасла?\"",
           font=SANS, fill=DIM)
    y += PAD + 20
    img = img.crop((0, 0, W, y))
    out = os.path.join(HERE, "pushkin_lesson.png")
    img.save(out)
    print(out, img.size)


if __name__ == "__main__":
    main()
