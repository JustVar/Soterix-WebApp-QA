"""In-Camera Search Page Object Model.

Models the in-camera forensic search that opens from within a video tile's
player controls. Allows searching for Person/Vehicle events within a specific
camera's feed using category, description, and duration filters.
"""
from playwright.sync_api import Page


class InCameraSearchPage:
    """Page object for the in-camera search overlay."""

    def __init__(self, page: Page):
        self.page = page

        # Search trigger (from video player controls)
        self.search_icon = page.locator(
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
        self.play_button = page.locator("img[src*='media/play']")

        # Loader
        self.loader = page.locator("[class*='CircularProgress']")

    # --- Open Search ---

    def open_search(self):
        """Open the in-camera search overlay from the video player controls."""
        self.search_icon.wait_for(state="visible", timeout=10000)
        self.search_icon.click()
        self.page.wait_for_timeout(2000)

    # --- Filters ---

    def select_category(self, index: int = 0):
        """Select a category from the first dropdown (0=Person, 1=Vehicle, etc.)."""
        containers = self.filter_containers
        for i in range(containers.count()):
            text = containers.nth(i).inner_text()
            if "Category" in text:
                containers.nth(i).click()
                self.page.wait_for_timeout(1000)
                self.dropdown_items.nth(index).click()
                self.page.wait_for_timeout(1000)
                return

    def select_description_gender(self, gender: str = "Male"):
        """Select a gender from the description dropdown."""
        containers = self.filter_containers
        for i in range(containers.count()):
            text = containers.nth(i).inner_text()
            if "Description" in text:
                containers.nth(i).click()
                self.page.wait_for_timeout(1000)
                gender_option = self.gender_container.locator(
                    f"p:text-is('{gender}')"
                )
                if gender_option.count() > 0:
                    gender_option.click()
                self.page.wait_for_timeout(1000)
                return

    def select_duration(self, index: int = 4):
        """Select a duration from the duration dropdown (4=Today)."""
        containers = self.filter_containers
        for i in range(containers.count()):
            text = containers.nth(i).inner_text()
            if "Category" not in text and "Description" not in text:
                containers.nth(i).click()
                self.page.wait_for_timeout(1000)
                if self.dropdown_items.count() > index:
                    self.dropdown_items.nth(index).click()
                self.page.wait_for_timeout(1000)
                return

    # --- Search & Results ---

    def execute_search(self, timeout: int = 60000):
        """Click the search button and wait for results."""
        self.search_button.click()
        self.page.wait_for_timeout(1000)

        # Wait for loader to finish. Bounded and non-fatal: the page
        # keeps several CircularProgress spinners alive (tile
        # placeholders never stop), so the results wait below is the
        # real signal.
        try:
            self.loader.first.wait_for(state="visible", timeout=5000)
        except Exception:
            pass
        try:
            self.loader.first.wait_for(state="hidden", timeout=15000)
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
        self.page.wait_for_timeout(500)

        play_btn = result.locator("img[src*='media/video-player-icon']")
        if play_btn.count() > 0:
            play_btn.click()
        else:
            # Fallback: click the result itself
            result.click()
        self.page.wait_for_timeout(2000)

        # Wait for the play button to appear (video loaded)
        self.play_button.first.wait_for(state="visible", timeout=timeout)
