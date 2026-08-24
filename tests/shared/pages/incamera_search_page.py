"""In-Camera Search Page Object Model.

Models the in-camera forensic search that opens from within a video tile's
player controls. Allows searching for Person/Vehicle events within a specific
camera's feed using category, description, and duration filters.
"""
from playwright.sync_api import Error as PlaywrightError, Page


class InCameraSearchPage:
    """Page object for the in-camera search overlay."""

    def __init__(self, page: Page):
        self.page = page

        # Search trigger (from video player controls)
        self.search_icon = page.locator(
            # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
            "img[src*='videoplayer/Search']"
        )

        # Filter dropdowns
        self.filter_containers = page.locator(".in-camera-box-container")
        self.dropdown_items = page.locator(".dropdownItem")

        # Gender/description
        self.gender_container = page.locator(".gender-option-container")

        # Search button (last "Search" text on the page)
        self.search_button = page.locator("text=Search").last

        # Results
        self.results_grid = page.locator(".twoColumnGrid")
        self.result_images = page.locator("[class*='imageResults']")

        # Playback
        self.play_icon = page.locator("img[src*='media/video-player-icon']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.play_button = page.locator("img[src*='media/play']")

        # Loader
        self.loader = page.locator("[class*='CircularProgress']")

    # --- Open Search ---

    def open_search(self):
        """Open the in-camera search overlay from the video player controls."""
        self.search_icon.wait_for(state="visible", timeout=10000)
        self.search_icon.click()
        # the filter containers rendering is the overlay-open signal
        self.filter_containers.first.wait_for(state="visible", timeout=10000)

    # --- Filters ---

    def select_category(self, index: int = 0):
        """Select a category from the first dropdown (0=Person, 1=Vehicle, etc.)."""
        containers = self.filter_containers
        for i in range(containers.count()):
            text = containers.nth(i).inner_text()
            if "Category" in text:
                containers.nth(i).click()
                # the item's visible wait is the opened signal; the item
                # hiding again is the selection-applied signal
                item = self.dropdown_items.nth(index)
                item.wait_for(state="visible", timeout=10000)
                item.click()
                self._appears_hidden(item, timeout=5000)
                return

    def select_description_gender(self, gender: str = "Male"):
        """Select a gender from the description dropdown."""
        containers = self.filter_containers
        for i in range(containers.count()):
            text = containers.nth(i).inner_text()
            if "Description" in text:
                containers.nth(i).click()
                # the gender container rendering is the opened signal
                self.gender_container.wait_for(state="visible", timeout=10000)
                gender_option = self.gender_container.locator(
                    f"p:text-is('{gender}')"
                )
                if gender_option.count() > 0:
                    gender_option.click()
                # a gender pick has no DOM signal of its own; the next
                # section open is the natural next wait
                self.page.wait_for_timeout(500)
                return

    def select_duration(self, index: int = 4):
        """Select a duration from the duration dropdown (4=Today)."""
        containers = self.filter_containers
        for i in range(containers.count()):
            text = containers.nth(i).inner_text()
            if "Category" not in text and "Description" not in text:
                containers.nth(i).click()
                # the first item rendering is the opened signal
                self._appears(self.dropdown_items.first, timeout=10000)
                if self.dropdown_items.count() > index:
                    item = self.dropdown_items.nth(index)
                    item.click()
                    # the item hiding is the selection-applied signal
                    self._appears_hidden(item, timeout=5000)
                return

    # --- Search & Results ---

    def execute_search(self, timeout: int = 60000):
        """Click the search button and wait for results."""
        self.search_button.click()

        # Wait for loader to finish. Bounded and non-fatal: the page
        # keeps several CircularProgress spinners alive (tile
        # placeholders never stop), so the results wait below is the
        # real signal.
        try:
            self.loader.first.wait_for(state="visible", timeout=5000)
        # the loader may never show on a fast search; the results wait
        # below is the oracle
        except Exception:
            pass
        try:
            self.loader.first.wait_for(state="hidden", timeout=15000)
        # tile placeholder spinners never stop; the results wait below
        # is the oracle
        except Exception:
            pass

        # Wait for results
        self.result_images.first.wait_for(state="visible", timeout=timeout)

    def get_result_count(self) -> int:
        """Return the number of search result images."""
        return self.result_images.count()

    def has_results(self) -> bool:
        """Return True if search results are present."""
        return self.result_images.count() > 0

    def play_result(self, index: int = 0, timeout: int = 30000):
        """Hover a result and click the play button."""
        result = self.result_images.nth(index)
        result.hover()

        # the hover-rendered play icon: a bounded wait, then click it,
        # falling back to the result itself when it never shows
        play_btn = result.locator("img[src*='media/video-player-icon']")
        if self._appears(play_btn.first, timeout=3000):
            play_btn.first.click()
        else:
            # Fallback: click the result itself
            result.click()

        # the player's play button appearing is the video-loaded signal
        self.play_button.first.wait_for(state="visible", timeout=timeout)

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
