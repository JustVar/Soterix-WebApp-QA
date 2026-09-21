"""LPR grid layout and playback-timeout popup tests.

The layout picker is three side-by-side buttons on the LPR camera
page (1x1, 2x2, 3x3); the active one carries the activeLayout class
and the visible empty-tile count matches the layout (1/4/9). The
timeout popup ('Set Timeout Duration') opens only while a stream is
playing - without one, the icon click yields nothing but its
'Playback Auto-Timeout' tooltip. Measured 08/12-08/13/2026.
"""
import re

import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.lpr_page import LprPage

SITE_NAME = config.get("test_site_name")
CAMERA_NAME = config.get("test_camera_name")

# One worker for every module that uses the LPR camera page: its layout (1x1, 2x2, 3x3) is kept
# on the server for each user, the layout test changes it, and the tests here measure tiles on
# 2x2. Under -n two workers raced on it (pytest.ini --dist loadgroup; audit 09/21/2026).
pytestmark = pytest.mark.xdist_group("account_lpr")


class TestLprGridLayout:
    """Tests for LPR grid layout selection."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        # No config guard: the layout test uses no tenant names
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

    def _layout_buttons(self):
        """The three layout buttons, anchored on the 1x1 icon."""
        bar = self.page.locator("img[alt='1*1']").first.locator(
            "xpath=ancestor::*[count(.//button) >= 3][1]"
        )
        return bar.locator("button")

    def _visible_tiles(self) -> int:
        """Visible empty tiles; hidden layouts stay mounted."""
        return self.page.evaluate(
            """() => [...document.querySelectorAll('body *')]
                .filter(e => e.children.length === 0
                        && e.getClientRects().length > 0
                        && (e.textContent || '').trim() ===
                           'Drag & Drop Camera here').length"""
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_select_grid_layouts(self):
        """Each layout button shows its tile count and active state.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens with three layout buttons.
        2. Click the 1x1 layout button.
           Expected: One empty tile shows and the 1x1 button is highlighted.
        3. Click the 2x2 layout button.
           Expected: Four empty tiles show and the 2x2 button is highlighted.
        4. Click the 3x3 layout button.
           Expected: Nine empty tiles show and the 3x3 button is highlighted.
        5. Click the 2x2 layout button again.
           Expected: Four empty tiles show.
        """
        self.step_capture.mark(1, "Navigate to the LPR camera page")
        self.lpr.ensure_lpr_camera_page()
        buttons = self._layout_buttons()
        # Exactly three: a toolbar gaining a fourth button would
        # silently remap the indexes
        expect(buttons).to_have_count(3, timeout=10000)

        try:
            for idx, count in ((0, 1), (1, 4), (2, 9)):
                self.step_capture.mark(
                    2 + idx, f"Select the {count}-tile layout"
                )
                buttons.nth(idx).click()
                assert self._wait_tiles(count), (
                    f"Layout button {idx} did not settle at {count} "
                    f"visible tiles (saw {self._visible_tiles()})"
                )
                assert buttons.nth(idx).evaluate(
                    "el => el.className.includes('activeLayout')"
                ), f"Layout button {idx} did not become active"
        finally:
            # The layout persists server-side per user (measured:
            # fresh sessions keep it), and the other LPR suites were
            # measured on 2x2 - restore it even on failure
            self.step_capture.mark(5, "Restore the 2x2 layout")
            buttons.nth(1).click()
            assert self._wait_tiles(4), "2x2 restore did not settle"

    def _wait_tiles(self, count: int, timeout_ms: int = 10000) -> bool:
        """Poll until the visible-tile count holds for two reads.

        Layout cross-fades keep both grids' tiles visible briefly, so
        a single sample can pass THROUGH the target transiently.
        """
        waited = 0
        streak = 0
        while waited <= timeout_ms:
            if self._visible_tiles() == count:
                streak += 1
                if streak >= 2:
                    return True
            else:
                streak = 0
            self.page.wait_for_timeout(250)  # poll tick, not a sleep
            waited += 250
        return False


class TestLprTimer:
    """Tests for the playback timeout popup."""

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

    def _open_popup_with_stream(self):
        """Play the configured camera and open the timeout popup."""
        self.lpr.ensure_lpr_camera_page()
        self.lpr.play_camera(site_name=SITE_NAME, camera_name=CAMERA_NAME)
        self.lpr.open_lpr_playback_timeout_popup()

    def _popup(self):
        """The timeout dialog, scoped off its title.

        Page-wide Save/Cancel picks can land on stale mounted
        dialogs or unrelated controls.
        """
        return self.page.get_by_text(
            "Set Timeout Duration"
        ).first.locator("xpath=ancestor::*[.//*[text()='Save']][1]")

    def _close_popup(self):
        cancel = self._popup().get_by_text("Cancel", exact=True).first
        cancel.click()
        expect(
            self.page.get_by_text("Set Timeout Duration").first
        ).to_be_hidden(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.intermittent
    def test_timer_popup_validation(self):
        """The popup opens over a playing stream and closes on Cancel.

        Steps:
        1. Click LPR in the left sidebar, open the Locations & Cameras panel, open the test site and its All Cameras group, and drag the configured test camera onto the last empty tile.
           Expected: The camera streams in the tile.
        2. Click the timer icon.
           Expected: The Set Timeout Duration popup opens with Save and Cancel buttons.
        3. Click Cancel, then click Reset View.
           Expected: The popup closes and the tiles are empty.
        """
        self.step_capture.mark(1, "Play a stream and open the popup")
        self._open_popup_with_stream()

        self.step_capture.mark(2, "Verify the popup controls")
        popup = self._popup()
        expect(popup.get_by_text("Save", exact=True)).to_have_count(1)
        expect(popup.get_by_text("Cancel", exact=True)).to_have_count(1)

        self.step_capture.mark(3, "Close and clear")
        self._close_popup()
        self.lpr.clear_all_tiles()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.intermittent
    def test_timer_dropdown_values(self):
        """The duration dropdown offers the preset values.

        Steps:
        1. Click LPR in the left sidebar, open the Locations & Cameras panel, open the test site and its All Cameras group, and drag the configured test camera onto the last empty tile.
           Expected: The camera streams in the tile.
        2. Click the timer icon.
           Expected: The Set Timeout Duration popup opens and shows a Minutes value.
        3. Click the Minutes value.
           Expected: The list shows 30 Minutes and 45 Minutes.
        4. Press Escape, click Cancel, then click Reset View.
           Expected: The popup closes and the tiles are empty.
        """
        self.step_capture.mark(1, "Play a stream and open the popup")
        self._open_popup_with_stream()

        self.step_capture.mark(2, "Open the duration dropdown")
        current = self._popup().get_by_text("Minutes", exact=False).first
        expect(current).to_have_text(re.compile(r"\d+ Minutes"))
        current.click()

        self.step_capture.mark(3, "Verify the preset options")
        options = self.page.locator("li:visible")
        expect(options.filter(has_text="30 Minutes")).to_have_count(1, timeout=10000)
        expect(options.filter(has_text="45 Minutes")).to_have_count(1)

        self.step_capture.mark(4, "Dismiss without saving")
        self.page.keyboard.press("Escape")
        self._close_popup()
        self.lpr.clear_all_tiles()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.intermittent
    def test_timer_cancel_button(self):
        """Cancel closes the popup without saving.

        Steps:
        1. Click LPR in the left sidebar, open the Locations & Cameras panel, open the test site and its All Cameras group, and drag the configured test camera onto the last empty tile.
           Expected: The camera streams in the tile.
        2. Click the timer icon, then click Cancel.
           Expected: The Set Timeout Duration popup closes.
        3. Click Reset View.
           Expected: The tiles are empty.
        """
        self.step_capture.mark(1, "Play a stream and open the popup")
        self._open_popup_with_stream()

        self.step_capture.mark(2, "Cancel the popup")
        self._popup().get_by_text("Cancel", exact=True).first.click()
        # The popup staying open after Cancel is this test's reason
        # to exist
        expect(
            self.page.get_by_text("Set Timeout Duration").first
        ).to_be_hidden(timeout=10000)

        self.step_capture.mark(3, "Clear the view")
        self.lpr.clear_all_tiles()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.intermittent
    def test_timer_after_page_refresh(self):
        """The popup reopens with a value after a reload.

        Steps:
        1. Click LPR in the left sidebar, open the Locations & Cameras panel, open the test site and its All Cameras group, and drag the configured test camera onto the last empty tile.
           Expected: The camera streams in the tile.
        2. Click the timer icon.
           Expected: The Set Timeout Duration popup opens and shows a Minutes value.
        3. Click Cancel, then reload the browser page.
           Expected: The LPR camera page loads again.
        4. Drag the test camera onto an empty tile, then click the timer icon again.
           Expected: The popup opens and still shows a Minutes value.
        5. Click Cancel, then click Reset View.
           Expected: The popup closes and the tiles are empty.
        """
        self.step_capture.mark(1, "Play a stream and open the popup")
        self._open_popup_with_stream()
        expect(
            self._popup().get_by_text("Minutes", exact=False).first
        ).to_have_text(re.compile(r"\d+ Minutes"))
        self._close_popup()

        self.step_capture.mark(2, "Reload and reopen")
        self.page.reload()
        self._open_popup_with_stream()
        expect(
            self._popup().get_by_text("Minutes", exact=False).first
        ).to_have_text(re.compile(r"\d+ Minutes"))

        self.step_capture.mark(3, "Close and clear")
        self._close_popup()
        self.lpr.clear_all_tiles()
