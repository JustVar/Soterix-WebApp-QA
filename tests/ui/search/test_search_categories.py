"""Global Search category-specific tests.

Covers Person, Vehicle, and Event category searches including
filter selection, search execution, result validation, and playback.

Migrated from Selenium:
- test_person_global_search (line 2290)
- test_vehicle_global_search (line 2420)
- test_global_event_search (line 2548)

Known limitations:
- Play result: QA env video streams use MediaSource (duration=Infinity).
  Occasionally a clip stream fails to load (stays at readyState=0).
  Play tests carry the `intermittent` marker as a label of that; nothing reruns
  them by itself (run.py --retry-streams is the one opt-in).
"""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.search_page import SearchPage

# One search job per account and no cancel (register row 100): every
# searching module shares this xdist group so --dist loadgroup runs them
# on one worker, and tests/shared/helpers/search_gap.py spaces the searches.
pytestmark = pytest.mark.xdist_group("account_search")


class TestSearchCategories:
    """Tests for category-specific Global Search flows."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.search = SearchPage(self.page)

    # --- Person Search (from test_person_global_search) ---

    @pytest.mark.ui
    @pytest.mark.search
    def test_person_search(self):
        """Verify Person search with Male description returns results.

        Selects Category=Person, Description=Male, site, duration,
        then executes search and validates results are loaded.

        Steps:
        1. Open Search, choose Category Person and Description Male, pick the configured site and cameras, and pick a duration.
           Expected: The Search button becomes enabled.
        2. Click Search.
           Expected: At least one Person result appears in the result grid.
        """
        self.search.navigate()
        self.search.wait_for_page_load()
        self.step_capture.mark(1, "Navigate to Global Search page")

        self.search.select_category("Person")
        self.step_capture.mark(2, "Select Category = 'Person' from the category dropdown")
        self.search.select_description_gender("Male")
        self.step_capture.mark(3, "Select Description = 'Male' from the gender dropdown")
        self.search.select_locations_cameras(None)
        self.step_capture.mark(4, "Select the test site location and cameras")
        self.search.select_duration_by_index(5)
        self.step_capture.mark(5, "Select duration filter (index 5)")
        self.search.execute_search(timeout=60000)

        count = self.search.get_result_count()
        assert count > 0, "Expected at least one Person search result"
        self.step_capture.mark(6, "Click Search button and wait for results")

    @pytest.mark.ui
    @pytest.mark.search
    def test_person_search_results_valid(self):
        """Verify Person search results contain valid images.

        Steps:
        1. Open Search and run a Person/Male search for the configured site over a duration.
           Expected: Person results appear in the result grid.
        2. Look at the first result's image.
           Expected: Its picture is a decoded blob, data or http image with a width above zero.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(None)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        # a result card is a div holding the picture as an <img> with a
        # blob source and a decoded width (measured 09/12/2026)
        # a result card is a div holding the picture as an <img> with a
        # blob source and a decoded width (measured 09/12/2026)
        # a result card is a div holding the picture as an <img> with a
        # blob source and a decoded width (measured 09/12/2026)
        first_result = self.search.result_images.first
        expect(first_result).to_be_visible(timeout=5000)
        picture = first_result.locator("img").first
        src = picture.get_attribute("src") or ""
        assert src.startswith(("blob:", "data:image", "http")), f"the first result's picture source is {src[:40]!r}"
        assert picture.evaluate("e => e.naturalWidth") > 0, "the first result's picture never decoded"
        picture = first_result.locator("img").first
        src = picture.get_attribute("src") or ""
        assert src.startswith(("blob:", "data:image", "http")), f"the first result's picture source is {src[:40]!r}"
        assert picture.evaluate("e => e.naturalWidth") > 0, "the first result's picture never decoded"
        picture = first_result.locator("img").first
        src = picture.get_attribute("src") or ""
        assert src.startswith(("blob:", "data:image", "http")), f"the first result's picture source is {src[:40]!r}"
        assert picture.evaluate("e => e.naturalWidth") > 0, "the first result's picture never decoded"

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.intermittent
    @pytest.mark.livestream
    def test_person_search_play_result(self):
        """Verify a Person search result plays to its end.

        Steps:
        1. On Search, pick the Person category, the Male description, the site's cameras and a duration, then search.
           Expected: Results are listed.
        2. Play the first result.
           Expected: The clip plays and the Replay icon shows when it ends.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(None)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        self.search.play_result(0, timeout=60000)

        assert self.search.is_replay_visible(timeout=120000) is True, (
            "Expected Replay icon after video clip finished playing"
        )

    # --- Vehicle Search (from test_vehicle_global_search) ---

    @pytest.mark.ui
    @pytest.mark.search
    def test_vehicle_search(self):
        """Verify Vehicle search returns results.

        Vehicle search skips Description (no gender filter).

        Steps:
        1. Open Search, choose Category Vehicle (it has no description filter), pick the configured site and cameras, and pick a duration.
           Expected: The Search button becomes enabled.
        2. Click Search.
           Expected: At least one Vehicle result appears in the result grid.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category("Vehicle")
        self.search.select_locations_cameras(None)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        count = self.search.get_result_count()
        assert count > 0, "Expected at least one Vehicle search result"

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.livestream
    def test_vehicle_search_play_result(self):
        """Verify a Vehicle search result plays to its end.

        Steps:
        1. On Search, pick the Vehicle category, the site's cameras and a duration, then search.
           Expected: Results are listed.
        2. Play the first result.
           Expected: The clip plays and the Replay icon shows when it ends.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category("Vehicle")
        self.search.select_locations_cameras(None)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        self.search.play_result(0, timeout=60000)

        assert self.search.is_replay_visible(timeout=120000) is True, (
            "Expected Replay icon after Vehicle clip finished playing"
        )

    # --- Event Search (from test_global_event_search) ---

    @pytest.mark.ui
    @pytest.mark.search
    def test_event_search(self):
        """Verify Event category search returns results.

        Steps:
        1. Open Search, choose Category Event, pick the configured site and cameras, and pick a duration.
           Expected: The Search button becomes enabled.
        2. Click Search.
           Expected: At least one Event result appears in the result grid.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category("Event")
        self.search.select_locations_cameras(None)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        count = self.search.get_result_count()
        assert count > 0, "Expected at least one Event search result"

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.intermittent
    @pytest.mark.livestream
    def test_event_search_play_result(self):
        """Verify playing an Event search result clip works.

        Steps:
        1. Open Search, run an Event search for the configured site over a duration.
           Expected: Event results appear in the result grid.
        2. Play the first result.
           Expected: The clip plays, and a Replay control appears when it ends.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category("Event")
        self.search.select_locations_cameras(None)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        self.search.play_result(0, timeout=60000)

        assert self.search.is_replay_visible(timeout=120000) is True, (
            "Expected Replay icon after Event clip finished playing"
        )
