"""Insights Page Object Model.

Models the Insights page including navigation to System Status dashboard,
switching to Widgets tab, widget creation with various graph types and
categories, widget search, and widget operations (view, report, delete).
"""
import datetime
from playwright.sync_api import Page, expect


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
            "img[src*='media/downAccordionIcon']"
        )

        # Widget search
        self.search_input = page.locator("input[placeholder='Search']")

        # Widget operations
        self.three_dots = page.locator("img[src*='media/three-dots']")
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
                self.page.wait_for_timeout(1000)
            except Exception:
                pass
            return

        self.insights_nav_link.click()

        # Wait for System Status link to appear (page loaded)
        self.system_status_link.first.wait_for(
            state="visible", timeout=30000
        )
        self._wait_for_loader_finish()

    def open_system_status(self, site_name: str = "Driver Site"):
        """Open the System Status dashboard and select a site.

        Navigates to Insights, clicks System Status, selects the given
        site from the dropdown, and verifies 'Devices' text appears.
        """
        self.navigate()

        self.system_status_link.first.click()

        # Wait for System Status to load
        self.site_dropdown.wait_for(state="visible", timeout=30000)
        self._wait_for_loader_finish()

        # Select site
        self.site_dropdown.click()
        self.page.wait_for_timeout(1000)

        site_option = self.page.locator(
            f"div:text('{site_name}')"
        ).first
        site_option.wait_for(state="visible", timeout=10000)
        site_option.click()
        self.page.wait_for_timeout(3000)
        self._wait_for_loader_finish()

    def close_tab(self):
        """Close the currently open sub-tab (System Status, widget view, etc.)."""
        try:
            self.close_tab_icon.click()
            self.page.wait_for_timeout(1000)
        except Exception:
            pass

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
                      site_name: str = "Driver Site") -> str:
        """Create a widget with specified graph type and category.

        Returns the generated widget name for later search/operations.
        """
        self.switch_to_widgets()

        # Generate unique widget name
        now = datetime.datetime.now()
        ts = now.strftime("%Y%m%d%H%M%S")
        widget_name = f"{graph_name}_{category_name}_{ts}"

        # Click Create New Widget
        self.create_widget_button.click()

        # Wait for widget creation form
        self.save_button.wait_for(state="visible", timeout=60000)
        self.page.wait_for_timeout(1000)

        # Enter widget name
        self.widget_name_input.click()
        self.widget_name_input.fill("")
        self.widget_name_input.fill(widget_name)

        # Select Graph Type (dropdown index 0 - always stable)
        dropdowns = self.form_dropdowns
        graph_index = GRAPH_INDEX.get(graph_name, 0)

        dropdowns.nth(0).click()
        self.page.wait_for_timeout(500)
        self.dropdown_items.nth(graph_index).click()
        self.page.wait_for_timeout(500)

        # Select Category (dropdown index 1 - always stable)
        dropdowns.nth(1).click()
        self.page.wait_for_timeout(500)
        category_el = self.page.locator(
            f".dropdownItem:has-text('{category_name}')"
        ).first
        category_el.click()
        self.page.wait_for_timeout(500)

        # Select Description (dropdown index 2) - skip for Person
        if category_name.lower() != "person":
            dropdowns.nth(2).click()
            self.page.wait_for_timeout(500)

            if category_name.lower() == "vehicle":
                # Select car and bike icons
                car = self.page.locator("img[src*='media/carIcon']").first
                if car.count() > 0:
                    car.click()
                bike = self.page.locator(
                    "img[src*='media/motorcycleIcon']"
                ).first
                if bike.count() > 0:
                    bike.click()
            else:
                # Event: select first visible checkbox in description
                desc_cbs = self.page.locator(
                    ".PrivateSwitchBase-input"
                )
                for i in range(desc_cbs.count()):
                    if desc_cbs.nth(i).is_visible():
                        desc_cbs.nth(i).click()
                        self.page.wait_for_timeout(200)

            self.page.wait_for_timeout(500)
            # Close description dropdown
            arrows = self.accordion_arrows
            if arrows.count() > 2:
                arrows.nth(2).click()
                self.page.wait_for_timeout(500)

        # Select Site (index 3 - stable, before camera expansion)
        dropdowns.nth(3).click()
        self.page.wait_for_timeout(500)
        site_partial = site_name[:10]
        site_el = self.page.locator(
            f"p:has-text('{site_partial}')"
        ).first
        site_el.click()
        self.page.wait_for_timeout(500)

        # Select Camera - use label-based lookup (index 4 is stable
        # but camera expansion adds extra MuiPaper-root after it)
        cam_idx = self._find_section_index("Locations")
        if cam_idx >= 0:
            dropdowns.nth(cam_idx).click()
        else:
            dropdowns.nth(4).click()
        self.page.wait_for_timeout(500)

        if "heat" in graph_name.lower():
            # Heat map requires a single specific camera (not "All
            # Cameras" which is just a header).  Select the first
            # individual camera listed under the expanded section.
            self.page.evaluate("""() => {
                // Find the camera list panel that contains individual
                // camera <p> elements (the one starting with
                // "All Cameras" followed by camera names)
                const papers = document.querySelectorAll('.MuiPaper-root');
                for (const paper of papers) {
                    const text = (paper.textContent || '').trim();
                    if (text.startsWith('All Cameras')) {
                        // Get all <p> children - skip "All Cameras" header
                        const ps = paper.querySelectorAll('p');
                        for (const p of ps) {
                            const t = p.textContent.trim();
                            if (t && t !== 'All Cameras' && !t.match(/^\\d+$/)) {
                                p.click();
                                return;
                            }
                        }
                    }
                }
            }""")
            self.page.wait_for_timeout(500)
        else:
            # Non-heat: click first visible checkbox ("All Cameras")
            self._click_first_visible_checkbox()
            self.page.wait_for_timeout(500)
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
            self.page.wait_for_timeout(500)

        # Select Duration - use label-based lookup (index shifts
        # after camera expansion adds extra MuiPaper-root)
        dur_idx = self._find_section_index("Duration")
        if dur_idx >= 0:
            dropdowns.nth(dur_idx).click()
        else:
            dropdowns.nth(5).click()
        self.page.wait_for_timeout(500)
        yesterday_el = self.page.locator(
            ".dropdownItem:has-text('Yesterday')"
        ).first
        yesterday_el.click()
        self.page.wait_for_timeout(500)

        # Select Widget Size - use label-based lookup
        size_idx = self._find_section_index("Widget Size")
        if size_idx >= 0:
            dropdowns.nth(size_idx).click()
        else:
            dropdowns.nth(6).click()
        self.page.wait_for_timeout(500)
        size_label = WIDGET_SIZE.get(graph_name, WIDGET_SIZE["default"])
        size_el = self.page.locator(
            f".dropdownItem:has-text('{size_label}')"
        ).first
        size_el.click()
        self.page.wait_for_timeout(500)

        # Save & Preview
        self.save_button.click()

        # Wait for success message
        self.widget_success_msg.wait_for(
            state="visible", timeout=60000
        )
        self.page.wait_for_timeout(3000)

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
        self.page.wait_for_timeout(2000)

    # --- Widget operations ---

    def view_widget(self, widget_name: str):
        """Open a widget's View page via the three-dot menu."""
        self.search_widget(widget_name)

        dots = self.three_dots
        dots.last.click()
        self.page.wait_for_timeout(1000)

        view_item = self.page.locator("li:has-text('View')").first
        view_item.click()

        # Wait for the back arrow (View page loaded)
        self.back_arrow.first.wait_for(state="visible", timeout=30000)
        self.page.wait_for_timeout(2000)

        # Go back
        self.back_arrow.first.click()
        self.page.wait_for_timeout(1000)

    def download_report(self, widget_name: str):
        """Download a widget's report via the three-dot menu."""
        self.search_widget(widget_name)

        dots = self.three_dots
        dots.last.click()
        self.page.wait_for_timeout(1000)

        report_item = self.page.locator("li:has-text('Report')").first
        report_item.click()

        # Wait for three-dot menu popover to dismiss
        try:
            self.page.locator(".MuiPopover-root").wait_for(
                state="hidden", timeout=5000
            )
        except Exception:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)

        # Wait for download button
        self.report_download_button.wait_for(
            state="visible", timeout=30000
        )
        self.page.wait_for_timeout(1000)

        try:
            self.report_download_button.click(timeout=5000)
        except Exception:
            # Overlay might block - force click as fallback
            self.report_download_button.click(force=True)

        # Wait for success message (report generation can be slow)
        try:
            self.report_success_msg.wait_for(
                state="visible", timeout=60000
            )
        except Exception:
            # Toast may have appeared and dismissed before we checked,
            # or download completed without a toast. Verify by checking
            # the download button is no longer in a loading state.
            self.page.wait_for_timeout(3000)
        self.page.wait_for_timeout(1000)

    def delete_widget(self, widget_name: str):
        """Delete a widget via the three-dot menu and verify deletion."""
        self.search_widget(widget_name)

        dots = self.three_dots
        dots.last.click()
        self.page.wait_for_timeout(1000)

        delete_item = self.page.locator("li:has-text('Delete')").first
        delete_item.click()

        # Confirm deletion
        self.delete_confirm_button.wait_for(
            state="visible", timeout=30000
        )
        self.delete_confirm_button.click()
        self.page.wait_for_timeout(2000)

        # Verify widget is gone by searching again
        self.search_widget(widget_name)
        self.page.wait_for_timeout(2000)

        return self.three_dots.count() == 0

    # --- Helpers ---

    def _wait_for_loader_finish(self, timeout: int = 60000):
        """Wait for the CircularProgress loader to appear then disappear."""
        try:
            self.loader.first.wait_for(state="visible", timeout=5000)
        except Exception:
            pass
        try:
            self.loader.first.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass
