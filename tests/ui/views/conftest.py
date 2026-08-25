"""Views test fixtures - shared setup for full screen and bookmark tests."""
import pytest
from tests.shared.pages.views_page import ViewsPage
from tests.shared.pages.fullscreen_page import FullScreenPage


@pytest.fixture
def views_page(authenticated_page):
    """Provide a ViewsPage navigated to the Views page."""
    page = authenticated_page
    views = ViewsPage(page)
    views.navigate()
    views.wait_for_page_load()
    return views


@pytest.fixture
def fullscreen_page(authenticated_page):
    """Provide a FullScreenPage after entering full screen on the first tile.

    1. Navigates to Views
    2. Ensures a camera is loaded in a tile
    3. Enters full screen on that tile
    4. Waits for the stream to load
    """
    page = authenticated_page
    views = ViewsPage(page)
    views.navigate()
    views.wait_for_page_load()

    # Check if a camera is already in a tile
    video_tiles = page.locator("[class*='video_container'][class*='new_video_player']")
    if video_tiles.count() == 0:
        views.expand_site_and_show_cameras(None)
        views.add_first_camera_via_checkbox()
        # the tile appearing is the added signal
        video_tiles.first.wait_for(state="visible", timeout=30000)

    # Enter full screen; the stream-loaded wait is the entered signal
    views.enter_fullscreen_on_tile(0)

    fs = FullScreenPage(page)
    fs.wait_for_stream_loaded(timeout=120000)
    # the loader clearing is not playing: a dead stream fails here,
    # named, instead of later at a click
    fs.assert_stream_playing()

    return fs
