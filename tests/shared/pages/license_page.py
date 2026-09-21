"""License Page Object Model.

Shared page object for Licenses module - Available Licenses, Assigned Licenses,
device list, assign/unassign/suspend workflows, and CSV export.
Used by all License test modules.
"""
import re
import time

from playwright.sync_api import Error as PlaywrightError, Page, expect


class LicensePage:
    """Page object for the Licenses section."""

    def __init__(self, page: Page):
        self.page = page

        # Navigation
        self.license_nav_link = page.locator("a[href*='license']")
        self.loader = page.locator(".MuiCircularProgress-root, .loader")

        # Top-level widgets / summary
        self.total_licenses_widget = page.locator(
            "text=Total Licenses"
        ).locator("..")
        self.active_count = page.locator("text=Active").locator("..")
        self.available_count = page.locator("text=Available").locator("..")
        self.suspended_count = page.locator("text=Suspended").locator("..")

        # Tabs
        self.available_tab = page.locator(
            "button:has-text('Available'), p:has-text('Available Licenses')"
        ).first
        self.assigned_tab = page.locator(
            "button:has-text('Assigned'), p:has-text('Assigned Licenses')"
        ).first

        # Search
        self.search_input = page.locator(
            "input[placeholder*='Search'], input[placeholder*='search']"
        ).first

        # Available Licenses table
        self.license_rows = page.locator(
            "tr, div.license-row, div[class*='row']"
        )
        self.license_items = page.locator(
            "td, div[class*='license-item'], div[class*='cell']"
        )

        # CSV export
        self.csv_download_button = page.locator(
            # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
            "img[src*='downloadLicense'], img[src*='download'], img[alt='Download'], "
            "button:has-text('CSV'), button:has-text('Export'), button:has-text('Download')"
        ).first

        # Assigned Licenses - site expansion (MUI Table structure)
        self.site_rows = page.locator("tr.MuiTableRow-root")
        self.site_expand_icons = page.locator(
            "svg[data-testid='ExpandMoreIcon'], "
            "svg[class*='MuiSvgIcon-root']:has(path[d*='16.59'])"
        )
        # Class, not get_by_role('switch'): this build's MUI Switch input
        # carries no role attribute (a bare type=checkbox, probed
        # 08/24/2026), so the role matches nothing
        self.site_toggle_switches = page.locator(".MuiSwitch-root")

        # Device list (drill-down from feature)
        self.device_list_rows = page.locator(
            "tr[class*='device'], div[class*='device-row']"
        )
        self.breadcrumb = page.locator(
            "nav[aria-label='breadcrumb'], div[class*='breadcrumb']"
        )

        # Three-dot menu actions
        self.options_icons = page.locator(
            # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
            "img[src*='optionIcon'], img[src*='option'], "
            # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
            "button[class*='more'], img[src*='three-dot']"
        )
        self.suspend_option = page.locator(
            "li:has-text('Suspend'), div:has-text('Suspend License')"
        ).first
        self.unassign_option = page.locator(
            "li:has-text('Unassign'), div:has-text('Unassign License')"
        ).first

        # Confirmation dialog
        self.confirm_button = page.locator(
            "button:has-text('Confirm'), button:has-text('Yes'), "
            "button.btn-primary:has-text('Suspend'), "
            "button.btn-primary:has-text('Unassign')"
        ).first
        self.cancel_button = page.locator(
            "button:has-text('Cancel'), button:has-text('No')"
        ).first

        # Assign New License modal. The button is labeled 'Assign New'
        # and exists ONLY on the Assigned Licenses tab. It opens a
        # customMuiModal overlay (heading 'Assign New License',
        # Bulk/Individual toggle, Site select). The overlay is
        # position:fixed, so offsetParent-based visibility probes miss
        # it. No bare :has-text('Assign') clause: it substring-matches
        # the 'Assigned Licenses' TAB (DOM probes 08/09/2026).
        self.assign_button = page.locator(
            "button.add-btn, button:has-text('Assign New License'), "
            "button:has-text('Assign New')"
        ).first
        self.assign_panel = page.get_by_text("Assign to Individual").first
        self.assign_modal = page.locator(
            "div[class*='modal'], div[role='dialog']"
        )
        self.site_dropdown = page.locator(
            "div[role='combobox'], select[name*='site']"
        ).first
        self.device_checkboxes = page.locator(
            "input[type='checkbox']"
        )
        self.select_all_checkbox = page.locator(
            "input[type='checkbox'][name*='all'], "
            "th input[type='checkbox']"
        ).first
        self.assign_confirm_button = page.locator(
            "button:has-text('Assign')"
        ).last
        self.modal_close = page.locator(
            "button:has-text('Cancel'), button:has-text('Close'), "
            "button[class*='close']"
        ).first

    # ----- Navigation -----

    def navigate(self):
        """Navigate to Licenses page via Admin menu > Licenses."""
        # Click Admin menu first. Prefer the href link; fall back to the
        # text node if the sidebar has not rendered the anchor yet.
        admin_link = self.page.locator("a[href*='admin']").first
        if not self._appears(admin_link, timeout=3000):
            admin_link = self.page.get_by_text("Admin").first
        admin_link.wait_for(state="visible", timeout=10000)
        admin_link.click(force=True)

        # Then click Licenses submenu once the submenu reveals it
        license_link = self.page.locator("a[href*='license']").first
        if not self._appears(license_link, timeout=3000):
            license_link = self.page.get_by_text("License").first
        license_link.wait_for(state="visible", timeout=10000)
        license_link.click(force=True)
        self._wait_for_page_ready()

    def _wait_for_page_ready(self):
        """Wait for loaders to hide and content to appear."""
        # Loader may take a beat to appear, then must disappear
        self._appears(self.loader.first, timeout=2000)
        self._appears_hidden(self.loader.first, timeout=30000)

        # The main page renders the summary widget; sub-pages (device
        # list) render the breadcrumb instead. Either marks content
        # ready, so the wait does not burn its timeout on sub-pages.
        ready = self.total_licenses_widget.or_(self.breadcrumb.first)
        self._appears(ready.first, timeout=20000)
        # The table lands after the summary and re-renders once its data
        # arrives (india: ten rows, read as none 09/11/2026): wait for rows
        # and for their count to hold.
        self._table_settled()

    # ----- Tab switching -----

    def switch_to_available_tab(self):
        """Click the Available Licenses tab."""
        self.available_tab.wait_for(state="visible", timeout=10000)
        self.available_tab.click(force=True)
        # The tab fetch runs a loader cycle; page-ready covers it
        self._wait_for_page_ready()

    def switch_to_assigned_tab(self):
        """Click the Assigned Licenses tab."""
        self.assigned_tab.wait_for(state="visible", timeout=10000)
        self.assigned_tab.click(force=True)
        self._wait_for_page_ready()

    # ----- Search -----

    def search(self, query: str):
        """Type into the search input and wait for the filter to settle."""
        self.search_input.wait_for(state="visible", timeout=10000)
        self.search_input.fill(query)
        self._rows_settled()

    def clear_search(self):
        """Clear the search field and wait for the filter to settle."""
        self.search_input.fill("")
        self._rows_settled()

    # ----- Available Licenses -----

    def get_visible_row_count(self) -> int:
        """Count visible rows in the license table."""
        return self.license_rows.count()

    def get_column_headers(self) -> list[str]:
        """Return the text of column headers."""
        headers = self.page.locator(
            "th, div[class*='header'] div[class*='cell']"
        )
        texts = []
        for i in range(headers.count()):
            text = headers.nth(i).inner_text().strip()
            if text:
                texts.append(text)
        return texts

    # ----- CSV Export -----

    def download_csv(self) -> str:
        """Click the CSV download button and return the downloaded file path."""
        self.csv_download_button.wait_for(state="visible", timeout=10000)
        # Hover to activate the element; the download event is the signal
        self.csv_download_button.hover()
        with self.page.expect_download(timeout=15000) as download_info:
            self.csv_download_button.click(force=True)
        download = download_info.value
        path = download.path()
        return str(path) if path else ""

    # ----- Assigned Licenses - Site Expansion -----

    def get_site_count(self) -> int:
        """Count top-level site rows in Assigned Licenses."""
        return self.site_rows.count()

    def expand_site(self, index: int = 0):
        """Expand a site row to reveal feature-level licenses."""
        before = self.site_rows.count()
        self.site_expand_icons.nth(index).click()
        # Expansion inserts feature rows below the site row
        self._row_count_changed(before, "expand")

    def collapse_site(self, index: int = 0):
        """Collapse an expanded site row."""
        before = self.site_rows.count()
        self.site_expand_icons.nth(index).click()
        # Collapse removes the feature rows again
        self._row_count_changed(before, "collapse")

    def get_device_count(self) -> int:
        """Count devices in the device list page."""
        return self.device_list_rows.count()

    def open_device_menu(self, index: int = 0):
        """Open the three-dot options menu for a device."""
        self.options_icons.nth(index).click()
        # The menu popover carries the action options. :visible skips
        # stale keepMounted menus left hidden in the DOM.
        self.page.locator(
            "[role='menu']:visible, .MuiMenu-paper:visible"
        ).first.wait_for(state="visible", timeout=10000)

    def suspend_device(self, index: int = 0):
        """Suspend a device license via the options menu."""
        self.open_device_menu(index)
        self.suspend_option.click()
        # The confirmation dialog is the next step's target
        self.confirm_button.wait_for(state="visible", timeout=10000)

    def confirm_action(self):
        """Click the confirm button in the dialog."""
        self.confirm_button.click()
        # The clicked button leaves the DOM with the dialog
        self._appears_hidden(self.confirm_button, timeout=10000)
        self._wait_for_page_ready()

    def cancel_action(self):
        """Click the cancel button in the dialog."""
        self.cancel_button.click()
        self._appears_hidden(self.cancel_button, timeout=10000)

    def unassign_device(self, index: int = 0):
        """Unassign a device license via the options menu."""
        self.open_device_menu(index)
        self.unassign_option.click()
        self.confirm_button.wait_for(state="visible", timeout=10000)

    # ----- Assign New License -----

    def open_assign_panel(self):
        """Open the Assign New License modal.

        Returns False only when the 'Assign New' button is absent from
        the Assigned Licenses tab (a tenant without the feature - the
        callers' designed skip). A button that is present but does not
        open the modal is locator or app drift, and that must fail
        loud, not read as a skip: the feature is verified present on
        the QA tenant (08/09/2026).
        """
        self.switch_to_assigned_tab()
        if not self._appears(self.assign_button, timeout=10000):
            print("[LICENSE] No Assign New button on the Assigned tab")
            return False
        self.assign_button.click()
        if not self._appears(self.assign_panel, timeout=10000):
            raise RuntimeError(
                "Assign New was clicked but the assign modal did not "
                "render within 10s. The feature exists on this tenant, "
                "so this is locator or app drift, not unavailability."
            )
        return True

    # Alias: no current callers, kept so older call sites keep working
    open_assign_modal = open_assign_panel

    def close_assign_modal(self):
        """Close the assign modal.

        The customMuiModal has no Cancel button; Escape dismisses it.
        """
        self.page.keyboard.press("Escape")
        if not self._appears_hidden(self.assign_panel, timeout=10000):
            print("[LICENSE] Escape did not close the assign modal "
                  "within 10s")

    def select_site_in_modal(self, site_name: str):
        """Select a site from the dropdown in the assign modal."""
        self.site_dropdown.click()
        # get_by_role("option") covers both the MUI li[role='option'] and a
        # native <option>; accessible-name match is exact and escaped (the
        # option text is the bare site name, probe 09/02/2026).
        option = self.page.get_by_role(
            "option", name=site_name, exact=True
        ).first
        option.click()
        # Listbox hidden = MUI applied the selection (native selects
        # have no listbox, so a miss is fine)
        self._appears_hidden(
            self.page.locator("[role='listbox']"), timeout=10000
        )

    def select_device(self, index: int = 0):
        """Select a device checkbox for assignment.

        The next step (Assign) waits for its own actionability, so no
        wait is needed after the checkbox click.
        """
        self.device_checkboxes.nth(index).click(force=True)

    def select_all_devices(self):
        """Select the 'Select All' checkbox."""
        self.select_all_checkbox.click(force=True)

    def confirm_assignment(self):
        """Click the final Assign button in the modal."""
        self.assign_confirm_button.click()
        # Modal closes on success; then the page refreshes its data
        self._appears_hidden(self.assign_modal.first, timeout=15000)
        self._wait_for_page_ready()

    # ----- Navigation helpers -----

    def navigate_back_via_breadcrumb(self):
        """Click the breadcrumb to go back to the previous level."""
        links = self.breadcrumb.locator("a, span[class*='link']")
        if links.count() > 0:
            links.first.click()
            self._wait_for_page_ready()

    # ----- Readers: the numbers and names the tests reconcile -----
    #
    # Measured on both boxes 09/11/2026. The summary block reads
    # "Total Licenses 100  Active : 22  Available : 78  Suspended : 0"
    # (after the Sites and Site Admins blocks, which carry their own
    # Active/Suspended pairs); the Available table has the columns
    # Feature, Quantity, Available, Active; the Assigned table has eight
    # columns, a site row per site ("All Licenses", "18/74", Enabled) and,
    # once expanded, a feature row per licence ("1 / 6", issue and expiry
    # dates, the key, Enabled). A filter that matches nothing renders one
    # data row that reads "No Data!". The tabs are MUI tabs (role=tab,
    # aria-selected).

    AVAILABLE_HEADERS = ["Feature", "Quantity", "Available", "Active"]
    ASSIGNED_HEADERS = ["No.", "Site / Device", "License Item(SKU)", "Quantity",
                        "Issue Date", "Expiry Date", "License Key", "Status"]
    NO_DATA = "No Data!"
    SITE_ROW_ITEM = "All Licenses"
    # the stats are separated by a literal "|" in the rendered text
    _SUMMARY_RE = re.compile(
        r"Total Licenses\s*(\d+)[\s|]*Active\s*:\s*(\d+)[\s|]*Available\s*:\s*(\d+)[\s|]*Suspended\s*:\s*(\d+)")

    def summary_counts(self) -> dict[str, int]:
        """The licence summary as numbers: total, active, available, suspended.

        Walks up from the 'Total Licenses' label until the block's text
        carries all four numbers, so a re-nested layout still reads; a
        block that never matches raises with the text it saw.
        """
        label = self.page.locator("text=Total Licenses").first
        label.wait_for(state="visible", timeout=10000)
        seen = ""
        for level in range(1, 7):
            seen = " ".join(label.locator(f"xpath=ancestor::*[{level}]").inner_text().split())
            m = self._SUMMARY_RE.search(seen)
            if m:
                total, active, available, suspended = (int(x) for x in m.groups())
                return {"total": total, "active": active,
                        "available": available, "suspended": suspended}
        raise AssertionError(
            f"The licence summary did not read as 'Total Licenses N Active : a "
            f"Available : b Suspended : c'; the block reads: {seen[:200]!r}")

    def tab_names(self) -> list[str]:
        return [t.inner_text().strip() for t in self.page.locator("[role='tab']").all()]

    def selected_tab(self) -> str:
        """The text of the tab that is aria-selected, '' when none is."""
        selected = self.page.locator("[role='tab'][aria-selected='true']")
        return selected.first.inner_text().strip() if selected.count() else ""

    def table_headers(self) -> list[str]:
        return [h.inner_text().strip() for h in self.page.locator("th").all() if h.inner_text().strip()]

    def data_rows(self) -> list[list[str]]:
        """Every table row that has cells, as its cells' texts (whitespace collapsed)."""
        rows = self.page.locator("tr:has(td)")
        out = []
        for i in range(rows.count()):
            cells = rows.nth(i).locator("td")
            out.append([" ".join(cells.nth(j).inner_text().split()) for j in range(cells.count())])
        return out

    def is_no_data(self) -> bool:
        """True when the table shows exactly the 'No Data!' row and nothing else."""
        rows = self.data_rows()
        return len(rows) == 1 and any(c == self.NO_DATA for c in rows[0])

    def available_rows(self) -> list[dict]:
        """The Available table as [{name, quantity, available, active}]; the
        'No Data!' row is left out."""
        out = []
        for cells in self.data_rows():
            if len(cells) == 4 and cells[1].isdigit():
                out.append({"name": cells[0], "quantity": int(cells[1]),
                            "available": int(cells[2]), "active": int(cells[3])})
        return out

    @staticmethod
    def _split_quantity(text: str) -> tuple[int, int] | None:
        m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", text)
        return (int(m.group(1)), int(m.group(2))) if m else None

    def site_entries(self) -> list[dict]:
        """The Assigned table's site rows: [{no, site, assigned, total, status}].
        (site_rows is the raw locator the expand helpers count.)"""
        out = []
        for cells in self.data_rows():
            if len(cells) == 8 and cells[2] == self.SITE_ROW_ITEM:
                assigned, total = self._split_quantity(cells[3]) or (-1, -1)
                out.append({"no": cells[0], "site": cells[1], "assigned": assigned,
                            "total": total, "status": cells[7]})
        return out

    def feature_rows(self) -> list[dict]:
        """The expanded feature rows: [{no, name, assigned, total, issued, expires, key, status}]."""
        out = []
        for cells in self.data_rows():
            if len(cells) == 8 and cells[2] != self.SITE_ROW_ITEM and self._split_quantity(cells[3]):
                assigned, total = self._split_quantity(cells[3])
                out.append({"no": cells[0], "name": cells[2], "assigned": assigned, "total": total,
                            "issued": cells[4], "expires": cells[5], "key": cells[6], "status": cells[7]})
        return out

    def wait_for_feature_rows(self, timeout_s: float = 10.0) -> list[dict]:
        """The feature rows once the expansion has rendered them all.

        expand_site returns when the row count moves, which is the
        collapse container; its nested table lands a moment later and
        grows row by row (india: 2 of 15 read on the first tick), so the
        answer is the count that held for a second.
        """
        deadline = time.monotonic() + timeout_s
        last, stable = -1, 0
        while time.monotonic() < deadline:
            rows = self.feature_rows()
            stable = stable + 1 if rows and len(rows) == last else 0
            if stable >= 4:
                return rows
            last = len(rows)
            self.page.wait_for_timeout(250)  # poll tick for the nested table
        return self.feature_rows()

    def _table_settled(self, timeout_s: float = 15.0) -> None:
        """Wait for data rows to exist and their count to hold for a second."""
        rows = self.page.locator("tr:has(td)")
        deadline = time.monotonic() + timeout_s
        last, stable = -1, 0
        while time.monotonic() < deadline:
            n = rows.count()
            stable = stable + 1 if n and n == last else 0
            if stable >= 4:
                return
            last = n
            self.page.wait_for_timeout(250)  # poll tick for the table data

    def switch_states(self) -> list[bool]:
        """Each site switch's checked state, in table order."""
        return [s.locator("input[type='checkbox']").first.is_checked()
                for s in self.site_toggle_switches.all()]

    def go_to_views_and_back(self):
        """Leave the Licenses page through the Views nav link and come back."""
        # the Views link's href is "/" (the app's home), so it is found by its text
        views = self.page.locator("a:has-text('Views')").first
        views.wait_for(state="visible", timeout=10000)
        views.click(force=True)
        self.page.locator("text=Total Licenses").first.wait_for(state="hidden", timeout=10000)
        self.navigate()

    # ----- Wait helpers -----

    @staticmethod
    def _appears(locator, timeout: int = 5000) -> bool:
        """True when the element shows within timeout, False otherwise."""
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        # not visible in time is the answer False. The navigation and assign
        # callers branch on it, and the others use it as a settle before a
        # wait that raises
        except PlaywrightError:
            return False

    @staticmethod
    def _appears_hidden(locator, timeout: int = 5000) -> bool:
        """True when the element hides within timeout, False otherwise."""
        try:
            locator.wait_for(state="hidden", timeout=timeout)
            return True
        # still visible in time is the answer False. Callers use it as a
        # settle after a dialog closes, and the test asserts the table after
        except PlaywrightError:
            return False

    def _rows_settled(self, timeout_s: float = 5.0):
        """Wait for the filtered row count to hold for a full second.

        A search that matches everything never changes the count, so
        stability is the signal, not change: the first return is after
        one second of equal reads, which also gives the refetch a
        lead-in instead of settling on a transient state.
        """
        deadline = time.monotonic() + timeout_s
        last = -1
        stable = 0
        while time.monotonic() < deadline:
            current = self.license_rows.count()
            stable = stable + 1 if current == last else 0
            if stable >= 4:
                return
            last = current
            self.page.wait_for_timeout(250)  # poll tick for filter settle

    def _row_count_changed(self, before: int, action: str,
                           timeout_s: float = 10.0):
        """Wait for the row count to move off the pre-click baseline."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.site_rows.count() != before:
                return
            self.page.wait_for_timeout(250)  # poll tick for row change
        print(f"[LICENSE] Site {action} clicked but the row count "
              f"stayed at {before} for {timeout_s:.0f}s")

    def get_page_title_text(self) -> str:
        """Return the main heading text on the current licenses sub-page."""
        heading = self.page.locator(
            "h1, h2, h3, div[class*='title']"
        ).first
        if heading.count() > 0:
            return heading.inner_text().strip()
        return ""
