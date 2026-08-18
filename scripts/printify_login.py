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
PROFILE_DIR = PROJECT_ROOT / ".playwright" / "chrome-profile"
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


def ensure_chrome(open_url=None):
    """Ensure Chrome is running and reachable over CDP.

    If not running, launch it with the dedicated profile and debug port.
    If open_url is given, pass it as a URL to open in the new window.
    """
    if cdp_alive():
        return

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
            return
        time.sleep(0.5)

    raise RuntimeError(
        "Chrome failed to start or is not reachable on localhost:9222. "
        "Check if the port is blocked or Chrome is already running elsewhere."
    )


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
    ensure_chrome(open_url=LOGIN_URL)
    print("Log in inside the Chrome window that just opened. Waiting up to 5 minutes.")

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            start = time.time()
            while time.time() - start < 300:
                for context in browser.contexts:
                    for page in context.pages:
                        url = page.url
                        if (
                            url.startswith("https://printify.com/app")
                            and "login" not in url
                        ):
                            # Guard against false positives during redirect: check that
                            # the password input is not visible (indicates login page).
                            try:
                                page.locator("input[type='password']").is_visible(timeout=0)
                                # If visible, still on login page; continue polling.
                                continue
                            except Exception:
                                # Not visible; page is logged in.
                                pass
                            print("Logged in. Session lives in the dedicated Chrome profile; you can close the window or leave it open.")
                            return 0
                time.sleep(2)
            print("Login not completed within 5 minutes. Re-run scripts/printify_login.py to try again.")
            return 1
        finally:
            if browser:
                browser.close()


def check():
    """Verify the session is still valid.

    Attach to Chrome, open a test page to the app, and check if logged in.

    Note: unauthenticated visits to /app/store/products redirect to /app/auth/login
    with variable delay (observed 8-12 seconds). The URL alone is not reliable for
    detecting logged-out state; the login form (input[type="password"]) is the signal.
    """
    try:
        ensure_chrome()
    except RuntimeError as e:
        print(str(e))
        return 1

    with sync_playwright() as p:
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
                page.close()
                print("Session expired. Re-run scripts/printify_login.py (log in inside the Chrome window).")
                return 1

            # Otherwise, wait up to 20 seconds for the login form to appear.
            # If it does, user is logged out. If the wait times out, assume logged in.
            try:
                page.locator("input[type='password']").wait_for(state="visible", timeout=20000)
                # Login form appeared; definitely logged out.
                page.close()
                print("Session expired. Re-run scripts/printify_login.py (log in inside the Chrome window).")
                return 1
            except PlaywrightTimeout:
                # Login form did not appear within 20 seconds; treat as logged in.
                page.close()
                print("Session is valid.")
                return 0
        finally:
            if browser:
                browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the saved session still works")
    args = parser.parse_args()
    sys.exit(check() if args.check else login())


if __name__ == "__main__":
    main()
