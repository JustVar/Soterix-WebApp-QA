"""Insights Page Object Model.

Models the Insights page including navigation to System Status dashboard,
switching to Widgets tab, widget creation with various graph types and
categories, widget search, and widget operations (view, report, delete).
"""
import datetime
import re
import time

from playwright.sync_api import (
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    expect,
)

from tests.shared.helpers.shown_name import shown_as

# Graph type indices in the dropdown
GRAPH_INDEX = {"Line": 0, "Bar": 1, "Pie": 4, "Heat": 5}

# Widget size labels by graph type
WIDGET_SIZE = {"Pie": "Dashlet", "default": "Half Width"}


class InsightsPage:
    """Page object for the Insights page."""

    def __init__(self, page: Page):
        self.page = page

        # Navigation
        self.insights_nav_link = page.locator("a[href*='insights']").first
        self.system_status_link = page.locator(
            "a[href*='insights/systemStatus']"
        )

        # Insights page identity
        self.all_insights_tab = page.locator(
            "div.tabInner[title='All Insights']"
        )

        # Dashboard / Widgets toggle
        self.inactive_tab = page.locator(".toggleTabs_inactive")
        self.my_widgets_text = page.locator("p:has-text('My Widgets')")

        # System Status
        self.site_dropdown = page.locator(".dropdown-box").first
        self.devices_label = page.locator("p.grid-title:text-is('Devices')")

        # Widget creation
        self.create_widget_button = page.locator(".sky-button")
        self.widget_name_input = page.locator(".modalFormInput")
        self.save_button = page.locator(
            "button:has-text('Save')"
        ).first
        self.widget_success_msg = page.locator(
            "p:has-text('Widget created successfully')"
        )

        # Widget creation dropdowns (indexed: 0=graph, 1=category,
        # 2=description, 3=site, 4=camera, 5=duration, 6=size)
        self.form_dropdowns = page.locator(".MuiPaper-root")
        self.dropdown_items = page.locator(".dropdownItem")
        self.accordion_arrows = page.locator(
            # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
            "img[src*='media/downAccordionIcon']"
        )

        # Widget search
        self.search_input = page.locator("input[placeholder='Search']")

        # Widget operations
        self.three_dots = page.locator("img[src*='media/three-dots']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.back_arrow = page.locator("img[src*='media/backIconArrow']")
        self.report_download_button = page.locator(".save_button")
        self.report_success_msg = page.locator(
            "p:has-text('Report downloaded successfully')"
        )
        self.delete_confirm_button = page.locator(
            ".cancel_button_insights"
        )

        # Close tab icon
        self.close_tab_icon = page.locator(
            # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
            "img[src*='media/closeIcon']"
        ).first

        # Loader
        self.loader = page.locator(".MuiCircularProgress-root")

    # --- Navigation ---

    def navigate(self):
        """Navigate to the Insights page via the nav link."""
        # Check if already on Insights page
        if self.all_insights_tab.count() > 0:
            # Close any open sub-tab first
            try:
                self.close_tab_icon.click()
                self._appears_hidden(self.close_tab_icon, timeout=5000)
            # no open sub-tab means nothing to close; callers wait on
            # their own next element
            except Exception:
                pass
            return

        self.insights_nav_link.click()

        # Wait for System Status link to appear (page loaded)
        self.system_status_link.first.wait_for(
            state="visible", timeout=30000
        )
        self._wait_for_loader_finish()

    def open_system_status(self, site_name: str | None = None):
        """Open the System Status dashboard and select a site.

        Navigates to Insights, clicks System Status, selects the given
        site from the dropdown, and verifies 'Devices' text appears.
        Pass None to use test_site_name from config/env/.
        """
        if site_name is None:
            from config.base_config import config
            site_name = config.get("test_site_name")
            if not site_name:
                raise RuntimeError(
                    "test_site_name is not set for this ENV in config/env/. "
                    "Add it before running site-dependent tests."
                )

        self.navigate()

        self.system_status_link.first.click()

        # Wait for System Status to load
        self.site_dropdown.wait_for(state="visible", timeout=30000)
        self._wait_for_loader_finish()

        # Select site
        self.site_dropdown.click()

        site_option = self.page.locator(
            f"div:text('{site_name}')"
        ).first
        site_option.wait_for(state="visible", timeout=10000)
        site_option.click()
        # The dashboard renders the Devices grid once the site applies.
        # (The option text is no signal: the same name re-renders on the
        # dashboard itself after selection.)
        if not self._appears(self.devices_label, timeout=15000):
            print("[INSIGHTS] Site selected but the Devices grid did "
                  "not appear within 15s")
        self._wait_for_loader_finish()

    def close_tab(self):
        """Close the currently open sub-tab (System Status, widget view, etc.)."""
        self.close_tab_icon.click(timeout=10000)
        expect(self.close_tab_icon).to_be_hidden(timeout=5000)

    # Measured 09/12/2026 on US (register row 53). The landing (/insights)
    # reads: tabs My Dashboards and Widgets, Create New, 'Preset Dashboard'
    # with View All and the System Status link, 'My Dashboard' with View
    # All and, with no user dashboards, "My Dashboard is currently empty."
    # The Widgets tab reads 'Preset Widgets' with View All, the widget
    # list, 'My Widgets', Create New and a Search box. System Status
    # (/insights/systemStatus) shows Devices (Cameras, Smoke Detector,
    # Thermostats, Total), Cameras (Total, Fixed, PTZ, Zoom) and a Health
    # Monitor with Online/Offline counts per Camera and Sensor.
    LANDING_URL = "/insights"
    SYSTEM_STATUS_URL = "/insights/systemStatus"
    MY_DASHBOARD_EMPTY = "My Dashboard is currently empty."

    def system_status_figures(self) -> dict:
        """The System Status dashboard's device and camera counts.

        Keys: devices (cameras, smoke, thermostats, total), cameras (total,
        fixed, ptz, zoom), camera_online, camera_offline. Read from the
        page text with whitespace collapsed; a missing block raises with
        the text it read, so a relabelled dashboard fails by name.
        """
        text = " ".join(self.page.locator("body").inner_text().split())
        devices = re.search(
            r"Devices Cameras (\d+) Smoke Detector (\d+) Thermostats (\d+) Total (\d+)", text)
        cameras = re.search(r"Cameras Total (\d+) Fixed (\d+) PTZ (\d+) Zoom (\d+)", text)
        health = re.search(r"Online Offline Camera (\d+) (\d+)", text)
        missing = [name for name, m in (("Devices", devices), ("Cameras", cameras),
                                        ("Health Monitor", health)) if m is None]
        if missing:
            raise AssertionError(
                f"the System Status dashboard shows no {missing} block; it reads: {text[:300]!r}")
        return {
            "devices": {"cameras": int(devices.group(1)), "smoke": int(devices.group(2)),
                        "thermostats": int(devices.group(3)), "total": int(devices.group(4))},
            "cameras": {"total": int(cameras.group(1)), "fixed": int(cameras.group(2)),
                        "ptz": int(cameras.group(3)), "zoom": int(cameras.group(4))},
            "camera_online": int(health.group(1)),
            "camera_offline": int(health.group(2)),
        }

    def selected_site_text(self) -> str:
        """What the System Status site selector reads."""
        return self.site_dropdown.inner_text().strip()

    # --- Widgets tab ---

    def switch_to_widgets(self):
        """Switch from the Dashboard tab to the Widgets tab."""
        self.navigate()

        # Find the inactive tab that says "Widgets"
        inactive = self.inactive_tab
        inactive.wait_for(state="visible", timeout=30000)

        text = inactive.inner_text()
        if "widget" in text.lower():
            inactive.click()

        # Verify we switched to widgets
        self.my_widgets_text.wait_for(state="visible", timeout=15000)
        self._wait_for_loader_finish()

    # --- Helpers: form section lookup ---

    def _find_section_index(self, label):
        """Find the .MuiPaper-root index for a form section by label.

        Sections (Graph Type, Category, Description, Sites, etc.) are
        rendered as .MuiPaper-root elements. When some sections expand
        (e.g. Camera list), extra .MuiPaper-root elements are injected,
        shifting subsequent indices. This helper finds the correct index
        by matching the section's header text.
        """
        return self.page.evaluate("""(label) => {
            const papers = document.querySelectorAll('.MuiPaper-root');
            for (let i = 0; i < papers.length; i++) {
                const text = (papers[i].textContent || '').trimStart();
                if (text.startsWith(label)) return i;
            }
            return -1;
        }""", label)

    def _click_first_visible_checkbox(self):
        """Click the first visible .PrivateSwitchBase-input checkbox.

        After opening Description (Vehicle/Event), hidden checkboxes
        from that section remain in the DOM. This helper skips them
        and clicks the first actually-visible checkbox (the camera
        "All Cameras" toggle).
        """
        cbs = self.page.locator(".PrivateSwitchBase-input")
        for i in range(cbs.count()):
            if cbs.nth(i).is_visible():
                cbs.nth(i).click()
                return True
        # Fallback: force-click the first one
        if cbs.count() > 0:
            cbs.first.click(force=True)
            return True
        return False

    # --- Widget creation ---

    def create_widget(self, graph_name: str = "Line",
                      category_name: str = "Person",
                      site_name: str | None = None,
                      description_name: str | None = None,
                      camera_name: str | None = None) -> str:
        """Create a widget with specified graph type and category.

        Pass site_name=None to use test_site_name from config/env/.
        For the Event category, description_name selects one named
        description (e.g. 'License Plate Recognition') instead of the
        default every-visible-checkbox sweep; the description
        checkboxes carry the label in their name attribute.
        Returns the generated widget name for later search/operations.
        """
        if site_name is None:
            from config.base_config import config
            site_name = config.get("test_site_name")
            if not site_name:
                raise RuntimeError(
                    "test_site_name is not set for this ENV in config/env/. "
                    "Add it before running site-dependent tests."
                )

        self.switch_to_widgets()

        # Generate unique widget name
        now = datetime.datetime.now()
        ts = now.strftime("%Y%m%d%H%M%S")
        widget_name = f"{graph_name}_{category_name}_{ts}"

        # Click Create New Widget
        self.create_widget_button.click()

        # Wait for widget creation form
        self.save_button.wait_for(state="visible", timeout=60000)

        # Enter widget name
        self.widget_name_input.click()
        self.widget_name_input.fill("")
        self.widget_name_input.fill(widget_name)

        # Select Graph Type (dropdown index 0 - always stable). The
        # item click waits for the open dropdown on its own; the item
        # hiding again is the selection-applied signal.
        dropdowns = self.form_dropdowns
        graph_index = GRAPH_INDEX.get(graph_name, 0)

        dropdowns.nth(0).click()
        graph_el = self.dropdown_items.nth(graph_index)
        graph_el.click()
        self._appears_hidden(graph_el, timeout=3000)

        # Select Category (dropdown index 1 - always stable)
        dropdowns.nth(1).click()
        # Exact text intersected with the item class: escaped, and the
        # page renders 19 .dropdownItems across four dropdowns (graphs,
        # categories, sites, widths - probe 09/02/2026), so a substring
        # could land in the wrong dropdown entirely.
        category_el = self.page.get_by_text(
            category_name, exact=True
        ).and_(self.page.locator(".dropdownItem")).first
        category_el.click()
        self._appears_hidden(category_el, timeout=3000)

        # Select Description (dropdown index 2) - skip for Person
        if category_name.lower() != "person":
            dropdowns.nth(2).click()
            # The section's own controls rendering is the expanded
            # signal: the vehicle icons or the description checkboxes
            desc_controls = self.page.locator(
                # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
                "img[src*='media/carIcon'], .PrivateSwitchBase-input"
            ).filter(visible=True)
            self._appears(desc_controls.first, timeout=5000)

            if category_name.lower() == "vehicle":
                # Select car and bike icons
                car = self.page.locator("img[src*='media/carIcon']").first
                if car.count() > 0:
                    car.click()
                bike = self.page.locator(
                    # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
                    "img[src*='media/motorcycleIcon']"
                ).first
                if bike.count() > 0:
                    bike.click()
            elif description_name:
                # Event with a named description: the checkbox input
                # carries the label in its name attribute
                self.page.locator(
                    f".PrivateSwitchBase-input[name='{description_name}']"
                ).click()
            else:
                # Event: select first visible checkbox in description
                desc_cbs = self.page.locator(
                    ".PrivateSwitchBase-input"
                )
                for i in range(desc_cbs.count()):
                    if desc_cbs.nth(i).is_visible():
                        desc_cbs.nth(i).click()

            # Close description dropdown
            arrows = self.accordion_arrows
            if arrows.count() > 2:
                arrows.nth(2).click()
                # The section's controls hiding is the collapsed signal
                self._appears_hidden(desc_controls.first, timeout=5000)

        # Select Site (index 3 - stable, before camera expansion)
        dropdowns.nth(3).click()
        # Exact first: long site names render ellipsized in the DOM
        # ('Example Corporat...', probe 09/02/2026); when the exact
        # name is not on screen, fall back to an anchored, escaped
        # 10-char prefix.
        site_el = self.page.get_by_text(site_name, exact=True).and_(
            self.page.locator(".dropdownItem")).first
        if not site_el.count():
            site_el = self.page.locator(".dropdownItem").filter(
                has_text=re.compile("^" + re.escape(site_name[:10]))).first
        site_el.click()
        self._appears_hidden(site_el, timeout=3000)

        # Select Camera - use label-based lookup (index 4 is stable
        # but camera expansion adds extra MuiPaper-root after it)
        cam_idx = self._find_section_index("Locations")
        if cam_idx >= 0:
            dropdowns.nth(cam_idx).click()
        else:
            dropdowns.nth(4).click()
        # The All Cameras entry showing is the expanded signal
        all_cameras = self.page.get_by_text("All Cameras", exact=True).first
        self._appears(all_cameras, timeout=5000)

        if "heat" in graph_name.lower():
            # Heat map needs one specific camera (not "All Cameras", a
            # header). Pick the CONFIGURED camera: on the Videonetics
            # site the first row is an offline emulator camera the app
            # will not select, so picking "the first row" built the heat
            # map against no camera (09/16/2026). Fall back to the first
            # selectable row when no camera is configured.
            if camera_name is None:
                from config.base_config import config as _cfg
                camera_name = _cfg.get("test_camera_name")

            if camera_name:
                # The row (not its <p>) owns the click handler and the
                # camera-selected state (trace 08/25/2026). The list can
                # render a hidden copy first, so match by the accordion
                # class and the name and count selected rows by name.
                # Probed 09/16/2026: the row applies camera-selected
                # about 0.5 s after a click once the list has settled; a
                # single click fired before it settled was the Heat_Person
                # miss, so click with a short retry.
                # the list cuts a long name in the DOM ('Soterix Multica...' on
                # US, 09/17/2026), so match the name or its ellipsis cut
                target = (
                    self.page.locator(".location-popup-accordian")
                    .filter(has_text=shown_as(camera_name))
                    # .first: a hidden copy of the list renders first, and
                    # the selected check counts matching rows by name across
                    # both copies, so clicking either row applies the state
                    .first
                )
                try:
                    target.wait_for(state="attached", timeout=8000)
                except PlaywrightError:
                    raise RuntimeError(
                        f"Heat map wanted the configured camera {camera_name!r} "
                        f"but no such row is under All Cameras; update "
                        f"test_camera_name or the site"
                    ) from None
                picked_name = camera_name
                selected = self.page.locator(
                    ".location-popup-accordian.camera-selected"
                ).filter(has_text=shown_as(camera_name))
                for _ in range(5):
                    if selected.count():
                        break
                    target.evaluate("el => el.click()")
                    self.page.wait_for_timeout(600)  # the row applies the state ~0.5 s after the click
            else:
                # No configured camera: the first selectable row. The row
                # (not its <p>) owns the click handler (trace 08/25/2026).
                picked_name = self.page.evaluate("""() => {
                    const papers = document.querySelectorAll('.MuiPaper-root');
                    for (const paper of papers) {
                        const text = (paper.textContent || '').trim();
                        if (!text.startsWith('All Cameras')) continue;
                        const rows = [...paper.querySelectorAll('.location-popup-accordian')];
                        const target = rows.find(r => {
                            const t = (r.textContent || '').trim();
                            return t && t !== 'All Cameras' && !t.match(/^\\d+$/)
                                && !r.classList.contains('camera-selected');
                        });
                        if (target) { target.click(); return (target.textContent || '').trim(); }
                    }
                    return null;
                }""")
                if not picked_name:
                    raise RuntimeError(
                        "Heat map camera pick found no camera row under All Cameras"
                    )
                selected = self.page.locator(
                    ".location-popup-accordian.camera-selected"
                ).filter(has_text=picked_name)

            try:
                expect(selected).not_to_have_count(0, timeout=5000)
            except AssertionError:
                # Name every row and its state so the failure carries the
                # facts a fix needs
                print("[INSIGHTS] heat map camera rows: "
                      + str(self.page.evaluate("""() => Array.from(
                          document.querySelectorAll('.location-popup-accordian')
                        ).map(r => ({text: (r.textContent || '').trim().slice(0, 30),
                                     cls: r.className}))""")))
                raise RuntimeError(
                    f"Heat map camera pick did not apply: '{picked_name}' is not "
                    f"the selected row within 5s; the widget would be created "
                    f"against no camera"
                ) from None
        else:
            # Non-heat: click first visible checkbox ("All Cameras")
            self._click_first_visible_checkbox()
            # Close camera dropdown via its accordion arrow
            cam_arrow_idx = self.page.evaluate("""() => {
                const papers = document.querySelectorAll('.MuiPaper-root');
                for (let i = 0; i < papers.length; i++) {
                    const t = (papers[i].textContent || '').trimStart();
                    if (t.startsWith('Locations')) {
                        const arrow = papers[i].querySelector(
                            "img[src*='downAccordionIcon']"
                        );
                        if (arrow) { arrow.click(); return i; }
                    }
                }
                return -1;
            }""")
            # The All Cameras entry hiding is the collapsed signal
            self._appears_hidden(all_cameras, timeout=5000)

        # Select Duration - use label-based lookup (index shifts
        # after camera expansion adds extra MuiPaper-root)
        dur_idx = self._find_section_index("Duration")
        if dur_idx >= 0:
            dropdowns.nth(dur_idx).click()
        else:
            dropdowns.nth(5).click()
        yesterday_el = self.page.locator(
            ".dropdownItem:has-text('Yesterday')"
        ).first
        yesterday_el.click()
        self._appears_hidden(yesterday_el, timeout=3000)

        # Select Widget Size - use label-based lookup
        size_idx = self._find_section_index("Widget Size")
        if size_idx >= 0:
            dropdowns.nth(size_idx).click()
        else:
            dropdowns.nth(6).click()
        size_label = WIDGET_SIZE.get(graph_name, WIDGET_SIZE["default"])
        size_el = self.page.locator(
            f".dropdownItem:has-text('{size_label}')"
        ).first
        size_el.click()
        self._appears_hidden(size_el, timeout=3000)

        # Save & Preview
        self.save_button.click()

        # The success toast is the created signal
        self.widget_success_msg.wait_for(
            state="visible", timeout=60000
        )

        # Close the creation tab
        self.close_tab()

        return widget_name

    # --- Widget search ---

    def search_widget(self, widget_name: str):
        """Search for a widget by name in the Widgets tab."""
        self.switch_to_widgets()

        self.search_input.click()
        self.search_input.fill("")
        self.search_input.fill(widget_name)
        self._widgets_settled()

    def _open_widget_menu(self):
        """Open the three-dot menu on the last matching widget."""
        self.three_dots.last.click()
        # The menu popover carries the widget actions. :visible skips
        # stale keepMounted popovers left hidden in the DOM.
        self.page.locator(".MuiPopover-root:visible").first.wait_for(
            state="visible", timeout=10000
        )

    # --- Widget operations ---

    def view_widget(self, widget_name: str):
        """Open a widget's View page via the three-dot menu."""
        self.search_widget(widget_name)
        self._open_widget_menu()

        view_item = self.page.locator("li:has-text('View')").first
        view_item.click()

        # Wait for the back arrow (View page loaded)
        self.back_arrow.first.wait_for(state="visible", timeout=30000)
        self._wait_for_loader_finish()

        # Go back; the arrow leaves the page with the View tab
        self.back_arrow.first.click()
        self._appears_hidden(self.back_arrow.first, timeout=10000)

    def download_report(self, widget_name: str):
        """Download a widget's report via the three-dot menu."""
        self.search_widget(widget_name)
        self._open_widget_menu()

        report_item = self.page.locator("li:has-text('Report')").first
        report_item.click()

        # Wait for three-dot menu popover to dismiss
        try:
            self.page.locator(".MuiPopover-root").wait_for(
                state="hidden", timeout=5000
            )
        except Exception:
            self.page.keyboard.press("Escape")

        # Wait for download button
        self.report_download_button.wait_for(
            state="visible", timeout=30000
        )

        # The browser download starting is the completion signal: a
        # toast is no oracle - it can show and dismiss unseen while a
        # slow report generates.
        try:
            with self.page.expect_download(timeout=90000):
                try:
                    self.report_download_button.click(timeout=5000)
                except PlaywrightError:
                    # Overlay might block - force click as fallback
                    self.report_download_button.click(force=True)
        except PlaywrightTimeoutError:
            raise AssertionError(
                f"No report download started for '{widget_name}' "
                "within 90s of clicking the download button"
            ) from None

    def delete_widget(self, widget_name: str):
        """Delete a widget via the three-dot menu and verify deletion."""
        self.search_widget(widget_name)
        self._open_widget_menu()

        delete_item = self.page.locator("li:has-text('Delete')").first
        delete_item.click()

        # Confirm deletion; the dialog leaves the DOM with the button
        self.delete_confirm_button.wait_for(
            state="visible", timeout=30000
        )
        self.delete_confirm_button.click()
        self._appears_hidden(self.delete_confirm_button, timeout=10000)

        # Verify widget is gone by searching again. The grid can render
        # the deleted card until the server refetch lands, so poll for
        # the empty state instead of trusting the first read.
        self.search_widget(widget_name)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if self.three_dots.count() == 0:
                return True
            self.page.wait_for_timeout(250)  # server refetch may lag
        return self.three_dots.count() == 0

    # --- Helpers ---

    def _wait_for_loader_finish(self, timeout: int = 60000):
        """Wait for the CircularProgress loader to appear then disappear."""
        try:
            # Short appear grace: instant responses show no loader at all
            self.loader.first.wait_for(state="visible", timeout=2000)
        # an instant response shows no loader at all; the hidden wait
        # below covers the slow case
        except Exception:
            pass
        try:
            self.loader.first.wait_for(state="hidden", timeout=timeout)
        # a lingering spinner is a settle, not the oracle; every caller
        # waits on its own next element
        except Exception:
            pass

    @staticmethod
    def _appears(locator, timeout: int = 5000) -> bool:
        """True when the element shows within timeout, False otherwise."""
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except PlaywrightError:
            return False

    @staticmethod
    def _appears_hidden(locator, timeout: int = 5000) -> bool:
        """True when the element hides within timeout, False otherwise."""
        try:
            locator.wait_for(state="hidden", timeout=timeout)
            return True
        except PlaywrightError:
            return False

    def _widgets_settled(self, timeout_s: float = 5.0):
        """Wait for the widget grid count to hold for a full second.

        A query that matches the same set never changes the count, so
        stability is the signal, not change: the first return is after
        one second of equal reads, which also gives the refetch a
        lead-in instead of settling on a transient state.
        """
        deadline = time.monotonic() + timeout_s
        last = -1
        stable = 0
        while time.monotonic() < deadline:
            current = self.three_dots.count()
            stable = stable + 1 if current == last else 0
            if stable >= 4:
                return
            last = current
            self.page.wait_for_timeout(250)  # poll tick for filter settle
