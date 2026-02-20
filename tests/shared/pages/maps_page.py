"""Maps Page Object Model.

Models the standalone Maps page (sidebar nav link), including site selection,
map card grid, camera overlay, and online camera playback.
"""
from playwright.sync_api import Page, expect


class MapsPage:
    """Page object for the Maps page."""

    def __init__(self, page: Page):
        self.page = page

        # Navigation
        self.maps_nav_link = page.locator("a[href*='maps']")

        # Site dropdown
        self.site_dropdown = page.locator(".dropdown-box")
        self.dropdown_text = page.locator(".dropdown_text")
        self.dropdown_options = page.locator(".optionsdataDiv")

        # Map cards grid
        self.map_cards = page.locator(".grid-cards")

        # Device count inside a map card
        self.device_count_elements = page.locator(".icon-text-aligner, .icon-text-alinger")

        # Camera icons on opened map
        self.camera_icons = page.locator("img[src*='media/cameraIcon']")
        self.online_camera_icons = page.locator("img[src*='media/cameraIconGreen']")

        # Loader
        self.loader = page.locator(".MuiCircularProgress-root")

        # Stream failure
        self.stream_failed_text = page.locator("text=failed to load")

    # --- Navigation ---

    def navigate(self):
        """Navigate to the Maps page via sidebar nav link."""
        self.maps_nav_link.click()
        self._wait_for_dropdown_loaded()

    def _wait_for_dropdown_loaded(self):
        """Wait for the site dropdown to finish loading sites."""
        self.dropdown_text.wait_for(state="visible", timeout=15000)

        # Poll until dropdown text no longer says "sites" (loading state)
        for _ in range(20):
            title = self.dropdown_text.get_attribute("title") or ""
            if "sites" not in title.lower():
                break
            self.page.wait_for_timeout(3000)

        self.page.wait_for_timeout(1000)

    # --- Site selection ---

    def select_site(self, site_name: str):
        """Open dropdown and select a site by name."""
        self.site_dropdown.click()
        self.page.wait_for_timeout(1000)

        self.dropdown_options.wait_for(state="visible", timeout=10000)
        site_option = self.dropdown_options.locator(f"text={site_name}")
        site_option.scroll_into_view_if_needed()
        site_option.click()

        # Wait for map cards to appear
        self.map_cards.first.wait_for(state="visible", timeout=60000)
        self.page.wait_for_timeout(1000)

    def get_site_options(self) -> list:
        """Open dropdown and return available site names."""
        self.site_dropdown.click()
        self.page.wait_for_timeout(1000)

        self.dropdown_options.wait_for(state="visible", timeout=10000)
        options = self.dropdown_options.locator("p, div, span")
        texts = []
        for i in range(options.count()):
            text = options.nth(i).inner_text().strip()
            if text and text not in texts:
                texts.append(text)

        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        return texts

    def get_selected_site_text(self) -> str:
        """Return the currently selected site name from the dropdown."""
        return (self.dropdown_text.get_attribute("title") or "").strip()

    # --- Map cards ---

    def get_map_card_count(self) -> int:
        """Return the number of map cards displayed."""
        return self.map_cards.count()

    def find_map_with_cameras(self):
        """Find and return the first map card that has cameras (device count > 0).

        Returns the card locator, or None if no map has cameras.
        """
        card_count = self.map_cards.count()
        for i in range(card_count):
            card = self.map_cards.nth(i)
            device_elements = card.locator(".icon-text-aligner div, .icon-text-alinger div")
            # The second div inside icon-text-aligner contains the count
            if device_elements.count() >= 2:
                count_text = device_elements.nth(1).inner_text().strip()
                if count_text != "0":
                    return card
        return None

    # --- Map interaction ---

    def open_map(self, map_card):
        """Click a map card to open it and wait for camera icons to appear."""
        map_card.click()
        self.camera_icons.first.wait_for(state="visible", timeout=60000)
        self.page.wait_for_timeout(1000)

    def get_online_camera_count(self) -> int:
        """Return the number of online (green) camera icons on the open map."""
        return self.online_camera_icons.count()

    def play_camera(self, index: int = 0):
        """Click an online camera icon to play its stream."""
        self.online_camera_icons.nth(index).click()
        self._wait_for_loader_finish()

    def _wait_for_loader_finish(self):
        """Wait for CircularProgress loader to appear and disappear."""
        try:
            if self.loader.count() > 0 and self.loader.first.is_visible():
                self.loader.first.wait_for(state="hidden", timeout=60000)
        except Exception:
            pass
        self.page.wait_for_timeout(2000)

    def is_stream_failed(self) -> bool:
        """Check if stream shows a 'failed to load' message."""
        return self.stream_failed_text.count() > 0
