#!/usr/bin/env python3
"""Crop any illustration to 3:2 and resize it to 1536x1024 PNG.

The card and reel renderers expect Figma's 1536x1024 art. Backup images
(Runway Gen-4 comes back 1440x1080) are cropped around a vertical focus
point and scaled to that size.

usage: python3 tools/fit_art.py in.jpg out.png [focus_y 0..1, default 0.5]
"""
import sys
from PIL import Image

W, H = 1536, 1024


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, out = sys.argv[1], sys.argv[2]
    fy = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    im = Image.open(src).convert("RGB")
    w, h = im.size
    if w / h > W / H:  # too wide: trim the sides evenly
        cw = round(h * W / H)
        x = (w - cw) // 2
        box = (x, 0, x + cw, h)
    else:  # too tall: trim top/bottom around the focus point
        ch = round(w * H / W)
        y = min(max(round((h - ch) * fy), 0), h - ch)
        box = (0, y, w, y + ch)
    im.crop(box).resize((W, H), Image.LANCZOS).save(out)
    print(f"{w}x{h} -> crop {box} -> {W}x{H}")


if __name__ == "__main__":
    main()
