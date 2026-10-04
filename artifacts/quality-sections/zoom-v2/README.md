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

# Round 2: Temple Square, true logo size, DTG close-up, Kling 3 (3 Oct 2026)

Evan's notes after round 1: open on Temple Square with the Salt Lake Temple
recognizable behind (blur allowed), make sure the logo is the right size, show a
real DTG texture when zoomed in, and use Kling 3 for the film.

## Logo size

The front logo is 6.0 in ink to ink, its top 3 in below the top of the RT0063 front
print area (BRAND.md, decisions.md). Measured on Tapstitch's own flat mockup
(`photo-mockup-spike/flat-originals/ogden/tee_black_front.png`, 35.5 px per inch):
logo width is 0.72 of the collar's outer width, and the logo top sits 3.4 in below
the bottom of the collar band. Round 1's opening shot had the logo at 0.51 of the
collar: about a third too small. The cause: its scale was set from the worn torso
width, read as a flat-lay chest (22 in), but a flat tee's width is half its
circumference and a worn one wraps round the sides. Round 2 sets the scale from
things that do not drape: the collar opening (about 8 in) and ear to ear (about
6 in), both giving about 45 px per inch on the new shot. Composited at 43 px per
inch: logo/collar 0.70 (mockup 0.72), collar-to-logo gap/logo width 0.57 (0.59).
The new shot also uses the real blank (mockup with the logo painted out) as a
garment reference, so the collar is the RT0063's narrow rib instead of a wide one.

## Opening shot

`slc/s1.png` to `s4.png`, contact sheet `slc/contact.jpg`. GPT Image 2.5 sunburst,
three references: a CC BY-SA 4.0 Wikimedia Commons photo of the Salt Lake Temple
("Salt Lake Temple 05.jpg", used only as a reference, not reproduced), the round 1
model shot for the man and the light, and the logo-free Tapstitch blank. Chosen: s2
(job bf025c99), temple centred behind him with all three east spires and Moroni
clear.

## The chain (`chain2/`)

| Frame | What | Square for the next frame (px of 2048) |
|---|---|---|
| J0 | Temple Square, logo at true size | 787, 905, 460 wide |
| J1 | Collar and logo (job 44034477) | 942, 1062, 440 wide |
| J2 | DTG ink on the knit (job c623bab6) | 900, 1560, 488 wide |
| J3 | Yarn (job a3a73c31) | (last) |

## DTG ink (`printlay.py`, `stitch=`)

Water-based white sprayed into cotton: it coats the raised loop tops and thins in the
valleys (coverage from the knit relief), the letter edges are decided loop by loop
(edge threshold moved by the relief), the ink carries the fibre grain, and loose
fibre hairs stay dark over it. The effect scales with magnification (full at about
30 px per stitch): at arm's length DTG reads as solid matte white, so J1 (about 6.5
px per stitch) gets a trace of it and J2 (about 30) the full treatment.

## The film

Kling 3 (pro, 1:1, 5 s, sound off) with start and end frames. J0 to J1 (job
182c6e88) and J1 to J2 (cf86823b) keep the lettering exact. J2 to J3 (b18c63ea)
turned the O of PEOPLE into an R midway, which cannot ship. `render_seg.py` renders
that hand-off from the real frames with the canvas engine's own math (it can only
move pixels, never redraw letters); it is the fallback if Kling's retries also warp.

Kling's two retries of J2 to J3 (jobs 9c0666ce, e29e7788) made the same O-to-R
swap, so the shipped film uses Kling for the first two hand-offs and
`render_seg.py` for the last, joined with 0.25 s dissolves (Kling's last frame
drifts slightly from J2, which showed as a 6.8 frame-difference jump at a hard
cut; with the dissolve the largest steps are inside the knit zoom, not at a join).
14.6 s, `pp-dive-slc-film-1080.mp4` (5.1 MB) and `-720.mp4` (3.1 MB) in Files,
captions at 0, 3.9, 8.6 and 13.0 s.

Deployed to the V3 preview (`templates/index.json` there and here are identical):
dive photos `pp-dive-slc-1-temple-square.jpg` to `pp-dive-slc-4-yarn.jpg`, film as
above. `qa/`: `live4-desk.jpg` (live preview; film row shows the still fallback
because the test Chromium cannot decode H.264), `dive2-desk.jpg` (local sweep, no
seams), `film2-strip.jpg`, `logo-size-vs-tapstitch.jpg`.

# Round 3: the real temple wall, full screen, text over the picture (3 Oct 2026)

Evan chose the photo chain (the dive) over the film. The film section stays in the
theme but is set `"disabled": true` on the homepage.

## What Temple Square looks like now

Checked against the Church's own update, "Temple Square Renovation Update: June
2026" (newsroom.churchofjesuschrist.org), photos dated 23 to 25 June 2026: the
ground right at the temple's east towers is a new plaza of grey granite pavers
over snowmelt tubing (being laid in June), the walls are the rough-dressed granite
with deep arched windows and portals, the restored oak east doors went back in on
23 to 25 June, and trees and gardens sit further out. There are no lawns or flower
beds against the walls, so round 2's opening shot was wrong for the spot. The
renovation is not finished: construction is expected to wrap at the end of 2026,
and the rededication period is 5 April to 1 October 2027 (open house 2027). The
new shot shows the paving finished and without workers, which is how it will look
rather than how it looked in June.

Reference used (as a model reference only; the Church's photo is not stored here):
https://newsroom.churchofjesuschrist.org/download/WP5-Paving-work-in-front-of-east-towers-with-snow-melt-tubing.jpg

## Chain (`chain3/`), photos `web3/`

| Frame | What | Square for the next frame (px of 2048) | Focus (x, y %) |
|---|---|---|---|
| K0 | In front of the east wall (`wall/w3.png`, job 6cd18519) | 788, 860, 500 | 50, 42 |
| K1 | Collar and logo (job 60116621) | 943, 992, 440 | 50, 55 |
| K2 | DTG print (job a7233b0a) | 900, 1556, 488 | 50, 50 |
| K3 | Yarn (job 302ce472) | (last) | 50, 50 |

Logo set the round 2 way: collar outer width 387 px, logo 0.73 of it (283 px, about
47 px per inch), top 0.59 logo widths below the collar band.

## Full screen

`pp-zoom-dive` now fills the pinned band edge to edge with the words over the
picture (bottom left, on a soft shade; progress dots on the right edge). The
photos stay square: the screen sees a screen-shaped window inside each one, placed
by a per-step focus point that glides to the next photo's focus, so the window at
the end of a zoom is exactly the window the next photo starts with, on any screen
shape. Local sweep: no jumps at hand-offs on 1440x900 or 390x844.
`qa/live5-desk.jpg`, `qa/live5-mob.jpg`: the store preview.

## Round 4: real DTG ink on the print and collar frames

Evan asked for the logo in the print close-up to look exactly like a good DTG
print on cotton, rendered by gpt_image_2_5 sunburst, with bright opaque white ink.
The collar frame gets the same treatment so the ink doesn't change colour as K1
hands off to K2.

Style references (copyrighted web photos, used privately as model references
only and not stored here):
- White DTG on black, close up: https://image.rolanddga.com/-/media/roland/images/blog/2021/white-ink-article/closeup.jpg
- A combed cotton fibre macro, found through Yandex image search.

How (`dtg_ink.py`): the model re-renders the current frame with the style
references. Its pixels are kept only where they are ink, inside the real letter
shapes grown by half a knit stitch. Everything else is the old frame unchanged,
so the letters can't drift and every hand-off stays exact.

| Frame | Generation | Kept | Ink vs true letters (IoU) | Hand-off check |
|---|---|---|---|---|
| K2 print | 7f26f740 (of 3) | `chain3/K2dtg.png`, `web3/pp-dive-wall-3b-dtg-print.jpg` | 0.921 | K2 to K3 square sits below the logo, untouched |
| K1 collar | 4fd784cb (of 2) | `chain3/K1dtg.png`, `web3/pp-dive-wall-2b-collar.jpg` | (strokes 3 to 5 px, checked by eye) | `align.py` K1 to K2: shift 0, 0, score 0.992 |

The ink brightness step at each hand-off is 10 to 16 levels (the old K1 to K2 step
was 15). `qa/live6-desk.jpg`, `qa/live6-mob.jpg`, `qa/live6-dtg-closeup.jpg`: the
store preview after the swap.
