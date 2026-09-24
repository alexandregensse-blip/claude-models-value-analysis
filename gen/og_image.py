#!/usr/bin/env python3
"""Share image (Open Graph, 1200 × 630) → og-image.png at the repo root. Static on purpose: title, subtitle, domain
and the favicon's frontier motif — no figure that would go stale between builds. Rerun only when the title changes:
    uv run --no-project --with pillow python gen/og_image.py"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import SITE_HOST                                # the domain printed on the image follows SITE_URL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1200, 630
PAPER, INK, MUTED = "#F4EFE6", "#2B2723", "#7C7568"
DOTS = ["#3F8A78", "#D9694B", "#1C7FB8", "#7B3FBF"]      # model colours of the page, no ranking implied

img = Image.new("RGB", (W, H), PAPER)
d = ImageDraw.Draw(img)
font = lambda size: ImageFont.load_default(size=size)

d.text((72, 70), "Claude cost vs quality", font=font(76), fill=INK)
d.text((72, 168), "Fable, Opus, Sonnet, Haiku compared", font=font(46), fill=INK)
d.text((72, 246), "Relative cost and quality of every model,", font=font(32), fill=MUTED)
d.text((72, 290), "at every effort level, open data", font=font(32), fill=MUTED)
d.text((72, 540), SITE_HOST, font=font(34), fill=INK)

# Frontier motif, bottom right: a rising curve, dots unlabelled (the ranking lives in the data, not in the image).
pts = [(700, 520), (820, 430), (960, 380), (1110, 345)]
d.line(pts, fill="#CFC5B4", width=8, joint="curve")
for (x, y), col in zip(pts, DOTS):
    d.ellipse((x - 22, y - 22, x + 22, y + 22), fill=col)

img.save(os.path.join(ROOT, "og-image.png"), optimize=True)
print("wrote og-image.png")
