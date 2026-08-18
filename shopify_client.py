"""Minimal Shopify Admin API client for post-publish product media work.

Needs in .env:
  SHOPIFY_STORE_DOMAIN=xxxx.myshopify.com
  SHOPIFY_ADMIN_TOKEN=shpat_...   (custom app, read_products + write_products)
"""

import mimetypes
from pathlib import Path

import requests
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent
API_VERSION = "2025-07"


class ShopifyError(Exception):
    pass


class ShopifyClient:
    def __init__(self):
        env = dotenv_values(PROJECT_ROOT / ".env")
        domain, token = env.get("SHOPIFY_STORE_DOMAIN"), env.get("SHOPIFY_ADMIN_TOKEN")
        if not domain or not token:
            raise SystemExit("Add SHOPIFY_STORE_DOMAIN and SHOPIFY_ADMIN_TOKEN to .env first.")
        self.url = f"https://{domain}/admin/api/{API_VERSION}/graphql.json"
        self.headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

    def gql(self, query, variables=None):
        r = requests.post(self.url, headers=self.headers,
                          json={"query": query, "variables": variables or {}}, timeout=60)
        data = r.json()
        if not r.ok or data.get("errors"):
            raise ShopifyError(str(data.get("errors") or r.text)[:800])
        return data["data"]

    def all_products_with_media(self):
        """One paginated pass over the catalog: [{id, title, alts}, ...].
        A list, not a dict, so duplicate titles stay visible: two live products
        can share a title, and keying by it drops one of them entirely, which
        no caller can detect or recover from.
        Scales as O(catalog/25) queries instead of one query per product."""
        out, cursor = [], None
        while True:
            data = self.gql("""
              query($after: String) { products(first: 25, after: $after) {
                pageInfo { hasNextPage endCursor }
                nodes { id title media(first: 20) { nodes { alt } } } } }""",
                {"after": cursor})
            block = data["products"]
            for p in block["nodes"]:
                out.append({"id": p["id"], "title": p["title"].strip(),
                            "alts": [m.get("alt") or "" for m in p["media"]["nodes"]]})
            if not block["pageInfo"]["hasNextPage"]:
                return out
            cursor = block["pageInfo"]["endCursor"]

    def all_products_summary(self):
        """One paginated pass over the catalog: [{title, handle, status,
        publishedAt}, ...]. A list, not a dict, so duplicate titles stay visible."""
        out, cursor = [], None
        while True:
            data = self.gql("""
              query($after: String) { products(first: 100, after: $after) {
                pageInfo { hasNextPage endCursor }
                nodes { title handle status publishedAt } } }""",
                {"after": cursor})
            block = data["products"]
            out.extend(block["nodes"])
            if not block["pageInfo"]["hasNextPage"]:
                return out
            cursor = block["pageInfo"]["endCursor"]

    def find_product_by_title(self, title):
        data = self.gql("""
          query($q: String!) { products(first: 5, query: $q) {
            nodes { id title media(first: 20) { nodes { id alt ... on MediaImage { image { url } } } } } } }""",
            {"q": f'title:"{title}"'})
        exact = [p for p in data["products"]["nodes"] if p["title"].strip() == title]
        return exact[0] if len(exact) == 1 else None

    def upload_media_image(self, product_gid, png_path, alt):
        """Staged upload then attach to the product. Returns the new media id."""
        png_path = Path(png_path)
        mime = mimetypes.guess_type(png_path.name)[0] or "image/png"
        staged = self.gql("""
          mutation($input: [StagedUploadInput!]!) { stagedUploadsCreate(input: $input) {
            stagedTargets { url resourceUrl parameters { name value } }
            userErrors { message } } }""",
            {"input": [{"resource": "IMAGE", "filename": png_path.name,
                        "mimeType": mime, "httpMethod": "POST"}]})
        errs = staged["stagedUploadsCreate"]["userErrors"]
        if errs:
            raise ShopifyError(str(errs))
        target = staged["stagedUploadsCreate"]["stagedTargets"][0]
        form = {p["name"]: p["value"] for p in target["parameters"]}
        with open(png_path, "rb") as f:
            up = requests.post(target["url"], data=form, files={"file": (png_path.name, f, mime)}, timeout=120)
        if up.status_code not in (200, 201, 204):
            raise ShopifyError(f"staged upload HTTP {up.status_code}: {up.text[:300]}")
        created = self.gql("""
          mutation($productId: ID!, $media: [CreateMediaInput!]!) {
            productCreateMedia(productId: $productId, media: $media) {
              media { id status } mediaUserErrors { message } } }""",
            {"productId": product_gid,
             "media": [{"originalSource": target["resourceUrl"], "alt": alt, "mediaContentType": "IMAGE"}]})
        errs = created["productCreateMedia"]["mediaUserErrors"]
        if errs:
            raise ShopifyError(str(errs))
        return created["productCreateMedia"]["media"][0]["id"]

    def move_media_to_position(self, product_gid, media_id, position_index):
        """0-based index; position 2 in the gallery = index 1."""
        moves = [{"id": media_id, "newPosition": str(position_index)}]
        data = self.gql("""
          mutation($id: ID!, $moves: [MoveInput!]!) {
            productReorderMedia(id: $id, moves: $moves) {
              mediaUserErrors { message } } }""",
            {"id": product_gid, "moves": moves})
        errs = data["productReorderMedia"]["mediaUserErrors"]
        if errs:
            raise ShopifyError(str(errs))
