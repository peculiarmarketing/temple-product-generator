# Map on-model placement: locked

Locked 9 Oct 2026. Evan approved every map tee, sweatshirt and hoodie, front and back, in every colour, and asked for the positions and sizes to be anchored so every future map product gets the same placement.

## What is locked

`placement_lock.json` is the single source of placement. `composite_maps.py build` reads only this file.

- **Per base photo (34: 3 garments, front and back, every colour):**
  - the exact quad where the print canvas lands on that photo (2880px coordinates);
  - the map or logo ink box;
  - the hood edge (hoodie backs);
  - the fold scale;
  - a hash of the photo's pixels. If a base photo changes, build and check both refuse to run.
- **Per garment and view (6):**
  - the print canvas size and ink box the quads were measured for;
  - Tapstitch's placement of that print on the template (scale, top, left, width, height, angle);
  - the rule values that produced the lock.
- **Fold:** displace 0.75, strength 55, band 4 to 20, shade 1.8, texture 0.35, opacity 0.93.
- **Hood:** covers the top 3% of the map, and the print is held flat for 80px below the hood edge.

## The approved rules, in words

These rules produced the lock. They are recorded in `docs/decisions.md`, 9 Oct 2026.

- **True size.** The print is scaled by the garment's collar-to-hem length, the same as on Tapstitch's flat lay.
- **Backs.** The map is 90% of true size, with its top edge held. It is centred on each photo's own measured centre line; on the hoodie that is the middle of the hood. On the hoodie, the hood lies over the top 3% of the map.
- **Fronts.**
  - Tee and sweatshirt: the logo is 95% of true size and sits 2.5 in higher than Tapstitch's flat placement.
  - Hoodie: the logo is 85.5% (90% × 95%) and sits 1.0 in higher.
- **Sweatshirt fit.** The sweatshirt uses the loose, long fit from Evan's Tapstitch reference photo (`refs/crew_fit_tapstitch.jpg`).

## Adding a new city

0. **Fresh checkout.** Run `python composite_maps.py fetch`. The base photos (324 MB) and prints are gitignored. It downloads them from their Shopify Files backup (`backup.json`, permanent public links, no login) and falls back to Higgsfield and Tapstitch. It checks every photo pixel for pixel against the lock.
1. **Create the products.** Make the city's three map products on Tapstitch from the same templates. Tapstitch must place the print the same way: same scale, top, left, width and height as Nauvoo and Salt Lake City.
2. **Add the print files.** Put the six print files in `prints/` as `<city>_<tee|crew|hoodie>_<front|back>.png`, and add their Tapstitch placement entries to `prints/prints.json`.
3. **Check the fit.** Run `python composite_maps.py check <city>`. It confirms that all six prints exist, that each canvas is the locked size, that each Tapstitch placement matches, and that no base photo has changed. If anything differs, it stops. A different placement would print somewhere else on the real garment, so the on-model photos would be wrong.
4. **Build.** Run `python composite_maps.py build <city>` (34 finals), then `python review_sheets.py`.
5. **Publish.** Show Evan the sheets. Then run `python scripts/onmodel_maps_apply.py --place <city>` to see the plan, `--apply` to publish, and `--verify` to check. Product handles follow the pattern of the first two cities.

The map art inside the canvas can differ from city to city. Because the canvas is laid on the locked quad, each map lands exactly where Tapstitch prints it.

## Changing the lock

Only change the lock with Evan's approval. Edit the rules in `composite_maps.py`, run `detect` if the photos changed, then run `lock --force`, rebuild, and review.

## Proof the lock matches what is live

- **Ink boxes.** The locked ink box of every one of the 68 finals matches the approved build log. Two hoodie-back widths differ by 1px out of 1353 (rounding).
- **Rebuilt finals.** Three finals were rebuilt from the lock: a royal blue hoodie back, a heather gray sweatshirt back and a cream tee front. They differ from the approved files only by JPEG noise, with a mean difference of 0.05 levels out of 255 or less.
