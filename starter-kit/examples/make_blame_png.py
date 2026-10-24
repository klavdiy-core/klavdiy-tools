"""Render examples/blame.png: a constructed session, and blame_check's REAL verdict on it.
    pip install pillow ; python examples/make_blame_png.py
"""
import json
import os
import sys
import tempfile
import textwrap

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "hooks"))
import blame_check  # noqa: E402

W, PAD, LINE = 1000, 26, 24
BG, FG, DIM, GREEN, YELLOW, CYAN, RED = (24, 26, 33), (220, 223, 228), (120, 126, 140), (120, 200, 120), (230, 200, 110), (110, 190, 230), (235, 120, 110)
REPLY = "This looks like a network issue on the server side, not the code."


def font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            pass
    return ImageFont.load_default()


MONO, BOLD = font(["consola.ttf", "DejaVuSansMono.ttf"], 17), font(["consolab.ttf", "DejaVuSansMono-Bold.ttf"], 17)


def session(d):
    steps = [
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Edit",
                                                       "input": {"file_path": "deploy/sync.py", "old_string": "a", "new_string": "b"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "./deploy.sh"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "is_error": True,
                                                  "content": "ssh: connect to host staging port 2222: Connection timed out"}]}},
    ]
    p = os.path.join(d, "t.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(s) for s in steps) + "\n")
    return p


def main():
    with tempfile.TemporaryDirectory() as d:
        code, err = blame_check.run([], json.dumps({"transcript_path": session(d), "stop_hook_active": False,
                                                    "last_assistant_message": REPLY}))
    rows = [("a constructed session (the hook's verdict below is its real output):", MONO, DIM), ("", MONO, FG),
            ("Claude  Edit  deploy/sync.py", MONO, FG),
            ("Claude  Bash  ./deploy.sh", MONO, FG),
            ("        ssh: connect to host staging port 2222: Connection timed out", MONO, RED), ("", MONO, FG),
            ("Claude, ending the turn:", MONO, DIM), ("  " + REPLY, BOLD, CYAN), ("", MONO, FG),
            (f"blame_check (Stop hook) -> exit {code}, the turn does not end:", MONO, DIM)]
    rows += [("  " + l, MONO, YELLOW) for l in textwrap.wrap(err.strip(), 86)]
    rows += [("", MONO, FG), ("Next it has to look at its own diff, or say plainly that it hasn't.", MONO, GREEN)]
    img = Image.new("RGB", (W, PAD * 2 + LINE * len(rows)), BG)
    dr = ImageDraw.Draw(img)
    for i, (t, f, c) in enumerate(rows):
        dr.text((PAD, PAD + i * LINE), t, font=f, fill=c)
    p = os.path.join(HERE, "blame.png")
    img.save(p)
    print(p, img.size, code)


if __name__ == "__main__":
    main()
