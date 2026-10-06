"""Attach to a real Chrome that Evan logged into by hand, over CDP.

Why this shape rather than a Playwright-launched browser: Cloudflare blocks
Playwright-launched browsers outright. The working pattern, proven since 18 Aug
2026 on the old supplier's editor automation, is that Evan logs in once inside a
REAL Google Chrome running a dedicated profile with a debug port open, and
scripts attach to that Chrome afterwards. The session lives in the profile and
survives across days and reboots. No script ever sees his password.

The profile directories are gitignored and iCloud-excluded. Never commit one,
never print its contents.
"""

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

PROJECT_ROOT = Path(__file__).resolve().parent
CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


@dataclass
class Site:
    """One automated site: where to log in, how to tell you are logged in, and
    which Chrome profile and debug port belong to it. Separate ports let
    two automated browsers run at the same time."""
    name: str
    profile_dir: Path
    debug_port: int
    login_url: str
    app_url: str
    app_url_prefix: str
    logged_out_marker: str = "login"

    @property
    def cdp_url(self):
        return f"http://localhost:{self.debug_port}"


TAPSTITCH = Site(
    name="Tapstitch",
    profile_dir=PROJECT_ROOT / ".playwright.nosync" / "tapstitch-profile",
    debug_port=9223,  # 9222 belonged to the old supplier's profile
    login_url="https://www.tapstitch.com/login",
    app_url="https://www.tapstitch.com/dashboard",
    app_url_prefix="https://www.tapstitch.com/",
)


def cdp_alive(site):
    try:
        return requests.get(f"{site.cdp_url}/json/version", timeout=1).status_code == 200
    except Exception:
        return False


def _ensure_page_target(site):
    """Make sure at least one page target exists on the CDP endpoint.

    If the human closes the dedicated Chrome's window, Chrome keeps running
    windowless on macOS. cdp_alive() still reports true, but /json then lists
    zero "page" targets, and with no page there is no browser context for
    Playwright to attach to: connect_over_cdp fails with "Browser context
    management is not supported" even though CDP is reachable. Creating one page
    restores a context. PUT, not GET: Chrome's /json/new requires PUT.
    """
    try:
        targets = requests.get(f"{site.cdp_url}/json", timeout=2).json()
    except Exception:
        return
    if any(t.get("type") == "page" for t in targets):
        return
    try:
        requests.put(f"{site.cdp_url}/json/new?about:blank", timeout=2)
    except Exception:
        pass


def ensure_chrome(site, open_url=None):
    if cdp_alive(site):
        _ensure_page_target(site)
        return
    if not Path(CHROME_BINARY).exists():
        raise RuntimeError(f"Google Chrome not found at {CHROME_BINARY}. "
                           f"Edit CHROME_BINARY in browser_session.py.")
    site.profile_dir.parent.mkdir(exist_ok=True)
    cmd = [CHROME_BINARY, f"--user-data-dir={site.profile_dir}",
           f"--remote-debugging-port={site.debug_port}",
           "--no-first-run", "--no-default-browser-check"]
    if open_url:
        cmd.append(open_url)
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    start = time.time()
    while time.time() - start < 15:
        if cdp_alive(site):
            _ensure_page_target(site)
            return
        time.sleep(0.5)
    raise RuntimeError(f"Chrome did not come up on localhost:{site.debug_port}. "
                       f"Check whether the port is taken or Chrome is running elsewhere.")


def _url_looks_logged_in(site, url):
    return url.startswith(site.app_url_prefix) and site.logged_out_marker not in url


def _page_logged_in(site, page):
    if not _url_looks_logged_in(site, page.url):
        return False
    try:
        return not page.locator("input[type='password']").is_visible()
    except Exception:
        return False  # page navigating mid-check; poll again


def login(site):
    """Open the login page and wait for Evan to finish. Automates nothing.

    Cross-origin navigations during login (login page, Cloudflare challenge,
    back into the app) make Chrome swap the tab's renderer process and CDP
    target, so a long-lived connection's page list goes stale. Poll Chrome's own
    /json endpoint, which always reflects live targets, then open a short-lived
    connection to confirm.
    """
    try:
        ensure_chrome(site, open_url=site.login_url)
    except RuntimeError as e:
        print(str(e))
        return 1
    print(f"Log in to {site.name} inside the Chrome window that just opened. "
          f"Waiting up to 5 minutes.")
    with sync_playwright() as p:
        start = time.time()
        while time.time() - start < 300:
            try:
                targets = requests.get(f"{site.cdp_url}/json", timeout=2).json()
            except Exception:
                time.sleep(2)
                continue
            if any(t.get("type") == "page" and _url_looks_logged_in(site, t.get("url", ""))
                   for t in targets):
                browser = None
                try:
                    browser = p.chromium.connect_over_cdp(site.cdp_url)
                    for ctx in browser.contexts:
                        for page in ctx.pages:
                            if _page_logged_in(site, page):
                                print(f"Logged in. The session lives in the dedicated Chrome "
                                      f"profile; you can close the window or leave it open.")
                                return 0
                except Exception:
                    pass  # target churn during login navigations; keep polling
                finally:
                    if browser:
                        browser.close()
            time.sleep(2)
    print(f"Login not completed within 5 minutes. Re-run to try again.")
    return 1


def check(site):
    """Verify the saved session still works. Returns 0 when logged in."""
    try:
        ensure_chrome(site)
    except RuntimeError as e:
        print(str(e))
        return 1
    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.connect_over_cdp(site.cdp_url)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.new_page()
            try:
                page.goto(site.app_url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
            if f"/{site.logged_out_marker}" in page.url:
                page.close()
                print(f"Session expired. Re-run the login command.")
                return 1
            try:
                # An unauthenticated visit can redirect with a variable delay, so
                # the login FORM is the signal, not the URL.
                page.locator("input[type='password']").wait_for(state="visible", timeout=20000)
                page.close()
                print("Session expired. Re-run the login command.")
                return 1
            except PlaywrightTimeout:
                if not page.url.startswith(site.app_url_prefix):
                    page.close()
                    print(f"Could not reach {site.name}. Session state unknown.")
                    return 1
                page.close()
                print("Session is valid.")
                return 0
        finally:
            if browser:
                browser.close()


def connect(site):
    """A live Playwright browser attached to the dedicated Chrome. Caller closes it."""
    ensure_chrome(site)
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(site.cdp_url)
    return p, browser
