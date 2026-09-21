"""LPR camera playback and views integration tests.

Tests for LPR camera playback, timeout settings, and views page
integration. Playback flow: the Locations & Cameras panel starts
closed and lists site > camera groups > cameras; cameras drag onto
'Drag & Drop Camera here' tiles.
"""
import re

import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.lpr_page import LprPage

SITE_NAME = config.get("test_site_name")
CAMERA_NAME = config.get("test_camera_name")
# measured 09/12/2026 on US (register row 53)
VIEWS_SUBTABS = ["Devices", "My Views", "Insights", "Maps", "Channels"]

# One worker for every module that uses the LPR camera page: its layout (1x1, 2x2, 3x3) is kept
# on the server for each user, the layout test changes it, and the tests here measure tiles on
# 2x2. Under -n two workers raced on it (pytest.ini --dist loadgroup; audit 09/21/2026).
pytestmark = pytest.mark.xdist_group("account_lpr")


class TestLprCameraPlayback:
    """Tests for LPR camera playback functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        if not SITE_NAME or not CAMERA_NAME:
            pytest.skip(
                "test_site_name / test_camera_name not configured "
                "for this ENV (see config/env/)"
            )
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_navigate_to_lpr_camera_page(self):
        """Navigate to LPR camera/playback page.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens, the URL ends with /lpr, and a tile reads Drag & Drop Camera here.
        """
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, "Verify a playback tile is visible")
        expect(
            self.page.get_by_text("Drag & Drop Camera here", exact=True).first
        ).to_be_visible(timeout=15000)

        self.step_capture.mark(3, "Verify on correct URL")
        assert "/lpr" in self.page.url, "Not on LPR camera page"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_open_locations_dropdown(self):
        """Verify Locations & Cameras dropdown opens and lists the site.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens.
        2. Click the Locations & Cameras header.
           Expected: The panel lists the configured test site with its camera count.
        """
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()
        self.step_capture.mark(2, "Open the Locations & Cameras dropdown")
        self.lpr.ensure_lpr_dropdown_open()
        self.step_capture.mark(3, "Verify the configured site is listed with its camera count")
        # .first: the panel lists each site once, with its count beside it
        site_row = self.page.get_by_text(SITE_NAME, exact=False).first
        expect(site_row).to_be_visible(timeout=30000)
        row_text = " ".join(site_row.locator("xpath=..").inner_text().split())
        assert re.fullmatch(rf"{re.escape(SITE_NAME)} \d+", row_text) is not None, (
            f"the site row reads {row_text!r}; expected the site name and its camera count")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_wait_for_site_list_loading(self):
        """Verify site list loads correctly.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens.
        2. Click the Locations & Cameras header and wait for the list to load.
           Expected: The configured test site appears in the panel with a camera count above zero.
        """
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()
        self.step_capture.mark(2, "Open the panel and wait for the site")
        self.lpr.ensure_lpr_dropdown_open()
        self.lpr.wait_for_site_list(SITE_NAME)
        # .first: the panel lists each site once, with its count beside it
        site_row = self.page.get_by_text(SITE_NAME, exact=False).first
        row_text = " ".join(site_row.locator("xpath=..").inner_text().split())
        count = row_text.rsplit(" ", 1)[-1]
        assert count.isdigit(), f"the site row reads {row_text!r}; expected a camera count"
        assert int(count) > 0, f"the site row reads {row_text!r}; the site lists no cameras"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_safe_reset_to_views(self):
        """Verify safe reset lands on the Views page.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens and the URL ends with /lpr.
        2. Reload the browser page.
           Expected: The application loads again.
        3. Click Views in the left sidebar.
           Expected: The address is the site root and the subtab bar reads Devices, My Views, Insights, Maps, Channels.
        """
        # Start away from Views: a reset that does nothing must fail here
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()
        assert "/lpr" in self.page.url, "Not on LPR camera page"
        self.step_capture.mark(2, "Call safe reset to Views")
        self.lpr.safe_reset_to_views()
        self.step_capture.mark(3, "Verify the Views page is active")
        # Views renders at the root URL; its subtab bar names the five views
        expect(self.page).to_have_url(re.compile(r"^https?://[^/]+/?$"), timeout=15000)
        tabs = self.page.locator(".viewTabs").first
        expect(tabs).to_be_visible(timeout=15000)
        names = [" ".join(x.split()) for x in tabs.inner_text().split("\n") if x.strip()]
        assert names == VIEWS_SUBTABS, f"the Views subtab bar reads {names}, expected {VIEWS_SUBTABS}"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.intermittent
    def test_camera_tile_activation(self):
        """Play the configured camera, then activate its tile.

        Steps:
        1. Click LPR in the left sidebar, open the Locations & Cameras panel, open the test site and its All Cameras group, and drag the configured test camera onto the last empty tile.
           Expected: The camera streams in the tile.
        2. Click the streaming tile.
           Expected: Exactly one tile shows the live icon.
        """
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()
        self.step_capture.mark(2, f"Play camera '{CAMERA_NAME}'")
        self.lpr.play_camera(site_name=SITE_NAME, camera_name=CAMERA_NAME)
        self.step_capture.mark(3, "Activate the camera tile")
        self.lpr.activate_camera_tile()
        # The live icon shows only on an activated tile. Visible ones only:
        # the player keeps a second, hidden copy in its top bar (measured
        # 09/18/2026: 0 x 0 px, the same src), and the count read 2.
        live_icons = self.page.locator("img[alt='live icon']").filter(visible=True)
        expect(live_icons).to_have_count(1, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_dismiss_backdrop(self):
        """Verify backdrop dismissal leaves no click-blocking overlay.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens.
        2. Press Escape if a dialog backdrop covers the page.
           Expected: No backdrop is visible and the page accepts clicks.
        """
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, "Dismiss any backdrop")
        self.lpr.dismiss_any_backdrop()

        self.step_capture.mark(3, "Verify no backdrop blocks the page")
        # Visible-filtered: MUI keeps detached hidden backdrops in the
        # DOM, so a bare count (or a .first peek) checks the wrong thing
        expect(
            self.page.locator("div[class*='MuiBackdrop-root']:visible")
        ).to_have_count(0)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.intermittent
    def test_open_playback_timeout_popup(self):
        """Verify the timeout popup opens for a playing LPR stream.

        The popup opens only while a stream plays; without one the
        icon click yields nothing but its tooltip.

        Steps:
        1. Click LPR in the left sidebar, open the Locations & Cameras panel, open the test site and its All Cameras group, and drag the configured test camera onto the last empty tile.
           Expected: The camera streams in the tile.
        2. Click the timer icon.
           Expected: The Set Timeout Duration popup opens with a Cancel button.
        3. Click Cancel, then click Reset View.
           Expected: The popup closes and the tiles are empty.
        """
        self.step_capture.mark(1, "Play the configured camera")
        self.lpr.ensure_lpr_camera_page()
        self.lpr.play_camera(site_name=SITE_NAME, camera_name=CAMERA_NAME)

        self.step_capture.mark(2, "Open the playback timeout popup")
        self.lpr.open_playback_timeout_popup()
        # Dialog-scoped: page-wide Cancel picks can land elsewhere
        popup = self.page.get_by_text("Set Timeout Duration").first\
            .locator("xpath=ancestor::*[.//*[text()='Save']][1]")
        expect(popup.get_by_text("Cancel", exact=True).first)\
            .to_be_visible()

        self.step_capture.mark(3, "Cancel and clear the view")
        popup.get_by_text("Cancel", exact=True).first.click()
        expect(
            self.page.get_by_text("Set Timeout Duration").first
        ).to_be_hidden(timeout=10000)
        self.lpr.clear_all_tiles()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.intermittent
    def test_open_lpr_playback_timeout_popup(self):
        """Verify the LPR timeout popup opens and closes cleanly.

        Steps:
        1. Click LPR in the left sidebar, open the Locations & Cameras panel, open the test site and its All Cameras group, and drag the configured test camera onto the last empty tile.
           Expected: The camera streams in the tile.
        2. Click the timer icon.
           Expected: The Set Timeout Duration popup opens with a Save button.
        3. Click Cancel, then click Reset View.
           Expected: The popup closes and the tiles are empty.
        """
        self.step_capture.mark(1, "Play the configured camera")
        self.lpr.ensure_lpr_camera_page()
        self.lpr.play_camera(site_name=SITE_NAME, camera_name=CAMERA_NAME)

        self.step_capture.mark(2, "Open the LPR playback timeout popup")
        self.lpr.open_lpr_playback_timeout_popup()
        # Dialog-scoped: page-wide Save/Cancel picks can land elsewhere
        popup = self.page.get_by_text("Set Timeout Duration").first\
            .locator("xpath=ancestor::*[.//*[text()='Save']][1]")
        expect(popup.get_by_text("Save", exact=True).first)\
            .to_be_visible()

        self.step_capture.mark(3, "Cancel and clear the view")
        popup.get_by_text("Cancel", exact=True).first.click()
        expect(
            self.page.get_by_text("Set Timeout Duration").first
        ).to_be_hidden(timeout=10000)
        self.lpr.clear_all_tiles()


class TestLprViewsIntegration:
    """Tests for LPR integration with Views page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        if not SITE_NAME or not CAMERA_NAME:
            pytest.skip(
                "test_site_name / test_camera_name not configured "
                "for this ENV (see config/env/)"
            )
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_navigate_to_views_page(self):
        """Verify navigation to Views page.

        Steps:
        1. Click Views in the left sidebar.
           Expected: The address is the site root and the subtab bar reads Devices, My Views, Insights, Maps, Channels.
        """
        self.step_capture.mark(1, "Navigate to Views page")
        self.lpr.go_to_views_page()
        self.step_capture.mark(2, "Verify on Views page")
        # Views renders at the root URL; its subtab bar names the five views
        expect(self.page).to_have_url(re.compile(r"^https?://[^/]+/?$"), timeout=15000)
        tabs = self.page.locator(".viewTabs").first
        expect(tabs).to_be_visible(timeout=15000)
        names = [" ".join(x.split()) for x in tabs.inner_text().split("\n") if x.strip()]
        assert names == VIEWS_SUBTABS, f"the Views subtab bar reads {names}, expected {VIEWS_SUBTABS}"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_safe_views_navigation_on_non_views_page(self):
        """Verify safe navigation to Views works from non-Views pages.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The LPR Lists page opens.
        2. Click Views in the left sidebar.
           Expected: The address is the site root and the subtab bar reads Devices, My Views, Insights, Maps, Channels.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page first")
        self.lpr.navigate_to_lpr()
        self.step_capture.mark(2, "Navigate to Views")
        self.lpr.go_to_views_page()
        self.step_capture.mark(3, "Verify the Views page is active")
        # Views renders at the root URL; its subtab bar names the five views
        expect(self.page).to_have_url(re.compile(r"^https?://[^/]+/?$"), timeout=15000)
        tabs = self.page.locator(".viewTabs").first
        expect(tabs).to_be_visible(timeout=15000)
        names = [" ".join(x.split()) for x in tabs.inner_text().split("\n") if x.strip()]
        assert names == VIEWS_SUBTABS, f"the Views subtab bar reads {names}, expected {VIEWS_SUBTABS}"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.intermittent
    def test_play_camera_by_location(self):
        """Verify the configured camera plays from its site group.

        The oracle lives in play_camera: it raises when the camera is
        missing or no new stream appears past the baseline.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens.
        2. Click the Locations & Cameras header, click the test site, then click the All Cameras group.
           Expected: The configured test camera row is listed.
        3. Drag the camera row onto the last empty tile.
           Expected: The camera streams in the tile.
        4. Click Reset View.
           Expected: The tiles are empty.
        """
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, f"Play camera '{CAMERA_NAME}'")
        self.lpr.play_camera(site_name=SITE_NAME, camera_name=CAMERA_NAME)

        self.step_capture.mark(3, "Clear the view")
        self.lpr.clear_all_tiles()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.intermittent
    def test_play_all_cameras(self):
        """Verify the whole camera group plays onto the tiles.

        The oracle lives in play_camera: it raises when no new stream
        appears past the baseline after the group drop.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens.
        2. Click the Locations & Cameras header, then click the test site.
           Expected: The All Cameras group row is listed.
        3. Drag the All Cameras group row onto the last empty tile.
           Expected: At least one camera of the group streams in a tile.
        4. Click Reset View.
           Expected: The tiles are empty.
        """
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, f"Play all cameras of '{SITE_NAME}'")
        self.lpr.play_camera(site_name=SITE_NAME, play_all_cameras=True)

        self.step_capture.mark(3, "Clear the view")
        self.lpr.clear_all_tiles()
