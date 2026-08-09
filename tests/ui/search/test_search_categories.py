"""Global Search category-specific tests.

Covers Person, Vehicle, and Event category searches including
filter selection, search execution, result validation, and playback.

Migrated from Selenium:
- test_person_global_search (line 2290)
- test_vehicle_global_search (line 2420)
- test_global_event_search (line 2548)

Known limitations:
- Vehicle search: the test site had no vehicle detections when the
  skips were added (pre-rename tenant). Recheck against the current
  tenant - tracked in docs/TEST_REPAIRS.md section B.
- Play result: QA env video streams use MediaSource (duration=Infinity).
  Occasionally a clip stream fails to load (stays at readyState=0).
  Play tests use @flaky(reruns=1) to handle transient stream failures.
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.search_page import SearchPage





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
        """Verify Person search results contain valid images."""
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(None)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        first_result = self.search.result_images.first
        expect(first_result).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.flaky(reruns=1)
    def test_person_search_play_result(self):
        """Verify playing a Person search result clip works."""
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(None)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        self.search.play_result(0, timeout=60000)

        assert self.search.is_replay_visible(timeout=120000), (
            "Expected Replay icon after video clip finished playing"
        )

    # --- Vehicle Search (from test_vehicle_global_search) ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.skip(
        reason="Driver Site has no vehicle detections; needs different "
        "account/site with vehicle data"
    )
    def test_vehicle_search(self):
        """Verify Vehicle search returns results.

        Vehicle search skips Description (no gender filter).
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
    @pytest.mark.skip(
        reason="Driver Site has no vehicle detections; needs different "
        "account/site with vehicle data"
    )
    def test_vehicle_search_play_result(self):
        """Verify playing a Vehicle search result clip works."""
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category("Vehicle")
        self.search.select_locations_cameras(None)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        self.search.play_result(0, timeout=60000)

        assert self.search.is_replay_visible(timeout=120000), (
            "Expected Replay icon after Vehicle clip finished playing"
        )

    # --- Event Search (from test_global_event_search) ---

    @pytest.mark.ui
    @pytest.mark.search
    def test_event_search(self):
        """Verify Event category search returns results."""
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
    @pytest.mark.flaky(reruns=1)
    def test_event_search_play_result(self):
        """Verify playing an Event search result clip works."""
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category("Event")
        self.search.select_locations_cameras(None)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        self.search.play_result(0, timeout=60000)

        assert self.search.is_replay_visible(timeout=120000), (
            "Expected Replay icon after Event clip finished playing"
        )
