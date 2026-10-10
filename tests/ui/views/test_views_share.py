"""Share Live View test - share a live camera stream via email and copy link."""
import re

import pytest

from tests.shared.pages.views_page import ViewsPage

SITE_NAME = None


SHARE_LINK_RE = re.compile(r"https?://[^/\s]+/\S+")


@pytest.mark.ui
@pytest.mark.livestream
def test_share_live_view(authenticated_page):
    """Verify sharing a live view via email and copying the share link.

    Flow:
    1. Navigate to Views, ensure a camera is streaming in a tile
    2. Hover tile -> three-dot menu -> timeline hover -> share icon
    3. Fill email, click Share
    4. Click Copy to copy the link (the clipboard then holds an http link)
    5. Close the share dialog
    """
    page = authenticated_page
    views = ViewsPage(page)
    views.navigate()
    views.wait_for_page_load()

    # Ensure a camera is loaded in a tile
    video_tiles = page.locator(
        "[class*='video_container'][class*='new_video_player']"
    )
    if video_tiles.count() == 0:
        views.expand_site_and_show_cameras(SITE_NAME)
        views.add_first_camera_via_checkbox()
        # the tile appearing is the added signal
        video_tiles.first.wait_for(state="visible", timeout=30000)

    # Share the live view
    copied = views.share_live_view_on_tile(
        email="share-recipient@example.com",
        tile_index=0,
    )
    # Copy puts the share link on the clipboard; the helper reads it back
    assert copied.startswith("http"), f"Copy put {copied!r} on the clipboard, not a share link"
    # a full link with a host and a path, and no spaces or line breaks around it
    assert SHARE_LINK_RE.fullmatch(copied) is not None, f"Copy put {copied!r} on the clipboard, not one clean link"

    # If we got here without an exception, the share flow completed.
    # The share dialog opened, email was filled, Share was clicked,
    # and Copy was attempted. The dialog should have closed or be closeable.
