# What the live store already knows about Tapstitch

**Date:** 14 Sep 2026. Read from the Shopify Admin API during the migration build,
not from Tapstitch. Everything here is measured, not assumed.

## Tapstitch already syncs to Shopify, and already has

Four Tapstitch products exist on the store right now, all **DRAFT**, created
28 Aug 2026 (the SKU prefix `260828` is the date):

| Title | Handle | Price | Colors |
|---|---|---|---|
| Tapstitch Hoodie Test | `tapstitch-hoodie-test` | $74.99 | Blackish Green, Apricot, Black, Navy Blue, Coffee, Dark Gray |
| Tapstitch Hoodie Test (Manti) | `tapstitch-hoodie-test-manti` | $74.99 | same |
| Tapstitch Crewneck Test | `tapstitch-crewneck-test` | $64.99 | White, Apricot, Black, Navy Blue |
| Tapstitch Crewneck Test (Lindon) | `tapstitch-crewneck-test-lindon` | $64.99 | same |

Sizes are S, M, L, XL, 2XL on all four. There is **no tee test product**.

This answers a question the migration plan left open: the Tapstitch to Shopify
product sync works, and Evan has already driven it by hand. The browser
automation only has to reach "publish"; Shopify gets the product from there.

## Load-bearing differences from the old catalogue's products

1. **Vendor is `ODMPOD`, not the old supplier's name.** Anything that identifies a product by
   vendor has to learn the new value.

2. **`productType` is EMPTY on every Tapstitch product.** This is the one that
   silently breaks things. `scripts/shopify_fixups.py` is keyed entirely on
   `productType`: `first_colors_by_type()`, `wants_color_order()` and
   `colorway_renames_by_type()` all compare against it, so on a Tapstitch
   product every colour fixup does nothing at all and reports success. **The runner must set `productType`
   immediately after publish**, before any fixup pass runs.
   `scripts/art_images.py` is unaffected: it matches on `" Temple"` in the title.

3. **Option order is Color then Size** (`'Blackish Green / S'`). The old
   catalogue's was Size then Color (`'S / Blue Jean'`). Anything parsing a variant title
   positionally has to cope with both while the catalogues overlap.

4. **No tags at all.** The old supplier stamped every listing with junk tags ("4th of
   July", "US Elections Season", "TikTok", "Streetwear"), which BRAND.md section
   19 lists as an open cleanup item. Tapstitch products arrive clean, so the
   migration closes that item by itself.

## Catalogue state at the moment of the snapshot

171 products total: 162 retiring temple listings (all ACTIVE), and 9
left alone.

**Two stray duplicate listings, both created 27 Aug 2026.** Each is a second copy
of a Salt Lake parent listing, sitting live at its own web address:

| Real parent | Created | Stray | Created |
|---|---|---|---|
| `salt-lake-city-temple-tee` | 8 Aug | `essential-temple-tee` | 27 Aug |
| (a second Salt Lake tee line, since dropped) | 18 Aug | its stray twin | 27 Aug |

The real parents are the ones the Easify dropdown links at, and the 8 Aug tee is
the one carrying the art close-up card. The same-day creation of both strays
suggests one accident, probably a publish that minted a fresh handle from the
title rather than reusing the existing one. The pull-down snapshot keeps the
older listing in each pair and reports the stray; it never deletes one on its own.

Of the 9 left alone:

- **Temple Art File**: the $4.95 SVG download. Not a garment; stays live
  and sellable while the garment catalogue is dark.
- **Three Nauvoo "Limited Edition" products** (tee, hoodie, crew): Evan's
  hand-built one-offs. Excluded by the pipeline's long-standing one-off rule, so
  the pull-down leaves them alone. Deleted at Evan's instruction on 14 Sep 2026,
  because they could not be fulfilled once the old supplier was retired.
- **Cornerstone Sweatpants**: an old-supplier product outside the temple
  catalogue, ACTIVE, $44.99. Deleted the same day for the same reason.
- The four Tapstitch test products above.

## What this does not tell us

The print area dimensions. Shopify carries the finished product, not the design
canvas, so the true Tapstitch print area still has to come from the editor when
Evan picks blanks. The garment configs carry a clearly marked placeholder until
then.
