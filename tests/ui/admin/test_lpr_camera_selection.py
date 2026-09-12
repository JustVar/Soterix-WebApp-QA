"""LPR Camera selection tests - group checkbox, drag-drop, single camera.

Rebuilt 08/13/2026. The old file navigated to Admin > LPR (the Lists
page), failed to find the Locations & Cameras panel there, and
returned early - all three tests passed without testing anything. The
panel lives on the sidebar LPR camera page: camera and group rows are
draggable and show a hover checkbox (sidebar-custom-checkbox) that
adds them to the grid. A new video element past the baseline is the
started signal (measured: the group checkbox took the page from 0 to
4 streams; empty tiles keep placeholder spinners alive forever, so
loader waits can never finish). Reset View clears the grid to 0
videos, and placements are session-scoped.

The panel has no camera search box (the page's only Search input
belongs to the Widgets panel), so the old search step is gone.
"""
import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.lpr_page import LprPage

SITE_NAME = config.get("test_site_name")
CAMERA_NAME = config.get("test_camera_name")


class TestLprCameraSelection:
    """Tests for LPR camera selection and manipulation."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

    def _expect_new_stream(self, before: int, timeout: int = 60000):
        """A video element past the baseline is the started signal."""
        self.page.locator("video").nth(before).wait_for(
            state="attached", timeout=timeout
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_select_multi_camera_by_site(self):
        """The group row's hover checkbox starts the group's cameras.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens with empty tiles that read Drag & Drop Camera here.
        2. Click the Locations & Cameras header.
           Expected: The panel opens and lists the configured test site.
        3. Click the test site.
           Expected: The All Cameras group row shows under the site.
        4. Hover the group row and click its checkbox.
           Expected: At least one new stream starts in a tile.
        5. Click Reset View.
           Expected: Every tile is empty again.
        """
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, "Open the Locations & Cameras panel")
        self.lpr.ensure_lpr_dropdown_open()

        self.step_capture.mark(3, f"Open site '{SITE_NAME}'")
        group = self.lpr.open_site_group(SITE_NAME)

        self.step_capture.mark(4, "Hover the group row, click its checkbox")
        before = self.page.locator("video").count()
        group.hover()
        group.locator(".sidebar-custom-checkbox").first.click()

        self.step_capture.mark(5, "A new stream past the baseline starts")
        self._expect_new_stream(before)

        self.step_capture.mark(6, "Reset View clears the grid")
        self.page.get_by_text("Reset View", exact=True).click()
        expect(self.page.locator("video")).to_have_count(0, timeout=15000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_drag_drop_camera_to_grid(self):
        """Dragging the group onto a tile starts its cameras.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens with empty tiles that read Drag & Drop Camera here.
        2. Click the Locations & Cameras header, then click the test site.
           Expected: The All Cameras group row shows under the site.
        3. Drag the All Cameras group row onto the last empty tile.
           Expected: At least one camera of the group starts streaming in a tile.
        """
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, f"Drag the '{SITE_NAME}' group to a tile")
        # oracle: play_camera raises unless a new stream element
        # appears after the drop (one stream by design - the shared
        # tenant keeps offline cameras in the group)
        self.lpr.play_camera(SITE_NAME, play_all_cameras=True)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_hover_and_select_single_camera(self):
        """A camera row's hover checkbox starts that camera.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens with empty tiles that read Drag & Drop Camera here.
        2. Click the Locations & Cameras header, click the test site, then click the All Cameras group.
           Expected: The configured test camera row shows under the group.
        3. Hover the camera row and click its checkbox.
           Expected: The camera starts streaming in a tile.
        """
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, "Open the Locations & Cameras panel")
        self.lpr.ensure_lpr_dropdown_open()

        self.step_capture.mark(3, f"Expand to camera '{CAMERA_NAME}'")
        group = self.lpr.open_site_group(SITE_NAME)
        cameras = self.page.locator("div[draggable='true']").filter(
            has_text=CAMERA_NAME
        )
        try:
            cameras.first.wait_for(state="visible", timeout=3000)
        # the group may still be collapsed; one expand click self-heals
        except Exception:
            group.click()
            cameras.first.wait_for(state="visible", timeout=15000)

        self.step_capture.mark(4, "Hover the camera row, click its checkbox")
        before = self.page.locator("video").count()
        row = cameras.first
        row.hover()
        # JS click on the inner input: the row re-renders continuously
        # (its snapshot image refreshes), so a pointer click never
        # passes the stability check, and MUI checkboxes handle the
        # change on the input, not the span (the sequences page uses
        # the same input-targeted JS click). The new-stream wait below
        # is the oracle.
        row.locator(
            ".sidebar-custom-checkbox input[type='checkbox']"
        ).first.evaluate("el => el.click()")

        self.step_capture.mark(5, "A new stream past the baseline starts")
        self._expect_new_stream(before)
