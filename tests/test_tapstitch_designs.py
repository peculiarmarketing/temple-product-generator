"""Offline tests for the Designs-tab summary. No network.

Run: ./.venv.nosync/bin/python tests/test_tapstitch_designs.py

Pinned: the id-to-time decode, calibrated 8 Oct 2026 against the rollout
ledger (commit 1557569335835394048, logged as saved at 17:44:28 UTC on 7 Oct,
decodes to 17:44:27.9), and
the store-status rule the --unpublished filter depends on. The records below
are shaped like the live ones but carry no account data.
"""

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tapstitch_api as T

spec = importlib.util.spec_from_file_location("designs_cli", ROOT / "scripts" / "tapstitch_designs.py")
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)

# --- id_time() ---------------------------------------------------------------
got = T.id_time("1557569335835394048").replace(microsecond=0)
assert got == datetime(2026, 10, 7, 17, 44, 27, tzinfo=timezone.utc), got


# --- store_status() ----------------------------------------------------------
def design(*ids):
    return {"linkedStoresProductList": {
        "productCount": len(ids),
        "stores": [{"products": [{"uniqueId": i, "title": f"T{i}"} for i in ids]}] if ids else []}}


status = {"a": "published", "b": "delisted", "c": "delisted"}
assert D.store_status(design(), status) == "not linked"
assert D.store_status(design("a"), status) == "published"
assert D.store_status(design("b", "a"), status) == "published", "one published link is enough"
assert D.store_status(design("b", "c"), status) == "delisted"
assert D.store_status(design("zz"), status) == "unknown"
assert D.linked(design("a", "b")) == [("a", "Ta"), ("b", "Tb")]

print("test_tapstitch_designs: all assertions passed")
