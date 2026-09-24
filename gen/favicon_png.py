#!/usr/bin/env python3
"""favicon.png (96 × 96) at the repo root: the same drawing as favicon.svg, for Google Search, which
does not show SVG favicons. Standard library only (no Pillow): the shapes of favicon.svg are drawn
by supersampling and written as an RGBA PNG. Rerun only when favicon.svg changes:
    python3 gen/favicon_png.py"""
import math
import os
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE, VIEW, SS = 96, 64, 4                    # output pixels, favicon.svg viewBox, samples per axis


def rgb(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


# favicon.svg, shape by shape (viewBox 0 0 64 64), painted in this order.
BG, BG_RX = rgb("#2B2723"), 14
LINE, LINE_W, LINE_OPACITY = rgb("#F4EFE6"), 3, 0.55
PTS = [(12, 50), (24, 31), (38, 23), (52, 16)]
DOTS = list(zip(PTS, (rgb("#3F8A78"), rgb("#D9694B"), rgb("#1C7FB8"), rgb("#7B3FBF"))))
DOT_R = 6


def in_rounded_rect(x, y):
    cx = min(max(x, BG_RX), VIEW - BG_RX)
    cy = min(max(y, BG_RX), VIEW - BG_RX)
    return 0 <= x <= VIEW and 0 <= y <= VIEW and (x - cx) ** 2 + (y - cy) ** 2 <= BG_RX ** 2


def seg_dist(x, y, a, b):
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - ax - t * dx, y - ay - t * dy)


def sample(x, y):
    """Colour (r, g, b, a in 0..1) of favicon.svg at a point of its viewBox."""
    if not in_rounded_rect(x, y):
        return (0.0, 0.0, 0.0, 0.0)
    c = BG
    for (px, py), col in DOTS:                # dots are painted over the line: check them first
        if (x - px) ** 2 + (y - py) ** 2 <= DOT_R ** 2:
            return (*col, 1.0)
    if min(seg_dist(x, y, PTS[i], PTS[i + 1]) for i in range(len(PTS) - 1)) <= LINE_W / 2:
        c = tuple(LINE_OPACITY * l + (1 - LINE_OPACITY) * b for l, b in zip(LINE, c))
    return (*c, 1.0)


def render():
    rows = []
    scale = VIEW / SIZE
    for j in range(SIZE):
        row = bytearray([0])                  # PNG filter type 0 for each scanline
        for i in range(SIZE):
            r = g = b = a = 0.0
            for sj in range(SS):
                for si in range(SS):
                    sr, sg, sb, sa = sample((i + (si + 0.5) / SS) * scale, (j + (sj + 0.5) / SS) * scale)
                    r, g, b, a = r + sr * sa, g + sg * sa, b + sb * sa, a + sa
            n = SS * SS
            row += bytes((round(r / a), round(g / a), round(b / a), round(255 * a / n)) if a else (0, 0, 0, 0))
        rows.append(bytes(row))
    return b"".join(rows)


def png(raw):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)   # 8-bit RGBA
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


with open(os.path.join(ROOT, "favicon.png"), "wb") as f:
    f.write(png(render()))
print("wrote favicon.png")
