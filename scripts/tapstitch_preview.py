"""Render the Tapstitch designs onto a garment-coloured background, as one page.

This is the gate for the new back design. The logo moved to the front, so the
back is temple plus location text and every temple's proportions changed. Evan
judges all of them in one pass here before anything is uploaded.

Previews render at low resolution into artifacts/, never into the Temples
folders: the print area is still a placeholder until a blank is picked, so the
real full-size print files would only have to be rebuilt and re-synced. Build
those with scripts/tapstitch_build.py once the numbers are real.

Usage:
  python scripts/tapstitch_preview.py                     # every temple, tee canvas
  python scripts/tapstitch_preview.py --temple "Logan"
  python scripts/tapstitch_preview.py --spacing-study     # bottom-margin comparison
"""

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

import flatten
import generate
import layout
from layout import PROJECT_ROOT

OUT = PROJECT_ROOT / "artifacts" / "tapstitch-previews"
PREVIEW_DPI = 45


def render(temple, manifest, garment_cfg, color, spacing_overrides=None):
    """One preview: the design flattened, then laid on the garment colour."""
    cfg = dict(garment_cfg)
    if spacing_overrides:
        merged = dict(cfg.get("spacing_overrides") or {})
        for k, v in spacing_overrides.items():
            merged[k] = {**merged.get(k, {}), **v} if isinstance(v, dict) else v
        cfg["spacing_overrides"] = merged

    r = flatten.build_back(temple, manifest, cfg, color)
    area = cfg["print_area"]
    scale = PREVIEW_DPI / area["dpi"]
    w, h = round(area["width_px"] * scale), round(area["height_px"] * scale)
    design = r["image"].resize((w, h), Image.LANCZOS)

    bg = cfg.get("preview_color_hex", "#3b3b3b").lstrip("#")
    canvas = Image.new("RGB", (w, h), tuple(int(bg[i:i + 2], 16) for i in (0, 2, 4)))
    canvas.paste(design, (0, 0), design)

    g = r["geometry"]
    h_in = area["height_px"] / area["dpi"]
    facts = {
        "ink_width_in": round(g["temple"]["ink_width_in"], 2),
        "ink_bottom_in": round(g["temple"]["ink_bottom_in"], 2),
        "text_bottom_in": round(g["location_text"]["bottom_in"], 2),
        "empty_below_in": round(h_in - g["location_text"]["bottom_in"], 2),
        "fill_pct": round(100 * g["location_text"]["bottom_in"] / h_in),
        "problems": flatten.validate(r["image"], cfg, r["sources"], color, pre_matte=r["raw"]),
    }
    return canvas, facts


def spacing_study(temple, garment_cfg, color):
    """The same temple at several bottom margins.

    RETIRED 14 Sep 2026 and kept only as a tool. The question it existed to
    answer is closed: there is no bottom margin any more. The stack is centred
    in the print file and the margins are 0.0, so nothing caps a tall temple
    below the 12.0in width rule. main() no longer calls this.
    """
    manifest = generate.load_manifest(temple)
    out = []
    for margin in (2.5, 2.0, 1.5, 1.0):
        img, facts = render(temple, manifest, garment_cfg, color,
                            spacing_overrides={"bottom_margin_in": margin})
        name = f"study_{temple.lower().replace(' ', '-')}_margin{margin}.png"
        img.save(OUT / name)
        out.append((margin, name, facts))
    return out


def anchor_study(garment_cfg, color, temples=("Monticello", "Salt Lake")):
    """A wide temple and a tall one, top-anchored and centred.

    Why: top-anchoring leaves a wide short temple floating at the top of the
    print area. Measured across 40 temples, the empty canvas below the text
    runs from 2.5in to 8.6in depending purely on the building's proportions.
    The logo used to sit down there. Now nothing does.
    """
    out = []
    for temple in temples:
        try:
            manifest = generate.load_manifest(temple)
        except SystemExit:
            continue
        for anchor in ("top", "center"):
            img, facts = render(temple, manifest, garment_cfg, color,
                                spacing_overrides={"vertical_anchor": anchor})
            name = f"anchor_{temple.lower().replace(' ', '-')}_{anchor}.png"
            img.save(OUT / name)
            out.append((temple, anchor, name, facts))
    return out


def page(rows, studies, anchors, garment_cfg, color):
    """The review sheet.

    Set in Alata, the same face the location line is printed in on the garments
    themselves, so the page reads in the product's own voice. Measurements sit in
    a mono face with tabular figures because they are meant to be compared down
    a column, not read as prose.
    """
    area = garment_cfg["print_area"]
    w_in, h_in = area["width_px"] / area["dpi"], area["height_px"] / area["dpi"]
    sp = layout.load_spacing(garment_cfg)
    target = sp["temple_target_ink_width_in"]
    empties = sorted(r[2]["empty_below_in"] for r in rows)

    def card(img_name, title, sub, problems=(), gauge=None):
        bar = ""
        if gauge is not None:
            bar = (f"<div class=gauge><span style='width:{gauge}%'></span></div>"
                   f"<div class=gauge-label>{gauge}% of the print area used</div>")
        bad = "".join(f"<p class=flag>{html.escape(p)}</p>" for p in problems)
        return (f"<figure class=proof>"
                f"<img src='{html.escape(img_name)}' alt='{html.escape(title)}' loading=lazy>"
                f"<figcaption><span class=proof-name>{html.escape(title)}</span>"
                f"<span class=proof-meta>{sub}</span>{bar}{bad}</figcaption></figure>")

    head = f"""<!doctype html><html lang=en><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>Temple Back Proof Sheet</title>
<link rel=preconnect href="https://fonts.googleapis.com">
<link rel=preconnect href="https://fonts.gstatic.com" crossorigin>
<link rel=stylesheet href="https://fonts.googleapis.com/css2?family=Alata&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root {{
  --paper:#FAF9F6; --surface:#FFFFFF; --sunk:#F2F2EC;
  --ink:#1B1E1A; --ink-2:#59635A; --ink-3:#8C948B;
  --rule:#E3E3DB; --rule-firm:#CFCFC4;
  --accent:#4A5340; --accent-ink:#3C442F; --accent-wash:#EDF0E6;
  --flag:#9A3B24;
  --shadow:0 1px 2px rgba(27,30,26,.06), 0 8px 24px -16px rgba(27,30,26,.28);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme=light]) {{
    --paper:#14170F; --surface:#1B1F17; --sunk:#11140D;
    --ink:#EDEFE5; --ink-2:#A7B09D; --ink-3:#7B8474;
    --rule:#2A3024; --rule-firm:#3A4232;
    --accent:#A8BC8A; --accent-ink:#C3D3A9; --accent-wash:#232A1C;
    --flag:#E4886B;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.7);
  }}
}}
:root[data-theme=dark] {{
  --paper:#14170F; --surface:#1B1F17; --sunk:#11140D;
  --ink:#EDEFE5; --ink-2:#A7B09D; --ink-3:#7B8474;
  --rule:#2A3024; --rule-firm:#3A4232;
  --accent:#A8BC8A; --accent-ink:#C3D3A9; --accent-wash:#232A1C;
  --flag:#E4886B;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.7);
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink);
  font:16px/1.6 "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
  -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1180px; margin:0 auto; padding:0 20px; padding-block:48px 72px; }}
h1 {{ font:400 clamp(30px,5vw,44px)/1.1 Alata, ui-sans-serif, system-ui, sans-serif;
  margin:0 0 10px; letter-spacing:-.01em; text-wrap:balance; }}
h2 {{ font:400 24px/1.25 Alata, ui-sans-serif, system-ui, sans-serif;
  margin:0 0 6px; text-wrap:balance; }}
p {{ margin:0 0 12px; max-width:66ch; color:var(--ink-2); }}
b {{ color:var(--ink); font-weight:600; }}
.eyebrow {{ font:500 12px/1 "IBM Plex Mono", ui-monospace, monospace;
  letter-spacing:.14em; text-transform:uppercase; color:var(--accent-ink); margin:0 0 14px; }}
.specline {{ display:flex; flex-wrap:wrap; gap:8px 22px; margin:22px 0 0;
  padding-top:18px; border-top:1px solid var(--rule);
  font:400 13px/1.4 "IBM Plex Mono", ui-monospace, monospace; color:var(--ink-3); }}
.specline b {{ font-weight:500; color:var(--ink-2); }}
section {{ margin-top:56px; }}
.panel {{ background:var(--surface); border:1px solid var(--rule);
  border-left:3px solid var(--accent); border-radius:3px;
  padding:24px; box-shadow:var(--shadow); }}
.panel p:last-of-type {{ margin-bottom:0; }}
.strip {{ display:grid; gap:20px; margin-top:24px;
  grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); }}
.grid {{ display:grid; gap:28px 20px; margin-top:24px;
  grid-template-columns:repeat(auto-fill, minmax(176px, 1fr)); }}
.proof {{ margin:0; display:flex; flex-direction:column; gap:10px; }}
.proof img {{ width:100%; max-width:100%; display:block; border-radius:2px;
  background:var(--sunk); border:1px solid var(--rule); }}
.proof figcaption {{ display:flex; flex-direction:column; gap:3px; }}
.proof-name {{ font:400 15px/1.25 Alata, ui-sans-serif, system-ui, sans-serif; color:var(--ink); }}
.proof-meta {{ font:400 12px/1.5 "IBM Plex Mono", ui-monospace, monospace;
  color:var(--ink-3); font-variant-numeric:tabular-nums; }}
.gauge {{ height:3px; background:var(--rule); border-radius:2px; overflow:hidden; margin-top:4px; }}
.gauge span {{ display:block; height:100%; background:var(--accent); }}
.gauge-label {{ font:400 11px/1.4 "IBM Plex Mono", ui-monospace, monospace; color:var(--ink-3);
  font-variant-numeric:tabular-nums; }}
.flag {{ font:400 12px/1.45 "IBM Plex Sans", sans-serif; color:var(--flag); margin:2px 0 0; }}
.pairhead {{ font:500 12px/1 "IBM Plex Mono", ui-monospace, monospace;
  letter-spacing:.12em; text-transform:uppercase; color:var(--ink-3);
  margin:26px 0 -6px; }}
@media (max-width:420px) {{ .grid {{ grid-template-columns:repeat(2, 1fr); gap:20px 14px; }} }}
</style>
<body><main class=wrap>

<p class=eyebrow>Proof sheet &middot; back print</p>
<h1>Temple back designs, without the logo</h1>
<p>The logo has moved to the front print, so the back is the temple and the city
line only. The spacing is settled: centred in the print area, city line the same
height on every product. Below is the reasoning, then all {len(rows)} temples.</p>
<p class=specline>
  <span><b>print area</b> {w_in:.2f} &times; {h_in:.2f} in</span>
  <span><b>ink</b> {html.escape(color)}</span>
  <span><b>city line</b> {sp['location_text_height_in']} in of ink</span>
  <span><b>placement</b> centred, no margins</span>
  <span><b>temple width</b> {target} in max, ink to ink</span>
  <span><b>gap</b> {sp['gap_ink_to_text_in']} in under the temple's lowest ink</span>
  <span><b>backgrounds</b> approximate, not the real blank</span>
</p>
"""

    parts = [head]

    parts.append(f"""<section>
<p class=eyebrow>Settled 14 September 2026</p>
<div class=panel>
<h2>Centred, and the city line is always {sp['location_text_height_in']} in tall</h2>
<p>Both calls came out of removing the logo from the back. The comparisons below
are kept as the evidence behind them, not as open questions.</p>
<p><b>Centred, not anchored to the top.</b> Top-anchoring read completely
differently depending on the building: a wide, short temple reached its target
width early and left the rest of the canvas bare. Monticello was the extreme,
sitting {anchors[0][3]['empty_below_in'] if anchors else '?'} in above empty space.
Centred, every temple sits at the same height on the garment.</p>
<div class=strip>""")
    for temple, anchor, name, facts in anchors:
        label = ("top anchored, the old way" if anchor == "top" else "centred, chosen")
        parts.append(card(name, f"{temple}, {label}", f"{facts['empty_below_in']} in below"))
    parts.append(f"""</div>
<p style="margin-top:22px"><b>The city line is {sp['location_text_height_in']} in on
every temple</b>, measured on the ink rather than on the box around it. The type
was never what varied; the art beside it was. A fixed height means every product
reads at the same size. At this height the longest line in the catalog,
SARATOGA SPRINGS, UTAH, is 9.52 in wide, comfortably inside the narrowest back
print area of the three garments ({w_in:.2f} in on this one).</p>
<p><b>Nothing is measured from an edge.</b> The temple and the city line are
centred in the print file, horizontally and vertically, with the temple spanning
no more than {target} in at its widest ink and the city line sitting
{sp['gap_ink_to_text_in']} in below the temple's lowest ink. The old top and
bottom margins came off the old layout, where the logo sat at the bottom of
the back; centring made them meaningless and they were the only thing keeping
tall temples under full width.</p>
</div></section>""")

    parts.append(f"""<section>
<p class=eyebrow>As built today</p>
<h2>Every temple ({len(rows)})</h2>
<p>Centred, city line {sp['location_text_height_in']} in. The bar under each shows
how much of the print area's height the design uses. These are built on the real
Tapstitch print area for this garment, {w_in:.2f} &times; {h_in:.2f} in, read off
the editor on 14 September 2026.</p>
<div class=grid>""")
    for temple, name, facts in rows:
        parts.append(card(name, temple,
                          f"{facts['ink_width_in']} in wide &middot; "
                          f"{facts['empty_below_in']} in below",
                          problems=facts["problems"], gauge=facts["fill_pct"]))
    parts.append("</div></section></main></body></html>")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--temple")
    ap.add_argument("--garment", default="tee",
                    help="which canvas to preview on. All three share a placeholder "
                         "print area until blanks are picked, so one is representative.")
    ap.add_argument("--color", default="white", help="ink colour")
    ap.add_argument("--study-temple", default="Salt Lake")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    cfg = generate.load_garment_config(a.garment)
    temples = [a.temple] if a.temple else [f.name for f in flatten.temple_folders()]

    rows = []
    for n, temple in enumerate(temples, 1):
        print(f"[{n}/{len(temples)}] {temple}", file=sys.stderr, flush=True)
        try:
            generate.detect_art_files(flatten.TEMPLES_DIR / temple)
            manifest = generate.load_manifest(temple)
        except SystemExit:
            continue
        try:
            img, facts = render(temple, manifest, cfg, a.color)
        except Exception as e:
            print(f"    skipped: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        name = f"{temple.lower().replace(' ', '-').replace('*', '')}.png"
        img_path = OUT / name
        if not flatten._inside(img_path, OUT):
            raise SystemExit(f"Refusing to write outside {OUT}: temple {temple!r}")
        img.save(img_path)
        rows.append((temple, name, facts))

    studies = []
    print("anchor study", file=sys.stderr, flush=True)
    anchors = anchor_study(cfg, a.color)

    name = "index.html" if not a.temple else \
        f"index-{a.temple.lower().replace(' ', '-').replace('*', '')}.html"
    out_path = OUT / name
    if not flatten._inside(out_path, OUT):
        raise SystemExit(f"Refusing to write outside {OUT}: --temple {a.temple!r}")
    out_path.write_text(page(rows, studies, anchors, cfg, a.color))
    print(f"\n{len(rows)} previews -> {out_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
