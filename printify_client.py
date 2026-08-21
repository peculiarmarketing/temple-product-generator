"""Printify REST API client for the temple product generator.

This is the shared code path for exploration (Phase 1) and production
(Phase 3+). Keep the surface minimal: methods are added in the phase
that first calls them.
"""

import time
import uuid
from pathlib import Path

import requests
from dotenv import dotenv_values

BASE_URL = "https://api.printify.com/v1"
USER_AGENT = "peculiar-people-generator"
PROJECT_ROOT = Path(__file__).resolve().parent

# Transient-fault retry budget for replayable calls (see _request).
TRANSIENT_ATTEMPTS = 4
TRANSIENT_BACKOFF_S = 3

# Writable keys per the spec (docs/temple-catalog-generator-plan.md, Phase 1).
# POST/PUT product bodies may contain nothing outside these.
WRITABLE_PRODUCT_KEYS = (
    "title",
    "description",
    "safety_information",
    "blueprint_id",
    "print_provider_id",
    "variants",
    "print_areas",
)
WRITABLE_VARIANT_KEYS = ("id", "price", "is_enabled")
WRITABLE_IMAGE_LAYER_KEYS = ("id", "x", "y", "scale", "angle")
# No "id" on text layers: their GET ids are layer instance UUIDs, not media
# library images, and POST validates every images[].id against the library
# (rejects with code 8253 "Provided images do not exist").
WRITABLE_TEXT_LAYER_KEYS = ("x", "y", "scale", "angle") + (
    "type",
    "font_family",
    "font_size",
    "font_weight",
    "font_color",
    "font_style",
    "input_text",
    "text_align",
)


class PrintifyError(Exception):
    def __init__(self, method, path, status, body, deny_reason=None):
        self.method = method
        self.path = path
        self.status = status
        self.body = body
        self.deny_reason = deny_reason
        msg = f"{method} {path} -> HTTP {status}"
        if deny_reason:
            msg += f" (x-deny-reason: {deny_reason})"
        msg += f"\n{body[:2000]}"
        super().__init__(msg)


class PrintifyClient:
    def __init__(self, token, shop_id, user_agent=USER_AGENT):
        self.shop_id = shop_id
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "User-Agent": user_agent,
                "Content-Type": "application/json;charset=utf-8",
            }
        )

    def _is_replayable(self, method, path):
        """Whether repeating this call cannot create a second thing. GET and
        PUT are idempotent by definition (a PUT re-sends the same body to the
        same product id). An image upload is safe to repeat because a replay
        at worst leaves an unreferenced asset in the library; the generator
        uses whichever id comes back. Everything else, notably product
        creation and publish, is left alone: a replay there could duplicate a
        product or a storefront listing."""
        return method in ("GET", "PUT") or path.startswith("/uploads/")

    def _request(self, method, path, json=None, timeout=60, _retried=False, _attempt=1):
        # A whole sweep is dozens of calls; one transient fault used to kill
        # the run mid-catalog. Observed in the 20 Aug 2026 sweep: an
        # SSLV3_ALERT_BAD_RECORD_MAC on an upload and an HTTP 500 on a product
        # PUT, both of which succeeded on a retry. Only replayable calls are
        # retried, and attempts stay low because the account's error budget is
        # 5% of requests.
        try:
            resp = self.session.request(method, f"{BASE_URL}{path}", json=json, timeout=timeout)
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            if _attempt >= TRANSIENT_ATTEMPTS or not self._is_replayable(method, path):
                raise
            time.sleep(TRANSIENT_BACKOFF_S * _attempt)
            print(f"  transient {type(e).__name__} on {method} {path}; "
                  f"retry {_attempt + 1} of {TRANSIENT_ATTEMPTS}")
            return self._request(method, path, json=json, timeout=timeout,
                                 _retried=_retried, _attempt=_attempt + 1)
        if resp.status_code == 429 and not _retried:
            # Retry exactly once. The account's error budget is 5% of requests;
            # aggressive retries can trip it.
            wait = int(resp.headers.get("Retry-After", 10))
            time.sleep(wait)
            return self._request(method, path, json=json, timeout=timeout, _retried=True)
        if (resp.status_code >= 500 and _attempt < TRANSIENT_ATTEMPTS
                and self._is_replayable(method, path)):
            time.sleep(TRANSIENT_BACKOFF_S * _attempt)
            print(f"  transient HTTP {resp.status_code} on {method} {path}; "
                  f"retry {_attempt + 1} of {TRANSIENT_ATTEMPTS}")
            return self._request(method, path, json=json, timeout=timeout,
                                 _retried=_retried, _attempt=_attempt + 1)
        if not resp.ok:
            raise PrintifyError(
                method,
                path,
                resp.status_code,
                resp.text,
                deny_reason=resp.headers.get("x-deny-reason"),
            )
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def get_shops(self):
        return self._request("GET", "/shops.json")

    def list_products(self, page=1, limit=50):
        return self._request("GET", f"/shops/{self.shop_id}/products.json?page={page}&limit={limit}")

    def all_products(self, limit=50, max_pages=100):
        """Every product in the shop. Printify's pagination metadata is not
        trustworthy: on a 123-product shop it reports total=91 and last_page=2
        with next_page_url=null on page 2, while page 3 still returns real
        products. Trusting either field truncates the catalog at 100 and makes
        existing products look missing. The only reliable stop is an empty
        page. Ids can repeat across pages when the underlying list shifts, so
        dedupe while preserving order."""
        items, seen, page = [], set(), 1
        while page <= max_pages:
            resp = self.list_products(page=page, limit=limit)
            data = resp.get("data", resp) if isinstance(resp, dict) else resp
            if not data:
                break
            for product in data:
                if product["id"] not in seen:
                    seen.add(product["id"])
                    items.append(product)
            page += 1
        else:
            raise SystemExit(f"Product listing did not terminate within {max_pages} pages.")
        return items

    def get_product(self, product_id):
        return self._request("GET", f"/shops/{self.shop_id}/products/{product_id}.json")

    def create_product(self, body):
        return self._request("POST", f"/shops/{self.shop_id}/products.json", json=body)

    def update_product(self, product_id, body):
        return self._request("PUT", f"/shops/{self.shop_id}/products/{product_id}.json", json=body)

    def delete_product(self, product_id):
        return self._request("DELETE", f"/shops/{self.shop_id}/products/{product_id}.json")

    def upload_image(self, file_name, contents_b64):
        # Base64 path; sandbox files are not URL-reachable. Fine under ~5MB.
        return self._request(
            "POST", "/uploads/images.json", json={"file_name": file_name, "contents": contents_b64}, timeout=180
        )

    def archive_upload(self, image_id):
        return self._request("POST", f"/uploads/{image_id}/archive.json")


def writable_product_body(product_json):
    """Strip a GET product response down to exactly the writable keys."""
    body = {k: product_json[k] for k in WRITABLE_PRODUCT_KEYS if k in product_json}
    body["variants"] = [
        {k: v[k] for k in WRITABLE_VARIANT_KEYS if k in v} for v in body.get("variants", [])
    ]
    areas = []
    for area in body.get("print_areas", []):
        clean = {"variant_ids": area["variant_ids"], "placeholders": []}
        if "background" in area:
            clean["background"] = area["background"]
        for ph in area.get("placeholders", []):
            if not ph.get("images"):
                # GET includes every available position, even unused ones with an
                # empty images array; POST rejects those as "field is required".
                continue
            layers = []
            for layer in ph.get("images", []):
                is_text = layer.get("type") == "text/svg"
                keys = WRITABLE_TEXT_LAYER_KEYS if is_text else WRITABLE_IMAGE_LAYER_KEYS
                clean_layer = {k: layer[k] for k in keys if k in layer}
                if is_text:
                    # id is required on text layers but must be a fresh UUID:
                    # reusing a GET response's text layer id fails the media
                    # library existence check (code 8253).
                    clean_layer["id"] = str(uuid.uuid4())
                layers.append(clean_layer)
            clean["placeholders"].append({"position": ph["position"], "images": layers})
        areas.append(clean)
    body["print_areas"] = areas
    return body


def load_config():
    env = dotenv_values(PROJECT_ROOT / ".env")
    token = env.get("PRINTIFY_API_TOKEN", "")
    shop_id = env.get("PRINTIFY_SHOP_ID", "")
    if not token or token == "PASTE_TOKEN_HERE":
        raise SystemExit(
            "No Printify token found. Open .env in the project root and replace "
            "PASTE_TOKEN_HERE with your Personal Access Token "
            "(Printify > My Profile > Connections)."
        )
    if not shop_id:
        raise SystemExit("PRINTIFY_SHOP_ID missing from .env.")
    return token, int(shop_id)
