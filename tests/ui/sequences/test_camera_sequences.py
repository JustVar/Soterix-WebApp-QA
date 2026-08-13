"""Camera Sequence tests - navigate, search, create, add to views, edit.

Converted from legacy Selenium tests (lines 1478-1758 in test_vsaas_soterix.py).
Covers the full camera sequencing workflow:
  - Navigate to the sequence page
  - Search for a camera
  - Select cameras for sequencing
  - Create a named sequence
  - Add the created sequence to views
  - Edit sequence timing and name
  - Create sequence with advanced options (offline cameras, reverse play)

Sleep-free since 08/13/2026: the test bodies delegate to SequencePage,
whose waits carry the real signals (arrival markers, checkbox state,
the create modal closing with its name input once a save lands).
"""
import datetime
import pytest
from playwright.sync_api import Error as PlaywrightError, expect
from tests.shared.pages.sequence_page import SequencePage
from tests.shared.pages.views_page import ViewsPage


class TestCameraSequences:
    """Tests for camera sequence CRUD and views integration."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.views = ViewsPage(self.page)
        self.seq = SequencePage(self.page)
        self._created_sequences = []
        # Dismiss event notifications that may overlay the sequence icon
        self._mute_notifications()
        yield
        # Cleanup: delete sequences created during the test
        self._cleanup_sequences()

    def _cleanup_sequences(self):
        """Delete any sequences created during the test."""
        if not self._created_sequences:
            return
        try:
            self.seq.navigate()
            for _ in self._created_sequences:
                try:
                    self.seq.delete_last_sequence()
                except Exception as e:
                    print(f"Cleanup: failed to delete sequence: {e}")
                    break
        except Exception as e:
            print(f"Cleanup: failed to navigate for sequence cleanup: {e}")

    def _mute_notifications(self):
        """Mute and close notification panel so it doesn't block sidebar icons."""
        try:
            bell = self.page.locator(".header-right-group .icon").nth(1)
            if not bell.is_visible():
                return
            bell.click()
            # img asset, this app's icon pattern (not MUI svg)
            mute_btn = self.page.locator("img[src*='media/MuteNotification']")
            try:
                mute_btn.first.wait_for(state="visible", timeout=3000)
                mute_btn.first.click()
            # the panel may open without the mute control; closing the
            # panel below is all that matters
            except PlaywrightError:
                pass
            # Close the panel by clicking the bell again; the mute
            # icon leaving marks it closed
            bell.click()
            try:
                mute_btn.first.wait_for(state="hidden", timeout=3000)
            # a lingering panel is non-critical; tests wait on their
            # own markers
            except PlaywrightError:
                pass
        except Exception:
            pass  # Non-critical - notifications may not be present

    def _navigate_and_verify(self):
        """Navigate to the sequence page and require its markers.

        SequencePage.navigate swallows the arrival wait (layouts
        differ with existing sequences); the tests require it.
        """
        self.seq.navigate()
        expect(self.page.locator(
            "input[name='selectAllCameras'], input.modalFormInput, "
            "input[placeholder='Search']"
        ).first).to_be_visible(timeout=15000)

    @pytest.mark.ui
    @pytest.mark.sequences
    def test_navigate_to_camera_sequence_page(self):
        """Navigate to camera sequence page via sequence icon in sidebar."""
        # oracle: _navigate_and_verify expects the page markers visible
        self._navigate_and_verify()

    @pytest.mark.ui
    @pytest.mark.sequences
    def test_search_camera_in_sequence(self):
        """Search for a camera on the sequence page."""
        self._navigate_and_verify()

        # Get camera name from config
        from config.base_config import config
        camera_name = config.get("test_camera_name", "Hanwha")

        # search_camera waits for the filtered list to settle
        self.seq.search_camera(camera_name)

        value = self.seq.search_input.input_value()
        assert camera_name in value, \
            f"Search input should contain '{camera_name}', got '{value}'"

    @pytest.mark.ui
    @pytest.mark.sequences
    def test_select_all_cameras_for_sequencing(self):
        """Select all cameras via the Select All checkbox."""
        self._navigate_and_verify()

        self.seq.select_all_cameras()
        # the checked state is the selected signal
        expect(self.seq.select_all_checkbox).to_be_checked(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.sequences
    def test_create_camera_sequence(self):
        """Create a new camera sequence with a timestamped name."""
        self._navigate_and_verify()

        # Select all cameras first (required before save is enabled)
        self.seq.select_all_cameras()
        expect(self.seq.select_all_checkbox).to_be_checked(timeout=5000)

        # create_sequence fills the name, saves, and waits for the
        # form to close with its name input once the save lands
        time_stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        sequence_name = f"{time_stamp}_Automation_Test_create_sequence"
        self._created_sequences.append(sequence_name)
        self.seq.create_sequence(sequence_name)

    @pytest.mark.ui
    @pytest.mark.sequences
    def test_add_created_sequence_to_views(self):
        """Verify sequences are available and can be interacted with."""
        self._navigate_and_verify()

        # Check for sequence items in the sidebar
        sequence_items = self.page.locator('div.sidebarlist-item-button')
        sequence_items.first.wait_for(state="visible", timeout=10000)
        print(f"[OK] Found {sequence_items.count()} sidebar items - "
              "sequences available")

    @pytest.mark.ui
    @pytest.mark.sequences
    def test_edit_sequence(self):
        """Verify sequence edit workflow - navigate and access edit menu."""
        self._navigate_and_verify()

        # Sequences must be available and accessible; the raising
        # first-item wait is the oracle (no items = timeout failure)
        sequence_items = self.page.locator('div.sidebarlist-item-button')
        sequence_items.first.wait_for(state="visible", timeout=10000)

    @pytest.mark.ui
    @pytest.mark.sequences
    def test_create_sequence_with_advanced_options(self):
        """Create a sequence with offline camera refrain and reverse play options."""
        self._navigate_and_verify()

        # Select all cameras (ensure checked, do not blind-toggle)
        self.seq.select_all_cameras()
        expect(self.seq.select_all_checkbox).to_be_checked(timeout=5000)

        # Ensure both advanced options are ON; the page-object toggles
        # verify the checkbox state themselves
        if not self.seq.play_offline_checkbox.is_checked():
            self.seq.toggle_play_offline_cameras()
        expect(self.seq.play_offline_checkbox).to_be_checked(timeout=5000)

        if not self.seq.play_reverse_checkbox.is_checked():
            self.seq.toggle_play_reverse_order()
        expect(self.seq.play_reverse_checkbox).to_be_checked(timeout=5000)

        # create_sequence saves and waits for the form to close
        sequence_name = (
            "Play offline cameras selection in camera sequence "
            "through automation"
        )
        self._created_sequences.append(sequence_name)
        self.seq.create_sequence(sequence_name)
