"""In-Camera Search tests - forensic search within a specific camera's feed.

Migrated from legacy Selenium test_incamera_search (lines 1381-1476).
Tests the in-camera search overlay that opens from the video player controls,
allowing Person/Vehicle search with filters within a single camera's feed.
"""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.fullscreen_page import FullScreenPage
from tests.shared.pages.incamera_search_page import InCameraSearchPage
from tests.shared.pages.views_page import ViewsPage


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
            # Use first available site instead of hardcoded name (the
            # expand call confirms cameras visible on its own)
            self.views.expand_site_and_show_cameras(None)

            thumb_count = self.views.camera_thumbnails.count()
            print(f"\nDEBUG: camera_thumbnails count = {thumb_count}")
            print(f"DEBUG: page URL = {self.page.url}")

            # expand_site_and_show_cameras only returns once cameras
            # are visible, so an empty count here contradicts it: the
            # panel is broken, not empty (register item 25).
            assert thumb_count > 0, (
                "The camera panel reports cameras visible but no "
                ".cameraThumbnailWrapper is on screen, so no camera can be "
                "added to set up the stream"
            )

            # the tile appearing is the added signal
            self.views.add_first_camera_via_checkbox()
            # A tile that never appears is the tenant's stream failure,
            # and it goes red so it gets counted - run.py
            # --retry-streams reruns exactly that class. The old
            # handler reported it as Blocked (register item 25).
            video_tiles.first.wait_for(state="visible", timeout=30000)

        # Enter fullscreen; the stream-loaded wait is the entered signal
        self.views.enter_fullscreen_on_tile(0)
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

        # The setup put the camera in fullscreen and waited for its
        # stream, so the player chrome is up: a missing search icon is
        # a regression, not an absent artifact (register item 25).
        expect(ics.search_icon.first).to_be_visible(timeout=10000)

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

        # Same as above: the player chrome is proved up by the setup.
        expect(ics.search_icon.first).to_be_visible(timeout=10000)

        ics.open_search()
        ics.select_category(index=0)
        ics.select_description_gender("Male")
        ics.select_duration(index=4)
        ics.execute_search(timeout=60000)

        if not ics.has_results():
            # The search ran to completion above, so this is the
            # tenant's data: no Person/Male detection on this camera
            # today. test_incamera_search asserts the same search DOES
            # return results, so a standing skip here means that test
            # is red too.
            pytest.skip(
                "The Person/Male/Today in-camera search returned no result "
                "to play on this camera"
            )

        # oracle: play_result raises unless the player's play button
        # appears after the result click
        ics.play_result(index=0, timeout=30000)
