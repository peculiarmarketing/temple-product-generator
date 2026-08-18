"""Playwright driver for the Printify editor date-layer flow.

Mirrors Evan's manual click path exactly as recorded in
docs/discovery/2026-08-date-layer-editor-notes.md. That document is the
authority for the flow; update it and config/date_layer.json together
whenever Printify changes the editor.

Session model: Playwright-launched browsers fail Printify's Cloudflare
Turnstile challenge regardless of human input (automation fingerprint), so
this driver never launches a browser of its own. It attaches over the
Chrome DevTools Protocol to Evan's real, already-logged-in Chrome, managed
by scripts/printify_login.py (ensure_chrome(), CDP_URL). Exiting the
context manager only disconnects Playwright; it never closes Chrome.

Never clicks Save product except inside apply(), which is the method Task
6 (and a human-supervised 5b run) calls for a real, one-time application.
Never deletes or moves existing layers. Never writes print_areas over the
API; the API cannot write text layers at all (settled Phase 1 finding).
"""

from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from scripts.printify_login import CDP_URL, ensure_chrome

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class LoggedOut(Exception):
    """The attached Chrome session is not logged into Printify.

    Re-run scripts/printify_login.py (log in inside the Chrome window that
    opens) and retry. Do not attempt to log in from this module.
    """


def _locator(page, sel):
    if sel["kind"] == "role":
        if "name" in sel:
            return page.get_by_role(sel["role"], name=sel["name"], exact=sel.get("exact", False))
        return page.get_by_role(sel["role"])
    if sel["kind"] == "label":
        return page.get_by_label(sel["label"])
    if sel["kind"] == "text":
        return page.get_by_text(sel["text"], exact=sel.get("exact", False))
    if sel["kind"] == "css":
        return page.locator(sel["css"])
    raise ValueError(f"unknown selector kind: {sel['kind']}")


class EditorDriver:
    """Context manager that drives the Printify product editor over CDP.

    Usage:
        with EditorDriver(cfg) as driver:
            driver.apply(product_id, plan)

    apply() is the only entry point Task 6 needs; the rest are building
    blocks used by the dry test and by repair sessions.
    """

    def __init__(self, cfg):
        self.cfg = cfg

    def __enter__(self):
        ensure_chrome()
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.connect_over_cdp(CDP_URL)
        except Exception as exc:
            self._pw.stop()
            raise RuntimeError(
                "Could not attach to the running Chrome over CDP. This "
                "used to happen every time (see task-5-report.md for the "
                "history), but ensure_chrome() now creates a page target "
                "before returning, which fixed it. If it still fails, "
                "something else is wrong; do not add --enable-automation "
                "or any other fingerprint-affecting flag to work around it."
            ) from exc
        self._context = (
            self._browser.contexts[0]
            if self._browser.contexts
            else self._browser.new_context()
        )
        self.page = self._context.new_page()
        return self

    def __exit__(self, *exc):
        # This connection attaches to Evan's real Chrome; closing it only
        # disconnects Playwright from Chrome, it does not close the browser.
        self._browser.close()
        self._pw.stop()
        return False

    def _sel(self, name):
        return _locator(self.page, self.cfg["selectors"][name])

    def _assert_logged_in(self):
        marker = self._sel("login_form_marker")
        if marker.is_visible(timeout=2000):
            raise LoggedOut("editor redirected to a login form")

    def _close_info_modal_if_present(self):
        """Close the "Important product information" modal that can cover
        the editor on open. No-op if it is not showing."""
        dialog = self._sel("info_modal")
        try:
            if dialog.is_visible(timeout=3000):
                self._sel("info_modal_close_button").first.click()
        except Exception:
            pass

    def open_product(self, product_id):
        url = self.cfg["editor_url_template"].format(product_id=product_id)
        self.page.goto(url, wait_until="networkidle")
        self._assert_logged_in()
        self._sel("variants_panel_heading").wait_for(timeout=30_000)
        self._close_info_modal_if_present()
        self.switch_to_back_side()

    def switch_to_back_side(self):
        self._sel("back_side_button").click()

    def has_text_layer(self):
        """In-editor idempotency guard, independent of the API-side gate in
        scripts/add_date_layer.py (gate()). Checks the currently viewed
        side only; open_product() already switches to the back side, where
        the personalization text layer lives. Verified live: the marker is
        present on the back side of Brigham City (which already has its
        date layer) and absent on the front side of the same product.

        Uses a bounded wait rather than a bare count(): count() is a
        synchronous snapshot with no auto-wait, so a slow panel render
        right after switch_to_back_side()'s click could transiently read 0
        on a product that does have a date layer. In apply(), a false
        False here would add a duplicate layer, exactly what this guard
        exists to prevent, so absence is only concluded after giving the
        DOM up to 5 seconds to settle.
        """
        try:
            self._sel("existing_text_layer_marker").first.wait_for(state="attached", timeout=5000)
            return True
        except PlaywrightTimeout:
            return False

    def _select_group(self, group):
        """Select the variant group to edit by clicking its color swatch in
        the "Variants and layers" panel.

        Verified live against Brigham City: each swatch is a button whose
        accessible name is the exact colorway name (e.g. "Graphite"), with
        no visible text, confirmed via aria-label in the DOM
        (data-testid="colorChipButton"). The blue "variant-specific design"
        dot shown on some swatches is a pure CSS decoration; it is not
        exposed as a distinguishing accessible attribute (every swatch's
        accessibility subtree is structurally identical whether or not it
        has a dot).

        group["colorway"] names the exact accessible name of the dark
        swatch to click, resolved by
        scripts/add_date_layer.py:group_colorway() from the product's live
        color option and the group's first variant id. An earlier version
        of this method picked the dark swatch by position in
        config["dark_colorways_for_reference"] (group["index"]); that
        misclicked whenever a product's dark-group count or order did not
        line up with that fixed four-entry list (confirmed: the standard
        five-group product has four dark groups at global indices 1..4,
        one past the list's end, causing both wrong clicks and an
        eventual IndexError). dark_colorways_for_reference remains in
        config as documentation of the reference product's dark colorway
        names; it is no longer used to resolve which swatch a given dark
        group maps to.

        When group["dark"] is false, the light/default group is reached
        exactly as before: by clicking whichever on-screen swatch's name
        is not in dark_colorways_for_reference (the editor opens on a dark
        variant-specific design, so this is what switches to the shared
        default design; any non-dark swatch reaches the same default
        design, per the discovery notes).

        Verified live end to end on Brigham City (index-based, prior
        version): clicking dark index 0 selected Graphite (panel showed
        "Revert Graphite to default design"), clicking the light path
        switched away from any variant-specific design (the "Currently
        editing variant specific design" status disappeared), and clicking
        dark index 3 reselected True Navy. No layer was added or changed
        during that check; only the currently-viewed design switched, the
        same as clicking "Back side" does. Re-verified live against the
        colorway-name path in the Task 6b fix: see task-6-report.md for
        the transition log.
        """
        dark_names = self.cfg["dark_colorways_for_reference"]
        if not group.get("dark"):
            swatches = self._sel("variant_swatch_group")
            for i in range(swatches.count()):
                candidate = swatches.nth(i)
                if candidate.get_attribute("aria-label") not in dark_names:
                    candidate.click()
                    return
            raise RuntimeError("no light (non-variant-specific) swatch found")

        colorway = group.get("colorway")
        if colorway is None:
            raise RuntimeError(
                "dark group has no resolved colorway (product's color "
                "option or variant options did not match); cannot pick a "
                "swatch"
            )
        button = self.page.get_by_role("button", name=colorway, exact=True)
        if button.count() == 0:
            raise RuntimeError(f"no swatch found for colorway {colorway!r}")
        button.click()

    def add_date_layer_to_current_group(self, dark):
        """Add the personalization text layer to the currently selected
        variant group and style it. Uses "Add personalizable text" (not
        plain "Add text"): the discovery notes record that this button
        creates a layer already wired for personalization, so no separate
        personalization-toggle step is needed."""
        cfg = self.cfg
        self._sel("personalize_button").click()
        self._sel("personalize_panel_heading").wait_for(timeout=10_000)
        self._sel("add_personalizable_text_button").click()
        self._sel("text_input").fill(cfg["placeholder_text"])
        self._sel("layer_toolbar_font_dropdown").first.click()
        self.page.get_by_text(cfg["font_family"], exact=True).click()
        color = cfg["font_color_dark_groups"] if dark else cfg["font_color_light_groups"]
        self._sel("layer_toolbar_color_button").click()
        self._sel("layer_toolbar_color_hex_input").fill(color.lstrip("#"))
        self.page.keyboard.press("Enter")

    def position_layer(self, left_pct, top_pct):
        """Type the box dimensions and the top-left position directly.

        left_pct and top_pct are precomputed by
        scripts/add_date_layer.py:editor_percent(), which reproduces Evan's
        mouse-snap centering result (calibrated digit for digit against the
        Brigham City draft). Typing both values is simpler and more
        deterministic than reproducing the snap-and-nudge by mouse.

        Verified live: selecting an existing text layer shows the Width,
        Height, Position left, and Position top fields immediately, without
        needing to click the toolbar's "Position" button first (clicking it
        twice on an already-selected layer did not hide or show anything).
        The click is kept here anyway, matching the discovery notes'
        description of the flow for a layer that was *just created* rather
        than one that already existed; confirm in 5b whether it is truly a
        no-op right after add_date_layer_to_current_group(), too.
        """
        cfg = self.cfg
        self._sel("layer_toolbar_position_button").click()
        self._sel("width_input").fill(str(cfg["box_width_in"]))
        self._sel("height_input").fill(str(cfg["box_height_in"]))
        self._sel("position_left_input").fill(str(left_pct))
        self._sel("position_top_input").fill(str(top_pct))
        self._sel("position_top_input").press("Enter")

    def save(self):
        self._sel("save_button").click()
        self.page.wait_for_load_state("networkidle")

    def apply(self, product_id, plan):
        """Full recorded flow for one product: the default/light group
        first with black text, then each dark swatch with white text.

        plan["groups"] entries are {"dark": bool, "colorway": str | None},
        built by scripts/add_date_layer.py:build_plan(). _select_group()
        resolves each dark entry's swatch by matching "colorway" to a
        button's accessible name, not by position in a fixed reference
        list; a per-group RuntimeError from an unresolved or missing
        colorway propagates out of apply() and is treated as a per-product
        failure by main()'s caller.

        Never called during Task 5a; the first real caller is Task 6 or a
        human-supervised 5b run.
        """
        self.open_product(product_id)
        if self.has_text_layer():
            return
        for group in plan["groups"]:
            self._select_group(group)
            self.add_date_layer_to_current_group(group["dark"])
            self.position_layer(plan["left_pct"], plan["top_pct"])
        self.save()
