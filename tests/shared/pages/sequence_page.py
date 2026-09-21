"""Camera Sequence Page Object Model.

Models the camera sequence page accessible via the sidebar sequence icon.
Supports creating, searching, selecting, editing, and adding sequences
to the views panel.
"""
import datetime
import time

import pytest
from playwright.sync_api import Error as PlaywrightError, Page, expect


class SequencePage:
    """Page object for Camera Sequence functionality."""

    def __init__(self, page: Page):
        self.page = page

        # Navigation
        self.sequence_icon = page.locator(
            "img[alt='SequenceIcon'][width='24'][height='24']"
        )

        # Search
        self.search_input = page.locator("input[placeholder='Search']").first

        # Camera selection
        self.select_all_checkbox = page.locator("input[name='selectAllCameras']")
        self.camera_checkboxes = page.locator(
            "input[type='checkbox'].PrivateSwitchBase-input"
        )

        # Create/Edit modal
        self.sequence_name_input = page.locator("input.modalFormInput")
        self.save_button = page.locator(
            "button.modalSaveBtn:has-text('Save')"
        )
        self.update_button = page.locator("button:has-text('Update')")

        # Timing dropdown
        self.timing_dropdown_5s = page.locator("div:has-text('5 Sec')").first
        self.timing_option_10s = page.locator("li:text-is('10 Seconds')")

        # Advanced options
        self.play_offline_checkbox = page.locator(
            "input[name='playOfflineCameras']"
        )
        self.play_reverse_checkbox = page.locator(
            "input[name='playReverseOrder']"
        )

        # Rows of the Views sidebar. They are the SITES until the Sequences section is open
        # (measured 09/21/2026 on india: 17 rows before, 64 with the section open). A saved
        # sequence is a row with span[title="<its name>"], and its 3-dot menu has Edit and
        # Delete. Until that day this locator was read as "the sequence list", so the cleanup
        # never found a sequence and 55 of them piled up on india from 08/08.
        self.sidebar_items = page.locator(
            "div.MuiListItemButton-root.sidebarlist-item-button"
        )
        self.sequences_title = page.locator("span[title='Sequences']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.three_dot_menu = page.locator("img[src*='3-dot']")

    # --- Navigation ---

    def navigate(self):
        """Navigate to the Camera Sequence page via the sidebar icon.

        The secondaryHeader div can overlay the icon - dismiss it first,
        then fall back to force-click or JS click if still intercepted.
        """
        self.sequence_icon.wait_for(state="visible", timeout=10000)
        # Dismiss the secondaryHeader overlay if present
        try:
            header = self.page.locator("div.secondaryHeader")
            if header.count() > 0 and header.first.is_visible():
                # Try clicking outside or pressing Escape to dismiss
                self.page.keyboard.press("Escape")
                self._appears_hidden(header.first, timeout=2000)
        # the secondaryheader overlay is optional; the icon click below falls
        # back to a js click when it still intercepts
        except Exception:
            pass
        try:
            self.sequence_icon.click(timeout=5000)
        # the secondaryHeader overlay can intercept the pointer click. The JS
        # click below raises if the icon is gone, and the tests expect the
        # sequence page markers after navigate returns
        except Exception:
            # secondaryHeader still intercepting - use JS click to bypass
            self.sequence_icon.evaluate("el => el.click()")

        # Wait for sequence page to fully load - look for sequence-specific elements
        try:
            self.page.locator(
                "input[name='selectAllCameras'], input.modalFormInput, input[placeholder='Search']"
            ).first.wait_for(state="visible", timeout=10000)
        # arrival is the callers' oracle: _navigate_and_verify
        # (test_camera_sequences.py) expects this same marker union,
        # select_first_camera's retry waits on the camera list after this,
        # and _cleanup_sequences calls this in teardown, where delete_sequence then
        # waits for the sidebar item and reports a miss
        except Exception:
            pass

    # --- Search ---

    def search_camera(self, camera_name: str):
        """Search for a camera by name on the sequence page."""
        self.search_input.wait_for(state="visible", timeout=20000)
        self.search_input.clear()
        self.search_input.fill(camera_name)
        self._camera_list_settled()

    # --- Camera Selection ---

    def select_all_cameras(self):
        """Click the Select All Cameras checkbox."""
        self.select_all_checkbox.wait_for(state="attached", timeout=10000)
        if not self.select_all_checkbox.is_checked():
            # MUI checkbox is a hidden input - use JS click
            self.select_all_checkbox.evaluate("el => el.click()")
            self._expect_checked(self.select_all_checkbox, True)

    def select_first_camera(self):
        """Select the first available camera checkbox (excluding Select All)."""
        # Wait for checkboxes to be present - retry navigate if not found
        try:
            self.camera_checkboxes.first.wait_for(state="attached", timeout=15000)
        # no checkbox means the JS click navigation did not land. The handler
        # navigates one more time, and its own checkbox wait raises if the
        # list is still absent
        except Exception:
            # JS click navigation may not have landed - retry navigation
            self.navigate()
            self.camera_checkboxes.first.wait_for(state="attached", timeout=15000)

        # The selectAll checkbox renders before the camera list arrives
        # from its async fetch: wait until individual cameras exist too
        deadline = time.monotonic() + 10.0
        while (time.monotonic() < deadline
               and self.camera_checkboxes.count() <= 1):
            self.page.wait_for_timeout(250)  # poll tick for camera fetch

        # Skip the selectAllCameras checkbox - find first individual camera checkbox
        for i in range(self.camera_checkboxes.count()):
            cb = self.camera_checkboxes.nth(i)
            name = cb.get_attribute("name") or ""
            if name != "selectAllCameras":
                # MUI checkboxes are hidden inputs - use JS click
                cb.evaluate("el => el.click()")
                self._expect_checked(cb, True)
                return

        # Fallback: JS click second checkbox (first is usually selectAll)
        if self.camera_checkboxes.count() > 1:
            cb = self.camera_checkboxes.nth(1)
            cb.evaluate("el => el.click()")
            self._expect_checked(cb, True)

    # --- Create Sequence ---

    def create_sequence(self, name: str | None = None) -> str:
        """Create a new camera sequence with the given name.

        Args:
            name: Sequence name. If None, generates a timestamped name.

        Returns:
            The sequence name used.
        """
        if name is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
            name = f"{timestamp}_Automation_Test_create_sequence"

        self.sequence_name_input.wait_for(state="visible", timeout=10000)
        self.sequence_name_input.clear()
        self.sequence_name_input.fill(name)

        self.save_button.wait_for(state="visible", timeout=10000)

        # Form validation enables the button; give it a bounded wait
        # before falling back to the forced-click path
        try:
            expect(self.save_button).to_be_enabled(timeout=5000)
            self.save_button.click(timeout=10000)
        # Save did not become enabled in 5 s. A forced click is one more try. The
        # form-closed check below raises when the save did not land.
        except AssertionError:
            try:
                self.save_button.click(force=True, timeout=10000)
            # The forced click raised. A JavaScript click is the last try, and the
            # form-closed check below raises when it did nothing.
            except PlaywrightError:
                self.page.evaluate("document.querySelector('button.modalSaveBtn').click()")

        # The form closes with its name input once the save lands. Until 09/21/2026 a
        # form that stayed open only printed a line: a forced click on a disabled Save
        # raises nothing, and the 2 tests that end here passed with nothing saved.
        if not self._appears_hidden(self.sequence_name_input, timeout=15000):
            raise AssertionError(
                f"Save was clicked but the sequence form stayed open for 15 s: "
                f"the sequence '{name}' was not saved")

        return name

    def update_sequence_name(self, new_name: str):
        """Update the sequence name in the edit modal."""
        self.sequence_name_input.wait_for(state="visible", timeout=10000)
        # Triple-click to select all text, then type new name
        # (MUI React inputs don't always respond to .clear())
        self.sequence_name_input.click(click_count=3)
        self.sequence_name_input.fill(new_name)
        # Verify the value was set
        actual = self.sequence_name_input.input_value()
        if actual != new_name:
            # Fallback: select all via keyboard and retype
            self.sequence_name_input.click()
            self.page.keyboard.press("Control+a")
            self.page.keyboard.type(new_name)

    def click_update(self):
        """Click the Update button in the edit modal."""
        self.update_button.wait_for(state="visible", timeout=10000)
        self.update_button.click()
        # The modal closes with its Update button once the save lands
        if not self._appears_hidden(self.update_button, timeout=15000):
            print("[SEQUENCE] Update clicked but the button is still "
                  "visible after 15s")

    # --- Delete Sequence ---

    def open_sequences_list(self):
        """Show the saved sequences: the Sequences section of the Views sidebar.

        The section is a toggle with no state attribute. The row count says which way the
        click went: opening adds rows, and a click that removed rows closed an open section,
        so it is clicked one more time.
        """
        # the create form is a modal over Views, and its backdrop stops each click below it
        if self.sequence_name_input.is_visible():
            self.page.keyboard.press("Escape")
            self.sequence_name_input.wait_for(state="hidden", timeout=10000)
        self.sequences_title.first.wait_for(state="visible", timeout=20000)
        before = self.sidebar_items.count()
        self.sequences_title.first.click(timeout=10000)
        self.page.wait_for_timeout(1500)  # the section renders its rows with no other signal
        if self.sidebar_items.count() < before:
            self.sequences_title.first.click(timeout=10000)
            self.page.wait_for_timeout(1500)  # the same render, for the second click

    def sequence_item(self, name: str):
        """The row of the saved sequence with exactly this name (open_sequences_list first)."""
        return self.sidebar_items.filter(has=self.page.get_by_title(name, exact=True))

    def delete_sequence(self, name: str) -> bool:
        """Delete 1 sequence with exactly this name. False when no such sequence is listed.

        By name, never by position. The cleanup used a method that removed whatever was last
        in the sidebar: a sequence of a different person on the shared tenant when this test's
        own create had failed (found 09/21/2026). The proof is the count of items with this
        name: it must go down by 1. Waiting for "the first item" to hide cannot tell a delete
        from a second item with the same name taking its place.
        """
        self.open_sequences_list()
        item = self.sequence_item(name)
        # The list hydrates a beat after the page settles: wait before the name reads as absent
        try:
            item.first.wait_for(state="visible", timeout=10000)
        # absent after 10 s means no item of this name is listed, and the caller decides what that means
        except PlaywrightError:
            return False
        before = item.count()
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        item.first.locator("img[src*='3-dot']").click(timeout=10000)
        self.page.locator("[role='menuitem']:has-text('Delete'):visible").first.click(timeout=10000)
        confirm = self.page.get_by_role("button", name="Delete", exact=True)
        # some builds delete with no dialog, so the confirm is optional. The count below is the proof.
        if self._appears(confirm.first, timeout=5000):
            confirm.first.click(timeout=10000)
        expect(item).to_have_count(before - 1, timeout=15000)
        return True

    # --- Advanced Options ---

    def toggle_play_offline_cameras(self):
        """Toggle the 'Play Offline Cameras' checkbox."""
        self.play_offline_checkbox.wait_for(state="attached", timeout=10000)
        before = self.play_offline_checkbox.is_checked()
        self.play_offline_checkbox.click(force=True)
        self._expect_checked(self.play_offline_checkbox, not before)

    def toggle_play_reverse_order(self):
        """Toggle the 'Play Reverse Order' checkbox."""
        self.play_reverse_checkbox.wait_for(state="attached", timeout=10000)
        before = self.play_reverse_checkbox.is_checked()
        self.play_reverse_checkbox.click(force=True)
        self._expect_checked(self.play_reverse_checkbox, not before)

    # --- Wait helpers ---

    @staticmethod
    def _appears(locator, timeout: int = 5000) -> bool:
        """True when the element shows within timeout, False otherwise."""
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        # probe: a timeout is the False answer, not a fault. The caller
        # decides what False means
        except PlaywrightError:
            return False

    @staticmethod
    def _appears_hidden(locator, timeout: int = 5000) -> bool:
        """True when the element hides within timeout, False otherwise."""
        try:
            locator.wait_for(state="hidden", timeout=timeout)
            return True
        # probe: a timeout is the False answer, not a fault. navigate uses it as
        # an optional settle wait.
        # create_sequence raises on a False, and click_update logs it
        except PlaywrightError:
            return False

    @staticmethod
    def _expect_checked(checkbox, checked: bool):
        """Wait for a checkbox input to reach the wanted state."""
        try:
            if checked:
                expect(checkbox).to_be_checked(timeout=5000)
            else:
                expect(checkbox).not_to_be_checked(timeout=5000)
        # a checkbox that did not change is logged, not raised. The tests
        # expect the checked state themselves after select_all_cameras and
        # after each advanced-option toggle
        except AssertionError:
            print(f"[SEQUENCE] Checkbox did not become "
                  f"{'checked' if checked else 'unchecked'} within 5s")

    def _camera_list_settled(self, timeout_s: float = 5.0):
        """Wait for the camera list count to hold for a full second.

        A query that matches the same set never changes the count, so
        stability is the signal, not change: the first return is after
        one second of equal reads, which also gives the refetch a
        lead-in instead of settling on a transient state.
        """
        deadline = time.monotonic() + timeout_s
        last = -1
        stable = 0
        while time.monotonic() < deadline:
            current = self.camera_checkboxes.count()
            stable = stable + 1 if current == last else 0
            if stable >= 4:
                return
            last = current
            self.page.wait_for_timeout(250)  # poll tick for filter settle
