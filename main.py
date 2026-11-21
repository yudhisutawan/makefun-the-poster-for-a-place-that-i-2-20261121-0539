#!/usr/bin/env python3
"""VELDARA — The Poster for a Place That Isn't There.

A travel poster for Veldara, a city of floating islands above a sea of
clouds, drawn entirely in code at runtime: pure-stdlib vector drawing
(zlib + struct PNG encoder, no network, no assets, no fonts on disk).

Run:  python3 main.py            -> writes /output/entry.png
      (falls back to ./output/entry.png when /output is not writable)
"""
import math
import os
import random
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def blend(self, x, y, c, a):
        """Alpha-blend colour c (0..255) with alpha a (0..255) over pixel."""
        if 0 <= x < self.w and 0 <= y < self.h and a > 0:
            i = (y * self.w + x) * 3
            inv = 255 - a
            self.px[i] = (c[0] * a + self.px[i] * inv) // 255
            self.px[i + 1] = (c[1] * a + self.px[i + 1] * inv) // 255
            self.px[i + 2] = (c[2] * a + self.px[i + 2] * inv) // 255

    def rect(self, x0, y0, x1, y1, c):
        x0 = max(0, int(x0)); y0 = max(0, int(y0))
        x1 = min(self.w, int(x1)); y1 = min(self.h, int(y1))
        for y in range(y0, y1):
            base = (y * self.w + x0) * 3
            for x in range(x0, x1):
                i = base + (x - x0) * 3
                self.px[i], self.px[i + 1], self.px[i + 2] = c

    def rect_blend(self, x0, y0, x1, y1, c, a):
        for y in range(max(0, int(y0)), min(self.h, int(y1))):
            for x in range(max(0, int(x0)), min(self.w, int(x1))):
                self.blend(x, y, c, a)

    def hline(self, x0, x1, y, c):
        self.rect(x0, y, x1, y + 1, c)

    def vgrad(self, y0, y1, stops):
        """Vertical gradient; stops = [(y_fraction, (r,g,b)), ...] sorted."""
        for y in range(max(0, y0), min(self.h, y1)):
            t = (y - y0) / max(1, (y1 - y0))
            c = grad_at(stops, t)
            self.hline(0, self.w, y, c)

    def ellipse(self, cx, cy, rx, ry, c, alpha=255):
        for y in range(max(0, int(cy - ry)), min(self.h, int(cy + ry) + 1)):
            dy = (y - cy) / ry
            if abs(dy) > 1:
                continue
            dx = rx * math.sqrt(1 - dy * dy)
            x0, x1 = int(cx - dx), int(cx + dx)
            if alpha == 255:
                self.rect(x0, y, x1 + 1, y + 1, c)
            else:
                self.rect_blend(x0, y, x1 + 1, y + 1, c, alpha)

    def circle(self, cx, cy, r, c, alpha=255):
        self.ellipse(cx, cy, r, r, c, alpha)

    def poly(self, pts, c, alpha=255):
        """Scanline fill of a polygon [(x, y), ...]."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = max(0, int(min(ys))), min(self.h - 1, int(max(ys)) + 1)
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x1, y1p = pts[i]
                x2, y2p = pts[(i + 1) % n]
                if (y1p <= y < y2p) or (y2p <= y < y1p):
                    t = (y - y1p) / (y2p - y1p)
                    xs.append(x1 + t * (x2 - x1))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa, xb = int(xs[k]), int(xs[k + 1])
                if alpha == 255:
                    self.rect(xa, y, xb + 1, y + 1, c)
                else:
                    self.rect_blend(xa, y, xb + 1, y + 1, c, alpha)

    def line(self, x0, y0, x1, y1, c, width=1):
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        r = width // 2
        for s in range(steps + 1):
            t = s / max(1, steps)
            x = int(x0 + (x1 - x0) * t)
            y = int(y0 + (y1 - y0) * t)
            self.circle(x, y, max(1, r), c)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def grad_at(stops, t):
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        if t <= stops[i][0]:
            t0, c0 = stops[i - 1]
            t1, c1 = stops[i]
            return lerp(c0, c1, (t - t0) / max(1e-9, t1 - t0))
    return stops[-1][1]


# ---------------------------------------------------------------- PNG out
def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def write_png(cv, path):
    w, h = cv.w, cv.h
    raw = bytearray()
    bpp = 3
    prev = bytearray(w * bpp)
    for y in range(h):
        row = bytes(cv.px[y * w * bpp:(y + 1) * w * bpp])
        best, best_data = None, None
        for f in range(5):
            if f == 0:
                data = row
            elif f == 1:
                data = bytes((row[i] - (row[i - bpp] if i >= bpp else 0)) & 255
                             for i in range(len(row)))
            elif f == 2:
                data = bytes((row[i] - prev[i]) & 255 for i in range(len(row)))
            elif f == 3:
                data = bytes((row[i] - ((row[i - bpp] if i >= bpp else 0) + prev[i]) // 2) & 255
                             for i in range(len(row)))
            else:
                out = bytearray(len(row))
                for i in range(len(row)):
                    a = row[i - bpp] if i >= bpp else 0
                    b = prev[i]
                    c = prev[i - bpp] if i >= bpp else 0
                    out[i] = (row[i] - _paeth(a, b, c)) & 255
                data = bytes(out)
            score = sum(v if v < 128 else 256 - v for v in data)
            if best is None or score < best:
                best, best_data = score, data
                best_f = f
        raw.append(best_f)
        raw.extend(best_data)
        prev = bytearray(row)
    comp = zlib.compress(bytes(raw), 9)

    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        return out + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


# ---------------------------------------------------------------- 5x7 font
FONT = {}
def _g(ch, rows):
    FONT[ch] = ["".join("1" if c == "#" else "0" for c in r) for r in rows]

_g("A", [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"])
_g("B", ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "])
_g("C", [" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "])
_g("D", ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "])
_g("E", ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"])
_g("F", ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "])
_g("G", [" ### ", "#   #", "#    ", "#  ##", "#   #", "#   #", " ####"])
_g("H", ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"])
_g("I", [" ### ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "])
_g("J", ["  ###", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "])
_g("K", ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"])
_g("L", ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"])
_g("M", ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"])
_g("N", ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"])
_g("O", [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "])
_g("P", ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "])
_g("Q", [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"])
_g("R", ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"])
_g("S", [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "])
_g("T", ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "])
_g("U", ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "])
_g("V", ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "])
_g("W", ["#   #", "#   #", "#   #", "# # #", "# # #", "# # #", " # # "])
_g("X", ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"])
_g("Y", ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "])
_g("Z", ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"])
_g("0", [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "])
_g("1", ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "])
_g("2", [" ### ", "#   #", "    #", "  ## ", " #   ", "#    ", "#####"])
_g("3", ["#####", "   # ", "  #  ", "   # ", "    #", "#   #", " ### "])
_g("4", ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "])
_g("5", ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "])
_g("6", ["  ## ", " #   ", "#    ", "#### ", "#   #", "#   #", " ### "])
_g("7", ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "])
_g("8", [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "])
_g("9", [" ### ", "#   #", "#   #", " ####", "    #", "   # ", " ##  "])
_g(".", ["     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "])
_g(",", ["     ", "     ", "     ", "     ", " ##  ", "  #  ", " #   "])
_g("-", ["     ", "     ", "     ", " ### ", "     ", "     ", "     "])
_g("'", ["  #  ", "  #  ", " #   ", "     ", "     ", "     ", "     "])
_g("!", ["  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "     ", "  #  "])


def text_width(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(cv, x, y, s, scale, color):
    for ci, ch in enumerate(s):
        glyph = FONT.get(ch)
        if glyph is None:
            continue
        cx = x + ci * 6 * scale
        for r in range(7):
            for col in range(5):
                if glyph[r][col] == "1":
                    cv.rect(cx + col * scale, y + r * scale,
                            cx + (col + 1) * scale, y + (r + 1) * scale, color)


# ---------------------------------------------------------------- palette
INDIGO   = (28, 35, 80)
VIOLET   = (90, 62, 138)
MAUVE    = (198, 95, 116)
AMBER    = (242, 166, 90)
GOLD     = (247, 200, 115)
SUN      = (255, 233, 168)
CREAM    = (255, 243, 214)
PEACH    = (246, 200, 159)
LAVENDER = (201, 168, 216)
ROCK     = (107, 74, 99)
ROCK_DK  = (58, 43, 79)
ROCK_LT  = (138, 96, 118)
LEAF     = (95, 168, 106)
LEAF_DK  = (62, 124, 107)
WALL     = (247, 232, 200)
ROOF     = (232, 106, 90)
TEAL     = (46, 127, 122)
WATER    = (216, 236, 247)
BAND     = (20, 26, 61)
GOLDLINE = (232, 182, 76)
PLUM     = (43, 32, 66)

# ---------------------------------------------------------------- sky
def draw_sky(cv):
    cv.vgrad(0, 848, [
        (0.00, INDIGO), (0.30, VIOLET), (0.55, MAUVE),
        (0.78, AMBER), (1.00, GOLD),
    ])
    rng = random.Random(7)
    for _ in range(90):  # fading stars high in the sky
        x = rng.randint(10, 1014)
        y = rng.randint(10, 330)
        a = int(200 * (1 - y / 420)) + 20
        s = rng.choice([1, 1, 2])
        cv.rect_blend(x, y, x + s, y + s, CREAM, max(15, min(220, a)))
    # sun + halo
    for r, a in ((168, 14), (138, 22), (112, 40)):
        cv.circle(762, 330, r, SUN, a)
    cv.circle(762, 330, 86, SUN)
    cv.circle(762, 330, 72, (255, 244, 200))


def draw_cloud(cv, cx, cy, s, base, shade):
    """A puffy cloud from overlapping ellipses."""
    for dx, dy, rx, ry, c in (
        (-52, 6, 58, 22, shade), (0, -6, 66, 26, base),
        (54, 8, 56, 20, shade), (-18, 12, 60, 20, base),
        (28, 14, 58, 18, base), (0, 10, 92, 20, base),
    ):
        cv.ellipse(int(cx + dx * s), int(cy + dy * s),
                   int(rx * s), int(ry * s), c)


def draw_cloud_sea(cv):
    # warm sea of clouds the islands float above
    cv.vgrad(690, 848, [(0.0, (250, 214, 158)), (0.6, PEACH), (1.0, (233, 178, 150))])
    for cx, cy, s in ((120, 716, 1.5), (330, 700, 1.8), (560, 724, 1.6),
                      (790, 706, 1.9), (960, 726, 1.5), (220, 762, 1.7),
                      (470, 770, 1.9), (720, 772, 1.8), (920, 776, 1.6),
                      (60, 800, 1.6), (380, 812, 1.8), (640, 816, 1.7),
                      (880, 814, 1.8)):
        draw_cloud(cv, cx, cy, s, CREAM, (244, 190, 160))
    # soft shadows under the cloud tops
    for cx, cy, s in ((330, 742, 1.7), (720, 748, 1.8), (120, 758, 1.4)):
        cv.ellipse(cx, cy, int(95 * s), int(12 * s), (226, 158, 138), 45)


# ---------------------------------------------------------------- islands
def waterfall(cv, x, y0, y1, w):
    """A falling stream: pale body, white core streaks, mist at the base."""
    cv.poly([(x - w // 2, y0), (x + w // 2, y0),
             (x + w // 2 - 4, y1), (x - w // 2 + 4, y1)], (196, 224, 238))
    cv.poly([(x - w // 5, y0), (x + w // 5, y0),
             (x + w // 5 - 2, y1), (x - w // 5 + 2, y1)], (240, 248, 252))
    cv.line(x - w // 3, y0 + 8, x - w // 3 + 3, y1 - 12, (255, 255, 255), 2)
    cv.ellipse(x, y1, w, 10, (255, 250, 235), 110)


def house(cv, x, y, w, h, roof_c):
    cv.rect(x, y, x + w, y + h, WALL)
    cv.poly([(x - 3, y), (x + w // 2, y - h // 2), (x + w + 3, y)], roof_c)
    # lit windows
    for wx in range(x + 5, x + w - 4, 12):
        cv.rect(wx, y + h // 3, wx + 5, y + h // 3 + 7, GOLD)


def tree(cv, x, y, s):
    cv.rect(x - 2, y, x + 3, y + 14 * s, (90, 60, 60))
    cv.circle(x, y - 4 * s, 11 * s, LEAF)
    cv.circle(x - 9 * s, y + 2 * s, 8 * s, LEAF_DK)
    cv.circle(x + 9 * s, y + 2 * s, 8 * s, LEAF)


def tower(cv, x, y, w, h):
    """A slim spire tower with a glowing beacon."""
    cv.rect(x, y, x + w, y + h, WALL)
    cv.rect(x, y + h // 3, x + w, y + h // 3 + 6, TEAL)
    cv.rect(x, y + 2 * h // 3, x + w, y + 2 * h // 3 + 6, TEAL)
    cv.poly([(x - 2, y), (x + w // 2, y - 26), (x + w + 2, y)], ROOF)
    cv.circle(x + w // 2, y - 30, 7, SUN)
    for r, a in ((26, 30), (40, 16)):
        cv.circle(x + w // 2, y - 30, r, SUN, a)


def island(cv, cx, top_y, half_w, depth, town=True):
    """Floating rock: green plateau, tapering stone underside."""
    pts = [(cx - half_w, top_y), (cx + half_w, top_y),
           (cx + half_w * 0.72, top_y + depth * 0.45),
           (cx + half_w * 0.34, top_y + depth * 0.82),
           (cx, top_y + depth),
           (cx - half_w * 0.34, top_y + depth * 0.82),
           (cx - half_w * 0.72, top_y + depth * 0.45)]
    cv.poly(pts, ROCK)
    # sunlit facet on the left, shadow facet on the right
    cv.poly([(cx - half_w, top_y), (cx - half_w * 0.72, top_y + depth * 0.45),
             (cx - half_w * 0.34, top_y + depth * 0.82), (cx, top_y + depth),
             (cx - half_w * 0.1, top_y + depth * 0.4), (cx - half_w * 0.55, top_y)],
            ROCK_LT, 90)
    cv.poly([(cx + half_w, top_y), (cx + half_w * 0.72, top_y + depth * 0.45),
             (cx + half_w * 0.34, top_y + depth * 0.82), (cx, top_y + depth),
             (cx + half_w * 0.1, top_y + depth * 0.4), (cx + half_w * 0.55, top_y)],
            ROCK_DK, 110)
    # green plateau cap
    cv.ellipse(cx, top_y + 2, half_w, 16, LEAF)
    cv.ellipse(cx, top_y - 2, half_w - 8, 12, LEAF_DK)
    cv.ellipse(cx, top_y - 4, half_w - 30, 9, LEAF)
    return pts


def main_island(cv):
    cx, top_y, half_w = 512, 512, 268
    island(cv, cx, top_y, half_w, 218)
    # town on the plateau
    house(cv, 300, 470, 46, 42, ROOF)
    house(cv, 352, 462, 40, 50, TEAL)
    house(cv, 398, 474, 52, 38, ROOF)
    house(cv, 456, 458, 44, 54, TEAL)
    # domed hall
    cv.rect(508, 462, 566, 512, WALL)
    cv.ellipse(537, 462, 30, 26, ROOF)
    cv.rect(532, 478, 542, 492, GOLD)
    tower(cv, 600, 402, 30, 110)
    house(cv, 640, 472, 48, 40, ROOF)
    house(cv, 694, 466, 42, 46, TEAL)
    house(cv, 742, 476, 40, 36, ROOF)
    tree(cv, 288, 500, 1)
    tree(cv, 770, 498, 1)
    # waterfalls pouring off both edges into the clouds
    waterfall(cv, 268, 520, 716, 26)
    waterfall(cv, 756, 520, 712, 22)


def left_island(cv):
    cx, top_y, half_w = 168, 606, 96
    island(cv, cx, top_y, half_w, 96)
    tree(cv, 140, 596, 1)
    tree(cv, 196, 598, 1)
    house(cv, 152, 576, 34, 30, ROOF)
    waterfall(cv, 96, 612, 700, 14)


def right_island(cv):
    cx, top_y, half_w = 872, 566, 88
    island(cv, cx, top_y, half_w, 92)
    # lighthouse
    cv.rect(858, 486, 886, 566, WALL)
    cv.rect(858, 506, 886, 514, ROOF)
    cv.rect(858, 532, 886, 540, ROOF)
    cv.poly([(856, 486), (872, 462), (888, 486)], (43, 32, 66))
    cv.circle(872, 478, 6, SUN)
    # beacon rays
    cv.poly([(872, 478), (1000, 440), (1000, 470)], SUN, 36)
    cv.poly([(872, 478), (760, 448), (760, 472)], SUN, 30)
    tree(cv, 830, 556, 1)
    waterfall(cv, 946, 572, 700, 13)


def balloon(cv, cx, cy, r, env, stripe):
    cv.line(cx, cy + r, cx - 8, cy + r + 26, PLUM, 2)
    cv.line(cx, cy + r, cx + 8, cy + r + 26, PLUM, 2)
    cv.circle(cx, cy, r, env)
    cv.ellipse(cx, cy - r // 4, int(r * 0.42), int(r * 0.85), stripe)
    cv.ellipse(cx, cy, int(r * 0.72), int(r * 0.9), env)
    cv.poly([(cx - 12, cy + r + 22), (cx + 12, cy + r + 22),
             (cx + 9, cy + r + 40), (cx - 9, cy + r + 40)], (122, 82, 62))
    cv.circle(cx - int(r * 0.45), cy - int(r * 0.45), int(r * 0.2), (255, 255, 255), 120)


def birds(cv):
    for x, y, s in ((300, 210, 9), (340, 238, 7), (620, 168, 8),
                    (760, 300, 7), (180, 330, 8), (900, 330, 7),
                    (420, 150, 6), (560, 250, 6)):
        cv.line(x - s, y, x, y - s // 2, PLUM, 2)
        cv.line(x, y - s // 2, x + s, y, PLUM, 2)


# ---------------------------------------------------------------- compose
def build():
    cv = Canvas(W, H)
    draw_sky(cv)
    balloon(cv, 236, 262, 46, ROOF, CREAM)
    balloon(cv, 836, 206, 38, TEAL, CREAM)
    balloon(cv, 468, 158, 26, GOLD, CREAM)
    birds(cv)
    draw_cloud_sea(cv)
    main_island(cv)
    left_island(cv)
    right_island(cv)
    # title band
    cv.rect(0, 848, W, H, BAND)
    cv.rect(0, 848, W, 852, GOLDLINE)
    cv.rect(0, 856, W, 857, GOLDLINE)
    name = "VELDARA"
    scale = 13
    nx = (W - text_width(name, scale)) // 2
    draw_text(cv, nx, 872, name, scale, CREAM)
    slogan = "WHERE THE SKY COMES TO STAY"
    ss = 4
    sx = (W - text_width(slogan, ss)) // 2
    draw_text(cv, sx, 982, slogan, ss, GOLD)
    # small gold diamonds flanking the slogan
    for dx in (-46, 46):
        cx = W // 2 + dx * 8
        cv.poly([(cx, 986), (cx + 6, 992), (cx, 998), (cx - 6, 992)], GOLDLINE)
    return cv


def main():
    cv = build()
    outdir = "/output"
    try:
        os.makedirs(outdir, exist_ok=True)
        test = os.path.join(outdir, ".wtest")
        with open(test, "wb") as fh:
            fh.write(b"")
        os.remove(test)
    except OSError:
        outdir = "output"
        os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    size = write_png(cv, path)
    print(f"wrote {path} {W}x{H} {size} bytes")


if __name__ == "__main__":
    main()
