"""Global Search zone and line drawing tests.

Covers Zone and Line category searches where the user draws a polygon
or line on a canvas before executing the search.

Migrated from Selenium:
- test_zone_global_search (line 2676)
- test_line_global_search (line 2849)
"""
import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.search_page import SearchPage

# The shared tenant renames cameras, so the name lives in config. The
# drawing searches take their own camera when the box names one: india's
# test camera is offline and its search never completes (register row 76).
CAMERA_NAME = config.get("search_camera_name") or config.get("test_camera_name")
# The india backend scans a 30-day window at about 1% a minute and hands
# events over as it reaches them: measured 09/16/2026 on Thermal-14 at
# rest, the first Zone result landed at 114 s and the first Line result at
# 130 s, against 14 s to 100% on US. The old 120 s budget cut india off a
# few seconds before its first result.
SEARCH_BUDGET_MS = 240000



class TestSearchDrawing:
    """Tests for zone and line drawing on the Global Search page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.search = SearchPage(self.page)

    # --- Zone Search (from test_zone_global_search) ---

    @pytest.mark.ui
    @pytest.mark.search
    def test_zone_search_draw_zone(self):
        """A zone can be drawn on a camera's search canvas.

        Steps:
        1. On Search, pick the Zone category and open the zone drawing for the configured camera.
           Expected: The drawing canvas shows with a width and a height above zero.
        2. Draw a rectangle on the canvas.
           Expected: The Done button becomes enabled.
        3. Click Done.
           Expected: The zone is accepted.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category_by_index(3)
        self.search.open_zone_drawing(CAMERA_NAME)

        expect(self.search.canvas).to_be_visible(timeout=30000)
        box = self.search.canvas.bounding_box()
        assert box is not None, "the drawing canvas has no bounding box"
        assert box["width"] > 0, f"the drawing canvas has no width: {box}"
        assert box["height"] > 0, f"the drawing canvas has no height: {box}"
        self.search.draw_zone()
        expect(self.search.done_button).to_be_enabled(timeout=10000)
        self.search.click_done()

    @pytest.mark.ui
    @pytest.mark.search
    def test_zone_search_returns_results(self):
        """Verify Zone search returns results after drawing and searching.

        Full flow: draw zone on canvas, select duration, execute search,
        and validate results are loaded.

        Steps:
        1. Open Search, choose the Zone category, open the drawing view for the configured camera, draw a zone and click Done.
           Expected: The zone is accepted and the search filters are shown again.
        2. Pick a duration and click Search.
           Expected: At least one Zone result appears in the result grid.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category_by_index(3)
        self.search.open_zone_drawing(CAMERA_NAME)
        self.search.draw_zone()
        self.search.click_done()

        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=SEARCH_BUDGET_MS)

        count = self.search.get_result_count()
        assert count > 0, "Expected at least one Zone search result"

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.flaky(reruns=1)
    @pytest.mark.livestream
    def test_zone_search_play_result(self):
        """Verify a Zone search result plays to its end.

        Steps:
        1. On Search, pick the Zone category, open the zone drawing for the configured camera, draw a zone and click Done.
           Expected: The zone is accepted.
        2. Pick a duration and search.
           Expected: Results are listed.
        3. Play the first result.
           Expected: The clip plays and the Replay icon shows when it ends.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category_by_index(3)
        self.search.open_zone_drawing(CAMERA_NAME)
        self.search.draw_zone()
        self.search.click_done()

        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=SEARCH_BUDGET_MS)

        self.search.play_result(0, timeout=60000)

        assert self.search.is_replay_visible(timeout=120000) is True, (
            "Expected Replay icon after Zone clip finished playing"
        )

    # --- Line Search (from test_line_global_search) ---

    @pytest.mark.ui
    @pytest.mark.search
    def test_line_search_draw_line(self):
        """Verify a line can be drawn on the canvas.

        Opens the Line drawing canvas for a camera, draws a line,
        and clicks Done.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category_by_index(4)
        self.search.open_line_drawing(CAMERA_NAME)

        expect(self.search.canvas).to_be_visible(timeout=30000)
        box = self.search.canvas.bounding_box()
        assert box is not None, "the drawing canvas has no bounding box"
        assert box["width"] > 0, f"the drawing canvas has no width: {box}"
        assert box["height"] > 0, f"the drawing canvas has no height: {box}"
        self.search.draw_line()
        expect(self.search.done_button).to_be_enabled(timeout=10000)
        self.search.click_done()

    @pytest.mark.ui
    @pytest.mark.search
    def test_line_search_returns_results(self):
        """Verify Line search returns results after drawing and searching.

        Steps:
        1. Open Search, choose the Line category, open the drawing view for the configured camera, draw a line and click Done.
           Expected: The line is accepted and the search filters are shown again.
        2. Pick a duration and click Search.
           Expected: At least one Line result appears in the result grid.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category_by_index(4)
        self.search.open_line_drawing(CAMERA_NAME)
        self.search.draw_line()
        self.search.click_done()

        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=SEARCH_BUDGET_MS)

        count = self.search.get_result_count()
        assert count > 0, "Expected at least one Line search result"

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.flaky(reruns=1)
    @pytest.mark.livestream
    def test_line_search_play_result(self):
        """A Line search result plays to its end.

        Steps:
        1. On Search, pick the Line category, open the line drawing for the configured camera, draw a line and click Done.
           Expected: The line is accepted.
        2. Pick a duration and search.
           Expected: Results are listed.
        3. Play the first result.
           Expected: The clip plays and the Replay icon shows when it ends.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category_by_index(4)
        self.search.open_line_drawing(CAMERA_NAME)
        self.search.draw_line()
        self.search.click_done()

        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=SEARCH_BUDGET_MS)

        self.search.play_result(0, timeout=60000)

        assert self.search.is_replay_visible(timeout=120000) is True, (
            "Expected Replay icon after Line clip finished playing"
        )
