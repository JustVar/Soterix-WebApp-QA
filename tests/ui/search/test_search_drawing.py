"""Global Search zone and line drawing tests.

Covers Zone and Line category searches where the user draws a polygon
or line on a canvas before executing the search.

Migrated from Selenium:
- test_zone_global_search (line 2676)
- test_line_global_search (line 2849)
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.search_page import SearchPage


SITE_NAME = "Driver Site"
CAMERA_NAME = "Hanwha_6"


class TestSearchDrawing:
    """Tests for zone and line drawing on the Global Search page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.search = SearchPage(self.page)

    # --- Zone Search (from test_zone_global_search) ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.qatouch("LD3mGJ")
    def test_zone_search_draw_zone(self):
        """Verify a zone can be drawn on the canvas.

        Opens the Zone drawing canvas for a camera, draws a rectangular
        polygon, and clicks Done. The canvas and Done button should
        both be interactable.
        """
        self.search.navigate()
        self.search.wait_for_page_load()
        self.step_capture.mark(1, "Navigate to Global Search page")

        self.search.select_category_by_index(3)
        self.step_capture.mark(2, "Select Zone category from dropdown")

        self.search.open_zone_drawing(CAMERA_NAME)
        self.step_capture.mark(3, "Open zone drawing canvas for camera")

        expect(self.search.canvas).to_be_visible(timeout=30000)
        self.search.draw_zone()
        self.step_capture.mark(4, "Draw a rectangular zone on the canvas")

        expect(self.search.done_button).to_be_visible(timeout=10000)
        self.search.click_done()
        self.step_capture.mark(5, "Click Done to confirm zone drawing")

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.qatouch("J8d9R1")
    def test_zone_search_returns_results(self):
        """Verify Zone search returns results after drawing and searching.

        Full flow: draw zone on canvas, select duration, execute search,
        and validate results are loaded.
        """
        self.search.navigate()
        self.search.wait_for_page_load()
        self.step_capture.mark(1, "Navigate to Global Search page")

        self.search.select_category_by_index(3)
        self.step_capture.mark(2, "Select Zone category from dropdown")

        self.search.open_zone_drawing(CAMERA_NAME)
        self.search.draw_zone()
        self.search.click_done()
        self.step_capture.mark(3, "Draw zone on canvas and click Done")

        self.search.select_duration_by_index(5)
        self.step_capture.mark(4, "Select duration filter")

        self.search.execute_search(timeout=60000)
        self.step_capture.mark(5, "Click Search and wait for results")

        count = self.search.get_result_count()
        assert count > 0, "Expected at least one Zone search result"
        self.step_capture.mark(6, "Verify Zone search returns at least one result")

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.flaky(reruns=1)
    @pytest.mark.qatouch("dyp4pB")
    def test_zone_search_play_result(self):
        """Verify playing a Zone search result clip works."""
        self.search.navigate()
        self.search.wait_for_page_load()
        self.step_capture.mark(1, "Navigate to Global Search page")

        self.search.select_category_by_index(3)
        self.step_capture.mark(2, "Select Zone category from dropdown")

        self.search.open_zone_drawing(CAMERA_NAME)
        self.search.draw_zone()
        self.search.click_done()
        self.step_capture.mark(3, "Draw zone on canvas and click Done")

        self.search.select_duration_by_index(5)
        self.step_capture.mark(4, "Select duration filter")

        self.search.execute_search(timeout=60000)
        self.step_capture.mark(5, "Click Search and wait for results")

        self.search.play_result(0, timeout=60000)
        self.step_capture.mark(6, "Click play on the first search result")

        assert self.search.is_replay_visible(timeout=120000), (
            "Expected Replay icon after Zone clip finished playing"
        )
        self.step_capture.mark(7, "Verify Replay icon appears after clip finishes")

    # --- Line Search (from test_line_global_search) ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.qatouch("mBdpdb")
    def test_line_search_draw_line(self):
        """Verify a line can be drawn on the canvas.

        Opens the Line drawing canvas for a camera, draws a line,
        and clicks Done.
        """
        self.search.navigate()
        self.search.wait_for_page_load()
        self.step_capture.mark(1, "Navigate to Global Search page")

        self.search.select_category_by_index(4)
        self.step_capture.mark(2, "Select Line category from dropdown")

        self.search.open_line_drawing(CAMERA_NAME)
        self.step_capture.mark(3, "Open line drawing canvas for camera")

        expect(self.search.canvas).to_be_visible(timeout=30000)
        self.search.draw_line()
        self.step_capture.mark(4, "Draw a line on the canvas")

        expect(self.search.done_button).to_be_visible(timeout=10000)
        self.search.click_done()
        self.step_capture.mark(5, "Click Done to confirm line drawing")

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.qatouch("J8d9R1")
    def test_line_search_returns_results(self):
        """Verify Line search returns results after drawing and searching."""
        self.search.navigate()
        self.search.wait_for_page_load()
        self.step_capture.mark(1, "Navigate to Global Search page")

        self.search.select_category_by_index(4)
        self.step_capture.mark(2, "Select Line category from dropdown")

        self.search.open_line_drawing(CAMERA_NAME)
        self.search.draw_line()
        self.search.click_done()
        self.step_capture.mark(3, "Draw line on canvas and click Done")

        self.search.select_duration_by_index(5)
        self.step_capture.mark(4, "Select duration filter")

        self.search.execute_search(timeout=60000)
        self.step_capture.mark(5, "Click Search and wait for results")

        count = self.search.get_result_count()
        assert count > 0, "Expected at least one Line search result"
        self.step_capture.mark(6, "Verify Line search returns at least one result")

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.flaky(reruns=1)
    @pytest.mark.qatouch("wmjKjZ")
    def test_line_search_play_result(self):
        """Verify playing a Line search result clip works."""
        self.search.navigate()
        self.search.wait_for_page_load()
        self.step_capture.mark(1, "Navigate to Global Search page")

        self.search.select_category_by_index(4)
        self.step_capture.mark(2, "Select Line category from dropdown")

        self.search.open_line_drawing(CAMERA_NAME)
        self.search.draw_line()
        self.search.click_done()
        self.step_capture.mark(3, "Draw line on canvas and click Done")

        self.search.select_duration_by_index(5)
        self.step_capture.mark(4, "Select duration filter")

        self.search.execute_search(timeout=60000)
        self.step_capture.mark(5, "Click Search and wait for results")

        self.search.play_result(0, timeout=60000)
        self.step_capture.mark(6, "Click play on the first search result")

        assert self.search.is_replay_visible(timeout=120000), (
            "Expected Replay icon after Line clip finished playing"
        )
        self.step_capture.mark(7, "Verify Replay icon appears after clip finishes")
