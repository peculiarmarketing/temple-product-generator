# Scroll zoom v2: the dive (3 Oct 2026)

Draft 1 redone after Evan's notes: smoother, original photos that blend into each
other, logo-first opening shot, copy about fabric, print and construction.

## The image chain

Each frame is a close-up of a square inside the frame before it, so the zoom can hand
off with nothing to see at the cut.

| Frame | What | Made from | Square for the next frame (px of 2048) |
|---|---|---|---|
| I0 | Black tee, outdoors, logo on chest | `lifestyle/option2.png` + real logo (`printlay.py`) | 725, 585, 500 wide |
| I1 | Collar and logo | Higgsfield GPT Image 2.5 sunburst, high, 2k, from `R0_plain_up.jpg` (job c70308e8) + logo | 934, 1237, 400 wide |
| I2 | Ink on the knit | same model from `R1_plain_up.jpg` (job 5b3d538b) + logo with knit breakup | 900, 1520, 512 wide |
| I3 | Yarn macro | same model from `R2_up.jpg` (job a7e52c33) | (last) |

The logo is never drawn by the image model. `printlay.py` lays the uploaded logo PNG
at its true printed size (6 in wide, about 37.5 px per inch in I0) on the plain
generated fabric, bent slightly along the folds. References are cut from the plain
frames so each model pass only has fabric to re-render. `align.py` measures how far
each generated frame drifted from its reference (scale and shift by edge
correlation); all three came back at scale 1.0, shift 0, scores 0.997, 0.90, 0.93,
so the squares above are used as cut.

`web/` holds the four JPGs uploaded to Content > Files (pp-dive-1-tee.jpg and on).
The PNGs stay on disk only (gitignored).

## The film

MiniMax H3 (2K, 1:1, 5 s) with start and end frames: I0 to I1 (job 4d701007), I1 to
I2 (251b6923), I2 to I3 (ebf01a0c). Joined with the duplicate join frames dropped,
15.4 s at 24 fps, then encoded for scrubbing (H.264, keyframe every 6 frames, no
B-frames, faststart): `pp-dive-film-1080.mp4` (6.6 MB, CRF 28) and
`pp-dive-film-720.mp4` (4.3 MB). Uploaded to Content > Files as plain files so
Shopify serves them byte for byte (it re-encodes videos uploaded as videos). The CDN
answers range requests (206), which seeking needs. MP4s are gitignored.

## Copy

Both humanizer passes. Facts from BRAND.md section 7 (samples judged side by side,
light and stiff blanks passed on) and the verified Tapstitch specs (RT0063, 100%
cotton, 260 gsm; DTG print; 300 DPI print files; ribbed collar).

`qa/`: live preview screenshots (dive top row, film bottom row; the film shows its
poster because the test Chromium has no H.264 decoder) and frame strips of the film.
