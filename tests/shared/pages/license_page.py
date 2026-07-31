"""License Page Object Model.

Shared page object for Licenses module - Available Licenses, Assigned Licenses,
device list, assign/unassign/suspend workflows, and CSV export.
Used by all License test modules.
"""
from playwright.sync_api import Page, expect


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
            "img[src*='downloadLicense'], img[src*='download'], img[alt='Download'], "
            "button:has-text('CSV'), button:has-text('Export'), button:has-text('Download')"
        ).first

        # Assigned Licenses - site expansion (MUI Table structure)
        self.site_rows = page.locator("tr.MuiTableRow-root")
        self.site_expand_icons = page.locator(
            "svg[data-testid='ExpandMoreIcon'], "
            "svg[class*='MuiSvgIcon-root']:has(path[d*='16.59'])"
        )
        self.site_toggle_switches = page.locator(".MuiSwitch-root")

        # Feature-level rows (inside expanded site)
        self.feature_rows = page.locator(
            "div[class*='feature-row'], tr[class*='feature'], "
            "div[class*='nested'], div[class*='sub-row']"
        )
        self.feature_toggle_switches = page.locator(
            "div[class*='feature'] .MuiSwitch-root, "
            "div[class*='nested'] .MuiSwitch-root"
        )

        # Device list (drill-down from feature)
        self.device_list_rows = page.locator(
            "tr[class*='device'], div[class*='device-row']"
        )
        self.breadcrumb = page.locator(
            "nav[aria-label='breadcrumb'], div[class*='breadcrumb']"
        )

        # Three-dot menu actions
        self.options_icons = page.locator(
            "img[src*='optionIcon'], img[src*='option'], "
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

        # Assign New License modal
        self.assign_button = page.locator(
            "button.add-btn, button:has-text('Assign New License'), "
            "button:has-text('Assign License'), button:has-text('Assign')"
        ).first
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
        # Wait for any overlays to clear
        self.page.wait_for_timeout(1000)

        # Click Admin menu first
        admin_link = self.page.locator("a[href*='admin']").first
        if not admin_link.is_visible():
            admin_link = self.page.get_by_text("Admin").first
        admin_link.wait_for(state="visible", timeout=10000)
        admin_link.click(force=True)
        self.page.wait_for_timeout(2000)

        # Then click Licenses submenu
        license_link = self.page.locator("a[href*='license']").first
        if not license_link.is_visible():
            license_link = self.page.get_by_text("License").first
        license_link.wait_for(state="visible", timeout=10000)
        license_link.click(force=True)
        self.page.wait_for_timeout(3000)
        self._wait_for_page_ready()

    def _wait_for_page_ready(self):
        """Wait for loaders to hide and content to appear."""
        # Wait for any loaders to disappear
        loaders_hidden = False
        if self.loader.count() > 0:
            try:
                self.loader.first.wait_for(state="hidden", timeout=30000)
                loaders_hidden = True
            except Exception:
                pass

        # If we waited for loaders, add extra time for content to render
        if loaders_hidden:
            self.page.wait_for_timeout(2000)

        # Wait for main content to be visible
        content_found = False
        try:
            self.total_licenses_widget.wait_for(state="visible", timeout=20000)
            content_found = True
        except Exception:
            pass

        # Extra wait if content took time to appear
        if content_found:
            self.page.wait_for_timeout(1000)

    # ----- Tab switching -----

    def switch_to_available_tab(self):
        """Click the Available Licenses tab."""
        self.available_tab.wait_for(state="visible", timeout=10000)
        self.available_tab.click(force=True)
        self.page.wait_for_timeout(2000)
        self._wait_for_page_ready()

    def switch_to_assigned_tab(self):
        """Click the Assigned Licenses tab."""
        self.assigned_tab.wait_for(state="visible", timeout=10000)
        self.assigned_tab.click(force=True)
        self.page.wait_for_timeout(2000)
        self._wait_for_page_ready()

    # ----- Search -----

    def search(self, query: str):
        """Type into the search input."""
        self.search_input.wait_for(state="visible", timeout=10000)
        self.search_input.fill(query)
        self.page.wait_for_timeout(2000)

    def clear_search(self):
        """Clear the search field."""
        self.search_input.fill("")
        self.page.wait_for_timeout(2000)

    # ----- Available Licenses -----

    def get_visible_row_count(self) -> int:
        """Count visible rows in the license table."""
        self.page.wait_for_timeout(1000)
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
        # Hover to activate the element
        self.csv_download_button.hover()
        self.page.wait_for_timeout(500)
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
        expandable = self.site_expand_icons.nth(index)
        expandable.click()
        self.page.wait_for_timeout(2000)

    def collapse_site(self, index: int = 0):
        """Collapse an expanded site row."""
        expandable = self.site_expand_icons.nth(index)
        expandable.click()
        self.page.wait_for_timeout(1000)

    def toggle_site_enable(self, index: int = 0):
        """Toggle the enable/disable switch for a site."""
        self.site_toggle_switches.nth(index).click()
        self.page.wait_for_timeout(2000)

    # ----- Feature-Level -----

    def get_feature_count(self) -> int:
        """Count feature rows inside an expanded site."""
        return self.feature_rows.count()

    def toggle_feature_enable(self, index: int = 0):
        """Toggle the enable/disable switch for a feature."""
        self.feature_toggle_switches.nth(index).click()
        self.page.wait_for_timeout(2000)

    def click_feature_device_link(self, index: int = 0):
        """Click a feature row to navigate to the device list."""
        self.feature_rows.nth(index).click()
        self.page.wait_for_timeout(3000)

    # ----- Device List -----

    def get_device_count(self) -> int:
        """Count devices in the device list page."""
        return self.device_list_rows.count()

    def open_device_menu(self, index: int = 0):
        """Open the three-dot options menu for a device."""
        self.options_icons.nth(index).click()
        self.page.wait_for_timeout(1000)

    def suspend_device(self, index: int = 0):
        """Suspend a device license via the options menu."""
        self.open_device_menu(index)
        self.suspend_option.click()
        self.page.wait_for_timeout(1000)

    def confirm_action(self):
        """Click the confirm button in the dialog."""
        self.confirm_button.click()
        self.page.wait_for_timeout(2000)
        self._wait_for_page_ready()

    def cancel_action(self):
        """Click the cancel button in the dialog."""
        self.cancel_button.click()
        self.page.wait_for_timeout(1000)

    def unassign_device(self, index: int = 0):
        """Unassign a device license via the options menu."""
        self.open_device_menu(index)
        self.unassign_option.click()
        self.page.wait_for_timeout(1000)

    # ----- Assign New License -----

    def open_assign_modal(self):
        """Click the Assign New License button."""
        self.assign_button.wait_for(state="visible", timeout=10000)
        self.assign_button.click(force=True)
        self.page.wait_for_timeout(3000)

    def close_assign_modal(self):
        """Close the assign modal."""
        self.modal_close.click()
        self.page.wait_for_timeout(1000)

    def select_site_in_modal(self, site_name: str):
        """Select a site from the dropdown in the assign modal."""
        self.site_dropdown.click()
        self.page.wait_for_timeout(1000)
        option = self.page.locator(
            f"li[role='option']:has-text('{site_name}'), "
            f"option:has-text('{site_name}')"
        ).first
        option.click()
        self.page.wait_for_timeout(2000)

    def select_device(self, index: int = 0):
        """Select a device checkbox for assignment."""
        self.device_checkboxes.nth(index).click(force=True)
        self.page.wait_for_timeout(500)

    def select_all_devices(self):
        """Select the 'Select All' checkbox."""
        self.select_all_checkbox.click(force=True)
        self.page.wait_for_timeout(1000)

    def confirm_assignment(self):
        """Click the final Assign button in the modal."""
        self.assign_confirm_button.click()
        self.page.wait_for_timeout(3000)
        self._wait_for_page_ready()

    # ----- Navigation helpers -----

    def navigate_back_via_breadcrumb(self):
        """Click the breadcrumb to go back to the previous level."""
        links = self.breadcrumb.locator("a, span[class*='link']")
        if links.count() > 0:
            links.first.click()
            self.page.wait_for_timeout(2000)

    def get_page_title_text(self) -> str:
        """Return the main heading text on the current licenses sub-page."""
        heading = self.page.locator(
            "h1, h2, h3, div[class*='title']"
        ).first
        if heading.count() > 0:
            return heading.inner_text().strip()
        return ""
