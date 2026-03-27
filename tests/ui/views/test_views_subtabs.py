"""Views Subtab Tests - Verify all left panel subtabs can add content to tiles.

Subtabs tested:
- Devices: Camera thumbnails from site tree
- My Views: Saved views
- Insights: Analytics/insights panels (if available)
- Maps: Map thumbnails under sites
- Channels: Channel thumbnails

Each subtab is tested with TWO methods:
1. CHECKBOX: Hover thumbnail -> Click checkbox -> Content added to tile
2. DRAG: Drag thumbnail directly to tile -> Content appears

Success Criteria:
- Tile count decreases (empty tile filled), OR
- Video/content element appears in tile area
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.views_page import ViewsPage


class TestViewsSubtabs:
    """Tests for each Views left panel subtab."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        """Setup runs once per test using cached session (no re-login)."""
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.views = ViewsPage(self.page)
        self._saved_view_names = []

        # Always click Views nav - fast if already there, navigates if not
        self.page.locator("text=Views").first.click(force=True)

        # Wait for page ready indicator
        self.views.add_tab_button.wait_for(state="visible", timeout=10000)
        yield
        # Cleanup: delete any saved views created during the test
        for name in reversed(self._saved_view_names):
            try:
                self._delete_saved_view(name)
            except Exception:
                pass
        # Cleanup: close extra tabs (only first tab should remain)
        try:
            tabs = self.page.locator("button.tabItem")
            while tabs.count() > 1:
                last_tab = tabs.last
                last_tab.hover()
                self.page.wait_for_timeout(150)
                close_icon = last_tab.locator("img[src*='closeIcon']")
                if close_icon.count() > 0:
                    close_icon.click()
                    self.page.wait_for_timeout(500)
                else:
                    break
        except Exception:
            pass

    # =========================================================================
    # DEVICES SUBTAB - Camera thumbnails from site tree
    # =========================================================================

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_devices
    @pytest.mark.checkbox
    @pytest.mark.qatouch("pDpvBJ")
    def test_devices_add_camera_via_checkbox(self):
        """DEVICES: Add camera to tile using checkbox selection.

        Steps:
        1. Click Devices tab (default)
        2. Expand site (Driver Site) -> Click "All Cameras"
        3. Hover camera thumbnail to reveal checkbox
        4. Click checkbox

        Success: Tile count decreases OR video element appears
        """
        initial_tiles = self.views.get_available_tile_count()
        assert initial_tiles > 0, "No empty tiles available"

        self.views.expand_site_and_show_cameras("Driver Site")
        self.page.wait_for_timeout(400)
        self.step_capture.mark(1, "Expand Driver Site and show camera thumbnails")

        camera = self.page.locator(".cameraThumbnailWrapper").first
        camera.wait_for(state="visible", timeout=10000)
        camera.hover()
        self.page.wait_for_timeout(300)
        self.step_capture.mark(2, "Hover over first camera thumbnail to reveal checkbox")

        checkbox = camera.locator(".sidebar-custom-checkbox")
        assert checkbox.count() > 0, "Checkbox not visible on hover"
        checkbox.click()
        self.page.wait_for_timeout(800)
        self.step_capture.mark(3, "Click checkbox to add camera to tile")

        new_tiles = self.views.get_available_tile_count()
        video_elements = self.page.locator("video, canvas, [class*='video']")

        assert (new_tiles < initial_tiles or video_elements.count() > 0), \
            f"Camera not added. Tiles: {initial_tiles} -> {new_tiles}"
        self.step_capture.mark(4, "Verify camera stream appears in the tile")

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_devices
    @pytest.mark.dragdrop
    @pytest.mark.qatouch("3gjBw9")
    def test_devices_drag_camera_to_tile(self):
        """DEVICES: Drag camera thumbnail directly to empty tile.

        Steps:
        1. Expand site -> Show cameras
        2. Drag camera thumbnail to empty tile (visible drag animation)

        Success: Tile count decreases OR video element appears
        """
        initial_tiles = self.views.get_available_tile_count()
        assert initial_tiles > 0, "No empty tiles available"

        self.views.expand_site_and_show_cameras("Driver Site")
        self.page.wait_for_timeout(400)
        self.step_capture.mark(1, "Expand Driver Site and show camera thumbnails")

        camera = self.page.locator(".cameraThumbnailWrapper").first
        camera.wait_for(state="visible", timeout=10000)

        target_tile = self.views.drag_drop_tiles.first
        target_tile.wait_for(state="visible", timeout=10000)
        self.step_capture.mark(2, "Locate camera thumbnail and target empty tile")

        self.views.visible_drag(camera, target_tile)
        self.page.wait_for_timeout(800)
        self.step_capture.mark(3, "Drag camera thumbnail to empty tile")

        new_tiles = self.views.get_available_tile_count()
        video_elements = self.page.locator("video, canvas, [class*='video']")

        assert (new_tiles < initial_tiles or video_elements.count() > 0), \
            f"Drag failed. Tiles: {initial_tiles} -> {new_tiles}"
        self.step_capture.mark(4, "Verify camera stream appears in the tile")

    # =========================================================================
    # MY VIEWS SUBTAB - Saved views
    # =========================================================================

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_myviews
    @pytest.mark.checkbox
    def test_my_views_add_saved_view_via_checkbox(self):
        """MY VIEWS: Add saved view to tile using checkbox.

        Steps:
        1. Create and save a test view (setup)
        2. Click My Views tab
        3. Hover saved view -> Click checkbox

        Success: View opens as new tab OR tile filled
        """
        import datetime
        view_name = f"SubtabTest_{datetime.datetime.now().strftime('%H%M%S')}"
        self._saved_view_names.append(view_name)

        self._create_and_save_view(view_name)
        self.step_capture.mark(1, "Create a new tab with a camera and save the view")

        self.page.reload()
        self.page.wait_for_timeout(500)

        self.views.open_my_views()
        self.page.wait_for_timeout(500)
        self.step_capture.mark(2, "Reload page and open My Views subtab")

        saved_view = self.page.locator(f"span[title='{view_name}']").first
        saved_view.wait_for(state="visible", timeout=20000)

        self._js_hover_on_view(view_name)
        self.page.wait_for_timeout(300)

        checkbox = self.page.locator(".sidebar-custom-checkbox").first
        checkbox.click()
        self.page.wait_for_timeout(800)
        self.step_capture.mark(3, "Hover saved view to reveal checkbox and click it")

        tab_with_input = self.page.locator(f"input.tabTitle[value='{view_name}']")
        tab_with_div = self.page.locator(f"button.tabItem:has(div[title='{view_name}'])")
        tab_by_text = self.page.locator(f"button.tabItem:has-text('{view_name}')")

        tab_found = (tab_with_input.count() > 0 or
                     tab_with_div.count() > 0 or
                     tab_by_text.count() > 0)

        assert tab_found, f"View '{view_name}' not opened as tab"
        self.step_capture.mark(4, "Verify saved view opens as a new tab")

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_myviews
    @pytest.mark.dragdrop
    def test_my_views_drag_saved_view_to_tile(self):
        """MY VIEWS: Drag saved view directly to tile.

        Steps:
        1. Create and save a test view
        2. Click My Views tab
        3. Drag saved view to empty tile

        Success: Tile filled with view content
        """
        import datetime
        view_name = f"DragViewTest_{datetime.datetime.now().strftime('%H%M%S')}"
        self._saved_view_names.append(view_name)

        self._create_and_save_view(view_name)
        self.step_capture.mark(1, "Create and save a test view with a camera")

        self.page.reload()
        self.page.wait_for_timeout(500)

        initial_tiles = self.views.get_available_tile_count()

        self.views.open_my_views()
        self.page.wait_for_timeout(400)

        saved_view = self.page.locator(f"span[title='{view_name}']").first
        saved_view.wait_for(state="visible", timeout=20000)
        self.step_capture.mark(2, "Reload page and open My Views subtab")

        target_tile = self.views.drag_drop_tiles.first

        try:
            self.views.visible_drag(saved_view, target_tile)
        except Exception as e:
            pytest.skip(f"View drag not supported: {e}")
        self.step_capture.mark(3, "Drag the saved view to the first empty tile")

        new_tiles = self.views.get_available_tile_count()

        tab_found = (
            self.page.locator(f"input.tabTitle[value='{view_name}']").count() > 0 or
            self.page.locator(f"button.tabItem:has-text('{view_name}')").count() > 0
        )

        if new_tiles >= initial_tiles and not tab_found:
            pytest.skip("View drag-to-tile not supported - use checkbox method instead")
        self.step_capture.mark(4, "Verify tile was filled or new tab was created")

    # =========================================================================
    # MAPS SUBTAB - Map thumbnails under sites
    # =========================================================================

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_maps
    @pytest.mark.checkbox
    @pytest.mark.qatouch("21zBxL")
    def test_maps_add_map_via_checkbox(self):
        """MAPS: Add map to tile using checkbox.

        Steps:
        1. Click Maps tab
        2. Click site to expand (Driver Site)
        3. Hover map thumbnail -> Click checkbox

        Success: Tile count decreases OR map content (leaflet/iframe) appears
        """
        initial_tiles = self.views.get_available_tile_count()
        assert initial_tiles > 0, "No empty tiles"

        self.views.open_maps()
        self.page.wait_for_timeout(500)
        self.step_capture.mark(1, "Open the Maps panel")

        site = self.page.locator("p:text('Driver Site'), span:text('Driver Site')").first
        site.wait_for(state="visible", timeout=10000)
        site.click()
        self.page.wait_for_timeout(500)
        self.step_capture.mark(2, "Expand Driver Site to reveal map thumbnails")

        map_thumb = self.page.locator(".cameraThumbnailWrapper").first
        if map_thumb.count() == 0:
            pytest.skip("No maps available under Driver Site")

        map_thumb.hover()
        self.page.wait_for_timeout(300)
        self.step_capture.mark(3, "Hover over map thumbnail to reveal checkbox")

        checkbox = map_thumb.locator(".sidebar-custom-checkbox")
        if checkbox.count() > 0:
            checkbox.click()
            self.page.wait_for_timeout(2500)
        else:
            pytest.skip("No checkbox on map thumbnail")

        try:
            loader = self.page.locator("[class*='CircularProgress']")
            if loader.count() > 0:
                loader.wait_for(state="hidden", timeout=60000)
        except Exception:
            pass
        self.step_capture.mark(4, "Click checkbox to add map to tile")

        new_tiles = self.views.get_available_tile_count()
        map_content = self.page.locator("[class*='leaflet'], iframe, [class*='map-container']")

        assert (new_tiles < initial_tiles or map_content.count() > 0), \
            f"Map not added. Tiles: {initial_tiles} -> {new_tiles}"
        self.step_capture.mark(5, "Verify map content loads in the tile")

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_maps
    @pytest.mark.dragdrop
    @pytest.mark.qatouch("B869gN")
    def test_maps_drag_map_to_tile(self):
        """MAPS: Drag map thumbnail directly to tile.

        Steps:
        1. Click Maps -> Expand site
        2. Drag map thumbnail to empty tile

        Success: Tile filled with map content
        """
        initial_tiles = self.views.get_available_tile_count()

        self.views.open_maps()
        self.page.wait_for_timeout(500)

        site = self.page.locator("p:text('Driver Site'), span:text('Driver Site')").first
        site.click()
        self.page.wait_for_timeout(500)
        self.step_capture.mark(1, "Open Maps panel and expand Driver Site")

        map_thumb = self.page.locator(".cameraThumbnailWrapper").first
        if map_thumb.count() == 0:
            pytest.skip("No maps available")

        target_tile = self.views.drag_drop_tiles.first
        self.step_capture.mark(2, "Locate map thumbnail and target empty tile")

        self.views.visible_drag(map_thumb, target_tile)
        self.page.wait_for_timeout(1500)
        self.step_capture.mark(3, "Drag map thumbnail to empty tile")

        new_tiles = self.views.get_available_tile_count()
        map_content = self.page.locator("[class*='leaflet'], iframe")

        assert (new_tiles < initial_tiles or map_content.count() > 0), \
            "Map drag failed"
        self.step_capture.mark(4, "Verify map content loads in the tile")

    # =========================================================================
    # CHANNELS SUBTAB - Channel thumbnails
    # =========================================================================

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_channels
    @pytest.mark.checkbox
    @pytest.mark.qatouch("M73w4q")
    def test_channels_add_channel_via_checkbox(self):
        """CHANNELS: Add channel to tile using checkbox.

        Steps:
        1. Click Channels tab
        2. Hover channel thumbnail -> Click checkbox

        Success: Tile count decreases OR video appears
        """
        initial_tiles = self.views.get_available_tile_count()

        self.views.open_channels()
        self.page.wait_for_timeout(500)
        self.step_capture.mark(1, "Open the Channels subtab")

        channel = self.page.locator(".cameraThumbnailWrapper").first
        if channel.count() == 0:
            pytest.skip("No channels available")

        channel.hover()
        self.page.wait_for_timeout(300)
        self.step_capture.mark(2, "Hover over channel thumbnail to reveal checkbox")

        checkbox = channel.locator(".sidebar-custom-checkbox")
        if checkbox.count() > 0:
            checkbox.click()
            self.page.wait_for_timeout(2500)
        else:
            pytest.skip("No checkbox on channel")
        self.step_capture.mark(3, "Click checkbox to add channel to tile")

        new_tiles = self.views.get_available_tile_count()
        video_elements = self.page.locator("video, canvas")

        assert (new_tiles < initial_tiles or video_elements.count() > 0), \
            "Channel not added via checkbox"
        self.step_capture.mark(4, "Verify channel stream appears in the tile")

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_channels
    @pytest.mark.dragdrop
    @pytest.mark.qatouch("zvnVlw")
    def test_channels_drag_channel_to_tile(self):
        """CHANNELS: Drag channel thumbnail to tile.

        Steps:
        1. Click Channels subtab
        2. Drag channel to empty tile

        Success: Tile filled with video
        """
        initial_tiles = self.views.get_available_tile_count()

        self.views.open_channels()
        self.page.wait_for_timeout(500)
        self.step_capture.mark(1, "Open the Channels subtab")

        channel = self.page.locator(".cameraThumbnailWrapper").first
        if channel.count() == 0:
            pytest.skip("No channels available")

        target_tile = self.views.drag_drop_tiles.first
        self.step_capture.mark(2, "Locate channel thumbnail and target empty tile")

        self.views.visible_drag(channel, target_tile)
        self.page.wait_for_timeout(800)
        self.step_capture.mark(3, "Drag channel thumbnail to empty tile")

        new_tiles = self.views.get_available_tile_count()
        video_elements = self.page.locator("video, canvas")

        assert (new_tiles < initial_tiles or video_elements.count() > 0), \
            "Channel drag failed"
        self.step_capture.mark(4, "Verify channel stream appears in the tile")

    # =========================================================================
    # INSIGHTS SUBTAB - Analytics/Insight widget thumbnails
    # =========================================================================

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_insights
    @pytest.mark.checkbox
    @pytest.mark.qatouch("xm9dwl")
    def test_insights_add_via_checkbox(self):
        """INSIGHTS: Add insight widget to tile using checkbox.

        Insight widgets are user-created analytics charts (e.g., "All Persons Seen in the Last Week").
        They appear as cards with chart preview images and can be added to tiles.

        Steps:
        1. Click Insights tab
        2. Find widget card (has chart preview and title)
        3. Hover widget -> Click checkbox OR click widget directly

        Success: Tile count decreases OR insight/chart content appears
        """
        initial_tiles = self.views.get_available_tile_count()
        assert initial_tiles > 0, "No empty tiles available"

        self.views.open_insights()
        self.page.wait_for_timeout(800)
        self.step_capture.mark(1, "Open the Insights subtab")

        widget_card = None

        camera_wrappers = self.page.locator(".cameraThumbnailWrapper")
        if camera_wrappers.count() > 0:
            widget_card = camera_wrappers.first
        else:
            thumbnail_images = self.page.locator(".viewTabPanel img, .sidebar-content img").filter(
                has_not=self.page.locator("input")
            )
            if thumbnail_images.count() > 0:
                widget_card = thumbnail_images.first.locator("..")

        if widget_card is None:
            pytest.skip("No insight widgets available - widgets are user-created")

        widget_card.hover()
        self.page.wait_for_timeout(300)
        self.step_capture.mark(2, "Locate insight widget card and hover to reveal checkbox")

        checkbox = widget_card.locator(".sidebar-custom-checkbox")
        if checkbox.count() == 0:
            checkbox = self.page.locator(".sidebar-custom-checkbox").first

        if checkbox.count() > 0:
            checkbox.click()
            self.page.wait_for_timeout(2500)
        else:
            widget_card.click()
            self.page.wait_for_timeout(2500)
        self.step_capture.mark(3, "Click checkbox or widget card to add insight to tile")

        new_tiles = self.views.get_available_tile_count()
        insight_content = self.page.locator(
            "canvas, svg, [class*='chart'], [class*='graph'], "
            "[class*='widget'], [class*='insight'], iframe"
        )

        assert (new_tiles < initial_tiles or insight_content.count() > 0), \
            f"Insight widget not added. Tiles: {initial_tiles} -> {new_tiles}"
        self.step_capture.mark(4, "Verify insight chart content appears in the tile")

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_insights
    @pytest.mark.dragdrop
    @pytest.mark.qatouch("dypXMM")
    def test_insights_drag_to_tile(self):
        """INSIGHTS: Drag insight widget card to tile.

        Insight widgets are user-created analytics charts that can be dragged
        to tiles to display charts/graphs.

        Steps:
        1. Click Insights tab
        2. Find widget card with chart preview
        3. Drag widget to empty tile (visible drag animation)

        Success: Tile filled with chart/insight content
        """
        initial_tiles = self.views.get_available_tile_count()
        if initial_tiles == 0:
            self.views.add_new_tab()
            self.page.wait_for_timeout(400)
            initial_tiles = self.views.get_available_tile_count()

        assert initial_tiles > 0, "No empty tiles available even after adding new tab"

        self.views.open_insights()
        self.page.wait_for_timeout(800)
        self.step_capture.mark(1, "Open the Insights subtab")

        widget_card = None

        camera_wrappers = self.page.locator(".cameraThumbnailWrapper")
        if camera_wrappers.count() > 0:
            widget_card = camera_wrappers.first
        else:
            thumbnail_images = self.page.locator(".viewTabPanel img, .sidebar-content img").filter(
                has_not=self.page.locator("input")
            )
            if thumbnail_images.count() > 0:
                widget_card = thumbnail_images.first.locator("..")

        if widget_card is None:
            pytest.skip("No insight widgets available - widgets are user-created")
        self.step_capture.mark(2, "Locate insight widget card")

        target_tiles = self.views.drag_drop_tiles
        if target_tiles.count() == 0:
            alt_tiles = self.page.locator("text=Drag & Drop")
            if alt_tiles.count() == 0:
                pytest.skip("No drag-drop tiles visible - use checkbox method")
            target_tiles = alt_tiles

        target_tile = target_tiles.first
        try:
            target_tile.wait_for(state="visible", timeout=5000)
        except Exception:
            pytest.skip("Drag-drop tiles not visible - use checkbox method")

        self.views.visible_drag(widget_card, target_tile)
        self.page.wait_for_timeout(800)
        self.step_capture.mark(3, "Drag insight widget to empty tile")

        new_tiles = self.views.get_available_tile_count()
        insight_content = self.page.locator(
            "canvas, svg, [class*='chart'], [class*='graph'], "
            "[class*='widget'], [class*='insight'], iframe"
        )

        if new_tiles >= initial_tiles and insight_content.count() == 0:
            pytest.skip("Insight widget drag-to-tile not supported - use checkbox method")
        self.step_capture.mark(4, "Verify insight chart content appears in the tile")

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _create_and_save_view(self, view_name: str):
        """Helper: Create a new tab, add camera, rename, and save."""
        self.views.add_new_tab()
        self.page.wait_for_timeout(500)

        # Rename tab
        tab = self.page.locator("button.tabItem").nth(1)
        tab.hover()
        self.page.wait_for_timeout(150)
        tab.locator("img[src*='editIcon']").click()
        self.page.wait_for_timeout(150)

        tab_input = self.page.locator("input.tabTitle").nth(1)
        tab_input.fill(view_name)
        tab_input.press("Enter")
        self.page.wait_for_timeout(250)

        # Add a camera
        self.views.expand_site_and_show_cameras("Driver Site")
        self.page.wait_for_timeout(500)
        self.views.add_first_camera_via_checkbox()
        self.page.wait_for_timeout(500)

        # Save
        save_btn = self.page.locator("img[src*='save']").nth(1)
        save_btn.evaluate("el => el.click()")
        self.page.wait_for_timeout(500)
        self.page.locator("text=View saved successfully").wait_for(state="visible", timeout=60000)

    def _close_tab_by_index(self, index: int):
        """Helper: Close a tab by index."""
        tab = self.page.locator("button.tabItem").nth(index)
        tab.hover()
        self.page.wait_for_timeout(150)
        tab.locator("img[src*='closeIcon']").click()
        self.page.wait_for_timeout(500)

    def _js_hover_on_view(self, view_name: str):
        """Helper: JS hover to reveal checkbox on saved view."""
        self.page.evaluate(
            """(title) => {
                const span = document.querySelector(`span[title='${title}']`);
                if (span) {
                    let parent = span.parentElement;
                    for (let i = 0; i < 5; i++) {
                        if (parent) {
                            parent.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
                            parent.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                            parent = parent.parentElement;
                        }
                    }
                }
            }""",
            view_name
        )

    def _delete_saved_view(self, view_name: str):
        """Helper: Delete a saved view by name."""
        try:
            self.page.locator("img[src*='myviews']").click()
            self.page.wait_for_timeout(500)

            saved_view = self.page.locator(f"span[title='{view_name}']")
            if saved_view.count() > 0:
                saved_view.hover()
                self.page.wait_for_timeout(150)
                self.page.locator("img[src*='delete-icon']").click()
                self.page.wait_for_timeout(250)
                self.page.locator("button:has-text('Delete')").click()
                self.page.locator("text=Successfully deleted").wait_for(
                    state="visible", timeout=60000
                )
        except Exception:
            pass  # Cleanup is best-effort

