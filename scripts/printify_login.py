"""Headed Printify login for the date-layer automation.

Evan logs in inside his real Google Chrome browser (dedicated profile). This
script attaches to Chrome over CDP (Chrome DevTools Protocol) and monitors for
login completion, then saves the session inside the Chrome profile. The session
persists in the dedicated browser profile across runs.

The profile directory is gitignored. Never commit it, never print its contents.

Login:  ./.venv.nosync/bin/python scripts/printify_login.py
Check:  ./.venv.nosync/bin/python scripts/printify_login.py --check
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = PROJECT_ROOT / ".playwright.nosync" / "chrome-profile"
CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9222
CDP_URL = f"http://localhost:{DEBUG_PORT}"
LOGIN_URL = "https://printify.com/app/login"
APP_URL = "https://printify.com/app/store/products"


def cdp_alive():
    """Check if Chrome DevTools Protocol is reachable."""
    try:
        response = requests.get(f"{CDP_URL}/json/version", timeout=1)
        return response.status_code == 200
    except Exception:
        return False


def _ensure_page_target():
    """Make sure at least one page target exists on the CDP endpoint.

    Mechanism: if the human closes the dedicated Chrome's window, Chrome
    keeps running windowless on macOS. cdp_alive() still reports true, but
    http://localhost:9222/json then lists zero "page" targets. With no page
    there is no browser context for Playwright to attach to, so
    connect_over_cdp's handshake fails with "Browser context management is
    not supported" even though the CDP endpoint itself is reachable.
    Creating one page target restores a context. PUT, not GET: Chrome's
    /json/new endpoint requires PUT.
    """
    try:
        targets = requests.get(f"{CDP_URL}/json", timeout=2).json()
    except Exception:
        return
    if any(target.get("type") == "page" for target in targets):
        return
    try:
        requests.put(f"{CDP_URL}/json/new?about:blank", timeout=2)
    except Exception:
        pass


def ensure_chrome(open_url=None):
    """Ensure Chrome is running and reachable over CDP.

    If not running, launch it with the dedicated profile and debug port.
    If open_url is given, pass it as a URL to open in the new window.
    """
    if cdp_alive():
        _ensure_page_target()
        return

    if not Path(CHROME_BINARY).exists():
        raise RuntimeError(
            f"Google Chrome not found at {CHROME_BINARY}. "
            "Edit CHROME_BINARY in scripts/printify_login.py."
        )

    PROFILE_DIR.parent.mkdir(exist_ok=True)
    cmd = [
        CHROME_BINARY,
        f"--user-data-dir={PROFILE_DIR}",
        f"--remote-debugging-port={DEBUG_PORT}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if open_url:
        cmd.append(open_url)

    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    start = time.time()
    while time.time() - start < 15:
        if cdp_alive():
            _ensure_page_target()
            return
        time.sleep(0.5)

    raise RuntimeError(
        "Chrome failed to start or is not reachable on localhost:9222. "
        "Check if the port is blocked or Chrome is already running elsewhere."
    )


def _url_looks_logged_in(url):
    """True when url is inside the Printify app and is not the login page."""
    return url.startswith("https://printify.com/app") and "login" not in url


def _page_logged_in(page):
    """True when this page is inside the Printify app and shows no login form."""
    if not _url_looks_logged_in(page.url):
        return False
    try:
        return not page.locator("input[type='password']").is_visible()
    except Exception:
        # Page navigating mid-check; treat as not logged in and poll again.
        return False


def login():
    """Open login URL in Chrome and wait for successful login.

    The human logs in inside the Chrome window. This script monitors for the
    logged-in state by checking that the URL starts with https://printify.com/app,
    does not contain "login", and the password input field is not visible.
    Does not automate any interaction; human does all input.

    Note: unauthenticated visits to /app/store/products redirect to /app/auth/login
    with variable delay (observed 8-12 seconds). The URL alone is not reliable for
    detecting logged-out state; the login form (input[type="password"]) is the signal.
    """
    try:
        ensure_chrome(open_url=LOGIN_URL)
    except RuntimeError as e:
        print(str(e))
        return 1
    print("Log in inside the Chrome window that just opened. Waiting up to 5 minutes.")

    # Cross-origin navigations during login (login page, Cloudflare challenge, back
    # into the app) make Chrome swap the tab's renderer process and CDP target. A
    # long-lived CDP connection's page list goes stale and stops reflecting the live
    # tab, so poll Chrome's own /json endpoint (which always reflects live targets)
    # for a candidate URL first, then open a short-lived connection to confirm it.
    with sync_playwright() as p:
        start = time.time()
        while time.time() - start < 300:
            try:
                targets = requests.get(f"{CDP_URL}/json", timeout=2).json()
            except Exception:
                time.sleep(2)
                continue

            candidate = any(
                target.get("type") == "page" and _url_looks_logged_in(target.get("url", ""))
                for target in targets
            )

            if candidate:
                browser = None
                try:
                    browser = p.chromium.connect_over_cdp(CDP_URL)
                    for context in browser.contexts:
                        for page in context.pages:
                            if _page_logged_in(page):
                                print("Logged in. Session lives in the dedicated Chrome profile; you can close the window or leave it open.")
                                return 0
                except Exception:
                    # Target churn during login navigations can break a single attach; keep polling.
                    pass
                finally:
                    if browser:
                        browser.close()

            time.sleep(2)

    print("Login not completed within 5 minutes. Re-run scripts/printify_login.py to try again.")
    return 1


def _safe_close(page):
    try:
        page.close()
    except Exception:
        pass


def check():
    """Verify the session is still valid.

    Attach to Chrome, open a test page to the app, and check if logged in.

    Note: unauthenticated visits to /app/store/products redirect to /app/auth/login
    with variable delay (observed 8-12 seconds). The URL alone is not reliable for
    detecting logged-out state; the login form (input[type="password"]) is the signal.

    Cross-origin activity in the dedicated Chrome window (a stray navigation, the
    human closing the tab) can swap the CDP target mid-wait, the same churn hazard
    login() polls around (see its comment above). A closed target raises
    TargetClosedError, not PlaywrightTimeout, so it needs its own retry on a fresh
    connection rather than being left to crash with a traceback that, once main()
    turns it into exit code 1, reads identically to a genuinely expired session.
    """
    try:
        ensure_chrome()
    except RuntimeError as e:
        print(str(e))
        return 1

    attempts = 3
    with sync_playwright() as p:
        for attempt in range(1, attempts + 1):
            browser = None
            try:
                browser = p.chromium.connect_over_cdp(CDP_URL)
                context = browser.contexts[0] if browser.contexts else browser.new_context()
                page = context.new_page()
                try:
                    page.goto(APP_URL, wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    pass

                # Fast path: if already redirected to auth/login, definitely logged out.
                if "auth/login" in page.url:
                    _safe_close(page)
                    print("Session expired. Re-run scripts/printify_login.py (log in inside the Chrome window).")
                    return 1

                # Otherwise, wait up to 20 seconds for the login form to appear.
                # If it does, user is logged out. If the wait times out, assume logged in.
                try:
                    page.locator("input[type='password']").wait_for(state="visible", timeout=20000)
                    # Login form appeared; definitely logged out.
                    _safe_close(page)
                    print("Session expired. Re-run scripts/printify_login.py (log in inside the Chrome window).")
                    return 1
                except PlaywrightTimeout:
                    # Login form did not appear within 20 seconds; treat as logged in,
                    # unless the page never actually reached the app (network/navigation
                    # failure landing on about:blank would otherwise look "valid" too).
                    if not page.url.startswith("https://printify.com/app"):
                        _safe_close(page)
                        print("Could not reach Printify (network or navigation failure). Session state unknown.")
                        return 1
                    _safe_close(page)
                    print("Session is valid.")
                    return 0
            except Exception:
                # Target closed mid-check; not a signal either way. Retry on a fresh
                # connection instead of letting it surface as an uncaught crash.
                if attempt == attempts:
                    print("Could not verify session (Chrome tab kept closing mid-check). Session state unknown; try again.")
                    return 1
                time.sleep(1)
            finally:
                if browser:
                    try:
                        browser.close()
                    except Exception:
                        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the saved session still works")
    args = parser.parse_args()
    sys.exit(check() if args.check else login())


if __name__ == "__main__":
    main()
