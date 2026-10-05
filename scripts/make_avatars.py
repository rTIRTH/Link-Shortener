#!/usr/bin/env python3
"""Generate the 20 pixel-art animal avatars (16x16 SVG) into app/static/avatars/.

Run:  python scripts/make_avatars.py            (writes the SVG files)
      python scripts/make_avatars.py --preview  (also writes /tmp/avatars.png, needs Pillow)
"""
import sys
from pathlib import Path

SIZE = 16
OUTLINE = "#2b2236"
EYE = "#241c2e"
WHITE = "#ffffff"
OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "avatars"

# Rounded face: {row: left_x}. Each row is filled from left_x to 15 - left_x.
HEAD = {5: 4, 6: 3, 7: 2, 8: 2, 9: 2, 10: 2, 11: 2, 12: 2, 13: 3, 14: 4}


class Canvas:
    def __init__(self, bg):
        self.bg = bg
        self.px = {}

    def put(self, x, y, c):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            self.px[(x, y)] = c

    def rect(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.put(xx, yy, c)

    def sput(self, x, y, c):  # mirrored pixel
        self.put(x, y, c)
        self.put(SIZE - 1 - x, y, c)

    def srect(self, x, y, w, h, c):  # mirrored rectangle
        self.rect(x, y, w, h, c)
        self.rect(SIZE - x - w, y, w, h, c)

    def rows(self, spec, c):
        for y, left in spec.items():
            self.rect(left, y, SIZE - 2 * left, 1, c)

    def eyes(self, y=8, color=EYE, h=2, x=5):
        self.srect(x, y, 1, h, color)


def pointy_ears(c, fur, inner, x=3, y=2, h=3, tip=None):
    for i in range(h):
        c.srect(x, y + i, i + 1, 1, fur)
    for i in range(1, h):
        c.sput(x + 1, y + i, inner)
    if tip:
        c.sput(x, y, tip)


def round_ears(c, fur, inner, x=2, y=3, size=3):
    c.srect(x, y, size, size, fur)
    c.sput(x + 1, y + 1, inner)


def cat():
    c = Canvas("#cfe8ff")
    pointy_ears(c, "#f0a04b", "#ffb3c1")
    c.rows(HEAD, "#f0a04b")
    c.srect(6, 5, 1, 2, "#c97a2b")
    c.sput(7, 6, "#c97a2b")
    c.srect(5, 10, 6, 4, "#fff1dc")
    c.eyes()
    c.srect(7, 10, 2, 1, "#ff8fa3")
    c.srect(7, 12, 1, 1, EYE)
    c.srect(8, 12, 1, 1, EYE)
    return c


def dog():
    c = Canvas("#ffe9b8")
    c.srect(0, 5, 3, 6, "#6b4226")
    c.rows(HEAD, "#c68642")
    c.srect(7, 5, 2, 4, "#fff1dc")
    c.srect(5, 10, 6, 4, "#fff1dc")
    c.eyes()
    c.srect(7, 10, 2, 2, EYE)
    c.srect(7, 13, 2, 1, "#ff8fa3")
    return c


def fox():
    c = Canvas("#d9f2d9")
    pointy_ears(c, "#ee7b30", "#fff1dc", y=1, h=4, tip=EYE)
    c.rows(HEAD, "#ee7b30")
    c.srect(2, 11, 3, 2, "#fff1dc")
    c.srect(5, 11, 6, 3, "#fff1dc")
    c.srect(4, 13, 8, 1, "#fff1dc")
    c.eyes()
    c.srect(7, 11, 2, 1, EYE)
    return c


def panda():
    c = Canvas("#d9f2d9")
    round_ears(c, EYE, EYE)
    c.rows(HEAD, "#f7f7f7")
    c.srect(4, 8, 3, 3, EYE)
    c.sput(5, 9, WHITE)
    c.srect(7, 11, 2, 1, EYE)
    c.srect(7, 12, 1, 1, EYE)
    c.srect(8, 12, 1, 1, EYE)
    return c


def rabbit():
    c = Canvas("#e8d9ff")
    c.srect(4, 0, 3, 6, "#f4f0f4")
    c.srect(5, 1, 1, 4, "#ffb3c1")
    c.rows(HEAD, "#f4f0f4")
    c.eyes(y=8)
    c.sput(3, 10, "#ffc4d0")
    c.srect(7, 10, 2, 1, "#ff8fa3")
    c.srect(7, 11, 1, 1, EYE)
    c.srect(8, 11, 1, 1, EYE)
    c.srect(7, 12, 2, 2, WHITE)
    c.put(7, 13, "#dcd6dc")
    return c


def bear():
    c = Canvas("#ffe9b8")
    round_ears(c, "#7a4a2a", "#d9a066")
    c.rows(HEAD, "#8b5a34")
    c.srect(5, 10, 6, 4, "#d9a066")
    c.eyes()
    c.srect(7, 10, 2, 1, EYE)
    c.srect(7, 12, 2, 1, EYE)
    return c


def frog():
    c = Canvas("#cfe8ff")
    c.srect(3, 3, 4, 4, "#6fcf4d")
    c.srect(4, 4, 2, 2, WHITE)
    c.sput(5, 5, EYE)
    c.rows({6: 2, 7: 1, 8: 1, 9: 1, 10: 1, 11: 1, 12: 2, 13: 3, 14: 4}, "#6fcf4d")
    c.sput(3, 5, "#6fcf4d")
    c.srect(7, 8, 1, 1, "#3c8a2a")
    c.srect(8, 8, 1, 1, "#3c8a2a")
    c.rect(3, 11, 10, 1, EYE)
    c.srect(2, 10, 1, 1, EYE)
    c.sput(4, 13, "#f7e08a")
    c.sput(3, 9, "#ffb3c1")
    return c


def owl():
    c = Canvas("#fde7c8")
    pointy_ears(c, "#8a6038", "#6b4226", x=3, y=2, h=3)
    c.rows(HEAD, "#a67c52")
    c.srect(3, 6, 4, 1, "#6b4226")
    c.srect(3, 7, 4, 4, WHITE)
    c.srect(4, 8, 2, 2, EYE)
    c.sput(4, 8, WHITE)
    c.srect(7, 10, 2, 2, "#f5a623")
    c.srect(5, 12, 6, 2, "#d9b48a")
    return c


def penguin():
    c = Canvas("#cfe8ff")
    c.rows(HEAD, "#2f3a52")
    c.rows({8: 4, 9: 3, 10: 3, 11: 3, 12: 3, 13: 4}, WHITE)
    c.srect(5, 9, 1, 1, EYE)
    c.srect(7, 10, 2, 2, "#f5a623")
    return c


def pig():
    c = Canvas("#d9f2d9")
    pointy_ears(c, "#f48fb1", "#ffc4d0", x=3, y=2, h=3)
    c.rows(HEAD, "#f8a5c2")
    c.eyes()
    c.srect(5, 10, 6, 4, "#ff8fb3")
    c.srect(6, 11, 1, 2, EYE)
    c.srect(9, 11, 1, 2, EYE)
    return c


def lion():
    c = Canvas("#ffe9b8")
    c.rows({1: 5, 2: 3, 3: 2, 4: 1, 5: 1, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0,
            12: 1, 13: 1, 14: 2, 15: 4}, "#8a4b1f")
    c.rows({4: 5, 5: 4, 6: 3, 7: 3, 8: 3, 9: 3, 10: 3, 11: 3, 12: 4, 13: 5, 14: 6},
           "#f2b84b")
    c.srect(2, 3, 2, 2, "#6b3a18")
    c.srect(5, 10, 6, 3, "#fff1dc")
    c.eyes(y=7, x=5)
    c.srect(7, 10, 2, 1, EYE)
    return c


def tiger():
    c = Canvas("#d9f2d9")
    round_ears(c, "#f08a24", "#fff1dc")
    c.rows(HEAD, "#f08a24")
    c.rect(6, 5, 4, 1, EYE)
    c.rect(7, 6, 2, 1, EYE)
    c.srect(2, 8, 2, 1, EYE)
    c.srect(2, 11, 2, 1, EYE)
    c.srect(5, 10, 6, 4, "#fff1dc")
    c.eyes()
    c.srect(7, 10, 2, 1, "#ff8fa3")
    return c


def monkey():
    c = Canvas("#fde7c8")
    c.srect(0, 6, 3, 4, "#7a4a2a")
    c.srect(1, 7, 1, 2, "#e8b98a")
    c.rows(HEAD, "#7a4a2a")
    c.rows({7: 4, 8: 4, 9: 4, 10: 4, 11: 4, 12: 4, 13: 5}, "#e8b98a")
    c.srect(4, 7, 3, 1, "#e8b98a")
    c.srect(5, 8, 1, 2, EYE)
    c.srect(7, 11, 1, 1, "#7a4a2a")
    c.srect(8, 11, 1, 1, "#7a4a2a")
    c.srect(6, 13, 4, 1, "#c98e62")
    return c


def koala():
    c = Canvas("#d9f2d9")
    c.srect(0, 3, 4, 4, "#9aa3ad")
    c.srect(1, 4, 2, 2, "#f1e9ee")
    c.rows(HEAD, "#a9b2bb")
    c.eyes(y=8)
    c.rows({9: 7, 10: 6, 11: 6}, EYE)
    return c


def mouse():
    c = Canvas("#e8d9ff")
    c.srect(1, 2, 4, 4, "#b9bec6")
    c.srect(2, 3, 2, 2, "#ffb3c1")
    c.rows(HEAD, "#cfd3d9")
    c.eyes()
    c.srect(7, 10, 2, 1, "#ff8fa3")
    c.srect(6, 11, 4, 1, "#e9ecef")
    c.sput(4, 12, "#ffc4d0")
    return c


def chicken():
    c = Canvas("#fff3b8")
    c.rect(7, 2, 2, 3, "#e53935")
    c.sput(6, 3, "#e53935")
    c.rows(HEAD, "#fbf7ee")
    c.eyes()
    c.srect(7, 10, 2, 2, "#f5a623")
    c.srect(7, 12, 2, 2, "#e53935")
    c.sput(3, 10, "#ffc4d0")
    return c


def duck():
    c = Canvas("#cfe8ff")
    c.sput(7, 4, "#f7d24a")
    c.rows(HEAD, "#f7d24a")
    c.eyes(y=8)
    c.srect(4, 10, 8, 3, "#f5851f")
    c.rect(4, 10, 8, 1, "#f9a03f")
    c.srect(6, 10, 1, 1, "#b85c10")
    c.srect(9, 10, 1, 1, "#b85c10")
    return c


def elephant():
    c = Canvas("#ffe9b8")
    c.srect(0, 5, 4, 8, "#8f98a3")
    c.srect(1, 7, 2, 4, "#ffb3c1")
    c.rows(HEAD, "#aab3bd")
    c.eyes(y=8)
    c.srect(7, 10, 2, 4, "#aab3bd")
    c.srect(7, 10, 1, 4, "#98a1ac")
    c.rect(7, 14, 3, 1, "#aab3bd")
    c.srect(5, 12, 1, 2, WHITE)
    return c


def wolf():
    c = Canvas("#cfe8ff")
    pointy_ears(c, "#6c7683", "#c9ced6", y=1, h=4)
    c.rows(HEAD, "#8c96a3")
    c.rect(5, 5, 6, 2, "#6c7683")
    c.srect(2, 11, 3, 2, "#dfe3e8")
    c.srect(5, 10, 6, 4, "#dfe3e8")
    c.eyes(y=8, color="#f5c542")
    c.sput(5, 9, EYE)
    c.srect(7, 10, 2, 1, EYE)
    return c


def raccoon():
    c = Canvas("#e8d9ff")
    round_ears(c, "#7d8794", "#f2f2f2")
    c.rows(HEAD, "#a3acb8")
    c.rect(3, 8, 10, 3, EYE)
    c.srect(2, 9, 1, 1, EYE)
    c.srect(5, 9, 1, 1, WHITE)
    c.srect(5, 11, 6, 3, WHITE)
    c.srect(7, 11, 2, 1, EYE)
    return c


ANIMALS = {
    "cat": cat, "dog": dog, "fox": fox, "panda": panda, "rabbit": rabbit,
    "bear": bear, "frog": frog, "owl": owl, "penguin": penguin, "pig": pig,
    "lion": lion, "tiger": tiger, "monkey": monkey, "koala": koala, "mouse": mouse,
    "chicken": chicken, "duck": duck, "elephant": elephant, "wolf": wolf,
    "raccoon": raccoon,
}


def with_outline(canvas):
    pixels = dict(canvas.px)
    outline = {}
    for (x, y) in pixels:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in pixels and 0 <= n[0] < SIZE and 0 <= n[1] < SIZE:
                outline[n] = OUTLINE
    return {**outline, **pixels}


def to_svg(canvas):
    pixels = with_outline(canvas)
    rects = [f'<rect width="{SIZE}" height="{SIZE}" fill="{canvas.bg}"/>']
    for y in range(SIZE):
        x = 0
        while x < SIZE:
            color = pixels.get((x, y))
            if color is None:
                x += 1
                continue
            start = x
            while x < SIZE and pixels.get((x, y)) == color:
                x += 1
            width = x - start
            rects.append(f'<rect x="{start}" y="{y}" width="{width}" height="1" fill="{color}"/>')
    body = "".join(rects)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
            f'width="128" height="128" shape-rendering="crispEdges">{body}</svg>\n')


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, build in ANIMALS.items():
        (OUT_DIR / f"{name}.svg").write_text(to_svg(build()), encoding="utf-8")
    print(f"Wrote {len(ANIMALS)} avatars to {OUT_DIR}")

    if "--preview" in sys.argv:
        from PIL import Image, ImageDraw
        scale, cols = 10, 5
        rows = (len(ANIMALS) + cols - 1) // cols
        cell = SIZE * scale
        sheet = Image.new("RGB", (cols * (cell + 12) + 12, rows * (cell + 28) + 12), "white")
        draw = ImageDraw.Draw(sheet)
        for i, (name, build) in enumerate(ANIMALS.items()):
            canvas = build()
            img = Image.new("RGB", (SIZE, SIZE), canvas.bg)
            for (x, y), color in with_outline(canvas).items():
                img.putpixel((x, y), tuple(int(color[j:j + 2], 16) for j in (1, 3, 5)))
            ox, oy = 12 + (i % cols) * (cell + 12), 12 + (i // cols) * (cell + 28)
            sheet.paste(img.resize((cell, cell), Image.NEAREST), (ox, oy))
            draw.text((ox, oy + cell + 4), name, fill="black")
        sheet.save("/tmp/avatars.png")


if __name__ == "__main__":
    main()
