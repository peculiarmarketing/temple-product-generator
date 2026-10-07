"""Pilot: re-save the Monticello tee's design with the lifted back print, then watch.

A RECORD of the 7 Oct 2026 pilot, kept for what it shows. Evan ran `save` by hand;
scripts/relift_rollout.py is the tool for any further product. The raw store
product listings it wrote were replaced by the redacted commit-evidence.json.

Usage: pilot.py snapshot TAG   (read-only: template, Tapstitch store product, Shopify product)
       pilot.py save           (the one write: save_design on the existing template)
"""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"scripts"))
import tapstitch_api as T, tapstitch_run as R, generate
from shopify_client import ShopifyClient
OUT = ROOT/"artifacts/tapstitch/pilot-monticello-tee"
TPL = "1550097164208914432"; SP_ID = "1550097204981673984"
HANDLE = "essential-heavyweight-temple-tee-monticello"

def shopify_state():
    c = ShopifyClient()
    q = '''query($h:String!){productByHandle(handle:$h){id title status updatedAt
      options{name values}
      media(first:30){nodes{id alt ... on MediaImage{image{url}}}}
      variants(first:60){nodes{title image{url}}}}}'''
    return c.gql(q, {"h": HANDLE})["productByHandle"]

def snapshot(tag):
    s = T.session()
    tpl = T.get_template(s, TPL)
    (OUT/f"template_{tag}.json").write_text(json.dumps(tpl, indent=1))
    sp = T.store_products(s, "Monticello")
    (OUT/f"storeproducts_{tag}.json").write_text(json.dumps(sp, indent=1))
    sh = shopify_state()
    (OUT/f"shopify_{tag}.json").write_text(json.dumps(sh, indent=1))
    cfg = json.loads(tpl.get("config") or "[]") if isinstance(tpl.get("config"), str) else tpl.get("config")
    srcs = [o.get("src") for p in (cfg or []) for o in p.get("objects", [])]
    print("template srcs:", srcs)
    print("shopify updatedAt:", sh["updatedAt"], "media:", len(sh["media"]["nodes"]),
          "alts blank:", sum(1 for m in sh["media"]["nodes"] if not m["alt"]))

def save():
    s = T.session()
    cfg = generate.load_garment_config("tee")
    pngs = R.print_files("Monticello", "tee", R.ink_color(cfg))
    print("uploading", [p.name for p in pngs])
    R.save_design(s, TPL, "tee", cfg, pngs, print)

if __name__ == "__main__":
    {"snapshot": lambda: snapshot(sys.argv[2]), "save": save}[sys.argv[1]]()
