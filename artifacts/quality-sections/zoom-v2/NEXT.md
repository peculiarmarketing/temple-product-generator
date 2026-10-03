# Scroll zoom v2: where we stopped (3 Oct 2026)

Paused by Evan after reviewing the dive and film on the preview theme
"Claude Code V3 zoom preview" (`gid://shopify/OnlineStoreTheme/194273870196`,
unpublished; Claude Code V2 is live and untouched). Nothing below is started.

## Evan's notes to act on

1. **Video model: use Kling 3** for the film instead of MiniMax H3. Same method:
   start and end frames from the image chain, one segment per hand-off, then join and
   encode for scrubbing (see README.md, "The film").
2. **Opening shot background: Temple Square in front of the Salt Lake Temple.** It can
   stay blurry (shallow depth of field) but must be recognizable. Regenerate I0, keep
   the black tee, the pose and the plain chest for the logo composite. Every later
   frame is cut from I0, so the whole chain (I1 to I3) and the film get rebuilt after.
3. **Logo size must be right.** Currently 6 in wide (from the anatomy section's "Our
   logo, 6 inches wide"), at about 37.5 px per inch in I0. Confirm the real front
   print width against the Tapstitch RT0063 front print settings before compositing.
4. **Close-up must read as DTG print.** At the print frame (I2) the ink should look like
   real direct-to-garment ink on cotton: thin layer soaked into the fibres, slightly
   matte, knit texture and stray fibres showing through, edges following the yarn.
   The current `printlay.py` texture breakup (0.35) reads too flat and clean. Options:
   a stronger fibre-driven alpha in `printlay.py`, or let the image model render the
   ink surface from a composite reference and re-check letter shapes against the PNG.

## State

- Branch `claude/homepage-quality-sections`, last commit 90e0f90 (pushed).
- Sections built and deployed to the V3 preview: `pp-zoom-dive` (photo chain) and
  `pp-zoom-film` (video). Evan has not picked one yet.
- Images in Content > Files: `pp-dive-1-tee.jpg` to `pp-dive-4-knit.jpg`; films
  `pp-dive-film-1080.mp4`, `pp-dive-film-720.mp4`. These will be replaced by the new
  chain (upload under new names, then update the preview template).
- Copy (both humanizer passes done) stays unless Evan changes it.
- Still open from earlier: shipping policy edit is manual (Evan).
