"""Record the Tapstitch editor's own network calls while Evan works by hand.

This exists to answer the first item in config/tapstitch.json's checklist, which
is the highest-value thing in the whole migration and the easiest to skip:

    BEFORE writing a single selector: open the network tab and save a design by
    hand. The save call almost certainly carries exact positions and upload
    references. If it does, a direct call is far sturdier than clicking through
    the UI and this whole file may be replaceable.

Reading devtools by hand and retyping what you see is lossy. This attaches to
the same dedicated Chrome that browser_session.py manages and records the calls
to disk, so the payloads can be read properly afterwards.

It AUTOMATES NOTHING. Evan drives the editor; this only listens. Nothing is
clicked, saved or published on his behalf.

    ./.venv.nosync/bin/python scripts/tapstitch_capture.py --minutes 20

SECRETS: request/response headers carry the session cookie and bearer tokens,
and signed upload URLs carry credentials in the query string. Everything on the
redaction list below is replaced before anything is written. The output
directory is gitignored, but treat a capture as sensitive anyway and do not
paste one into a chat or an issue without rereading it.
"""

import argparse
import json
import re
import sys
import time

import requests
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from browser_session import TAPSTITCH, connect

OUT_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "tapstitch" / "network"

# Header names are lowercased before this is consulted.
SECRET_HEADERS = {
    "cookie", "set-cookie", "authorization", "proxy-authorization",
    "x-auth-token", "x-api-key", "x-csrf-token", "x-xsrf-token",
}
# Names whose VALUE is a credential. The name itself is kept, so the shape of a
# signed upload URL or a save payload stays readable without the secret landing
# on disk.
#
# Matched on identifier SEGMENTS, not substrings. A substring test looks correct
# and quietly eats the payload: "sig" is inside "deSIGnId", "auth" is inside
# "author", "key" is inside "monkey". designId is the single most useful field
# in a save call, so this distinction is the difference between a capture that
# answers the question and one that looks fine and does not.
SECRET_WORDS = {
    "token", "key", "secret", "signature", "sig", "auth", "credential",
    "credentials", "password", "passwd", "pwd", "expires", "bearer",
    "session", "cookie", "email",
}


def _segments(name):
    """Split camelCase, snake_case, kebab-case and dotted names into words."""
    out = []
    for part in re.split(r"[^A-Za-z0-9]+", name):
        out.extend(re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|[0-9]+", part))
    return [s.lower() for s in out]


def is_secret_name(name):
    """True when any whole word in the name is a credential word.

    NOTE: a bare "key" is treated as secret, which also redacts an S3 object
    key. That costs nothing here — the upload URL's PATH is kept intact and
    carries the same object path — and it means an access key cannot slip
    through under a generic name.
    """
    return any(seg in SECRET_WORDS for seg in _segments(name))

# A response body big enough to be the asset itself rather than a description of
# it. Print files are megabytes; the calls worth reading are kilobytes.
MAX_BODY = 200_000

# Noise. The editor pulls fonts, sprites and telemetry constantly and none of it
# tells us how a design is saved.
SKIP_URL = re.compile(
    r"(google-analytics|googletagmanager|analytics\.google|googleadservices|"
    r"googlesyndication|gstatic\.com|google\.com/(measurement|rmkt|ads|pagead)|"
    r"/g/collect|facebook\.|doubleclick|hotjar|sentry|bat\.bing|linkedin\.com|"
    r"intercom|segment\.|clarity\.ms|fullstory|\.woff2?($|\?)|\.css($|\?)|"
    r"\.svg($|\?)|\.ico($|\?))", re.I)

# What we actually came for. Anything matching is called out in the live log and
# the closing summary, so the interesting call is not buried in hundreds of rows.
INTERESTING = re.compile(
    r"(save|design|product|upload|asset|artwork|print|mockup|publish|variant)", re.I)


def page_targets(site):
    """{target_id: url} for every live page, straight from Chrome.

    browser_session.login() learned this the hard way during Tapstitch logins:
    Chrome's /json is the only view of targets that stays correct across the
    renderer swaps this site causes.
    """
    try:
        targets = requests.get(f"{site.cdp_url}/json", timeout=2).json()
    except Exception:
        return {}
    return {t["id"]: t.get("url", "") for t in targets if t.get("type") == "page"}


def redact_url(url):
    parts = urlsplit(url)
    if not parts.query:
        return url
    q = [(k, "REDACTED" if is_secret_name(k) else v)
         for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def redact_headers(headers):
    return {k: ("REDACTED" if k.lower() in SECRET_HEADERS else v)
            for k, v in (headers or {}).items()}


def redact_body(text):
    """Blank obvious credential fields inside a JSON body without reshaping it.

    The body is what we are here to read, so this is deliberately narrow: only
    values whose KEY names a credential are replaced. Positions, sizes and asset
    references — the whole point of the capture — are left exactly as sent.
    """
    if not text:
        return text
    try:
        data = json.loads(text)
    except Exception:
        return text

    def walk(o):
        if isinstance(o, dict):
            return {k: ("REDACTED" if is_secret_name(k) else walk(v))
                    for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return o

    return json.dumps(walk(data))


class Capture:
    """Records via a CDP session per page target, not Playwright page events.

    WHY, because this was got wrong twice: a Playwright Page adopted from an
    already-running Chrome over connect_over_cdp does not reliably emit
    request/response events for traffic the HUMAN causes. Handlers attach
    without error and simply never fire, so the capture looks healthy and
    records nothing. A CDP session with Network.enable is attached to the target
    itself and keeps delivering across in-tab navigations, which is exactly the
    case that failed: Evan moved editor -> products pool -> product -> editor
    inside ONE tab, so the tab set never changed, nothing rebound, and a whole
    working session went unrecorded.
    """

    def __init__(self, path):
        self.fh = path.open("w", encoding="utf-8")
        self.count = 0
        self.interesting = []
        self.urls = []
        self.last_url = {}
        self.bound = {}          # target id -> CDPSession
        self.pending = {}        # CDP requestId -> (method, url)

    def record(self, row):
        self.fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.fh.flush()  # a capture killed with Ctrl-C must still be readable
        self.count += 1

    def note_url(self, target_id, url):
        """Record address-bar changes, as seen by Chrome's own /json endpoint.

        config/tapstitch.json wants urls.new_product and urls.products_list
        "filled from the address bar during the first session". This reads /json
        rather than a Playwright Page, because a Page handle reports the URL it
        last saw once its target is swapped.
        """
        if not url or url == self.last_url.get(target_id):
            return
        self.last_url[target_id] = url
        if url.startswith("about:"):
            return
        self.urls.append(url)
        self.record({
            "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": "navigation",
            "url": redact_url(url),
        })
        print(f"  -- now at {url[:130]}", flush=True)

    def bind(self, ctx, page, target_id):
        if target_id in self.bound:
            return
        try:
            sess = ctx.new_cdp_session(page)
            sess.send("Network.enable")
        except Exception as e:
            print(f"  !! could not attach to {target_id[:8]}: {type(e).__name__}",
                  flush=True)
            return
        self.bound[target_id] = sess
        sess.on("Network.requestWillBeSent", lambda e: self.on_request(sess, e))
        sess.on("Network.responseReceived", self.on_response)
        print(f"  .. recording target {target_id[:8]}", flush=True)

    def on_request(self, sess, e):
        req = e.get("request", {})
        url = req.get("url", "")
        if not url or SKIP_URL.search(url):
            return
        method = req.get("method", "")
        rtype = e.get("type", "")
        if rtype not in ("XHR", "Fetch") and method == "GET":
            return
        self.pending[e.get("requestId")] = (method, url)

        ctype = ""
        for k, v in (req.get("headers") or {}).items():
            if k.lower() == "content-type":
                ctype = v
        body = req.get("postData")
        if body is None and req.get("hasPostData"):
            # Chrome omits large bodies from the event; ask for them explicitly.
            try:
                body = sess.send("Network.getRequestPostData",
                                 {"requestId": e["requestId"]}).get("postData")
            except Exception:
                body = "<post body unavailable>"
        if body and ("multipart/form-data" in ctype or "octet-stream" in ctype):
            body = f"<{ctype} body not recorded>"   # the print file itself

        safe = redact_url(url)
        self.record({
            "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": "request",
            "method": method,
            "url": safe,
            "resource_type": rtype,
            "headers": redact_headers(req.get("headers")),
            "body": redact_body(body[:MAX_BODY]) if body else None,
        })
        if method != "GET" and INTERESTING.search(safe):
            self.interesting.append((method, safe))
            print(f"  >> {method} {safe[:130]}", flush=True)

    def on_response(self, e):
        rid = e.get("requestId")
        if rid not in self.pending:
            return
        method, url = self.pending.pop(rid)
        resp = e.get("response", {})
        self.record({
            "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": "response",
            "status": resp.get("status"),
            "method": method,
            "url": redact_url(url),
            "content_type": resp.get("mimeType", ""),
            "body": None,  # fetched separately only when asked for; see --bodies
        })

    def close(self):
        self.fh.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=float, default=20,
                    help="how long to listen before stopping (default 20)")
    a = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = OUT_DIR / f"capture-{stamp}.jsonl"

    p, browser = connect(TAPSTITCH)
    cap = Capture(path)
    try:
        print(f"Recording to {path}")
        print(f"Listening for {a.minutes:g} minutes. Ctrl-C stops early and keeps "
              f"what it has.\n")
        print("In the Chrome window: open the editor, build ONE design by hand, "
              "and save it.")
        print("Calls worth reading are flagged with >> as they happen.\n")

        deadline = time.time() + a.minutes * 60
        while time.time() < deadline:
            targets = page_targets(TAPSTITCH)
            for tid, url in targets.items():
                cap.note_url(tid, url)

            # Match live targets to Playwright pages by URL so each target gets
            # exactly one CDP session. Re-listing pages each pass picks up tabs
            # opened after connect.
            unbound = [t for t in targets if t not in cap.bound]
            if unbound:
                for ctx in browser.contexts:
                    for page in ctx.pages:
                        try:
                            purl = page.url
                        except Exception:
                            continue
                        for tid in list(unbound):
                            if targets[tid] == purl:
                                cap.bind(ctx, page, tid)
                                unbound.remove(tid)
                                break
            for tid in list(cap.bound):
                if tid not in targets:
                    cap.bound.pop(tid, None)   # tab closed

            # MUST pump Playwright, not time.sleep(). The sync API dispatches
            # events only while the caller is inside a Playwright call; a bare
            # sleep blocks the greenlet and every Network.* callback queues up
            # unseen. This one line is the difference between a capture that
            # records and one that prints "recording" and writes nothing.
            waited = False
            for ctx in browser.contexts:
                for page in ctx.pages:
                    try:
                        page.wait_for_timeout(1000)
                        waited = True
                    except Exception:
                        continue
                    break
                if waited:
                    break
            if not waited:
                time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        cap.close()
        try:
            browser.close()
        finally:
            p.stop()

    print(f"\n{cap.count} calls recorded to {path}")
    if cap.interesting:
        print(f"\n{len(cap.interesting)} non-GET calls matched the things we care about:")
        seen = set()
        for method, url in cap.interesting:
            base = url.split("?")[0]
            if (method, base) in seen:
                continue
            seen.add((method, base))
            print(f"  {method} {base}")
    else:
        print("\nNothing matched. If you did save a design, the call may be a "
              "websocket or a GraphQL POST to a generic endpoint — read the file.")

    if cap.urls:
        print(f"\nAddress bar went through {len(cap.urls)} pages, in order:")
        for u in cap.urls:
            print(f"  {u}")


if __name__ == "__main__":
    main()
