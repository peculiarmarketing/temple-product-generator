"""Minimal Shopify Admin API client for post-publish product media work.

Needs in .env:
  SHOPIFY_STORE_DOMAIN=xxxx.myshopify.com
  SHOPIFY_ADMIN_TOKEN=shpat_...   (custom app, read_products + write_products)
"""

import io
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
        """One paginated pass over the catalog: [{id, title, handle, status,
        publishedAt, productType}, ...]. A list, not a dict, so duplicate
        titles stay visible."""
        out, cursor = [], None
        while True:
            data = self.gql("""
              query($after: String) { products(first: 100, after: $after) {
                pageInfo { hasNextPage endCursor }
                nodes { id title handle status publishedAt productType } } }""",
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

    def find_product_by_handle(self, handle):
        """Handle lookup. Preferred over title for anything that has to bind a
        Printify product to its Shopify twin: handles are unique, titles are
        not (two products shared 'Nauvoo Temple Sweatshirt (front logo)')."""
        data = self.gql("""
          query($handle: String!) { productByIdentifier(identifier: {handle: $handle}) {
            id title handle status productType } }""", {"handle": handle})
        return data.get("productByIdentifier")

    def update_product(self, product_gid, **fields):
        """productUpdate with whatever scalar fields are passed (title,
        descriptionHtml, status). Nothing else on the product is touched, and
        no Printify republish is involved, so mockups, media order, handle and
        publication state all survive."""
        data = self.gql("""
          mutation($input: ProductUpdateInput!) {
            productUpdate(product: $input) {
              product { id title handle status }
              userErrors { field message } } }""",
            {"input": {"id": product_gid, **fields}})
        errs = data["productUpdate"]["userErrors"]
        if errs:
            raise ShopifyError(str(errs))
        return data["productUpdate"]["product"]

    def rename_option_value(self, product_gid, option_name, old_value, new_value):
        """Rename one value of one product option, e.g. the hoodie's
        'True Navy' to 'Blue Jean'. Variant titles follow automatically.

        Returns True if it renamed something, False if the old value is not on
        this product, which makes the call idempotent: a second run is a no-op
        rather than an error. Printify re-syncs variants on any republish and
        will push the old name back, so this is built to be re-run."""
        data = self.gql("""
          query($id: ID!) { product(id: $id) {
            options { id name optionValues { id name } } } }""", {"id": product_gid})
        product = data.get("product")
        if not product:
            raise ShopifyError(f"no product {product_gid}")
        for option in product["options"]:
            if option["name"] != option_name:
                continue
            if any(v["name"] == new_value for v in option["optionValues"]):
                return False  # already renamed
            match = next((v for v in option["optionValues"] if v["name"] == old_value), None)
            if match is None:
                return False
            result = self.gql("""
              mutation($productId: ID!, $option: OptionUpdateInput!,
                       $values: [OptionValueUpdateInput!]) {
                productOptionUpdate(productId: $productId, option: $option,
                                    optionValuesToUpdate: $values) {
                  userErrors { field message code } } }""",
                {"productId": product_gid, "option": {"id": option["id"]},
                 "values": [{"id": match["id"], "name": new_value}]})
            errs = result["productOptionUpdate"]["userErrors"]
            if errs:
                raise ShopifyError(str(errs))
            return True
        return False

    def reorder_option_values(self, product_gid, option_name, first_value, other_orders=None):
        """Move one value to the front of a product option's value list.

        Shopify preselects variant position 1, and position is computed from
        the option value order, so this is the only lever it gives over which
        variant a product page opens on. It is also the swatch display order,
        so the chosen color moves to the front of the swatch row too.

        `other_orders` gives a canonical order for the product's OTHER options,
        e.g. {"Size": ["S", "M", "L", ...]}. Pass it. Shopify re-derives every
        option's value order from the resulting variant sequence, so a color
        with gaps in its size run pushes the missing sizes to the back; feeding
        the currently stored order back in compounds that scrambling on every
        re-run, while a canonical order keeps the damage to one pass and no
        worse. Values absent from the product are dropped and any the caller
        did not list are appended in their current order.

        Returns True if it reordered, False if the value is already first or
        not on this product. Idempotent, and worth re-running: a Printify
        republish re-syncs variants and restores Printify's own order."""
        data = self.gql("""
          query($id: ID!) { product(id: $id) {
            options { id name optionValues { id name } } } }""", {"id": product_gid})
        product = data.get("product")
        if not product:
            raise ShopifyError(f"no product {product_gid}")
        option = next((o for o in product["options"] if o["name"] == option_name), None)
        if option is None:
            return False
        names = [v["name"] for v in option["optionValues"]]
        if not names or names[0] == first_value or first_value not in names:
            return False
        ordered = [first_value] + [n for n in names if n != first_value]
        # Every option has to be in the payload, not just the one moving:
        # productOptionsReorder rejects a partial list with MISSING_OPTION_NAME.
        # The others go back in exactly the order they came out.
        other_orders = other_orders or {}
        payload = []
        for opt in product["options"]:
            if opt["id"] == option["id"]:
                values = ordered
            else:
                current = [v["name"] for v in opt["optionValues"]]
                canonical = [n for n in other_orders.get(opt["name"], []) if n in current]
                values = canonical + [n for n in current if n not in canonical]
            payload.append({"id": opt["id"], "values": [{"name": n} for n in values]})
        result = self.gql("""
          mutation($productId: ID!, $options: [OptionReorderInput!]!) {
            productOptionsReorder(productId: $productId, options: $options) {
              userErrors { field message code } } }""",
            {"productId": product_gid, "options": payload})
        errs = result["productOptionsReorder"]["userErrors"]
        if errs:
            raise ShopifyError(str(errs))
        return True

    def product_media_and_variants(self, product_gid):
        """(media, variants) for matching a colorway to the mockup that shows
        it. Variant image URLs are the only reliable link: mockup media carry
        no alt text from Printify."""
        data = self.gql("""
          query($id: ID!) { product(id: $id) {
            media(first: 60) { nodes { ... on MediaImage { id alt image { url } } } }
            variants(first: 100) { nodes { title image { url } } } } }""",
            {"id": product_gid})
        product = data.get("product")
        if not product:
            raise ShopifyError(f"no product {product_gid}")
        return product["media"]["nodes"], product["variants"]["nodes"]

    @staticmethod
    def mean_rgb(url, timeout=60):
        """Average colour of an image's centre third, or None if unreadable.

        The centre is the garment itself, away from the white studio backdrop,
        so this separates colorways cleanly. Grayscale hashing does not: every
        mockup in a set is the same shirt in the same pose and only the colour
        differs."""
        from PIL import Image
        try:
            resp = requests.get(url, timeout=timeout)
            if not resp.ok:
                return None
            image = Image.open(io.BytesIO(resp.content)).convert("RGB")
            w, h = image.size
            patch = image.crop((w // 3, h // 3, 2 * w // 3, 2 * h // 3)).resize((32, 32))
            pixels = list(patch.get_flattened_data())
            n = len(pixels)
            return tuple(sum(px[i] for px in pixels) / n for i in range(3))
        except Exception:
            return None

    def media_id_by_color(self, product_gid, rgb, max_distance=12.0, min_ratio=3.0):
        """The media whose garment colour matches `rgb`, or None.

        The fallback for products whose variants carry no images, where
        media_id_for_colorway has nothing to match on. Deliberately refuses an
        ambiguous answer: the winner must be within max_distance AND clearly
        ahead of the runner-up, because featuring the wrong colorway is worse
        than featuring none. Observed on a real product: best 0.1, next 32.3."""
        media, _ = self.product_media_and_variants(product_gid)
        scored = []
        for node in media:
            url = (node.get("image") or {}).get("url")
            if not url:
                continue
            mean = self.mean_rgb(url)
            if mean is None:
                continue
            d = sum((a - b) ** 2 for a, b in zip(rgb, mean)) ** 0.5
            scored.append((d, node["id"]))
        if not scored:
            return None
        scored.sort(key=lambda x: x[0])
        best_d, best_id = scored[0]
        if best_d > max_distance:
            return None
        if len(scored) > 1 and scored[1][0] < best_d * min_ratio:
            return None
        return best_id

    def media_id_for_colorway(self, product_gid, colorway):
        """The media id of the mockup a colorway's variants point at, or None."""
        media, variants = self.product_media_and_variants(product_gid)
        urls = {(v["image"] or {}).get("url", "").split("?")[0]
                for v in variants
                if (v.get("title") or "").split("/")[0].strip() == colorway and v.get("image")}
        urls.discard("")
        if not urls:
            return None
        for node in media:
            if (node.get("image") or {}).get("url", "").split("?")[0] in urls:
                return node["id"]
        return None

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
