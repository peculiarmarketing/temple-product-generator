"""Direct HTTP client for the Tapstitch editor's own API.

Tapstitch has no public API, so the migration plan assumed product creation had
to go through their web editor by clicking. It does not. Recording the editor on
15 Sep 2026 showed every step is a JSON call, and replaying those calls the same
evening created a design from Python that Tapstitch accepted and rendered four
mockups from. `docs/discovery/2026-09-tapstitch-editor-api.md` has the evidence.

This module is that route, as code. It replaces the selector block in
config/tapstitch.json, which described a click path nobody needs to write.

AUTH is the dedicated Chrome profile's cookies, nothing else: no CSRF header, no
bearer token, no editor session. Evan logs in once with scripts/tapstitch_login.py
and the profile keeps the session for days. Never print the cookie jar.

WHAT THIS DOES NOT DO: create the Shopify-bound store product. That call is
`POST /api/services/user/distribution/stores/{storeId}/products` and it is the
one with consequences for a live storefront, so it is deliberately absent until
Evan decides to run it.
"""

import json
from pathlib import Path
from urllib.parse import urlsplit

import requests

from browser_session import TAPSTITCH, connect

BASE = "https://www.tapstitch.com"
CDN = "https://files.tapstitch.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")


class TapstitchError(Exception):
    pass


def session():
    """A requests.Session carrying the dedicated Chrome profile's cookies.

    Opening a Playwright connection purely to read cookies is wasteful but it is
    the only way to get them: the profile's cookie store is an encrypted SQLite
    file that Chrome holds open.
    """
    p, browser = connect(TAPSTITCH)
    try:
        jar = {c["name"]: c["value"]
               for c in browser.contexts[0].cookies()
               if "tapstitch" in c.get("domain", "")}
    finally:
        browser.close()
        p.stop()
    if not jar:
        raise TapstitchError("No Tapstitch cookies in the profile. Run "
                             "scripts/tapstitch_login.py first.")
    s = requests.Session()
    s.cookies.update(jar)
    s.headers.update({"accept": "*/*", "device": "pc", "User-Agent": UA})
    return s


def _data(r):
    """Unwrap Tapstitch's {code, msg, data} envelope.

    TRAP: a rejected call still returns HTTP 200. The status line is useless;
    `code` is the truth. A malformed design save comes back as code 10001,
    "System error, please refresh and try again", which says nothing about what
    was wrong — see save_design's docstring for what it actually wants.
    """
    r.raise_for_status()
    body = r.json()
    if body.get("code") != 200:
        raise TapstitchError(f"{r.request.method} {urlsplit(r.url).path} -> "
                             f"code={body.get('code')} msg={body.get('msg')!r}")
    return body.get("data")


def create_template(s, blank):
    """Create a design from a blank, addressed by SKU. Returns the template id.

    `blank` is the `api.blanks.<garment>` block in config/tapstitch.json.
    """
    payload = [{"addToProductList": False,
                "colorCode": blank["lead_colorCode"],
                "name": blank.get("name", ""),
                "productId": blank["productId"],
                "productSource": 1,
                "resourceCode": -1,
                "serviceId": "",
                "size": "",
                "specialProcessTags": blank["specialProcessTags"],
                "silSn": blank["silSn"]}]
    ids = _data(s.post(f"{BASE}/api/services/user/service/template",
                       data=json.dumps(payload),
                       headers={"Content-Type": "application/json"}, timeout=60))
    if not ids:
        raise TapstitchError("create_template returned no id")
    return ids[0]


def upload_print_file(s, png_path):
    """Upload one print file and return the CDN URL to reference it by.

    TRAP: `x-oss-meta-author` is part of what Alibaba OSS signs. Send the PUT
    without it and the upload is a bare 403 with no explanation, even though the
    signed URL is fresh and correct. The value is the `author` field that
    retrieve-upload-data returns alongside the URL.

    TRAP: the upload lands on the OSS bucket host, but a design must reference it
    on files.tapstitch.com. Same path, different host.
    """
    png_path = Path(png_path)
    up = _data(s.get(f"{BASE}/api/designs/user_cover_img/retrieve-upload-data",
                     params={"name": png_path.name}, timeout=30))
    r = requests.put(up["signatureUrl"], data=png_path.read_bytes(), timeout=300,
                     headers={"Content-Type": up["contentType"],
                              "x-oss-meta-author": up["author"],
                              "Referer": f"{BASE}/",
                              "User-Agent": UA})
    if r.status_code != 200:
        raise TapstitchError(f"OSS upload failed: HTTP {r.status_code} {r.text[:200]}")
    return CDN + urlsplit(up["resourceUrl"]).path


CANVAS = 700  # the editor's design canvas is always 700x700


def print_areas(template):
    """Each printable side's rectangle on the 700x700 canvas, from get_template().

    This is the canvas-to-print-area mapping the migration was missing. Tapstitch
    states it outright in craftItemDto.customArea: every side carries a
    `<side>_side_middle` detail whose x/y/width/height are canvas coordinates.
    The sleeves' `virtual` details are skipped; they are mockup anchors, not
    print areas.

    The rectangles are NOT the same across garments, and on the crew not even
    across sides. The tee is 260x327 on both sides; the crew is 210x281 on the
    back and 209x275 on the front. Reusing one garment's numbers on another
    misplaces and misscales the art with no error anywhere.
    """
    out = {}
    for area in template["craftItemDto"]["customArea"]:
        for det in area["details"]:
            if det.get("type") == "virtual":
                continue
            if det["id"] == f"{area['name']}_side_middle":
                out[area["name"]] = {k: float(det[k])
                                     for k in ("x", "y", "width", "height")}
    return out


def placement(area, src_size, canvas=CANVAS):
    """Lay one print file over its print area. Returns the editor's geometry.

    Derived from, and checked against, the tee design of 15 Sep 2026, whose
    back area is x=214 y=194 w=260 h=327 and whose saved object is left=344
    top=358 width=556 height=700 scale=0.4671428571:

    - The editor first fits the image inside the canvas (contain), TRUNCATING
      the minor dimension: 700 * 4386/5516 = 556.6 becomes 556, not 557.
    - scaleX and scaleY are both the print area's height over the canvas:
      327/700 = 0.4671428571. Height governs, and the width follows, which is
      safe only because every print file is built to the shape of its own print
      area. The assert below is what makes that a checked assumption rather than
      a silent one.
    - left and top are the print area's CENTRE, not its corner, and not the
      canvas's centre: 214 + 260/2 = 344, 194 + 327/2 = 357.5. The editor stored
      358, so it rounds; we send the exact centre, because half a canvas pixel
      is 0.03in on the garment and an exact centre needs no guess about which
      way Tapstitch rounds a .5.
    """
    w, h = src_size
    if h >= w:
        box_h, box_w = canvas, int(canvas * w / h)
    else:
        box_w, box_h = canvas, int(canvas * h / w)
    scale = area["height"] / box_h
    drawn_w = box_w * scale
    if abs(drawn_w - area["width"]) > 1.0:
        raise TapstitchError(
            f"print file {w}x{h} is the wrong shape for a "
            f"{area['width']:.0f}x{area['height']:.0f} print area: scaling it to "
            f"fit the height draws it {drawn_w:.1f} canvas px wide, not "
            f"{area['width']:.0f}. Rebuild the file to the print area's aspect.")
    return {"left": area["x"] + area["width"] / 2,
            "top": area["y"] + area["height"] / 2,
            "width": box_w, "height": box_h,
            "scaleX": scale, "scaleY": scale}


def design_object(piece, src, placement, src_size):
    """One image on one print area, in the shape the editor sends.

    Every key here is load-bearing. Dropping clipId, customAreaId, designPart,
    flipX/flipY or visible gets the same opaque code 10001 as sending nothing.

    `placement` is left/top/width/height/scaleX/scaleY on the editor's 700x700
    canvas, and comes from placement() below, which derives it from the garment's
    own print area rather than reusing the tee's observed numbers.
    """
    return {"zIndex": 3,
            "src": src,
            "angle": 0,
            "flipX": False, "flipY": False,
            "clipId": "LAYER_CLIP0",
            "customAreaId": f"{piece}_side_middle",
            "customAreaAngle": 0,
            "visible": True,
            "designPart": piece,
            "srcDetails": {"width": src_size[0], "height": src_size[1]},
            **placement}


def save_design(s, template_id, blank, pieces):
    """Save a design. `pieces` maps piece name -> design_object().

    TRAP: `virtualConfig` and `mockupConfig` are required siblings of `config`,
    both JSON-encoded STRINGS rather than objects, as is `config` itself. The
    editor sends mockupConfig with its own slightly different geometry; sending
    the same objects works and Tapstitch renders mockups from it.

    srcDetails.srcId is NOT required, which is why the multipart
    /api/designs/user_cover_img/save call this module skips can be skipped.
    """
    cfg = [{"piece": p, "objects": [o], "canvasSize": {"width": 700, "height": 700},
            "embs": []} for p, o in pieces.items()]
    mock = [{"piece": p, "objects": [o], "canvasSize": {"width": 700, "height": 700}}
            for p, o in pieces.items()]
    body = {"colorCode": blank["colorCodes"],
            "uniqueId": template_id,
            "resourceCode": -1,
            "productId": blank["productId"],
            "designTools": "2d-layers",
            "printType": 1,
            "isUsedHd": False,
            "dimension": "inches",
            "printingPreferenceType": None,
            "specialProcessTags": blank["specialProcessTags"],
            "branding": {"innerNeckLabelCommitId": "0", "hangtagCommitId": "0"},
            "virtualConfig": "[]",
            "mockupConfig": json.dumps(mock),
            "config": json.dumps(cfg)}
    return _data(s.put(f"{BASE}/api/designs/customized/templates/{template_id}",
                       data=json.dumps(body),
                       headers={"Content-Type": "application/json"}, timeout=120))


def get_template(s, template_id):
    """Read a design back. Use this to VERIFY a save rather than trusting it.

    Worth reading for its own sake: `backSideDpiTip` states the print area as
    Tapstitch sees it, e.g. "Print area size 2193 x 2758 px (150)DPI", which is
    how the 150 DPI reading in garments/*.json was confirmed without opening the
    editor.
    """
    return _data(s.get(f"{BASE}/api/designs/customized/templates/{template_id}",
                       timeout=30))


def distribute(s, store_product_ids):
    """PUBLISH store products to Shopify. This reaches the live storefront.

    The only call in this module with outward-facing consequences: a distributed
    product appears on the storefront as ACTIVE and is immediately purchasable.
    There is no undo here — unpublishing is a Shopify-side operation afterwards.

    `store_product_ids` are STORE-PRODUCT ids, which are a third kind of id and
    not interchangeable with the template id or the pool product id. It takes a
    list, so a batch is one call rather than one per product.

    TRAP: Tapstitch publishes with an EMPTY productType and every fixup in
    scripts/shopify_fixups.py is keyed on it, so colour ordering and the featured
    photo silently do nothing and report success. Set it before any fixup runs.

    TRAP: the publish can outrun the editor's own success state. Confirm against
    Shopify rather than trusting this call's response — measured 15 Sep 2026,
    the product took over a minute to appear after the call returned.
    """
    return _data(s.post(f"{BASE}/api/services/user/distribution/stores/products/distribute",
                        data=json.dumps({"uniqueIdList": list(store_product_ids)}),
                        headers={"Content-Type": "application/json"}, timeout=300))


def store_product_prefill(s, store_id, template_id):
    """Tapstitch's own draft of the store product for a saved design.

    Worth fetching before anything is published: it names the colours EXACTLY as
    Tapstitch will send them to Shopify, so the swatch names the Shopify fixups
    match on can be checked without publishing. It also carries the mockups,
    variants, costs and shipping profiles, so the create call is this payload
    edited rather than one built from scratch.
    """
    return _data(s.get(f"{BASE}/api/services/user/distribution/stores/{store_id}"
                       f"/products/templates/{template_id}/new", timeout=60))


def store_product_payload(prefill, title, retail_cents, description_html=None,
                          units="IMPERIAL"):
    """Turn a prefill into the create call's body.

    TRAP: the size guide is NOT a field in this payload. Tapstitch bakes the
    chosen table into description.content when the product is created, so the
    unit choice has to be right here and cannot be repaired afterwards. The
    prefill comes back with IMPERIAL and METRIC BOTH selected, which publishes
    inch/cm column pairs; Evan's rule is imperial. Pass description_html to send
    our own copy instead, in which case no Tapstitch table is added at all.

    Its IMPERIAL table carries no unit label anywhere, just bare numbers, which
    is why reference/garment-copy/*/size-guide.html is the better body.
    """
    if description_html is None:
        description_html = (prefill["description"]["content"]
                            + prefill["sizeGuide"]["descriptionHtml"][units])
    variants = []
    for v in prefill["variants"]:
        variants.append({**v, "retailPrice": retail_cents})
    return {"title": title,
            "description": {"type": "HTML", "content": description_html},
            "mockups": prefill["mockups"],
            "options": prefill["options"],
            "variants": variants,
            "costIncludesShipping": prefill["costIncludesShipping"],
            "shippingProfileIds": [sp["id"] for sp in prefill["shippingProfiles"]
                                   if sp.get("selected")],
            "tags": [],
            "visibility": prefill["visibility"],
            "collectionIds": [],
            "distribute": False}


def create_store_product(s, store_id, payload):
    """Create the Shopify-bound store product. Does NOT reach the storefront.

    With distribute False this stays inside Tapstitch, which is what makes the
    safe order possible: build the product, then delete the old listing to free
    its handle, then distribute(). The only irreversible step then happens after
    the replacement is known to exist.

    Returns the STORE-PRODUCT id, which is a third kind of id and the one
    distribute() wants.
    """
    d = _data(s.post(f"{BASE}/api/services/user/distribution/stores/{store_id}/products",
                     data=json.dumps(payload),
                     headers={"Content-Type": "application/json"}, timeout=300))
    if isinstance(d, dict):
        return d.get("uniqueId") or d.get("id") or d
    return d
