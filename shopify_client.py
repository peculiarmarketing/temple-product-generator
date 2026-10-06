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
        """One paginated pass over the catalog: [{id, title, handle, status,
        publishedAt, productType, createdAt, vendor}, ...]. A list, not a dict,
        so duplicate titles stay visible, and they do: two live products shared
        the exact title "Essential Temple Tee" on 14 Sep 2026. createdAt is what
        lets a caller tell the original from the later stray, and vendor is what
        tells an old listing from its Tapstitch replacement when both exist
        under the same title."""
        out, cursor = [], None
        while True:
            data = self.gql("""
              query($after: String) { products(first: 100, after: $after) {
                pageInfo { hasNextPage endCursor }
                nodes { id title handle status publishedAt productType createdAt vendor } } }""",
                {"after": cursor})
            block = data["products"]
            out.extend(block["nodes"])
            if not block["pageInfo"]["hasNextPage"]:
                return out
            cursor = block["pageInfo"]["endCursor"]

    def find_product_by_title(self, title):
        """The product with exactly this title, or None when 0 or 2+ match.

        `handle` is in the selection because a caller that has just published a
        product knows only the title: Shopify derives the address from it and
        every repair afterwards is addressed by handle. It was added 16 Sep 2026
        after scripts/tapstitch_run.py read product["handle"] off this and got a
        KeyError, which would have fired immediately after the one call in the
        migration that cannot be undone.
        """
        data = self.gql("""
          query($q: String!) { products(first: 5, query: $q) {
            nodes { id title handle media(first: 20) { nodes { id alt ... on MediaImage { image { url } } } } } } }""",
            {"q": f'title:"{title}"'})
        exact = [p for p in data["products"]["nodes"] if p["title"].strip() == title]
        return exact[0] if len(exact) == 1 else None

    def find_product_by_handle(self, handle):
        """Handle lookup. Preferred over title for anything that has to bind a
        product to its Shopify listing: handles are unique, titles are
        not (two products shared 'Nauvoo Temple Sweatshirt (front logo)')."""
        data = self.gql("""
          query($handle: String!) { productByIdentifier(identifier: {handle: $handle}) {
            id title handle status productType } }""", {"handle": handle})
        return data.get("productByIdentifier")

    def update_product(self, product_gid, **fields):
        """productUpdate with whatever scalar fields are passed (title,
        descriptionHtml, status). Nothing else on the product is touched,
        so mockups, media order, handle and publication state all survive."""
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

    def delete_product(self, product_gid):
        """Permanently delete one product. NOT part of any sequence.

        This existed for the swap-time delete that freed an old listing's address
        for its replacement. That is RETIRED (Evan, 16 Sep 2026, asked and
        confirmed): it never actually moved the address, because Shopify builds a
        new product's address from its title and ignores whatever a deletion just
        freed. Old listings now stay DRAFT, so this is only ever a deliberate
        one-off.

        There is no undo. Record the product before deleting it.
        """
        data = self.gql("""
          mutation($input: ProductDeleteInput!) {
            productDelete(input: $input) {
              deletedProductId
              userErrors { field message } } }""",
            {"input": {"id": product_gid}})
        errs = data["productDelete"]["userErrors"]
        if errs:
            raise ShopifyError(str(errs))
        return data["productDelete"]["deletedProductId"]

    def rename_option_value(self, product_gid, option_name, old_value, new_value):
        """Rename one value of one product option, e.g. Tapstitch's
        'Wine Red' to 'Maroon'. Variant titles follow automatically.

        Returns True if it renamed something, False if the old value is not on
        this product, which makes the call idempotent: a second run is a no-op
        rather than an error. A re-sync from the supplier can push the old name
        back, so this is built to be re-run."""
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
        not on this product. Idempotent, and worth re-running: a re-sync
        from the supplier restores the supplier's own order."""
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

    def update_media_alt(self, product_gid, media_gid, alt):
        """Rewrite one product image's alt text.

        The alt text on an on-model photo is not decoration: it is the only
        record of which colourway the photo shows, and
        bind_variants_to_onmodel.py pairs a variant to its photo by matching the
        variant's colour name against the tail of that string. Rename a colour
        on the storefront without rewriting the alt and the binding silently
        stops finding a photo for that colour on the next re-run.

        productUpdateMedia, not fileUpdate: fileUpdate is the more obvious
        mutation for an alt text but it demands write_files or write_themes,
        and this app's token carries neither. productUpdateMedia does the same
        job under write_products, which the token already has."""
        data = self.gql("""
          mutation($productId: ID!, $media: [UpdateMediaInput!]!) {
            productUpdateMedia(productId: $productId, media: $media) {
              media { ... on MediaImage { id alt } }
              mediaUserErrors { field message } } }""",
            {"productId": product_gid, "media": [{"id": media_gid, "alt": alt}]})
        errs = data["productUpdateMedia"]["mediaUserErrors"]
        if errs:
            raise ShopifyError(str(errs))
        return data["productUpdateMedia"]["media"][0]["alt"]

    def delete_media(self, product_gid, media_gids):
        """productDeleteMedia. Returns the deleted ids; raises on any media error.
        Callers must check first that no variant is bound to what they delete:
        a variant whose image is deleted shows no image on the storefront."""
        data = self.gql("""
          mutation($pid: ID!, $ids: [ID!]!) {
            productDeleteMedia(productId: $pid, mediaIds: $ids) {
              deletedMediaIds mediaUserErrors { message } } }""",
            {"pid": product_gid, "ids": list(media_gids)})["productDeleteMedia"]
        if data["mediaUserErrors"]:
            raise ShopifyError(str(data["mediaUserErrors"]))
        return data["deletedMediaIds"]

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
