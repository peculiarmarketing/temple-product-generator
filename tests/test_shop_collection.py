"""Offline tests for scripts/shop_collection.py with a stand-in Shopify client. No network.

Run: ./.venv.nosync/bin/python tests/test_shop_collection.py
"""

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.shop_collection as sc  # noqa: E402
from shopify_client import ShopifyError  # noqa: E402


class FakeShopify:
    """Answers the handful of queries the script makes. The live token has no
    read_publications scope (verified 23 Sep 2026), so by default that query is refused."""

    def __init__(self, exists=True, can_publish=False):
        self.exists, self.can_publish, self.calls = exists, can_publish, []

    def gql(self, query, variables=None):
        self.calls.append(query)
        if "collectionByHandle" in query:
            return {"collectionByHandle": {"id": "gid://shopify/Collection/1", "title": "Shop",
                                           "products": {"nodes": [{"title": "Tee"}]}} if self.exists else None}
        if "productByHandle" in query:
            return {"productByHandle": {"id": "gid://shopify/Product/9", "tags": ["listing:standalone"]}}
        if "collectionCreate" in query:
            self.exists = True
            return {"collectionCreate": {"collection": {"id": "gid://shopify/Collection/1"}, "userErrors": []}}
        if "publications" in query:
            if not self.can_publish:
                raise ShopifyError("Access denied for publications field. Required access: read_publications")
            return {"publications": {"nodes": [{"id": "gid://shopify/Publication/1", "name": "Online Store"}]}}
        if "publishablePublish" in query:
            return {"publishablePublish": {"userErrors": []}}
        raise AssertionError(f"unexpected query: {query[:60]}")


def run(fake, argv):
    real = sc.ShopifyClient
    sc.ShopifyClient = lambda: fake
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            rc = sc.main(argv)
    finally:
        sc.ShopifyClient = real
    return rc, out.getvalue()


# No publishing scope, collection not there yet: create it, then say plainly it is NOT live.
rc, out = run(FakeShopify(exists=False), ["--apply"])
assert rc == 1, out
assert "NOT published" in out and "Online Store" in out, out
assert "Shop now holds" not in out, "reported success for an unpublished collection"

# Re-run after that: the collection exists, and publishing must be tried again, not skipped.
fake = FakeShopify(exists=True)
rc, out = run(fake, ["--apply"])
assert rc == 1 and "NOT published" in out, out
assert any("publications" in q for q in fake.calls), "an existing collection was never published"

# With the scope, both paths publish and report what the collection holds.
for exists in (False, True):
    rc, out = run(FakeShopify(exists=exists, can_publish=True), ["--apply"])
    assert rc == 0 and "Shop now holds" in out, out

# The dry run writes nothing.
fake = FakeShopify(exists=False)
rc, out = run(fake, [])
assert rc == 0 and "DRY RUN" in out
assert not any(("collectionCreate" in q or "publishablePublish" in q) for q in fake.calls)

print("ok")
