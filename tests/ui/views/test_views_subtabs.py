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
import time

import pytest
from playwright.sync_api import expect
from config.base_config import config
from tests.shared.helpers.surface import require_items
from tests.shared.pages.insights_page import InsightsPage
from tests.shared.pages.views_page import ViewsPage

# The shared tenant renames sites, so the name lives in config
SITE_NAME = config.get("test_site_name")


class TestViewsSubtabs:
    """Tests for each Views left panel subtab."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        """Setup runs once per test using cached session (no re-login)."""
        self.page = authenticated_page
        self.views = ViewsPage(self.page)
        self._saved_view_names = []
        self._created_widgets = []
        self.insights = InsightsPage(self.page)

        # Always click Views nav - fast if already there, navigates if not
        self.page.locator("text=Views").first.click(force=True)

        # Wait for page ready indicator
        self.views.add_tab_button.wait_for(state="visible", timeout=10000)
        yield
        # Cleanup: delete any insight widgets created during the test
        for widget in reversed(self._created_widgets):
            try:
                self.insights.delete_widget(widget)
            # cleanup only: a leftover widget must not fail a test that
            # already passed - the failure is logged, and the name
            # carries its own timestamp for a manual sweep
            except Exception as e:
                print(f"Cleanup: failed to delete widget '{widget}': {e}")
        # Cleanup: delete any saved views created during the test
        for name in reversed(self._saved_view_names):
            try:
                self._delete_saved_view(name)
            # cleanup only: a leftover saved view must not fail a test that
            # already passed - the failure is logged
            except Exception as e:
                print(f"Cleanup: failed to delete view '{name}': {e}")
        # Cleanup: close extra tabs (only first tab should remain)
        try:
            tabs = self.page.locator("button.tabItem:visible")
            while tabs.count() > 1:
                before = tabs.count()
                last_tab = tabs.last
                last_tab.hover()
                # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
                close_icon = last_tab.locator("img[src*='closeIcon']")
                try:
                    close_icon.wait_for(state="visible", timeout=2000)
                except Exception:
                    break
                close_icon.click()
                expect(tabs).to_have_count(before - 1, timeout=5000)
        # cleanup only: an unclosed tab must not fail a test that already
        # passed - the failure is logged
        except Exception as e:
            print(f"Cleanup: failed to close extra tabs: {e}")

    # =========================================================================
    # HELPERS - waiting
    # =========================================================================

    def _content_baseline(self, content_selector: str) -> int:
        """Count content elements before an action, for _content_added."""
        return self.page.locator(content_selector).count()

    def _content_added(self, initial_tiles: int, content_selector: str,
                       baseline_content: int = 0,
                       timeout_s: float = 15.0) -> bool:
        """Poll until an empty tile is consumed or NEW content appears.

        The success condition is a disjunction (tile count dropped OR a
        content element was added), which no single locator wait can
        express, so this polls both sides and returns as soon as either is
        true. Returns False on timeout.

        baseline_content must be measured with _content_baseline() BEFORE
        the action: sidebar previews and already-filled tiles match the
        content selectors page-wide, so an absolute count > 0 check passes
        without the action doing anything (audit finding, 2026-08-07).
        Only an increase over the baseline counts as success.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.views.get_available_tile_count() < initial_tiles:
                return True
            if self.page.locator(content_selector).count() > baseline_content:
                return True
            self.page.wait_for_timeout(250)  # poll tick, not a blind sleep
        return False

    def _reveal_checkbox(self, thumbnail, timeout: int = 5000):
        """Hover a thumbnail and wait for its checkbox; None if it never shows."""
        thumbnail.hover()
        checkbox = thumbnail.locator(".sidebar-custom-checkbox")
        try:
            checkbox.wait_for(state="visible", timeout=timeout)
        except Exception:
            return None
        return checkbox

    # =========================================================================
    # DEVICES SUBTAB - Camera thumbnails from site tree
    # =========================================================================

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_devices
    @pytest.mark.checkbox
    def test_devices_add_camera_via_checkbox(self):
        """DEVICES: Add camera to tile using checkbox selection.

        Steps:
        1. On Views, open the Devices panel, expand the configured site and click All Cameras.
           Expected: The site's camera thumbnails are listed.
        2. Hover the configured camera's thumbnail and tick its checkbox.
           Expected: An empty tile fills with that camera's video.
        """
        initial_tiles = self.views.get_available_tile_count()
        assert initial_tiles > 0, "No empty tiles available"

        # Devices is default tab - expand site and show cameras
        self.views.expand_site_and_show_cameras(None)

        camera_name = config.get("test_camera_name")
        assert camera_name, "test_camera_name must be set in config/env for this test"

        content_sel = "video, canvas, [class*='video']"
        baseline = self._content_baseline(content_sel)
        # advisory content-health baseline: the tile settles, then the
        # advisory reports a dead stream (the QA tenant's stream may be down)
        health = self.views.content_health_snapshot()

        self.views.add_camera_via_checkbox(camera_name)

        assert self._content_added(initial_tiles, content_sel, baseline), \
            f"Camera '{camera_name}' not added. Tiles: {initial_tiles} -> {self.views.get_available_tile_count()}"
        self.views.wait_for_tiles_settled()
        self.views.log_new_content_issues(health, "camera add")

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_devices
    @pytest.mark.dragdrop
    def test_devices_drag_camera_to_tile(self):
        """DEVICES: Drag camera thumbnail directly to empty tile.

        Steps:
        1. Expand site -> Show cameras
        2. Drag camera thumbnail to empty tile (visible drag animation)

        Success: Tile count decreases OR video element appears
        """
        initial_tiles = self.views.get_available_tile_count()
        assert initial_tiles > 0, "No empty tiles available"

        self.views.expand_site_and_show_cameras(None)

        camera = self.page.locator(".cameraThumbnailWrapper").first
        camera.wait_for(state="visible", timeout=10000)

        target_tile = self.views.drag_drop_tiles.first
        target_tile.wait_for(state="visible", timeout=10000)

        # Perform visible drag using explicit mouse movements
        content_sel = "video, canvas, [class*='video']"
        baseline = self._content_baseline(content_sel)
        # advisory content-health baseline: a drop can consume the tile
        # yet render a broken image or a dead stream (observed live)
        health = self.views.content_health_snapshot()
        self._visible_drag(camera, target_tile)

        assert self._content_added(initial_tiles, content_sel, baseline), \
            f"Drag failed. Tiles: {initial_tiles} -> {self.views.get_available_tile_count()}"
        # first sidebar camera, maybe offline (see the checkbox test):
        # the tile settles so the advisory below sees the outcome
        self.views.wait_for_tiles_settled()
        self.views.log_new_content_issues(health, "camera drag")

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

        # Create a view to test with
        self._create_and_save_view(view_name)

        # Refresh page (required for My Views to properly list the new view)
        self.page.reload()

        # Open My Views subtab (click auto-waits after the reload)
        self.views.open_my_views()

        # Find and add saved view via checkbox
        saved_view = self.page.locator(f"span[title='{view_name}']").first
        saved_view.wait_for(state="visible", timeout=20000)

        # JS hover to reveal checkbox (React requires this); the click
        # auto-waits for the revealed checkbox
        self._js_hover_on_view(view_name)
        checkbox = self.page.locator(".sidebar-custom-checkbox").first
        checkbox.click()

        # Verify: the view opens as a tab. Tab selector varies, so check a
        # union of the known shapes with one retrying assertion.
        tab = (
            self.page.locator(f"input.tabTitle[value='{view_name}']")
            .or_(self.page.locator(f"button.tabItem:has(div[title='{view_name}'])"))
            .or_(self.page.locator(f"button.tabItem:has-text('{view_name}')"))
        )
        expect(tab.first).to_be_attached(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_myviews
    @pytest.mark.dragdrop
    def test_my_views_drag_saved_view_to_tile(self):
        """MY VIEWS: Drag saved view directly to tile.

        Steps:
        1. On Views, click the plus tab, rename the new tab, add the first camera with its checkbox, and click Save.
           Expected: A toast reads View saved successfully.
        2. Reload the page and click the My Views subtab.
           Expected: The saved view is listed by its name.
        3. Drag the saved view onto an empty tile.
           Expected: The tile fills with the view content, or the view opens as a new tab.
        """
        import datetime
        view_name = f"DragViewTest_{datetime.datetime.now().strftime('%H%M%S')}"
        self._saved_view_names.append(view_name)

        self._create_and_save_view(view_name)

        # Refresh page (required for My Views to properly list the new view)
        self.page.reload()

        initial_tiles = self.views.get_available_tile_count()

        # Open My Views subtab
        self.views.open_my_views()

        saved_view = self.page.locator(f"span[title='{view_name}']").first
        saved_view.wait_for(state="visible", timeout=20000)

        target_tile = self.views.drag_drop_tiles.first

        # Attempt drag with visible highlight - views may open as tabs rather than filling tiles
        content_sel = "video, canvas"
        baseline = self._content_baseline(content_sel)
        # The creation tab can survive the reload, so only a tab the
        # drop itself opens counts - measure against a pre-drag baseline
        tab_locators = (
            self.page.locator(f"input.tabTitle[value='{view_name}']"),
            self.page.locator(f"button.tabItem:has-text('{view_name}')"),
        )
        tabs_before = [loc.count() for loc in tab_locators]
        health = self.views.content_health_snapshot()
        # The drag is the behaviour under test. It used to run under a
        # handler that skipped on any exception, and a drop that landed
        # nothing skipped too, so this test had no failing path at all
        # (register item 25).
        self._visible_drag(saved_view, target_tile)

        # Give the drop a bounded window to land as either a tile or a tab
        filled = self._content_added(initial_tiles, content_sel, baseline, timeout_s=8.0)

        tab_found = any(
            loc.count() > before
            for loc, before in zip(tab_locators, tabs_before, strict=True)
        )

        assert filled or tab_found, (
            f"Dragging the saved view '{view_name}' onto a tile landed "
            f"nothing: no tile filled and no new tab opened within 8s"
        )
        self.views.log_new_content_issues(health, "view drag")

    # =========================================================================
    # MAPS SUBTAB - Map thumbnails under sites
    # =========================================================================

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_maps
    @pytest.mark.checkbox
    def test_maps_add_map_via_checkbox(self):
        """MAPS: Add map to tile using checkbox.

        Steps:
        1. On Views, open the Maps panel and expand the configured site.
           Expected: The site's map thumbnails are listed.
        2. Hover a map thumbnail and tick its checkbox.
           Expected: An empty tile fills with the map.
        """
        initial_tiles = self.views.get_available_tile_count()
        assert initial_tiles > 0, "No empty tiles"

        # Open Maps and expand the CONFIGURED site: click_site(None)
        # picked whichever row its heuristic reached first, so the skip
        # below named a site the test had never chosen (item 25).
        self.views.open_maps()
        self.views.click_site(SITE_NAME)

        map_thumb = self._require_map_thumbnails().first

        checkbox = self._reveal_checkbox(map_thumb)
        assert checkbox is not None, (
            "The map thumbnail exposes no hover checkbox, so the checkbox "
            "add path this test covers is gone"
        )
        content_sel = "[class*='leaflet'], iframe, [class*='map-container']"
        baseline = self._content_baseline(content_sel)
        checkbox.click()

        # No loader wait: empty tiles keep placeholder spinners alive,
        # so CircularProgress hidden can never finish; the content
        # poll below is the signal

        assert self._content_added(initial_tiles, content_sel, baseline), \
            f"Map not added. Tiles: {initial_tiles} -> {self.views.get_available_tile_count()}"

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_maps
    @pytest.mark.dragdrop
    def test_maps_drag_map_to_tile(self):
        """MAPS: Drag map thumbnail directly to tile.

        Steps:
        1. On Views, open the Maps panel and expand the configured site.
           Expected: The site's map thumbnails are listed.
        2. Drag a map thumbnail onto an empty tile.
           Expected: The tile fills with the map.
        """
        initial_tiles = self.views.get_available_tile_count()

        self.views.open_maps()
        self.views.click_site(SITE_NAME)

        map_thumb = self._require_map_thumbnails().first

        target_tile = self.views.drag_drop_tiles.first

        # Visible drag with animation
        content_sel = "[class*='leaflet'], iframe"
        baseline = self._content_baseline(content_sel)
        health = self.views.content_health_snapshot()
        self._visible_drag(map_thumb, target_tile)

        assert self._content_added(initial_tiles, content_sel, baseline), \
            "Map drag failed"
        self.views.log_new_content_issues(health, "map drag")

    # =========================================================================
    # CHANNELS SUBTAB - Channel thumbnails
    # =========================================================================

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_channels
    @pytest.mark.checkbox
    def test_channels_add_channel_via_checkbox(self):
        """CHANNELS: Add channel to tile using checkbox.

        Steps:
        1. Click Channels tab
        2. Hover channel thumbnail -> Click checkbox

        Success: Tile count decreases OR video appears
        """
        initial_tiles = self.views.get_available_tile_count()

        # Click Channels subtab (in .viewTabs, not left nav)
        self.views.open_channels()

        channel = self._require_channels().first

        checkbox = self._reveal_checkbox(channel)
        assert checkbox is not None, (
            "The channel thumbnail exposes no hover checkbox, so the "
            "checkbox add path this test covers is gone"
        )
        content_sel = "video, canvas"
        baseline = self._content_baseline(content_sel)
        checkbox.click()

        assert self._content_added(initial_tiles, content_sel, baseline), \
            "Channel not added via checkbox"

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_channels
    @pytest.mark.dragdrop
    def test_channels_drag_channel_to_tile(self):
        """CHANNELS: Drag channel thumbnail to tile.

        Steps:
        1. Click Channels subtab
        2. Drag channel to empty tile

        Success: Tile filled with video
        """
        initial_tiles = self.views.get_available_tile_count()

        # Click Channels subtab (in .viewTabs, not left nav)
        self.views.open_channels()

        channel = self._require_channels().first

        target_tile = self.views.drag_drop_tiles.first

        # Visible drag with animation
        content_sel = "video, canvas"
        baseline = self._content_baseline(content_sel)
        health = self.views.content_health_snapshot()
        self._visible_drag(channel, target_tile)

        assert self._content_added(initial_tiles, content_sel, baseline), \
            "Channel drag failed"
        self.views.log_new_content_issues(health, "channel drag")

    # =========================================================================
    # INSIGHTS SUBTAB - Analytics/Insight widget thumbnails
    # =========================================================================

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_insights
    @pytest.mark.checkbox
    def test_insights_add_via_checkbox(self):
        """INSIGHTS: Add insight widget to tile using checkbox.

        Insight widgets are user-created analytics charts (e.g., "All Persons Seen in the Last Week").
        They appear as cards with chart preview images and can be added to tiles.

        Steps:
        1. Create an insight widget, then on Views open the Insights panel.
           Expected: The widget's card is listed in the panel.
        2. Hover the widget card and tick its checkbox.
           Expected: An empty tile fills with the widget (on the current build the card offers no checkbox and drag is the add path, so the automated check stops there).
        """
        initial_tiles = self.views.get_available_tile_count()
        assert initial_tiles > 0, "No empty tiles available"

        # Widgets are user-created, so this test creates its own rather
        # than skipping on an empty panel or borrowing a teammate's
        # (register items 25 and 27).
        self._own_a_widget()

        # Click Insights subtab (top bar within Views, not left nav)
        self.views.open_insights()

        widget_card = self._require_insight_widget()

        checkbox = self._reveal_checkbox(widget_card)
        if checkbox is None:
            # Widget checkboxes sometimes render outside the card;
            # scope to the panel so a stray checkbox from another
            # subtab's item is never clicked
            fallback = self.page.locator(
                ".viewTabPanel .sidebar-custom-checkbox, "
                ".sidebar-content .sidebar-custom-checkbox"
            ).first
            if self.views._appears(fallback, timeout=2000):
                checkbox = fallback
        if checkbox is None:
            # Measured 2026-08-07 and again 2026-08-12: insight widgets
            # expose no hover checkbox and a direct card click adds
            # nothing. Drag-to-tile is the add path the UI supports
            # (covered by test_insights_drag_to_tile).
            pytest.skip(
                "Insight widgets expose no checkbox affordance; "
                "drag-to-tile is the supported add path"
            )

        # Tile-count oracle only: the sidebar previews match any
        # content selector page-wide, so a consumed tile is the one
        # signal a misfired add cannot fake
        checkbox.click()
        expect(self.views.drag_drop_tiles).to_have_count(
            initial_tiles - 1, timeout=15000
        )

    @pytest.mark.ui
    @pytest.mark.subtabs
    @pytest.mark.views_insights
    @pytest.mark.dragdrop
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
        # Ensure we have empty tiles by adding a new tab if needed
        initial_tiles = self.views.get_available_tile_count()
        if initial_tiles == 0:
            tabs = self.page.locator("button.tabItem:visible")
            before = tabs.count()
            self.views.add_new_tab()
            expect(tabs).to_have_count(before + 1, timeout=10000)
            # The tab-added signal precedes the new tab's tile render;
            # wait for a tile before reading the baseline count
            self.views._appears(self.views.drag_drop_tiles, timeout=5000)
            initial_tiles = self.views.get_available_tile_count()

        assert initial_tiles > 0, "No empty tiles available even after adding new tab"

        # Widgets are user-created, so this test creates its own
        # (register items 25 and 27).
        self._own_a_widget()

        # Click Insights subtab (top bar within Views, not left nav)
        self.views.open_insights()

        widget_card = self._require_insight_widget()

        target_tile = self.views.drag_drop_tiles.first
        target_tile.wait_for(state="visible", timeout=10000)

        # Forced drag, measured working 08/12/2026; the unforced drag
        # completes without adding anything
        target_tile.scroll_into_view_if_needed()
        health = self.views.content_health_snapshot()
        self._visible_drag(widget_card, target_tile, force=True)

        # Tile-count oracle only: the sidebar previews match any
        # content selector page-wide, so a consumed tile is the one
        # signal a misdropped drag cannot fake
        expect(self.views.drag_drop_tiles).to_have_count(
            initial_tiles - 1, timeout=15000
        )
        self.views.log_new_content_issues(health, "insight drag")

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _require_map_thumbnails(self):
        """Map thumbnails under the configured site, proved or explained.

        An empty Maps panel is the tenant's data and skips; a panel that
        never rendered is a fault and fails (register item 25).
        """
        thumbs = self.page.locator(".cameraThumbnailWrapper")
        require_items(
            thumbs,
            container=self.page.get_by_text(SITE_NAME, exact=True),
            surface=f"Views > Maps panel under site '{SITE_NAME}'",
            artifact="map thumbnail",
            empty_means="no map is published under this site",
            timeout_ms=5000,
        )
        return thumbs

    def _require_channels(self):
        """Channel thumbnails in the Channels panel, proved or explained."""
        channels = self.page.locator(".cameraThumbnailWrapper")
        require_items(
            channels,
            container=self.views.channels_tab,
            surface="Views > Channels panel",
            artifact="channel thumbnail",
            empty_means="this tenant has no channel published to Views",
            timeout_ms=5000,
        )
        return channels

    def _own_a_widget(self) -> str:
        """Create an insight widget this test owns, and return its name.

        Widgets are user-created, so the panel is empty on a clean
        tenant and these tests skipped every run; on a busy one they
        dragged a teammate's widget. Making one is the same fix the LPR
        lists got (register items 25 and 27). Line/Person is the
        cheapest shape the creation form offers.
        """
        name = self.insights.create_widget(
            graph_name="Line", category_name="Person", site_name=SITE_NAME
        )
        self._created_widgets.append(name)
        # The widget was made on the Insights page, so return to Views
        # before the caller opens the Insights SUBTAB.
        self.page.locator("text=Views").first.click(force=True)
        self.views.add_tab_button.wait_for(state="visible", timeout=10000)
        return name

    def _require_insight_widget(self):
        """The insight widget card this test made, or a loud failure.

        _own_a_widget ran first, so an empty panel here means the widget
        did not reach the Views subtab, which is a fault - not the
        absent artifact the old skip reported (register item 25).
        """
        card = self._find_insight_widget()
        assert card is not None, (
            "The Views > Insights panel shows no widget card although this "
            "test created one: the widget did not reach the subtab"
        )
        return card

    def _find_insight_widget(self):
        """Find an insight widget card; None when the tenant has no widgets.

        Waits briefly for the primary shape (cameraThumbnailWrapper) before
        trying the image fallback - an instant count() races the panel render.
        """
        camera_wrappers = self.page.locator(".cameraThumbnailWrapper")
        if self.views._appears(camera_wrappers, timeout=5000):
            return camera_wrappers.first

        # Fallback: look for thumbnail images in the insights panel
        thumbnail_images = self.page.locator(".viewTabPanel img, .sidebar-content img").filter(
            has_not=self.page.locator("input")  # Exclude search box area
        )
        if thumbnail_images.count() > 0:
            return thumbnail_images.first.locator("..")
        return None

    def _create_and_save_view(self, view_name: str):
        """Helper: Create a new tab, add camera, rename, and save."""
        tabs = self.page.locator("button.tabItem:visible")
        before = tabs.count()
        self.views.add_new_tab()
        expect(tabs).to_have_count(before + 1, timeout=10000)

        # Rename tab (clicks auto-wait for the hover-revealed icon)
        tab = self.page.locator("button.tabItem").nth(1)
        tab.hover()
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        tab.locator("img[src*='editIcon']").click()

        tab_input = self.page.locator("input.tabTitle").nth(1)
        tab_input.fill(view_name)
        tab_input.press("Enter")
        self.page.wait_for_timeout(250)  # rename commit has no DOM signal

        # Add a camera
        self.views.expand_site_and_show_cameras(None)
        self.views.add_first_camera_via_checkbox()

        # Save
        save_btn = self.page.locator("img[src*='save']").nth(1)
        save_btn.evaluate("el => el.click()")
        self.page.locator("text=View saved successfully").wait_for(state="visible", timeout=60000)

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
        """Helper: Delete a saved view by name.

        The img[src*=...] locators below trip the convention checker's
        img-src-locator rule, which advises preferring a data-testid. Checked
        against the test_delete_user trace on 2026-08-17: this app ships no
        data-testid attributes at all, and the icons are Next.js static assets
        (_next/static/media/delete-icon.415ce726.svg) rendered as plain <img>.
        The substring match is also required, not lazy - that filename carries
        a content hash that changes on every rebuild. Revisit if the app moves
        to MUI icon components.
        """
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.page.locator("img[src*='myviews']").click()
        saved_view = self.page.locator(f"span[title='{view_name}']")
        try:
            saved_view.wait_for(state="visible", timeout=5000)
        except Exception:
            return  # View not present - nothing to delete
        saved_view.hover()
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.page.locator("img[src*='delete-icon']").click()
        self.page.locator("button:has-text('Delete')").click()
        self.page.locator("text=Successfully deleted").wait_for(
            state="visible", timeout=60000
        )

    def _visible_drag(self, source, target, force: bool = False):
        """Helper: Perform a visible drag operation with highlights.

        Adds visual highlights around source (red) and target (green)
        elements, then performs the drag. The pauses are deliberate visual
        pacing so a tester watching in headed mode can follow the drag;
        they are not readiness waits.

        Args:
            source: Source locator to drag from
            target: Target locator to drag to
            force: Skip the drop target's actionability checks. Needed
                when the target grid relayouts continuously (insight
                tiles) and can never pass the stability check.
        """
        # Highlight source (red border - what we're dragging)
        try:
            source.evaluate("el => { el.style.outline = '4px solid red'; el.style.outlineOffset = '2px'; }")
        # the outline is headed-mode pacing only; drag_to below is the
        # real action and raises on its own
        except Exception:
            pass  # Visual highlight is non-essential
        self.page.wait_for_timeout(400)  # visual pacing

        # Highlight target (green border - where we're dropping)
        try:
            target.evaluate("el => { el.style.outline = '4px solid lime'; el.style.outlineOffset = '2px'; }")
        # the outline is headed-mode pacing only; drag_to below is the
        # real action and raises on its own
        except Exception:
            pass  # Visual highlight is non-essential
        self.page.wait_for_timeout(400)  # visual pacing

        # Perform the drag. The forced path keeps drag_to: insights is
        # its one caller and drag_to(force=True) is the measured-working
        # path there (08/12/2026). The unforced path uses the stepped
        # mouse drag - a single-jump drag_to reaches the app's drag
        # layer as a text selection, not a drag.
        if force:
            source.drag_to(target, force=True)
        else:
            self.views.mouse_drag(source, target)

        # Remove highlights
        try:
            source.evaluate("el => { el.style.outline = ''; el.style.outlineOffset = ''; }")
        # post-drop outline removal; the dragged thumbnail may have
        # re-rendered, and the caller's oracle follows
        except Exception:
            pass  # Element may have been detached after drag
        try:
            target.evaluate("el => { el.style.outline = ''; el.style.outlineOffset = ''; }")
        # post-drop outline removal; a filled tile replaces the empty
        # target, and the caller's oracle follows
        except Exception:
            pass  # Element may have been detached after drag
