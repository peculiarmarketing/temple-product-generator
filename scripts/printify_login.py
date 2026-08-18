"""Headed Printify login for the date-layer automation.

Evan types credentials himself in the opened browser window. This script
never sees, stores, or types credentials. It waits for the app to reach a
logged-in state, then saves browser storage state (cookies plus local
storage) to .playwright/printify-session.json.

The session file is gitignored. Never commit it, never print its contents.

Login:  ./.venv.nosync/bin/python scripts/printify_login.py
Check:  ./.venv.nosync/bin/python scripts/printify_login.py --check
"""

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_FILE = PROJECT_ROOT / ".playwright" / "printify-session.json"
LOGIN_URL = "https://printify.com/app/login"
APP_URL = "https://printify.com/app/store/products"


def _is_logged_in(page):
    return page.url.startswith("https://printify.com/app") and "login" not in page.url


def login():
    SESSION_FILE.parent.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(LOGIN_URL)
        print("Log in inside the browser window. Waiting up to 5 minutes.")
        page.wait_for_url(
            lambda url: url.startswith("https://printify.com/app") and "login" not in url,
            timeout=300_000,
        )
        page.wait_for_load_state("networkidle")
        context.storage_state(path=str(SESSION_FILE))
        browser.close()
    print(f"Session saved to {SESSION_FILE.relative_to(PROJECT_ROOT)}")


def check():
    if not SESSION_FILE.exists():
        print("No session file. Run scripts/printify_login.py first.")
        return 1
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_FILE))
        page = context.new_page()
        page.goto(APP_URL, wait_until="networkidle")
        ok = _is_logged_in(page)
        browser.close()
    if ok:
        print("Session is valid.")
        return 0
    print("Session expired. Re-run scripts/printify_login.py (headed login).")
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the saved session still works")
    args = parser.parse_args()
    sys.exit(check() if args.check else login() or 0)


if __name__ == "__main__":
    main()
