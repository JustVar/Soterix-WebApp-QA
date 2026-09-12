"""Camera Hardware Page Object Model.

Page object for Soterix C2C camera web UI (rebranded VCA).
Handles HTTP Basic Auth, main live view page, and Setup admin pages.

Supports single-lens and multi-lens cameras via a `camera_config` dict
passed at construction. Same UI across models - only expected values
(model name, license count, etc.) differ.

Access: http://<IP>/cgi-bin/index.cgi (main), /cgi-bin/admin/setup_main.cgi (setup)
Auth: HTTP Basic Auth (handled by browser context, not URL)
"""
import os
import re
import time

import pytest
from playwright.sync_api import BrowserContext, Page, expect

# Default camera config - used when no config dict provided (legacy env-var mode)
CAMERA_IP = os.environ.get("C2C_CAMERA_IP", "10.2.0.129")
CAMERA_USER = os.environ.get("C2C_CAMERA_USER", "root")
CAMERA_PASS = os.environ.get("C2C_CAMERA_PASS", "")  # required; the c2c conftest skips when unset


class CameraHardwarePage:
    """Page object for the camera's built-in web UI.

    Args:
        page: Playwright Page (must already be authenticated via browser
            context http_credentials - this class does not handle auth).
        config: Optional camera profile dict from c2c_cameras.yaml. When
            provided, tests can read expected values (model, license count,
            multi_lens, etc.) from self.config instead of hardcoding.
    """

    def __init__(self, page: Page, config: dict | None = None):
        self.page = page
        self.config = config or {
            "ip": CAMERA_IP, "user": CAMERA_USER, "password": CAMERA_PASS,
            "model": "BC-5V-1", "multi_lens": False, "lens_count": 1,
            "expected_license": "ProAI 1ch", "expected_license_count": 1,
        }
        self.ip = self.config["ip"]
        self.setup_url = f"http://{self.ip}/cgi-bin/admin/setup_main.cgi"
        self.main_url = f"http://{self.ip}/cgi-bin/index.cgi"

        # --- Main Page (Live View) ---
        self.setup_button = page.locator("button:has-text('Setup')")
        self.fullscreen_button = page.locator("button:has-text('Full screen')")
        self.channel_select = page.locator("select").first
        self.focus_button = page.locator("button:has-text('Focus')")
        self.calibrate_button = page.locator("button:has-text('Calibrate')")

    # ------------------------------------------------------------------ #
    #  Navigation
    # ------------------------------------------------------------------ #

    def navigate_to_main(self):
        """Navigate to the camera main live view page."""
        self.page.goto(self.main_url, wait_until="domcontentloaded", timeout=15000)
        return self

    def navigate_to_setup(self):
        """Navigate directly to the setup/admin page."""
        self.page.goto(self.setup_url, wait_until="domcontentloaded", timeout=15000)
        return self

    # The setup page (probed on camera .129, 09/11/2026): the sections are
    # <ul id=...> under #sub_menu whose own text is the name ("> NETWORK"),
    # the sub-sections are <li class=select_minor id=... href=...> inside
    # them, and the content pane is #tabs with a <div class=contentTitle>
    # heading whose text is NOT always the menu text ('MOTION' opens 'MOTION
    # DETECTION CONFIGURATION'). A bare text='X' matched the menu item and
    # the heading at once, and Playwright's strict mode refused the click
    # and the expect: 23 of 29 tests per camera failed that way on the
    # first real run from spartan1. Clicks go to the menu; checks to the
    # heading; the navigated signal is the heading changing.
    def _menu_section(self, section_text: str):
        """The <ul> under #sub_menu whose text starts with the section name.
        Case-insensitive: the Soterix section renders as 'soterix'.

        has_text sees the ul's textContent: the fold glyph, the name, then
        the entries with nothing between ('> NETWORKSTATUSNETWORK SETTINGS'),
        so the name is anchored at the start only. A line-end anchor matched
        nothing and every section click timed out (nightly 09/11/2026);
        measured on 10.2.0.171."""
        pattern = re.compile(rf"^\s*[>\u2228v]?\s*{re.escape(section_text)}", re.I)
        # .first: one section starts with the name; no section name is a
        # prefix of another's (VIDEO & AUDIO is asked for in full)
        return self.page.locator("#sub_menu > ul").filter(has_text=pattern).first

    def _menu_item(self, subsection_text: str):
        """The <li> under #sub_menu whose whole text is the sub-section name.
        Case-insensitive: 'RTSP authentication', 'Enable', 'connect' render
        in mixed case while the tests name them in capitals."""
        pattern = re.compile(rf"^\s*{re.escape(subsection_text)}\s*$", re.I)
        # .first: the pattern is anchored to the li's whole text, one entry has it
        return self.page.locator("#sub_menu li").filter(has_text=pattern).first

    def has_subsection(self, subsection_text: str) -> bool:
        """Does this camera's setup menu carry the entry at all? Firmware
        differs by model: DC-5V-1 and BC-5V-1 have no VCA > RULES and no
        Soterix > CONNECT entry (probed 09/11/2026)."""
        return self._menu_item(subsection_text).count() > 0

    def require_subsection(self, subsection_text: str) -> None:
        """Skip, naming the measured absence, when the menu has no such entry."""
        if not self.has_subsection(subsection_text):
            pytest.skip(f"this camera's setup menu has no '{subsection_text}' entry "
                        f"(measured on the page; firmware differs by model)")

    def navigate_to_setup_section(self, section_text: str):
        """Click a top-level nav section in Setup (e.g. 'CAMERA', 'NETWORK')."""
        self._menu_section(section_text).click()
        self.page.wait_for_timeout(500)  # the menu unfolds with no DOM signal of its own
        return self

    def navigate_to_vca_section(self):
        """Open the analytics section, whatever the firmware calls it.
        BC-5V-1 names it VCA; DC-5V-1 names it SETTINGS (Enable, RULES,
        COUNTERS, SCHEDULES, ... LICENSE; measured 09/11/2026). The
        section is found by its Enable entry, which both carry."""
        enable = self.page.locator("li").filter(has_text=re.compile(r"^\s*Enable\s*$", re.I))
        # .first: one section carries the analytics Enable entry
        section = self.page.locator("#sub_menu > ul").filter(has=enable).first
        if not section.count():
            names = self.page.locator("#sub_menu > ul").evaluate_all(
                "els => els.map(e => (e.textContent || '').trim().split(/\\s+/).slice(0, 2).join(' '))")
            raise AssertionError(
                f"no setup section carries an Enable entry (analytics): sections are {names}")
        section.click()
        self.page.wait_for_timeout(500)  # the menu unfolds with no DOM signal of its own
        return self

    def navigate_to_setup_subsection(self, subsection_text: str):
        """Click a sub-section link in Setup (e.g. 'VIDEO', 'OSD', 'ENABLE')
        and wait for the content heading to change."""
        before = self.current_heading()
        item = self._menu_item(subsection_text)
        if not item.count():
            raise AssertionError(f"this camera's setup menu has no '{subsection_text}' entry")
        item.click()
        self._wait_heading_change(before)
        self._wait_content_settled()
        return self

    def codec_select(self):
        """The Stream 1 codec select: the first select that offers H.265.
        The page's first select is not the codec on every firmware."""
        return self.select_with_option("H.265")

    def select_with_option(self, option_text: str):
        """The content pane's first select that offers an option with this
        text. Option values differ by firmware (the codec select carries
        '3' for H.265 on BC-5V-1), so tests read the selected option's text
        through selected_option, never the select's value."""
        return self.page.locator("#tabs select").filter(
            has=self.page.locator(f"option:has-text('{option_text}')")).first

    @staticmethod
    def selected_option(select):
        """The option a select currently shows; expect(...).to_have_text on it.
        Options are hidden elements, so a text= locator on one never reads
        as visible."""
        return select.locator("option:checked")

    def table_rows(self) -> list[list[str]]:
        """The content pane's table rows as cell texts, empty rows dropped.
        Header rows use th cells and so come back empty; a heading row
        set in td cells ('Assigned', 'License') stays, so callers match
        on the cells they expect."""
        rows = self.page.locator("#tabs tr").evaluate_all(
            "trs => trs.map(tr => [...tr.querySelectorAll('td')].map(td => td.innerText.trim()))")
        return [r for r in rows if any(r)]

    def content(self, text: "str | re.Pattern[str]"):
        """The content pane's first element carrying this text or pattern
        (a label, a status line, a version string), for pages with no
        .contentTitle such as the Soterix CONNECT onboard page."""
        # .first: callers pass a fixed page string (a title, a status
        # line), not an entity name, and the pane states it once
        return self.page.locator("#tabs").get_by_text(text).first

    def heading(self, text: str):
        """The content pane's heading for a setup page, exact text."""
        # .first: the content pane carries one title div; the filter only
        # guards against a stale duplicate while the pane re-renders
        return self.page.locator("#tabs .contentTitle").filter(has_text=text).first

    def current_heading(self) -> str:
        title = self.page.locator("#tabs .contentTitle").first
        try:
            return title.inner_text(timeout=2000).strip() if title.count() else ""
        except Exception:  # noqa: BLE001 - why: no heading yet is a valid 'before' for the change wait
            return ""

    def _wait_heading_change(self, before: str, timeout_ms: int = 10000) -> None:
        """Poll until the content heading reads something other than `before`.
        A click on the page already open changes nothing; the wait then
        ends at the timeout without raising, as the old fixed sleep did."""
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if self.current_heading() not in ("", before):
                return
            self.page.wait_for_timeout(200)  # poll tick for the content pane

    def _wait_content_settled(self, timeout_ms: int = 5000) -> None:
        """Poll until the content pane's text stops changing.
        The heading renders first and the labels fill 120 ms later
        (measured on 10.2.0.171, 09/11/2026): a body text read taken on
        the heading alone missed 'Auto exposure', '3D noise reduction'
        and 'Activation' on every camera."""
        pane = self.page.locator("#tabs")
        deadline = time.monotonic() + timeout_ms / 1000
        last = None
        while time.monotonic() < deadline:
            try:
                now = pane.inner_text(timeout=1000)
            except Exception:  # noqa: BLE001 - why: a pane mid-replace has no text yet; the next tick reads it
                now = None
            if now is not None and now == last:
                return
            last = now
            self.page.wait_for_timeout(100)  # poll tick for the label fill

    # ------------------------------------------------------------------ #
    #  Main Page - Live View assertions
    # ------------------------------------------------------------------ #

    def get_camera_time_text(self) -> str:
        """Get the camera time displayed on the main page."""
        return self.page.locator("text=/\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}/").inner_text()

    def is_soterix_branded(self) -> bool:
        """Check if the Soterix Systems branding is visible."""
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        return self.page.locator("img[src*='logo'], text='SOTERIX'").first.is_visible()

    # ------------------------------------------------------------------ #
    #  Setup - System Information
    # ------------------------------------------------------------------ #

    def get_system_info(self) -> dict:
        """Navigate to System Information and return all fields as a dict."""
        self.navigate_to_setup()
        self.navigate_to_setup_section("SYSTEM")
        self.navigate_to_setup_subsection("SYSTEM INFORMATION")

        info = {}
        fields = [
            "Model name", "Serial number", "Manufacturer", "Max resolution",
            "Max framerate", "Photo resistor(CDS)", "Alarm in", "Relay out",
            "Audio", "Optical zoom", "Digital zoom", "PTZ", "AI", "ONVIF"
        ]
        for field in fields:
            try:
                row = self.page.locator(f"text='{field}'").locator("..")
                value_el = row.locator("td:nth-child(2), span, >> text=/[A-Z].*$/").last
                info[field] = value_el.inner_text().strip()
            except Exception:
                info[field] = None

        # Editable fields
        info["Device name"] = self.page.locator("input").first.input_value()
        info["Location"] = self.page.locator("input").nth(1).input_value()
        return info

    def set_device_name(self, name: str):
        """Set the device name field."""
        inp = self.page.locator("input").first
        inp.fill(name)
        return self

    def set_location(self, location: str):
        """Set the location field."""
        inp = self.page.locator("input").nth(1)
        inp.fill(location)
        return self

    # ------------------------------------------------------------------ #
    #  Setup - Plugin info
    # ------------------------------------------------------------------ #

    def get_plugin_list(self) -> list[dict]:
        """Navigate to Plug-in page and return list of plugins with name/version/status."""
        self.navigate_to_setup()
        self.navigate_to_setup_section("SYSTEM")
        self.navigate_to_setup_subsection("PLUG-IN")
        self.page.wait_for_timeout(1000)

        plugins = []
        rows = self.page.locator("table").first.locator("tr")
        for i in range(1, rows.count()):  # skip header row
            cells = rows.nth(i).locator("td")
            if cells.count() >= 3:
                plugins.append({
                    "name": cells.nth(0).inner_text().strip(),
                    "version": cells.nth(1).inner_text().strip(),
                    "status": cells.nth(2).inner_text().strip(),
                })
        return plugins

    def get_storage_usage(self) -> int:
        """Get plugin storage usage percentage from the Plug-in page."""
        text = self.page.locator("text=/\\d+ %/").inner_text()
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else -1

    # ------------------------------------------------------------------ #
    #  Setup - Video Configuration
    # ------------------------------------------------------------------ #

    def get_stream_table(self) -> list[dict]:
        """Get the 3-stream summary table from Video Configuration."""
        self.navigate_to_setup()
        # VIDEO & AUDIO is the default expanded section, VIDEO is default page
        self.page.wait_for_timeout(500)

        streams = []
        rows = self.page.locator("table").first.locator("tr")
        for i in range(1, rows.count()):
            cells = rows.nth(i).locator("td")
            if cells.count() >= 4:
                streams.append({
                    "stream": cells.nth(0).inner_text().strip(),
                    "codec": cells.nth(1).inner_text().strip(),
                    "resolution": cells.nth(2).inner_text().strip(),
                    "fps": cells.nth(3).inner_text().strip(),
                })
        return streams

    def get_stream_detail(self, field: str) -> str:
        """Get a specific field value from the stream detail form (e.g. 'Bitrate mode')."""
        select = self.page.locator("select").filter(has=self.page.locator("option:checked"))
        # Try to find the field label and its adjacent value
        label = self.page.locator(f"text='{field}'").first
        sibling = label.locator("~ select, ~ input").first
        if sibling.count():
            tag = sibling.evaluate("el => el.tagName")
            if tag == "SELECT":
                return sibling.input_value()
            return sibling.input_value()
        return ""

    def set_codec(self, codec: str):
        """Change the codec dropdown value."""
        self.page.locator("select").first.select_option(label=codec)
        return self

    def set_resolution(self, resolution: str):
        """Change the resolution dropdown value."""
        self.page.locator("select").filter(
            has=self.page.locator(f"option[value='{resolution}']")
        ).first.select_option(value=resolution)
        return self

    # ------------------------------------------------------------------ #
    #  Setup - OSD
    # ------------------------------------------------------------------ #

    def navigate_to_osd(self):
        """Navigate to OSD Configuration."""
        self.navigate_to_setup()
        self.navigate_to_setup_subsection("OSD")
        return self

    # ------------------------------------------------------------------ #
    #  Setup - Audio
    # ------------------------------------------------------------------ #

    def navigate_to_audio(self):
        """Navigate to Audio Configuration."""
        self.navigate_to_setup()
        self.navigate_to_setup_subsection("AUDIO")
        return self

    # ------------------------------------------------------------------ #
    #  Setup - Network
    # ------------------------------------------------------------------ #

    def get_network_status(self) -> dict:
        """Navigate to Network Status and return all fields."""
        self.navigate_to_setup()
        self.navigate_to_setup_section("NETWORK")
        self.navigate_to_setup_subsection("STATUS")
        self.page.wait_for_timeout(500)

        status = {}
        fields = [
            "MAC address", "IP address", "Subnet mask", "Default gateway",
            "Preferred DNS server", "HTTP port", "HTTPS port", "RTSP port"
        ]
        for field in fields:
            try:
                label = self.page.locator(f"text='{field}'").first
                value = label.locator("~ td, + td").first.inner_text().strip()
                status[field] = value
            except Exception:
                status[field] = None
        return status

    # ------------------------------------------------------------------ #
    #  Setup - VCA
    # ------------------------------------------------------------------ #

    def get_vca_enable_status(self) -> dict:
        """Navigate to VCA > ENABLE and return enable state + tracker engine."""
        self.navigate_to_setup()
        self.navigate_to_setup_section("VCA")
        self.navigate_to_setup_subsection("ENABLE")
        self.page.wait_for_timeout(500)

        result = {}
        # Check if Enable radio is On
        on_radio = self.page.locator("input[type='radio']").first
        result["enabled"] = on_radio.is_checked()

        # Check which tracker engine is selected
        page_text = self.page.locator("body").inner_text()
        result["dl_object_tracker"] = "DL Object Tracker" in page_text
        result["intrusion_detection"] = "Intrusion detection" in page_text

        return result

    def get_vca_license(self) -> list[dict]:
        """Navigate to VCA > LICENSE and return the activated licenses.

        The page renders two tables: the "Activate License" form first, then
        "Activated License(s)". Taking table.first therefore read the form -
        which has no data rows - and returned an empty list, making a licensed
        camera look unlicensed. Match on the header row instead.
        """
        self.navigate_to_setup()
        self.navigate_to_setup_section("VCA")
        self.navigate_to_setup_subsection("LICENSE")
        self.page.wait_for_timeout(1000)

        return self.page.evaluate(
            r"""() => {
              for (const t of document.querySelectorAll('table')) {
                const rows = [...t.querySelectorAll('tr')];
                if (rows.length < 2) continue;
                const head = [...rows[0].querySelectorAll('td,th')]
                  .map(c => (c.innerText || '').trim().toLowerCase());
                const a = head.indexOf('assigned'), l = head.indexOf('license');
                if (a === -1 || l === -1) continue;
                const out = [];
                for (const tr of rows.slice(1)) {
                  const c = [...tr.querySelectorAll('td,th')]
                    .map(x => (x.innerText || '').trim());
                  if (c.length > Math.max(a, l) && (c[a] || c[l]))
                    out.push({assigned: c[a], license: c[l]});
                }
                return out;
              }
              return [];
            }"""
        )

    # ------------------------------------------------------------------ #
    #  Setup - Soterix Cloud Connect
    # ------------------------------------------------------------------ #

    def get_cloud_connect_status(self) -> dict:
        """Navigate to Soterix > CONNECT and report registration state.

        Returns a dict with a "state" of:
          registered     - "Registered Cloud Address" is shown
          waiting        - "Waiting for cloud registration..." (pending; the
                           camera has not completed registration)
          not_registered - the page explicitly says so
          unavailable    - the camera has no Soterix Cloud section at all,
                           which is the case on unbranded VCA units
          unknown        - page loaded but matched none of the above
        """
        result = {"is_registered": False, "is_unregistered": False,
                  "state": "unknown", "cloud_address": None}

        # Unbranded units have no Soterix section; say so rather than throwing.
        if self.page.locator("li#connect").count() == 0:
            result["state"] = "unavailable"
            return result

        self.navigate_to_setup()
        self.navigate_to_setup_section("Soterix")
        self.navigate_to_setup_subsection("CONNECT")
        self.page.wait_for_timeout(3000)  # cloud status resolves asynchronously

        page_text = self.page.locator("body").inner_text()
        result["is_registered"] = "Registered Cloud Address" in page_text
        result["is_unregistered"] = "I am not registered" in page_text

        if result["is_registered"]:
            result["state"] = "registered"
            try:
                addr = self.page.locator("text=/.*soterixcloud\\.com.*/").inner_text().strip()
                result["cloud_address"] = addr
            except Exception:
                result["cloud_address"] = None
        elif "Waiting for cloud registration" in page_text:
            result["state"] = "waiting"
        elif result["is_unregistered"]:
            result["state"] = "not_registered"
        return result

    # ------------------------------------------------------------------ #
    #  Setup - Motion Detection
    # ------------------------------------------------------------------ #

    def navigate_to_motion(self):
        """Navigate to Events > Motion Detection."""
        self.navigate_to_setup()
        self.navigate_to_setup_section("EVENTS")
        self.navigate_to_setup_subsection("MOTION")
        return self

    # ------------------------------------------------------------------ #
    #  Common actions
    # ------------------------------------------------------------------ #

    # :visible on each: the VIDEO page keeps two hidden Apply buttons
    # (preset and video-out) ahead of the live one, and .first on the
    # bare union waited 30 s on a hidden button (10.2.0.171, 09/11/2026)
    def click_apply(self):
        """Click the Apply button on the current setup page."""
        self.page.locator(
            "button:has-text('Apply'):visible, input[value='Apply']:visible").first.click()
        self.page.wait_for_timeout(1000)
        return self

    def click_default(self):
        """Click the Default button to restore factory defaults on current page."""
        self.page.locator(
            "button:has-text('Default'):visible, input[value='Default']:visible").first.click()
        self.page.wait_for_timeout(1000)
        return self

    def click_cancel(self):
        """Click the Cancel button on the current setup page."""
        self.page.locator(
            "button:has-text('Cancel'):visible, input[value='Cancel']:visible").first.click()
        self.page.wait_for_timeout(500)
        return self
