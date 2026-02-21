"""Camera Sequence Page Object Model.

Models the camera sequence page accessible via the sidebar sequence icon.
Supports creating, searching, selecting, editing, and adding sequences
to the views panel.
"""
import datetime
from playwright.sync_api import Page


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

        # Sidebar items (sequence list)
        self.sidebar_items = page.locator(
            "div.MuiListItemButton-root.sidebarlist-item-button"
        )
        self.sequences_title = page.locator("span[title='Sequences']")
        self.three_dot_menu = page.locator("img[src*='3-dot']")

    # --- Navigation ---

    def navigate(self):
        """Navigate to the Camera Sequence page via the sidebar icon."""
        self.sequence_icon.wait_for(state="visible", timeout=10000)
        self.sequence_icon.click()
        self.page.wait_for_timeout(2000)

    # --- Search ---

    def search_camera(self, camera_name: str):
        """Search for a camera by name on the sequence page."""
        self.search_input.wait_for(state="visible", timeout=10000)
        self.search_input.clear()
        self.search_input.fill(camera_name)
        self.page.wait_for_timeout(2000)

    # --- Camera Selection ---

    def select_all_cameras(self):
        """Click the Select All Cameras checkbox."""
        self.select_all_checkbox.wait_for(state="attached", timeout=10000)
        if not self.select_all_checkbox.is_checked():
            self.select_all_checkbox.click(force=True)
        self.page.wait_for_timeout(1000)

    def select_first_camera(self):
        """Select the first available camera checkbox."""
        if self.camera_checkboxes.count() > 0:
            self.camera_checkboxes.first.click(force=True)
            self.page.wait_for_timeout(1000)

    # --- Create Sequence ---

    def create_sequence(self, name: str = None) -> str:
        """Create a new camera sequence with the given name.

        Args:
            name: Sequence name. If None, generates a timestamped name.

        Returns:
            The sequence name used.
        """
        if name is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            name = f"{timestamp}_Automation_Test_create_sequence"

        self.sequence_name_input.wait_for(state="visible", timeout=10000)
        self.sequence_name_input.clear()
        self.sequence_name_input.fill(name)
        self.page.wait_for_timeout(1000)

        self.save_button.wait_for(state="visible", timeout=10000)
        self.save_button.click()
        self.page.wait_for_timeout(3000)

        return name

    # --- Add Sequence to Views ---

    def open_sequences_panel(self):
        """Open the Sequences panel in the sidebar."""
        self.sequences_title.wait_for(state="visible", timeout=10000)
        self.sequences_title.click()
        self.page.wait_for_timeout(2000)

    def select_last_sequence(self):
        """Select the last sequence in the sidebar list by clicking its checkbox."""
        self.sidebar_items.last.wait_for(state="visible", timeout=10000)

        # Get the title text of the last item
        title_element = self.sidebar_items.last.locator(
            "span.MuiTypography-caption"
        )
        title = title_element.inner_text() if title_element.count() > 0 else ""

        # Click the checkbox
        checkbox = self.sidebar_items.last.locator("input[type='checkbox']")
        if checkbox.count() > 0 and not checkbox.is_checked():
            try:
                checkbox.click()
            except Exception:
                checkbox.click(force=True)
        self.page.wait_for_timeout(1000)

        return title

    def add_sequence_to_views(self):
        """Open Sequences panel and select the last sequence to add to views.

        Returns the title of the selected sequence.
        """
        self.open_sequences_panel()
        return self.select_last_sequence()

    # --- Edit Sequence ---

    def open_edit_dialog(self):
        """Open the edit dialog for the last sequence via the 3-dot menu."""
        # Ensure the last sequence is selected first
        self.select_last_sequence()
        self.page.wait_for_timeout(1000)

        # Click 3-dot menu
        self.three_dot_menu.wait_for(state="visible", timeout=10000)
        self.three_dot_menu.click()
        self.page.wait_for_timeout(2000)

        # Press Enter to select Edit (first menu option)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(3000)

    def change_timing(self, from_text: str = "5 Sec", to_text: str = "10 Seconds"):
        """Change the sequence timing in the edit dialog."""
        timing_dropdown = self.page.locator(f"div:has-text('{from_text}')").first
        timing_dropdown.click()
        self.page.wait_for_timeout(1000)

        option = self.page.locator(f"li:text-is('{to_text}')")
        option.wait_for(state="visible", timeout=10000)
        option.click()
        self.page.wait_for_timeout(1000)

    def update_sequence_name(self, new_name: str):
        """Update the sequence name in the edit modal."""
        self.sequence_name_input.wait_for(state="visible", timeout=10000)
        self.sequence_name_input.clear()
        self.sequence_name_input.fill(new_name)
        self.page.wait_for_timeout(1000)

    def click_update(self):
        """Click the Update button in the edit modal."""
        self.update_button.wait_for(state="visible", timeout=10000)
        self.update_button.click()
        self.page.wait_for_timeout(3000)

    # --- Advanced Options ---

    def toggle_play_offline_cameras(self):
        """Toggle the 'Play Offline Cameras' checkbox."""
        self.play_offline_checkbox.wait_for(state="attached", timeout=10000)
        self.play_offline_checkbox.click(force=True)
        self.page.wait_for_timeout(1000)

    def toggle_play_reverse_order(self):
        """Toggle the 'Play Reverse Order' checkbox."""
        self.play_reverse_checkbox.wait_for(state="attached", timeout=10000)
        self.play_reverse_checkbox.click(force=True)
        self.page.wait_for_timeout(1000)
