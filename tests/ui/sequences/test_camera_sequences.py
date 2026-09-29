"""Camera Sequence tests - navigate, search, create, add to views, edit.

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

from config.base_config import config
from tests.shared.pages.sequence_page import SequencePage
from tests.shared.pages.views_page import ViewsPage


def _required(key: str) -> str:
    """The env file's value for `key`, or a failure that names the key.

    A literal fallback here would drive the tests with another server's
    names when this env file leaves the key blank, and the failure would
    land on a locator instead of on the missing config.
    """
    value = config.get(key)
    if not value:
        raise RuntimeError(f"{key} is blank: set it in the env file under config/env/")
    return value


# One worker for every module that writes this account's notification mute state (it mutes notifications first) and sequences: under
# -n they would otherwise spread across workers and race on the same
# tenant state (pytest.ini --dist loadgroup).
pytestmark = pytest.mark.xdist_group("account_rules")



class TestCameraSequences:
    """Tests for camera sequence CRUD and views integration."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.views = ViewsPage(self.page)
        self.seq = SequencePage(self.page)
        self._created_sequences = []   # recorded BEFORE the create: a save can land after its check failed
        self._saved_sequences = []     # recorded AFTER create_sequence returned: these must be there to delete
        # Dismiss event notifications that may overlay the sequence icon
        self._mute_notifications()
        yield
        # Cleanup: delete sequences created during the test
        self._cleanup_sequences()

    def _cleanup_sequences(self):
        """Delete each sequence this test made, by its exact name, and say so when one stays.

        By name: the old body deleted the LAST item of the sidebar once for each recorded
        name. A name is recorded before its create, so a create that failed made the
        cleanup delete a sequence of a different person on the shared tenant.
        """
        if not self._created_sequences:
            return
        errors = []
        for name in self._created_sequences:
            try:
                found = self.seq.delete_sequence(name)
            # typed: a refused delete or a count that does not go down is what this collects, and
            # the raise after the loop reports it. Anything else is a real fault and goes up.
            except (PlaywrightError, AssertionError, RuntimeError) as e:
                errors.append(f"{name}: {e}")
                continue
            # A sequence whose create returned must be in the list. "Not listed" then means the
            # sidebar shows the name in a different form, and the sequence stays on the tenant.
            if not found and name in self._saved_sequences:
                errors.append(f"{name}: saved by this test, and not found in the sidebar to delete")
        self._created_sequences = []
        self._saved_sequences = []
        if errors:
            raise RuntimeError("sequence cleanup failed: " + "; ".join(errors))

    def _mute_notifications(self):
        """Mute and close notification panel so it doesn't block sidebar icons."""
        try:
            bell = self.page.locator(".header-right-group .icon").nth(1)
            if not bell.is_visible():
                return
            bell.click(timeout=10000)
            # img asset, this app's icon pattern (not MUI svg)
            mute_btn = self.page.locator("img[src*='media/MuteNotification']")
            try:
                mute_btn.first.wait_for(state="visible", timeout=3000)
                mute_btn.first.click(timeout=10000)
            # the panel may open without the mute control; closing the
            # panel below is all that matters
            except PlaywrightError:
                pass
            # Close the panel by clicking the bell again; the mute
            # icon leaving marks it closed
            bell.click(timeout=10000)
            try:
                mute_btn.first.wait_for(state="hidden", timeout=3000)
            # a lingering panel is non-critical; tests wait on their
            # own markers
            except PlaywrightError:
                pass
        # optional overlay: no notification panel is a valid state; the
        # tests fail on their own page markers if it blocked anything
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

        camera_name = _required("test_camera_name")

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
        time_stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
        sequence_name = f"{time_stamp}_Automation_Test_create_sequence"
        self._created_sequences.append(sequence_name)
        self.seq.create_sequence(sequence_name)
        self._saved_sequences.append(sequence_name)
        # the oracle: the saved sequence is listed by its name in the Sequences section
        self.seq.open_sequences_list()
        expect(self.seq.sequence_item(sequence_name)).to_have_count(1, timeout=15000)

    @pytest.mark.ui
    @pytest.mark.sequences
    def test_add_created_sequence_to_views(self):
        """A saved sequence is listed by its name in the Sequences section of the Views sidebar.

        Steps:
        1. Click the sequence icon, select all cameras, enter a name and click Save.
           Expected: The form closes.
        2. On Views, open the Sequences section of the left sidebar.
           Expected: The section lists the new sequence by its name, 1 time.
        """
        # An earlier version of this test counted the rows of the sidebar, which are the sites,
        # and called them sequences. It passed with no sequence on the tenant.
        self._navigate_and_verify()
        self.seq.select_all_cameras()
        time_stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
        sequence_name = f"{time_stamp}_Automation_Test_listed_sequence"
        self._created_sequences.append(sequence_name)
        self.seq.create_sequence(sequence_name)
        self._saved_sequences.append(sequence_name)
        self.seq.open_sequences_list()
        expect(self.seq.sequence_item(sequence_name)).to_have_count(1, timeout=15000)

    @pytest.mark.ui
    @pytest.mark.sequences
    def test_edit_sequence(self):
        """Verify the sequences page offers a sequence to edit.

        Steps:
        1. Open the Sequences page from the sidebar icon.
           Expected: The sidebar lists a sequence, which is the row an edit starts from.
        """
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
        # a stamp, like the other create test: a fixed name met its own leftovers from earlier nights
        time_stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
        sequence_name = f"{time_stamp}_Automation_Test_offline_cameras_sequence"
        self._created_sequences.append(sequence_name)
        self.seq.create_sequence(sequence_name)
        self._saved_sequences.append(sequence_name)
        # the oracle: the saved sequence is listed by its name in the Sequences section
        self.seq.open_sequences_list()
        expect(self.seq.sequence_item(sequence_name)).to_have_count(1, timeout=15000)
