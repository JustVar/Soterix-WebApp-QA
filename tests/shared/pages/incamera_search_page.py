"""In-Camera Search Page Object Model.

Models the in-camera forensic search that opens from within a video tile's
player controls. Allows searching for Person/Vehicle events within a specific
camera's feed using category, description, and duration filters.
"""
import re

from playwright.sync_api import Error as PlaywrightError, Page

from tests.shared.helpers.search_job import SearchJob, require_results, watch_search


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

    def select_duration(self, label: str = "Today"):
        """Pick a duration by its label ("Today", "Last 7 Days", ...).

        The list is the Search page's (Last 1 Hour, Last 2 Hours, Today,
        Yesterday, Last 7 Days, Last 30 Days, Custom). Picking by index
        chose Last 7 Days once two options were added at the top, and that
        row sits under the player's "camera failed to load" banner, so the
        click never landed (09/11/2026).
        """
        containers = self.filter_containers
        for i in range(containers.count()):
            text = containers.nth(i).inner_text()
            if "Category" not in text and "Description" not in text:
                containers.nth(i).click()
                # the item rendering is the opened signal; a label the
                # list does not offer fails here, by name
                item = self.dropdown_items.filter(has_text=re.compile(
                    rf"^\s*{re.escape(label)}\s*$"))
                item.wait_for(state="visible", timeout=10000)
                item.click()
                # the item hiding is the selection-applied signal
                self._appears_hidden(item, timeout=5000)
                return
        raise AssertionError(
            "the in-camera search overlay has no Duration section "
            "(Category and Description only)")

    # --- Search & Results ---

    def execute_search(self, timeout: int = 60000) -> SearchJob:
        """Click Search and return once the server's job has delivered results.

        The in-camera search runs the same server job as the Search page
        (tests/shared/helpers/search_job.py), scoped to the one camera.
        `timeout` caps the server's work. A search that finishes with
        nothing skips with the measurements; one that never ran or never
        finished fails, naming which. The page's own spinners are not
        consulted: tile placeholder spinners never stop, so they were never
        a signal.
        """
        job = watch_search(self.page, self.search_button.click, timeout_ms=timeout)
        require_results(job, surface="In-camera search")
        # the server has delivered at least one result; the grid's first
        # card is a render away, not a network wait
        self.result_images.first.wait_for(state="visible", timeout=10000)
        return job

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
        # no play icon in time is the answer False. play_result then clicks
        # the result itself, and its wait for the player raises
        except PlaywrightError:
            return False

    @staticmethod
    def _appears_hidden(locator, timeout: int = 5000) -> bool:
        """True when the element hides within timeout, False otherwise."""
        try:
            locator.wait_for(state="hidden", timeout=timeout)
            return True
        # still visible in time is the answer False. The filter methods use
        # it as a settle after a pick, and the next filter click raises on a
        # list left open
        except PlaywrightError:
            return False
