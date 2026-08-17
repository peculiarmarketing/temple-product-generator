"""Local tracing stage: a temple folder holding only the source PNG gets its
black and white SVG pair traced automatically, using the exported
temple-svg-tracer script with the approved standard flags (--trim
--drop-label; no --square per the 17 Aug 2026 decision).

Every trace is verified against the tracer skill's own health checks before
any product is generated from it:
  - both variants written, fill counts equal and correctly colored
  - no ink touching the frame (the failure mode that loses linework)
  - detail retention vs the source sketch: lost solid ~0%, lost faint < 10%,
    ink weight delta within +/-8% (measured on an untrimmed QC trace so the
    render aligns with the source pixel for pixel)
A side-by-side check composite is saved to the folder as
"{Temple} trace check (auto).png" for Evan's optional eyeball; the real gate
remains his review of the unpublished product before publishing.
"""

import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import resvg_py
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent
TRACER = PROJECT_ROOT / "reference" / "skills" / "temple-svg-tracer" / "temple-svg-tracer" / "scripts" / "trace_to_svg.py"
STANDARD_FLAGS = ["--trim", "--drop-label"]
NON_SOURCE_MARKERS = ("(auto)", "location text", "art closeup", "trace check")
THRESHOLDS = {"lost_solid_pct": 0.5, "lost_faint_pct": 10.0, "weight_delta_pct": 8.0}


def find_source_png(folder, temple):
    exact = [p for p in folder.glob("*.png") if p.stem.lower() == temple.lower()]
    if exact:
        return exact[0]
    candidates = [p for p in folder.glob("*.png")
                  if not any(m in p.name.lower() for m in NON_SOURCE_MARKERS)]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise SystemExit(f"{temple}: several PNGs could be the source sketch "
                         f"({[p.name for p in candidates]}); name one '{temple}.png'.")
    return None


def _run_tracer(png_path, out_dir, extra_flags):
    cmd = [sys.executable, str(TRACER), str(png_path), "--out", str(out_dir)] + extra_flags
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise SystemExit(f"tracer failed: {r.stderr[-800:] or r.stdout[-800:]}")
    return r.stdout


SPECK_CUTOFF_FRAC = 0.005  # paths smaller than 0.5% of the drawing's longest side are dots


def strip_specks(black_svg, white_svg):
    """Remove speck paths: shadow-haze artifacts that binarization turns into
    isolated dots. A speck is a path whose whole extent is tiny relative to
    the drawing; real linework is long, so its paths are always large. The
    same indices are removed from both variants (shared geometry)."""
    import re
    b_txt = black_svg.read_text()
    paths = re.findall(r"<path[^>]*/?>(?:</path>)?", b_txt)
    vb = re.search(r'viewBox="([\d. -]+)"', b_txt)
    vw, vh = (float(x) for x in vb.group(1).split()[2:4])
    cutoff = max(vw, vh) * SPECK_CUTOFF_FRAC
    drop = set()
    for i, p in enumerate(paths):
        d = re.search(r'd="([^"]+)"', p)
        tf = re.search(r"translate\(([\d. ,-]+)\)", p)
        nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", d.group(1))]
        xs, ys = nums[0::2], nums[1::2]
        if xs and (max(xs) - min(xs)) < cutoff and (max(ys) - min(ys)) < cutoff:
            drop.add(i)
    if not drop:
        return 0
    for svg in (black_svg, white_svg):
        txt = svg.read_text()
        found = re.findall(r"<path[^>]*/?>(?:</path>)?", txt)
        for i in sorted(drop, reverse=True):
            txt = txt.replace(found[i], "", 1)
        svg.write_text(txt)
    return len(drop)


def _rasterize(svg_path, width=None, height=None):
    kw = {}
    if width:
        kw["width"] = int(width)
    if height:
        kw["height"] = int(height)
    return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=Path(svg_path).read_text(), **kw)))).convert("RGBA")


def verify_trace(folder, temple, source_png, qc_black_svg):
    black = folder / f"{temple} black.svg"
    white = folder / f"{temple} white.svg"
    problems, metrics = [], {}

    for path in (black, white):
        if not path.exists():
            raise SystemExit(f"{temple}: tracer did not write {path.name}")
    b_txt, w_txt = black.read_text(), white.read_text()
    b_fills, w_fills = b_txt.count('fill="#000000"'), w_txt.count('fill="#ffffff"')
    metrics["paths"] = b_fills
    if b_fills == 0 or b_fills != w_fills or w_txt.count('fill="#000000"') or b_txt.count('fill="#ffffff"'):
        problems.append(f"variant fill mismatch (black {b_fills}, white {w_fills})")

    img = _rasterize(black, width=800)
    a = np.asarray(img.getchannel("A")) > 40
    ys, xs = np.where(a)
    h, w = a.shape
    edges = (xs.min(), ys.min(), w - 1 - xs.max(), h - 1 - ys.max())
    metrics["edge_gaps_px"] = edges
    if min(edges) == 0:
        problems.append("ink touches the frame edge (linework at risk)")

    # detail retention against the source, pixel-aligned via the untrimmed QC trace
    src = np.asarray(Image.open(source_png).convert("L"))
    H, W = src.shape
    render = _rasterize(qc_black_svg, width=W, height=H)
    plate = Image.new("RGBA", render.size, (255, 255, 255, 255))
    plate.alpha_composite(render)
    out = np.asarray(plate.convert("L")) < 128
    if out.shape != src.shape:
        problems.append(f"QC render {out.shape} does not match source {src.shape}")
    else:
        faint, solid = src < 245, src < 170
        lost_faint = 100 * (faint & ~out).sum() / max(1, faint.sum())
        lost_solid = 100 * (solid & ~out).sum() / max(1, solid.sum())
        weight_delta = 100 * (int(out.sum()) - int(faint.sum())) / max(1, faint.sum())
        metrics.update(lost_faint_pct=round(lost_faint, 2), lost_solid_pct=round(lost_solid, 2),
                       weight_delta_pct=round(weight_delta, 2))
        if lost_solid > THRESHOLDS["lost_solid_pct"]:
            problems.append(f"lost solid ink {lost_solid:.1f}% (limit {THRESHOLDS['lost_solid_pct']}%)")
        if lost_faint > THRESHOLDS["lost_faint_pct"]:
            problems.append(f"lost faint ink {lost_faint:.1f}% (limit {THRESHOLDS['lost_faint_pct']}%)")
        if abs(weight_delta) > THRESHOLDS["weight_delta_pct"]:
            problems.append(f"ink weight delta {weight_delta:+.1f}% (limit +/-{THRESHOLDS['weight_delta_pct']}%)")

    # check composite: black on light plate beside white on dark plate
    side = 700
    combo = Image.new("RGB", (side * 2, side), (255, 255, 255))
    for i, (svg, bg) in enumerate(((black, (210, 235, 255)), (white, (20, 24, 40)))):
        r = _rasterize(svg, width=side - 40)
        tile = Image.new("RGBA", (side, side), bg + (255,))
        tile.alpha_composite(r, ((side - r.width) // 2, (side - r.height) // 2))
        combo.paste(tile.convert("RGB"), (i * side, 0))
    combo.save(folder / f"{temple} trace check (auto).png")

    return problems, metrics


def trace_temple(folder, temple):
    """Full stage: find PNG, production trace into the folder, QC trace for
    verification, verify. Returns metrics; raises SystemExit on any failure."""
    source = find_source_png(folder, temple)
    if source is None:
        raise SystemExit(f"{temple}: no SVGs and no source PNG found")
    with tempfile.TemporaryDirectory() as td:
        staged = Path(td) / f"{temple}.png"
        shutil.copyfile(source, staged)
        print(f"  tracing {source.name} (production pass)")
        _run_tracer(staged, folder, STANDARD_FLAGS)
        removed = strip_specks(folder / f"{temple} black.svg", folder / f"{temple} white.svg")
        if removed:
            print(f"  speck filter: removed {removed} shadow-haze dots")
        print(f"  tracing {source.name} (QC pass, untrimmed)")
        _run_tracer(staged, td, ["--drop-label", "--only", "black"])
        problems, metrics = verify_trace(folder, temple, source, Path(td) / f"{temple} black.svg")
    print(f"  trace metrics: {metrics}")
    if problems:
        raise SystemExit(f"{temple}: trace failed verification: " + "; ".join(problems))
    print(f"  trace verified; check composite saved as '{temple} trace check (auto).png'")
    return metrics
