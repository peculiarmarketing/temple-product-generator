"""Lay the real logo on the three garments in the spec overlay photo.

Input: the chosen GPT Image 2.5 render of Pexels 7972658 (2048x1360, plain black
blanks). Output: the same frame with the logo on each chest, placed by
zoom-v2/place_logo.py with the dive's proportions (0.73 of the collar width, top
0.59 logo widths below the collar band). Collars were measured on zoomed grids
of the render (grid.py).

place_logo keeps skin and straps in front on its own, but two things here are as
dark as the cloth: the hoodie's drawcords and the crewneck wearer's hair. Both are
put back in front of the print afterwards from the unprinted frame: the cords
from traced lines, the hair from its colour (hair is warm brown, the fabric a
slightly blue black, so red minus blue separates them). In the chosen frame her
hair was moved off the centre of her chest by a second render, so the hair mask
only matters at the edges.

Usage: python3 place_spec.py render.png out.png
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'zoom-v2'))
from place_logo import place  # noqa: E402

# (name, centre front at the bottom of the collar band, collar outer width, angle)
GARMENTS = [
    ('tee', (1155, 682), 125, 0),
    ('crew', (1663, 651), 133, 0),
    ('hoodie', (551, 614), 150, 3),  # hood opening measured like a collar
]

# hoodie drawcords, centre line top to bottom, about 9 px wide
CORDS = [((514, 600), (503, 768)), ((590, 612), (584, 792))]
CREW_BOX = (1560, 640, 1760, 790)


def cords_mask(size):
    m = Image.new('L', size, 0)
    d = ImageDraw.Draw(m)
    for a, b in CORDS:
        d.line([a, b], fill=255, width=11)
    return np.asarray(m.filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255


def hair_mask(img):
    x0, y0, x1, y1 = CREW_BOX
    warm = img[..., 0] - img[..., 2]
    m = np.zeros(img.shape[:2], np.float32)
    region = np.clip((warm[y0:y1, x0:x1] - 0.5) / 4.0, 0, 1)
    m[y0:y1, x0:x1] = region
    m = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))
    return np.asarray(m, np.float32) / 255


def main(src, out):
    tmp = out + '.tmp.png'
    cur = src
    for name, front, collar_w, angle in GARMENTS:
        place(cur, front, collar_w, angle, bend=2.5, out=tmp)
        cur = tmp
    orig = np.asarray(Image.open(src).convert('RGB'), np.float32)
    printed = np.asarray(Image.open(tmp).convert('RGB'), np.float32)
    front = np.maximum(cords_mask((orig.shape[1], orig.shape[0])), hair_mask(orig))[..., None]
    res = printed * (1 - front) + orig * front
    Image.fromarray(np.clip(res, 0, 255).astype(np.uint8)).save(out)
    os.remove(tmp)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
