"""In-Camera Search tests - forensic search within a specific camera's feed.

Migrated from legacy Selenium test_incamera_search (lines 1381-1476).
Tests the in-camera search overlay that opens from the video player controls,
allowing Person/Vehicle search with filters within a single camera's feed.
"""
import pytest
from tests.shared.pages.views_page import ViewsPage
from tests.shared.pages.fullscreen_page import FullScreenPage
from tests.shared.pages.incamera_search_page import InCameraSearchPage

SITE_NAME = "Driver Site"


class TestInCameraSearch:
    """Tests for in-camera forensic search."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.views = ViewsPage(self.page)
        self.views.navigate()
        self.views.wait_for_page_load()
        self._ensure_camera_streaming()
        yield

    def _ensure_camera_streaming(self):
        """Ensure a camera is streaming in a tile and enter fullscreen."""
        video_tiles = self.page.locator(
            "[class*='video_container'][class*='new_video_player']"
        )
        if video_tiles.count() == 0:
            self.views.expand_site_and_show_cameras(SITE_NAME)
            self.page.wait_for_timeout(500)
            self.views.add_first_camera_via_checkbox()
            self.page.wait_for_timeout(3000)
            video_tiles.first.wait_for(state="visible", timeout=30000)

        # Enter fullscreen to access player controls including search
        self.views.enter_fullscreen_on_tile(0)
        self.page.wait_for_timeout(2000)

        fs = FullScreenPage(self.page)
        fs.wait_for_stream_loaded(timeout=120000)

    @pytest.mark.ui
    @pytest.mark.incamera_search
    def test_incamera_search(self):
        """Verify in-camera search with Person/Male/Today filters returns results.

        Flow:
        1. Open in-camera search from video player controls
        2. Select Category = Person
        3. Select Description = Male
        4. Select Duration = Today
        5. Click Search
        6. Verify results appear
        """
        ics = InCameraSearchPage(self.page)

        # Open in-camera search
        if ics.search_icon.count() == 0:
            pytest.skip("In-camera search icon not available on this camera")

        ics.open_search()

        # Select filters: Person, Male, Today
        ics.select_category(index=0)  # Person
        ics.select_description_gender("Male")
        ics.select_duration(index=4)  # Today

        # Execute search
        ics.execute_search(timeout=60000)

        # Verify results
        assert ics.has_results(), "In-camera search returned no results"
        assert ics.get_result_count() > 0, "Expected at least one search result"

    @pytest.mark.ui
    @pytest.mark.incamera_search
    @pytest.mark.flaky(reruns=1)
    def test_incamera_search_play_result(self):
        """Verify playing an in-camera search result.

        Flow:
        1. Perform in-camera search (Person/Male/Today)
        2. Hover first result and click play
        3. Verify video plays (play button visible)
        """
        ics = InCameraSearchPage(self.page)

        if ics.search_icon.count() == 0:
            pytest.skip("In-camera search icon not available on this camera")

        ics.open_search()
        ics.select_category(index=0)
        ics.select_description_gender("Male")
        ics.select_duration(index=4)
        ics.execute_search(timeout=60000)

        if not ics.has_results():
            pytest.skip("No search results to play")

        ics.play_result(index=0, timeout=30000)
