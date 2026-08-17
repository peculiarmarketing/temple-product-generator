---
name: temple-svg-tracer
description: Converts black-line architectural sketch images (temple line art, building illustrations, ink drawings) from PNG or JPG into clean SVG vector files with transparent backgrounds and no white plate behind the linework, producing both a black and a white version of every image. Use this skill whenever the user uploads or references a line-art image and wants an SVG, a vector, a transparent version, a white or inverted version for dark shirts or dark backgrounds, a file for Cricut or Illustrator or Figma, or says anything like "vectorize this", "make this an SVG", "remove the white background", "give me a white version", "turn these into vectors", or "trace this". Always use this skill rather than tracing freehand or writing a one-off conversion script — the parameters are fixed here so every image in a set comes out matching.
---

# Temple SVG Tracer

Turns generated line-art sketches into production SVGs: transparent background, caption text separated into its own group, and two color variants per source — black linework for light garments and backgrounds, white for dark ones.

The entire point of this skill is **consistency across a set**. Ten temples traced on ten different days must look like they came from the same hand. So the tracing parameters live in the bundled script, not in judgment calls made per image. Do not improvise a different pipeline, and do not hand-tune settings for an individual image unless the user explicitly asks for a change to the whole set.

## Running it

```bash
python scripts/trace_to_svg.py '<input glob or paths>' --out <output dir>
```

Example:

```bash
python scripts/trace_to_svg.py '/mnt/project/*.png' --out /mnt/user-data/outputs/svg
```

For square, tightly-framed files:

```bash
python scripts/trace_to_svg.py '/mnt/project/*.png' --out /mnt/user-data/outputs/svg \
    --trim --square --drop-label
```

Quote globs so the shell passes the pattern through rather than expanding it. The script installs its own dependencies (`vtracer`, `Pillow`, `numpy`) on first run, so it works from a cold container.

It prints one line per image: ink coverage, path counts for each group, and the size of each variant written. Read those numbers — they are the diagnostic (see Checking the output).

## What comes out

Two files per source image, `NAME black.svg` and `NAME white.svg`, where `NAME` is the source filename unchanged. Name the source files after the temple and the outputs come out as `Salt Lake black.svg` — so the sources are worth naming properly up front rather than renaming a hundred outputs later. There is no plain `NAME.svg`; the color is always in the filename, because on a storefront the cost of shipping the wrong one is high and the two are indistinguishable in a file browser thumbnail — a white SVG previews as blank.

Filenames contain spaces, so quote every path in shell commands.

The pair comes from a single trace with the fill swapped on write, not from two separate traces, so the geometry is byte-identical between them. They can be stacked, swapped in a mockup, or scaled together with no drift.

Each SVG contains:

- No background rectangle. Light-filled paths are discarded during conversion, which is what makes the result genuinely transparent rather than white-backed. This matters more for the white variant than the black one: a white plate behind white linework is invisible until it prints.
- Every path filled with the variant color, `#000000` or `#ffffff` — pure values, since a near-white separates as a tinted ink rather than the base white in garment printing. These are filled outlines of the strokes, not stroked lines, so stroke width cannot be adjusted afterward — the weight is baked in from the source image. Recoloring to something other than black or white is a find-and-replace on the fill attribute across the file.
- `width`/`height` at the source image's native size, with a `viewBox` in the larger traced coordinate space. The file therefore drops into a layout at the expected scale while keeping the extra precision. The tracer emits no viewBox at all, so this has to be added. Under `--trim` both are recomputed to the trimmed window, still at native scale.
- `<g id="building">` and, when a caption is detected, `<g id="label">`. The user can hide or delete the label group in one click.

## Options

| Flag | Use when |
|---|---|
| `--threshold N` | Default 240, tuned to catch grey hairlines without swallowing the halo around solid strokes. Raise toward 248 only if faint lines are still dropping, accepting roughly 8% line fattening. Lower toward 220 if anti-aliasing haze is coming through as fuzz. |
| `--upscale N` | Default 2. Raise to 3 for sources under about 800px, where hairlines have even less pixel width to work with. Costs file size roughly linearly. |
| `--simplify` | Dense drawings producing very large files. Trades the faintest hairlines for a smaller file, so avoid it when fine detail is the point. |
| `--no-label-group` | Source has no caption text, or the caption should stay merged with the drawing. |
| `--only black` / `--only white` | Only one variant is wanted. Default writes both. Prefer the default even when only one is needed right now — the second file costs one fill swap, and regenerating it later means re-running the trace and trusting it to match. |
| `--trim` | Tighten the viewBox onto the ink, leaving only the margin. Off by default, because the untrimmed file preserves whatever framing the source had. |
| `--square` | With `--trim`, pad the short axis to a 1:1 viewBox. Requires `--trim`. |
| `--margin N` | Edge margin under `--trim`, as a percentage of the drawing's longest side. Default 2. |
| `--drop-label` | Omit the caption from the file entirely. Under `--trim`, this is what keeps framing consistent across a set. |

If one image in a set needs a different threshold to look right, that is a signal the source image is off — regenerate it rather than special-casing the trace, or the set will not match.

### Why upscaling matters more than threshold

The faintest guide lines in these sketches are sub-pixel strokes rendered as light grey, roughly 200-230 in tone. Two separate things destroy them at native resolution: a low threshold discards them as background, and spline fitting smooths a one-pixel line out of existence even when the threshold does catch it. Only the second problem is fixed by upscaling, and only the first by raising the threshold, so both settings are needed together. Dropping either one loses fine detail no matter how the other is tuned.

Aggressive despeckling is safe alongside this because the speckle filter works on connected-component area. A hairline is thin but long, so its area is large; isolated anti-aliasing dots are small. Filtering removes the dots and leaves the lines.

## Framing and 1:1

`--trim` is a window change, not a crop: it rewrites the `viewBox` and leaves every path untouched, so no geometry is discarded and nothing is resampled. Because the two variants share a trace, they share the window too.

Three requests conflict, and the caller usually wants all three: square, tight on every edge, and nothing cut off. Those can only hold together if the drawing itself is square, and a temple sketch never is. `--trim --square` resolves it by **padding** the short axis rather than cropping the long one — tight on two edges, symmetric breathing room on the other two, and every stroke intact. Cropping to square is not offered, because the faint construction lines that overshoot the silhouette are the first thing a square crop eats, and they are the whole look.

So: `--trim` alone for a tight file at the drawing's natural aspect, `--trim --square` for a 1:1 file. Reach for `--square` when the target frame is fixed — a print area, a Shopify grid, a paid social slot — and plain `--trim` when the art is being placed by hand and can size itself.

**Trim and captions interact.** The box is measured over the ink actually written to the file, so with a caption present it widens to whatever the longest temple name is. Across a set that means "Nauvoo" and "Tabernáculo de Guayaquil" frame differently, which is exactly the inconsistency this skill exists to prevent. Pair `--trim` with `--drop-label` when a set has to match, and hold the caption in the layout instead. If the caption must ship inside the SVG, trim measures it too rather than parking it outside the window and silently cutting it off.

Margins are scaled off the longest side, not per axis, so 2% reads as the same visual gap on all four edges rather than tight on one axis and loose on the other.

## Checking the output

Never hand back SVGs without looking at them. Transparency is invisible against a white chat background, and a failed trace can still produce a plausible-looking file. The white variant needs this even more than the black one — viewed anywhere light it is simply blank, which is indistinguishable from an empty file, a failed trace, and a correct result.

Check both variants, each over a plate that contrasts with its own ink:

```python
import cairosvg
from PIL import Image
for name, bg in [("Salt Lake black.svg", (0, 200, 255, 255)),
                 ("Salt Lake white.svg", (20, 24, 40, 255))]:
    cairosvg.svg2png(url=name, write_to="check.png", output_width=380)
    im = Image.open("check.png").convert("RGBA")
    plate = Image.new("RGBA", im.size, bg)
    plate.alpha_composite(im)
    plate.convert("RGB").save(name.replace(".svg", "_check.png"))
```

Neither plate is white, which is what proves the background is actually transparent rather than merely matching the page. Compositing the pair side by side, or a whole set into one contact sheet, makes everything reviewable at a glance.

Four things to look for:

**Both variants present and correctly colored.** A quick `grep -c 'fill="#ffffff"'` on the white file and the same for `#000000` on the black should return the same count, with zero of the opposite color in each. Equal counts also confirm the two came off the same trace.

**Label split correctness.** Render again with the label group stripped (`re.sub(r'<g id="label">.*?</g>', '', svg, flags=re.S)`) and confirm no letters remain behind and no part of the building went missing. The caption is found by scanning pixel rows for the band of near-empty space above the text, then tracing above and below that line as two separate passes. Tracing once and sorting paths afterward does not work: construction lines frequently run down and touch the lettering, fusing building and caption into one connected shape that cannot be separated after the fact.

**Framing, when trimming.** The script prints the emitted dimensions and ratio per file — confirm `1.000:1` when `--square` was asked for. Then measure the gap from the ink to each edge on a render and confirm all four are non-zero and that the two tight edges match the requested margin. A zero gap means something is touching the frame, which is the one failure mode that loses linework:

```python
import numpy as np, cairosvg
from PIL import Image
cairosvg.svg2png(url="Salt Lake black.svg", write_to="check.png", output_width=800)
ink = np.array(Image.open("check.png").convert("RGBA"))[:, :, 3] > 40
ys, xs = np.where(ink); H, W = ink.shape
print(f"L{xs.min()/W*100:.1f}% R{(W-xs.max())/W*100:.1f}% "
      f"T{ys.min()/H*100:.1f}% B{(H-ys.max())/H*100:.1f}%")
```

**Detail retention.** Faint guide lines extending past the silhouette are part of the intended look and must survive. Eyeballing a full-size render is not sensitive enough to catch their loss — measure it. Run this on the black variant only: it compares dark ink against a white plate, and the geometry is shared, so the result covers both files. Rasterize back at source resolution and diff — this one needs an untrimmed export, since it aligns the render against the source pixel for pixel:

```python
import numpy as np, cairosvg
from PIL import Image
src = np.array(Image.open("in.png").convert("L")); H, W = src.shape
cairosvg.svg2png(url="Salt Lake black.svg", write_to="check.png",
                 output_width=W, output_height=H, background_color="white")
out = np.array(Image.open("check.png").convert("L")) < 128
faint, solid = src < 245, src < 170
print(f"lost faint {(faint & ~out).sum()/faint.sum()*100:.1f}%")
print(f"lost solid {(solid & ~out).sum()/solid.sum()*100:.1f}%")
print(f"weight delta {(out.sum()-faint.sum())/faint.sum()*100:+.1f}%")
```

Healthy numbers on the tuned settings: lost solid at 0%, lost faint under about 10%, weight delta within a few percent either way. Lost faint never reaches zero because the outermost anti-aliased edge pixel of every stroke counts as source ink and cannot survive a binary trace — that residual is expected, not a defect. Lost solid above zero, or weight delta beyond roughly ±8%, means something is actually wrong.

Also crop in on a region of faint construction lines at high magnification and compare it against the same crop of the source. Aggregate percentages can look fine while a specific class of mark is missing.

## Reporting back

Present the files with `present_files`, keeping each temple's pair adjacent rather than grouping all the black files then all the white — the pair is the unit of work. Mention:

- Which variant is which, and that the white one previews as blank on a light background. Say this before the user opens it, not after they report an empty file.
- File sizes, flagging any outlier over ~400KB with `--simplify` as the remedy. The two variants are the same size; report it once per temple.
- That the caption sits in its own `label` group and can be removed.
- The aspect ratio when trimming, and — for `--square` — that the extra space sits on the short axis by design, since that is the part most likely to read as a bug rather than a choice.
- That stroke width is fixed, since anyone planning to restyle the linework in Illustrator needs to know that up front.

Skip the render checks from the report — they are verification, not deliverables.
