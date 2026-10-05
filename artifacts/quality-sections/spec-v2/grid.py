import sys
from PIL import Image, ImageDraw, ImageEnhance
src, x0, y0, x1, y1, out = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
im = Image.open(src).convert('RGB').crop((x0, y0, x1, y1))
im = ImageEnhance.Brightness(im).enhance(2.2)
s = 900 / im.width
im = im.resize((900, int(im.height * s)), Image.LANCZOS)
d = ImageDraw.Draw(im)
step = 10
for gx in range((x0 // step) * step, x1, step):
    X = (gx - x0) * s
    if X < 0: continue
    major = gx % 50 == 0
    d.line([(X, 0), (X, im.height)], fill=(255, 0, 0) if major else (90, 90, 90), width=1)
    if major: d.text((X + 2, 2), str(gx), fill=(255, 255, 0))
for gy in range((y0 // step) * step, y1, step):
    Y = (gy - y0) * s
    if Y < 0: continue
    major = gy % 50 == 0
    d.line([(0, Y), (im.width, Y)], fill=(255, 0, 0) if major else (90, 90, 90), width=1)
    if major: d.text((2, Y + 2), str(gy), fill=(255, 255, 0))
im.save(out, quality=90)
