"""Minimal Shopify Admin API client for post-publish product media work.

Needs in .env:
  SHOPIFY_STORE_DOMAIN=xxxx.myshopify.com
  SHOPIFY_ADMIN_TOKEN=shpat_...   (custom app, read_products + write_products)
"""

import mimetypes
import time
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

    def wait_for_media_ready(self, media_id, timeout_s=90):
        """Block until Shopify finishes ingesting an image.

        productCreateMedia returns while status is still UPLOADED/PROCESSING.
        Reordering media that has not settled produces a nondeterministic final
        order, which is how 22 art cards ended up at gallery position 1 instead
        of 2 on 20 Aug 2026, displacing the garment mockup as the featured
        image."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            data = self.gql("""
              query($id: ID!) { node(id: $id) {
                ... on MediaImage { id status } } }""", {"id": media_id})
            status = (data.get("node") or {}).get("status")
            if status == "READY":
                return True
            if status == "FAILED":
                raise ShopifyError(f"media {media_id} failed to process")
            time.sleep(2)
        raise ShopifyError(f"media {media_id} not READY after {timeout_s}s")

    def media_position(self, product_gid, media_id):
        """Current 0-based index of one media item, or None if absent."""
        data = self.gql("""
          query($id: ID!) { product(id: $id) {
            media(first: 50) { edges { node { ... on MediaImage { id } } } } } }""",
            {"id": product_gid})
        ids = [e["node"].get("id") for e in data["product"]["media"]["edges"]]
        return ids.index(media_id) if media_id in ids else None

    def move_media_to_position(self, product_gid, media_id, position_index, attempts=3):
        """0-based index; position 2 in the gallery = index 1.

        productReorderMedia is asynchronous: it returns a job and an empty
        mediaUserErrors as soon as the request is accepted, which is not the
        same as the move having happened. Wait for the job, then confirm the
        media actually sits where it should, and retry if it does not."""
        self.wait_for_media_ready(media_id)
        for attempt in range(1, attempts + 1):
            if self.media_position(product_gid, media_id) == position_index:
                return True
            moves = [{"id": media_id, "newPosition": str(position_index)}]
            data = self.gql("""
              mutation($id: ID!, $moves: [MoveInput!]!) {
                productReorderMedia(id: $id, moves: $moves) {
                  job { id done }
                  mediaUserErrors { message } } }""",
                {"id": product_gid, "moves": moves})
            errs = data["productReorderMedia"]["mediaUserErrors"]
            if errs:
                raise ShopifyError(str(errs))
            job = data["productReorderMedia"].get("job") or {}
            self._wait_for_job(job.get("id"))
            if self.media_position(product_gid, media_id) == position_index:
                return True
            time.sleep(2 * attempt)
        raise ShopifyError(
            f"media {media_id} still at index {self.media_position(product_gid, media_id)} "
            f"after {attempts} reorder attempts (wanted {position_index})")

    def _wait_for_job(self, job_id, timeout_s=60):
        if not job_id:
            return
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            data = self.gql("query($id: ID!) { job(id: $id) { id done } }", {"id": job_id})
            if (data.get("job") or {}).get("done"):
                return
            time.sleep(1)
