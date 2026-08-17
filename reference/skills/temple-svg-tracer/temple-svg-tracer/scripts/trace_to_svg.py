#!/usr/bin/env python3
"""
Convert black-ink-on-white line art PNGs into transparent-background SVGs.

Writes two files per input -- "NAME black.svg" and "NAME white.svg" -- carrying
identical geometry and differing only in fill. Both are transparent, so the
black one reads on light backgrounds and the white one on dark. Tracing runs
once and the fill is swapped on the way out, which is what guarantees the two
files register perfectly if they are ever stacked or swapped in a mockup.

Fixed parameters, chosen for loose architectural sketch line art. Do not tune
these per image -- consistency across a set is the whole point of this script.

Usage:
    python trace_to_svg.py INPUT [INPUT ...] --out OUTPUT_DIR
    python trace_to_svg.py /mnt/project/*.png --out /mnt/user-data/outputs/svg

Options:
    --threshold N     Ink cutoff, 0-255 (default 240). Raise to catch faint
                      construction lines, lower if grey haze is bleeding in.
    --upscale N       Resample factor before tracing (default 2). Raise for
                      small sources where hairlines have little pixel width.
    --only COLOR      Write just one variant, black or white. Default: both.
    --no-label-group  Do not wrap the caption text in its own <g>.
    --simplify        Heavier speckle filtering for smaller files.
    --trim            Tighten the viewBox onto the ink, leaving only --margin.
    --square          With --trim, pad the short axis to a 1:1 viewBox.
    --margin N        Edge margin under --trim, % of longest side (default 2).
    --drop-label      Omit the caption entirely.
"""

import argparse
import glob
import os
import re
import subprocess
import sys

# --- Locked tracing parameters -------------------------------------------
# Tuned on loose-sketch architectural line art with faint construction lines.
# Changing them changes the look, which defeats a repeatable pipeline.
#
# UPSCALE is the load-bearing setting. The faintest guide lines in these
# sketches are sub-pixel strokes rendered as light grey; at native resolution
# the spline fitter smooths them out of existence no matter how the threshold
# is set. Doubling the canvas first gives a hairline real width to trace.
UPSCALE = 2
# High enough to catch grey hairlines (which core out around 200-230), low
# enough that the anti-aliased halo on solid strokes is not swallowed too.
# Measured line weight change against source at this value: -1.7%.
THRESHOLD = 240
# Speckle filtering works on connected-component area. A hairline is thin but
# long, so its area is large and it survives filtering that still removes
# isolated anti-aliasing dots. This is why aggressive despeckling is safe here.
FILTER_SPECKLE = 6
FILTER_SPECKLE_SIMPLIFIED = 20
CORNER_THRESHOLD = 60
LENGTH_THRESHOLD = 2.0
LENGTH_THRESHOLD_SIMPLIFIED = 4.0
SPLICE_THRESHOLD = 45
# Coordinates already live in an upscaled space, so one decimal is plenty.
PATH_PRECISION = 1
PATH_PRECISION_SIMPLIFIED = 0
# Ink colors for the two output variants. Pure values, not off-black or
# off-white: these go to garment printing, where a near-white separates as a
# tinted ink rather than the base white.
VARIANT_FILLS = {"black": "#000000", "white": "#ffffff"}
# Breathing room left around the ink when trimming, as a percentage of the
# drawing's longest side. Scaling the margin off the long side rather than off
# each axis separately keeps it visually equal on all four edges instead of
# tight on one axis and loose on the other.
MARGIN_PCT = 2.0
# -------------------------------------------------------------------------


def ensure_deps():
    """Install vtracer/Pillow/numpy if missing. Safe to call repeatedly."""
    missing = []
    for mod, pkg in (("vtracer", "vtracer"), ("PIL", "Pillow"), ("numpy", "numpy")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"Installing: {', '.join(missing)}", file=sys.stderr)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--break-system-packages", *missing],
            check=True,
            stdout=subprocess.DEVNULL,
        )


def binarize(src, dst, threshold, upscale=UPSCALE):
    """Upscale, then flatten to pure black ink on pure white.

    Resample before thresholding, not after: LANCZOS preserves the grey ramp of
    a faint stroke, so a sub-pixel hairline becomes a genuine two-pixel line
    that the tracer can represent. Thresholding first would have already thrown
    that information away.

    Anti-aliased grey must then be forced to one side or the other, otherwise
    the tracer emits a halo of mid-grey shapes around every stroke.

    Returns (ink_percentage, ink mask, native (w, h))."""
    from PIL import Image
    import numpy as np

    im = Image.open(src).convert("L")
    native = im.size
    if upscale != 1:
        im = im.resize((native[0] * upscale, native[1] * upscale), Image.LANCZOS)

    a = np.array(im)
    mask = a < threshold
    b = np.where(mask, 0, 255).astype("uint8")
    Image.fromarray(b).convert("RGB").save(dst)
    return float(mask.mean() * 100), mask, native


def path_y_center(path_tag):
    """Vertical midpoint of a path, in absolute canvas coordinates.

    Classify by center rather than by the translate origin (the top edge):
    round glyphs like O overshoot the cap line, so their top can sit above a
    cut that their body clearly falls below. A center is unambiguous -- a
    caption letter's center is well under the cut, a building path's is not.

    vtracer emits only M/L/C/Z in spline mode, so every coordinate is part of
    an x,y pair and the odd-indexed numbers are the y values.
    """
    ty = re.search(r"transform=\"translate\(\s*[-\d.]+\s*,\s*([-\d.]+)\s*\)\"", path_tag)
    offset = float(ty.group(1)) if ty else 0.0

    d = re.search(r'\sd="([^"]*)"', path_tag)
    if not d:
        return offset
    nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", d.group(1))]
    ys = nums[1::2]
    if not ys:
        return offset
    return offset + (min(ys) + max(ys)) / 2.0


def parse_paths(svg_text):
    """Return (header, [(path_string, y_translate), ...])."""
    paths = re.findall(r"<path[^>]*/>", svg_text)
    out = []
    for p in paths:
        m = re.search(r"fill=\"(#[0-9a-fA-F]{6})\"", p)
        if m:
            h = m.group(1).lower()
            r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
            # A light fill is the background plate, not ink. Drop it -- this is
            # what makes the result transparent rather than white-backed.
            if (r + g + b) / 3 > 128:
                continue
            p = re.sub(r"fill=\"#[0-9a-fA-F]{6}\"", 'fill="#000000"', p)
        out.append((p, path_y_center(p)))
    header = svg_text.split("<path")[0].rstrip()
    if not header.endswith(">"):
        header += ">"
    return header, out


def find_label_cut(mask, quiet_frac=0.025, min_run_frac=0.011):
    """Find the y-coordinate separating the caption from the drawing.

    Work from the pixel rows rather than from path positions -- the caption sits
    under a band of near-empty rows, and that band is far easier to see in the
    row ink profile than in the tracer's output geometry.

    The band is "near-empty" rather than strictly empty because stray guide
    lines and ground strokes often clip into it. Scan upward and take the
    lowest qualifying band that still has a small amount of ink beneath it;
    capping that ink at a quarter of the total prevents ever cutting the
    building itself in half. Returns None when nothing convincing is found,
    in which case the caller should leave the drawing ungrouped.
    """
    rows = mask.sum(axis=1)
    h, w = mask.shape
    total = rows.sum()
    if total == 0:
        return None

    quiet = rows <= w * quiet_frac
    min_run = h * min_run_frac
    bands, i = [], 0
    while i < h:
        if quiet[i]:
            j = i
            while j < h and quiet[j]:
                j += 1
            if (j - i) >= min_run:
                bands.append((i, j))
            i = j
        else:
            i += 1

    for a, b in reversed(bands):
        if a <= h * 0.45:
            continue
        below = rows[b:].sum()
        if 0.005 * total < below < 0.25 * total:
            # Cut at the top of the quiet band. Anything inside the band is stray
            # by construction, so pulling the line up catches glyph parts that
            # start just above the caption baseline (letter counters, commas).
            return a + (b - a) * 0.15
    return None


def ink_viewbox(mask, margin_pct, square):
    """Tight window around every inked pixel, in traced coordinate space.

    Measure the box off the ink mask rather than off the traced path geometry.
    The mask is already in the upscaled coordinate space the tracer emits into,
    so the two line up exactly, and reading pixels avoids having to parse
    bezier control points -- a control point can sit outside the curve it
    describes, which would inflate the box by a few units for no reason.

    Returns (x, y, w, h) or None when the image is blank.
    """
    import numpy as np

    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    w, h = x1 - x0, y1 - y0

    margin = max(w, h) * margin_pct / 100.0
    if square:
        # Pad the short axis out to match the long one. Padding rather than
        # cropping is the only way to hit 1:1 without losing the faint
        # construction lines that overshoot the silhouette -- and those
        # overshoots are the whole look.
        side = max(w, h) + 2 * margin
        cx, cy = x0 + w / 2.0, y0 + h / 2.0
        return cx - side / 2.0, cy - side / 2.0, side, side
    return x0 - margin, y0 - margin, w + 2 * margin, h + 2 * margin


def trace_mask(mask, tmp_png, tmp_svg, simplify):
    """Trace a boolean ink mask and return (header, [(path, y_center), ...])."""
    import vtracer
    from PIL import Image
    import numpy as np

    arr = np.where(mask, 0, 255).astype("uint8")
    Image.fromarray(arr).convert("RGB").save(tmp_png)
    vtracer.convert_image_to_svg_py(
        tmp_png,
        tmp_svg,
        colormode="binary",
        mode="spline",
        filter_speckle=FILTER_SPECKLE_SIMPLIFIED if simplify else FILTER_SPECKLE,
        corner_threshold=CORNER_THRESHOLD,
        # File size is driven by node count and coordinate precision, not by
        # speckle filtering, so --simplify has to move these to have any effect.
        length_threshold=LENGTH_THRESHOLD_SIMPLIFIED if simplify else LENGTH_THRESHOLD,
        splice_threshold=SPLICE_THRESHOLD,
        path_precision=PATH_PRECISION_SIMPLIFIED if simplify else PATH_PRECISION,
    )
    return parse_paths(open(tmp_svg).read())


def convert(src, out_dir, threshold, simplify, label_group, upscale=UPSCALE,
            variants=("black", "white"), trim=False, square=False,
            margin_pct=MARGIN_PCT, drop_label=False):
    import numpy as np

    name = os.path.splitext(os.path.basename(src))[0]
    tmp_png = os.path.join(out_dir, f".{name}_bw.png")
    tmp_svg = os.path.join(out_dir, f".{name}_raw.svg")

    ink, mask, native = binarize(src, tmp_png, threshold, upscale)
    cut = find_label_cut(mask) if (label_group or drop_label) else None

    # Separate the caption in the pixel domain, not afterwards in the geometry.
    # Construction lines often run down and touch the lettering, which fuses
    # building and caption into a single connected shape that cannot be split
    # once traced. Masking first and tracing twice keeps them genuinely apart.
    # Both passes run on a full-size canvas so the coordinate systems line up.
    if cut is not None:
        row = int(cut)
        top, bottom = mask.copy(), mask.copy()
        top[row:, :] = False
        bottom[:row, :] = False
        header, body_paths = trace_mask(top, tmp_png, tmp_svg, simplify)
        if drop_label:
            label_paths = []
            kept = top
        else:
            _, label_paths = trace_mask(bottom, tmp_png, tmp_svg, simplify)
            kept = mask
    else:
        header, body_paths = trace_mask(mask, tmp_png, tmp_svg, simplify)
        label_paths = []
        kept = mask

    dim = re.search(r'width="(\d+)" height="(\d+)"', header)
    if dim:
        # The traced geometry lives in the upscaled space. Keep that as the
        # viewBox so no precision is lost, but advertise the drawing at its
        # native pixel size so it drops into a layout at the expected scale.
        tw, th = int(dim.group(1)), int(dim.group(2))
        # Trimming is a pure window change -- the paths are untouched, so
        # nothing is clipped and nothing is resampled. The box is measured over
        # whatever ink actually ends up in the file, which is why `kept` drops
        # the caption only when the caption is also being dropped from the
        # document. Measuring the building alone while still writing the label
        # would park the caption outside the window.
        box = ink_viewbox(kept, margin_pct, square) if trim else None
        if box is None:
            vb, ow, oh = f"0 0 {tw} {th}", native[0], native[1]
        else:
            x, y, w, h = box
            vb = f"{x:.1f} {y:.1f} {w:.1f} {h:.1f}"
            # Advertise at the same scale the untrimmed file would have used,
            # so a trimmed and an untrimmed export drop into a layout with the
            # linework at matching size rather than one appearing zoomed.
            ow, oh = max(1, round(w / upscale)), max(1, round(h / upscale))
        header = header.replace(
            f'width="{tw}" height="{th}"',
            f'width="{ow}" height="{oh}" viewBox="{vb}"',
        )

    lines = [header, '<g id="building">']
    lines += [p for p, _ in body_paths]
    lines.append("</g>")
    if label_paths:
        lines.append('<g id="label">')
        lines += [p for p, _ in label_paths]
        lines.append("</g>")
    lines.append("</svg>")
    doc = "\n".join(lines) + "\n"

    # One trace, two files. Recoloring the finished document rather than
    # re-tracing keeps the variants pixel-identical in geometry, so they can be
    # swapped in a mockup or stacked without any drift between them.
    written = {}
    for variant in variants:
        fill = VARIANT_FILLS[variant]
        out_path = os.path.join(out_dir, f"{name} {variant}.svg")
        with open(out_path, "w") as f:
            f.write(doc.replace('fill="#000000"', f'fill="{fill}"'))
        written[variant] = os.path.getsize(out_path) / 1024

    for t in (tmp_png, tmp_svg):
        if os.path.exists(t):
            os.remove(t)

    return {
        "name": name,
        "ink": ink,
        "building": len(body_paths),
        "label": len(label_paths),
        "written": written,
        "size": (ow, oh) if dim else native,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--threshold", type=int, default=THRESHOLD)
    ap.add_argument("--upscale", type=int, default=UPSCALE)
    ap.add_argument("--simplify", action="store_true")
    ap.add_argument("--no-label-group", action="store_true")
    ap.add_argument("--only", choices=sorted(VARIANT_FILLS), default=None,
                    help="Write only this variant. Default writes both.")
    ap.add_argument("--trim", action="store_true",
                    help="Crop the viewBox to the ink, leaving only --margin.")
    ap.add_argument("--square", action="store_true",
                    help="With --trim, pad the short axis to a 1:1 viewBox.")
    ap.add_argument("--margin", type=float, default=MARGIN_PCT,
                    help=f"Edge margin, %% of longest side (default {MARGIN_PCT}).")
    ap.add_argument("--drop-label", action="store_true",
                    help="Omit the caption entirely. With --trim, this is what "
                         "keeps framing consistent across a set.")
    args = ap.parse_args()
    variants = (args.only,) if args.only else ("black", "white")
    if args.square and not args.trim:
        # Squaring the untrimmed canvas would just pad the existing whitespace
        # out to 1:1, which is not what anyone asking for a square file wants.
        ap.error("--square requires --trim")

    ensure_deps()
    os.makedirs(args.out, exist_ok=True)

    files = []
    for pattern in args.inputs:
        files.extend(sorted(glob.glob(pattern)) if any(c in pattern for c in "*?[") else [pattern])
    if not files:
        sys.exit("No input files matched.")

    for src in files:
        r = convert(src, args.out, args.threshold, args.simplify,
                    not args.no_label_group, args.upscale, variants,
                    args.trim, args.square, args.margin, args.drop_label)
        note = ("label dropped" if args.drop_label and not r["label"]
                else f"{r['label']} label" if r["label"] else "no label split")
        sizes = ", ".join(f"{v} {kb:.0f}KB" for v, kb in r["written"].items())
        w, h = r["size"]
        ratio = f"{w}x{h} ({w / h:.3f}:1)"
        print(
            f"{r['name']}  ink {r['ink']:.1f}%  "
            f"{r['building']} building paths, {note}  {ratio}  [{sizes}]"
        )


if __name__ == "__main__":
    main()
