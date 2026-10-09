#!/usr/bin/env python
"""Register a map city for the on-model photos: its six print files and their
Tapstitch placements, in artifacts/onmodel-maps/prints/ (LOCK.md, "Adding a new
city", steps 2 and 3). 9 Oct 2026.

The print files are the ones map_run.py uploaded (artifacts/maps/<city>/<city>
<garment> white <side> print (map).png). The placement is computed exactly the
way map_run's save_design placed them on Tapstitch: tapstitch_api.placement()
on the template's own print area for that side. composite_maps.py check then
confirms every entry equals the locked placement before anything is built.

The template is the one the live store product prints from (read from
Tapstitch by the product's Shopify id), so a swapped listing (the tee colour
rollout) is handled.

  python scripts/onmodel_maps_register.py whitingham sharon ...
"""
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import generate                                  # noqa: E402
import map_run as M                              # noqa: E402
import tapstitch_api as T                        # noqa: E402
from shopify_client import ShopifyClient         # noqa: E402

MAPS = ROOT / "artifacts" / "onmodel-maps"
PRINTS = MAPS / "prints"
SIDES = {"back": "print_area", "front": "front_print_area"}


def main():
    s, sc = T.session(), ShopifyClient()
    pj = PRINTS / "prints.json"
    entries = json.loads(pj.read_text())
    for city in sys.argv[1:]:
        state = M.load_state(city)
        for g in M.GARMENTS:
            cfg = generate.load_garment_config(g)
            prod = sc.find_product_by_handle(state[g]["shopify_handle"])
            sp = T.store_product_for(s, prod["id"], prod["title"])
            tids = {pi["templateId"] for v in sp["variants"] for pi in v.get("productionItems", [])}
            if len(tids) != 1:
                raise SystemExit(f"{city} {g}: prints from {sorted(tids)}, expected one template")
            tid = tids.pop()
            areas = T.print_areas(T.get_template(s, tid))
            back, front = (Path(x) for x in state[g]["print_files"])
            for side, src in (("back", back), ("front", front)):
                dst = PRINTS / f"{city}_{g}_{side}.png"
                shutil.copyfile(src, dst)
                with Image.open(dst) as im:
                    size = im.size
                geo = T.placement(areas[cfg[SIDES[side]]["position"]], size)
                entries[dst.name] = {"template": tid, "piece": side,
                                     "src": f"local:{src}",
                                     **geo, "angle": 0}
            print(f"{city} {g}: template {tid}, prints registered")
    pj.write_text(json.dumps(entries, indent=1) + "\n")


if __name__ == "__main__":
    main()
