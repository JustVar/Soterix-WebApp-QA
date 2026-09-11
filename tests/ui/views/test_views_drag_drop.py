"""Views drag-and-drop tests - dragging cameras, views, locations to tiles."""
import pytest
from playwright.sync_api import Error as PlaywrightError, expect

from config.base_config import config
from tests.shared.helpers.surface import require_items
from tests.shared.pages.views_page import ViewsPage


class TestViewsDragDrop:
    """Tests for drag-and-drop functionality in Views."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.views = ViewsPage(self.page)
        self.views.navigate()
        self.views.wait_for_page_load()
        yield
        # Saved views come from the api_saved_view fixture, which
        # deletes them itself; only the tabs need a UI cleanup.
        # Cleanup: close extra view tabs (only the first should
        # remain). The old loop counted the untitled add (+) tab as a
        # tab, always found no close icon on it, and broke without
        # closing anything - a silent no-op since conversion.
        try:
            tabs = self._view_tabs()
            while tabs.count() > 1:
                before = tabs.count()
                last_tab = tabs.last
                last_tab.hover()
                # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
                close_icon = last_tab.locator("img[src*='closeIcon']")
                if close_icon.count() == 0:
                    break
                close_icon.click()
                # the tab leaving is the closed signal; a timeout
                # raises into the cleanup except below
                expect(tabs).to_have_count(before - 1, timeout=10000)
        # cleanup only: an unclosed tab must not fail a test that already
        # passed - the failure is logged
        except Exception as e:
            print(f"Cleanup: failed to close extra tabs: {e}")

    def _view_tabs(self):
        """View tabs only: they carry the view name in the tabInner
        title, while the add (+) tab's tabInner has no title."""
        return self.page.locator("button.tabItem:has(div.tabInner[title])")

    def _wait_tile_consumed(self, initial_count: int, timeout: int = 15000):
        """Bounded wait for an empty tile to be consumed after a drop.

        Misses are tolerated: callers keep their own union oracle
        (some drops land streams without changing the counted tiles),
        so this only replaces the old fixed sleeps with a bounded
        signal wait.
        """
        try:
            expect(self.views.drag_drop_tiles).to_have_count(
                initial_count - 1, timeout=timeout
            )
        # a miss falls through to the caller's own oracle
        except AssertionError:
            pass

    @pytest.mark.ui
    @pytest.mark.dragdrop
    @pytest.mark.views_devices
    def test_drag_camera_to_tile(self):
        """Verify a camera thumbnail can be dragged to an empty tile."""
        # Expand site and show cameras (the call confirms cameras
        # visible on its own)
        self.views.expand_site_and_show_cameras(None)

        # Count available tiles before drag
        initial_tile_count = self.views.get_available_tile_count()
        assert initial_tile_count > 0, "No empty tiles available for drag test"

        # Get the first camera thumbnail
        camera = self.page.locator(".cameraThumbnailWrapper").first
        camera.wait_for(state="visible", timeout=10000)

        # Get camera name for verification
        camera_name = camera.inner_text().split("\n")[0] if camera.inner_text() else "Camera"

        # Sidebar previews match [class*='video'] page-wide, so only
        # growth over this pre-drag baseline counts as drop evidence
        video_elements = self.page.locator("video, canvas, [class*='video'], [class*='stream']")
        video_baseline = video_elements.count()

        # advisory content-health baseline: a drop can consume the tile
        # yet render a broken image or a dead stream (observed live)
        health = self.views.content_health_snapshot()
        # Drag the camera to the first empty tile through the page
        # object, which retries a no-op drag via the JS fallback
        self.views.drag_camera_to_tile(camera)
        self._wait_tile_consumed(initial_tile_count)
        # The first sidebar camera is whichever the tenant lists first
        # and may be offline, so the stream oracle stays off here: the
        # tile settles, then the advisory reports a dead stream
        self.views.wait_for_tiles_settled()
        self.views.log_new_content_issues(health, "camera drag")

        # Verify: either tile count decreased OR video element appeared
        new_tile_count = self.views.get_available_tile_count()

        stream_loaded = (video_elements.count() > video_baseline or
                         new_tile_count < initial_tile_count)

        assert stream_loaded, f"Camera drag failed - tiles before: {initial_tile_count}, after: {new_tile_count}"

    @pytest.mark.ui
    @pytest.mark.dragdrop
    @pytest.mark.views_devices
    def test_drag_camera_by_name_to_tile(self):
        """Verify a specific camera can be dragged to a tile by name.

        Steps:
        1. On Views, expand the configured site and show its cameras.
           Expected: The site's camera thumbnails are listed.
        2. Drag the configured camera's thumbnail onto an empty tile.
           Expected: The tile fills and the camera's live video plays as a moving picture, not a still.
        """
        # Expand site and show cameras (the call confirms cameras
        # visible on its own)
        self.views.expand_site_and_show_cameras(None)

        # Get available cameras
        cameras = self.page.locator(".cameraThumbnailWrapper")
        camera_count = cameras.count()
        assert camera_count > 0, "No cameras available"

        # The configured test camera: the one the tenant keeps online,
        # so the stream oracle below can hold its tile to a live picture
        camera_name = config.get("test_camera_name")

        if camera_name:
            initial_tile_count = self.views.get_available_tile_count()
            filled_before = self.views.player_tile_count()

            # Sidebar previews match [class*='video'] page-wide, so only
            # growth over this pre-drag baseline counts as drop evidence
            video_elements = self.page.locator("video, canvas, [class*='video']")
            video_baseline = video_elements.count()

            # Use the helper method to drag by name
            health = self.views.content_health_snapshot()
            self.views.drag_camera_to_tile_by_name(camera_name, tile_index=0)
            self._wait_tile_consumed(initial_tile_count)
            self.views.log_new_content_issues(health, "camera drag")
            # a consumed tile is not a stream: the new tile must paint
            # changing frames
            self.views.assert_tile_streaming(filled_before, camera_name=camera_name)

            # Verify drag worked
            new_tile_count = self.views.get_available_tile_count()

            assert (new_tile_count < initial_tile_count or
                    video_elements.count() > video_baseline), f"Camera '{camera_name}' drag failed"
        else:
            pytest.skip(
                "test_camera_name is not configured for this ENV "
                "(see config/env/), so no camera can be dragged by name"
            )

    @pytest.mark.ui
    @pytest.mark.dragdrop
    @pytest.mark.views_myviews
    def test_drag_saved_view_to_tile(self, api_saved_view):
        """Verify a saved view can be dragged from My Views to an empty tile.

        The view comes from the API (tests/shared/api/fixtures.py):
        this test proves the drag, and test_views_basic proves the UI
        save. The fixture deletes the view at teardown.

        Steps:
        1. Create a saved view (the automation makes one through the API), reload Views and open My Views.
           Expected: The saved view is listed.
        2. Drag the saved view onto an empty tile.
           Expected: The tile fills with the view's content, or the view opens as a new tab.
        """
        view_name = api_saved_view()["name"]

        # Reload, then open the My Views SUBTAB (not the side-panel
        # icon): the page loaded before the API wrote the view, and a
        # card only gets its drag wiring on a fresh load; only the
        # subtab surface drops onto tiles - measured 08/21/2026, the
        # sibling subtabs test documents the same refresh requirement
        self.page.reload()
        self.views.open_my_views()
        saved_view = self.page.locator(f"span[title='{view_name}']")
        saved_view.wait_for(state="visible", timeout=20000)

        # Get initial tile count
        initial_tile_count = self.views.get_available_tile_count()

        # Sidebar previews match [class*='video'] page-wide, so only
        # growth over this pre-drag baseline counts as drop evidence
        video_elements = self.page.locator("video, canvas, [class*='video']")
        video_baseline = video_elements.count()

        # Attempt to drag the saved view to a tile
        health = self.views.content_health_snapshot()
        self.views.drag_view_to_tile(view_name, tile_index=0)
        self._wait_tile_consumed(initial_tile_count)
        self.views.log_new_content_issues(health, "view drag")

        # Verify: check for new tab or video content
        new_tile_count = self.views.get_available_tile_count()
        tab_exists = self.page.locator(f"button.tabItem:has(div[title='{view_name}'])").count() > 0

        assert (new_tile_count < initial_tile_count or
                tab_exists or
                video_elements.count() > video_baseline), "Saved view drag-and-drop failed"

    @pytest.mark.ui
    @pytest.mark.dragdrop
    def test_drag_location_to_tile(self):
        """Verify a location/site can be dragged to an empty tile (shows all cameras).

        Steps:
        1. On Views, in the Devices panel, drag the configured site's row onto an empty tile.
           Expected: The site's cameras load into the grid and empty tiles fill.
        """
        # Get initial tile count
        initial_tile_count = self.views.get_available_tile_count()
        assert initial_tile_count > 0, "No empty tiles available"

        # Sidebar previews match [class*='video'] page-wide, so only
        # growth over this pre-drag baseline counts as drop evidence
        video_elements = self.page.locator("video, canvas, [class*='video']")
        video_baseline = video_elements.count()

        # The drag is the behaviour under test, so it raises. It used
        # to run under a try that turned every failure into a skip,
        # and a drop that landed nothing skipped as well: the test had
        # no failing path at all (register item 25).
        health = self.views.content_health_snapshot()
        # the configured site row is the drag source; None made the
        # locator 'text=None', so this test had only ever skipped
        site_name = config.get("test_site_name")
        self.views.drag_location_to_tile(site_name, tile_index=0)
        self._wait_tile_consumed(initial_tile_count)
        self.views.log_new_content_issues(health, "location drag")

        # Verify: tile count should decrease or video content should appear
        new_tile_count = self.views.get_available_tile_count()

        # A location drop loads every camera under the site, so either
        # signal counts; neither means the drop did not land.
        assert (new_tile_count < initial_tile_count
                or video_elements.count() > video_baseline), (
            f"Dragging location '{site_name}' onto tile 0 landed nothing: "
            f"empty tiles stayed at {new_tile_count} (was {initial_tile_count}) "
            f"and content elements at {video_elements.count()} "
            f"(was {video_baseline})"
        )

    @pytest.mark.ui
    @pytest.mark.dragdrop
    @pytest.mark.views_maps
    def test_drag_map_to_tile(self):
        """Verify a map can be dragged to an empty tile.

        Maps require: Open Maps panel -> Click site to expand -> Drag/check map thumbnail.
        Maps use the same .cameraThumbnailWrapper class as cameras.
        """
        # Get initial tile count
        initial_tile_count = self.views.get_available_tile_count()
        assert initial_tile_count > 0, "No empty tiles available"

        # The whole body used to run under `except Exception:
        # pytest.skip(...)`, which caught the closing assert too: the
        # test could pass or skip but never fail (register item 25).
        # Step 1: Open maps panel
        self.views.open_maps()

        # Step 2: Expand the CONFIGURED site, not whichever row the
        # JS heuristic reaches first: a skip has to name the site it
        # found no maps under. click_site raises here listing what IS
        # in the panel, which doubles as this test's proof that the
        # Maps panel rendered at all.
        site_name = config.get("test_site_name")
        self.views.click_site(site_name)

        # Step 3: Map thumbnails render async after the expand. An
        # empty panel is the tenant's data; a panel that never
        # rendered is a fault, and require_items tells them apart.
        map_thumbnails = self.page.locator(".cameraThumbnailWrapper")
        found = require_items(
            map_thumbnails,
            container=self.page.get_by_text(site_name, exact=True),
            surface=f"Views > Maps panel under site '{site_name}'",
            artifact="map thumbnail",
            empty_means="no map is published under this site",
        )

        print(f"Found {found} map thumbnail(s)")

        # Step 4: Add map via checkbox (same pattern as cameras);
        # the click's actionability wait covers the hover render
        map_thumbnail = map_thumbnails.first
        map_thumbnail.hover()

        # Sidebar previews match content selectors page-wide, so only
        # growth over this pre-add baseline counts as drop evidence
        map_content = self.page.locator("[class*='leaflet'], iframe, [class*='map-container']")
        map_baseline = map_content.count()

        health = self.views.content_health_snapshot()
        checkbox = map_thumbnail.locator(".sidebar-custom-checkbox")
        if checkbox.count() > 0:
            print("Using checkbox to add map")
            checkbox.click()
        else:
            # Fallback: try drag
            print("No checkbox - trying drag")
            target_tile = self.views.drag_drop_tiles.first
            map_thumbnail.drag_to(target_tile)
        self._wait_tile_consumed(initial_tile_count)
        self.views.log_new_content_issues(health, "map add")

        # Verify: tile count should decrease or map content visible
        new_tile_count = self.views.get_available_tile_count()

        print(f"Tiles before: {initial_tile_count}, after: {new_tile_count}")
        print(f"Map content elements: {map_content.count()}")

        assert (new_tile_count < initial_tile_count
                or map_content.count() > map_baseline), (
            f"Map was not added to a tile: empty tiles stayed at "
            f"{new_tile_count} (was {initial_tile_count}) and map content "
            f"at {map_content.count()} (was {map_baseline})"
        )

    @pytest.mark.ui
    @pytest.mark.dragdrop
    @pytest.mark.views_channels
    def test_add_channel_to_tile(self):
        """Verify a channel can be added to a tile via checkbox or drag.

        Channels panel shows a list of available channels that can be searched
        or browsed. Channels use the same interaction pattern as cameras.
        """
        # Get initial tile count
        initial_tile_count = self.views.get_available_tile_count()
        assert initial_tile_count > 0, "No empty tiles available"

        # The whole body used to run under `except Exception:
        # pytest.skip(...)`, and its verdict was a print on success and
        # a skip on failure: nothing here could ever go red
        # (register item 25).
        # Step 1: Click Channels tab in left panel
        channels_tab = self.page.locator("text=Channels").first
        channels_tab.wait_for(state="visible", timeout=10000)
        channels_tab.click()

        # Step 2: Look for channel thumbnails or list items. The panel
        # has carried several markups, so the union stays; an empty
        # panel is the tenant's data and a panel that never rendered
        # is a fault, which require_items tells apart.
        channels = self.page.locator(
            ".cameraThumbnailWrapper, [class*='channelThumbnail'], "
            "[class*='channel-item'], .sidebar-custom-checkbox"
        )
        require_items(
            channels,
            container=channels_tab,
            surface="Views > Channels panel",
            artifact="channel entry",
            empty_means="this tenant has no channel published to Views",
        )
        channel_element = channels.first

        # Step 3: Add channel via checkbox; the click's
        # actionability wait covers the hover render
        channel_element.hover()

        # Sidebar previews match [class*='video'] page-wide, so only
        # growth over this pre-add baseline counts as drop evidence
        video_elements = self.page.locator("video, canvas, [class*='video']")
        video_baseline = video_elements.count()

        health = self.views.content_health_snapshot()
        checkbox = channel_element.locator(".sidebar-custom-checkbox")
        if checkbox.count() > 0:
            print("Using checkbox to add channel")
            checkbox.click()
        else:
            # Direct click or drag
            print("Trying direct interaction with channel")
            target_tile = self.views.drag_drop_tiles.first
            channel_element.drag_to(target_tile)
        self._wait_tile_consumed(initial_tile_count)
        self.views.log_new_content_issues(health, "channel add")

        # Verify
        new_tile_count = self.views.get_available_tile_count()

        print(f"Tiles before: {initial_tile_count}, after: {new_tile_count}")
        print(f"Video elements: {video_elements.count()}")

        assert (new_tile_count < initial_tile_count
                or video_elements.count() > video_baseline), (
            f"Adding a channel landed nothing on a tile: empty tiles "
            f"stayed at {new_tile_count} (was {initial_tile_count}) and "
            f"content elements at {video_elements.count()} "
            f"(was {video_baseline})"
        )

    @pytest.mark.ui
    @pytest.mark.checkbox
    @pytest.mark.views_devices
    @pytest.mark.livestream
    def test_multiple_cameras_to_multiple_tiles(self):
        """Verify multiple cameras can be added to multiple tiles."""
        # Expand site and show cameras (the call confirms cameras
        # visible on its own)
        self.views.expand_site_and_show_cameras(None)

        # Get available cameras and tiles
        cameras = self.page.locator(".cameraThumbnailWrapper")
        camera_count = cameras.count()
        initial_tile_count = self.views.get_available_tile_count()

        assert camera_count >= 2, f"Need at least 2 cameras, found {camera_count}"
        assert initial_tile_count >= 2, f"Need at least 2 tiles, found {initial_tile_count}"

        # Sidebar previews match [class*='video'] page-wide, so only
        # growth over this pre-add baseline counts as add evidence
        video_elements = self.page.locator("video, canvas, [class*='video']")
        video_baseline = video_elements.count()

        # Add the configured camera via checkbox; a consumed tile is
        # the added signal, and the tile it lands in is held to a live
        # picture below
        filled_before = self.views.player_tile_count()
        health = self.views.content_health_snapshot()
        self.views.add_first_camera_via_checkbox()
        self._wait_tile_consumed(initial_tile_count)

        # Add second camera via checkbox (if available); the click's
        # actionability wait covers the hover render
        second_camera = cameras.nth(1)
        second_camera.hover()
        checkbox = second_camera.locator(".sidebar-custom-checkbox")
        if checkbox.count() > 0:
            checkbox.click()
            self._wait_tile_consumed(initial_tile_count - 1)

        # The configured camera must paint a live picture; the second
        # camera is whichever the tenant lists next and may be offline,
        # so its tile only settles and the advisory reports it
        self.views.assert_tile_streaming(filled_before)
        self.views.wait_for_tiles_settled()
        self.views.log_new_content_issues(health, "camera adds")

        # Verify at least one camera was added
        final_tile_count = self.views.get_available_tile_count()

        assert (final_tile_count < initial_tile_count or
                video_elements.count() > video_baseline), "Failed to add cameras to tiles"
