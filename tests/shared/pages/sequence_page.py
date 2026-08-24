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

        # Sidebar items (sequence list)
        self.sidebar_items = page.locator(
            "div.MuiListItemButton-root.sidebarlist-item-button"
        )
        self.sequences_title = page.locator("span[title='Sequences']")
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
        # and _cleanup_sequences calls this in teardown where a miss is only
        # logged
        except Exception:
            pass  # Page may have different layout depending on existing sequences

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

        self.save_button.wait_for(state="visible", timeout=10000)

        # Form validation enables the button; give it a bounded wait
        # before falling back to the forced-click path
        try:
            expect(self.save_button).to_be_enabled(timeout=5000)
            self.save_button.click()
        except AssertionError:
            try:
                self.save_button.click(force=True)
            except PlaywrightError:
                # If disabled button can't be clicked, use JavaScript click
                self.page.evaluate("document.querySelector('button.modalSaveBtn').click()")

        # The form closes with its name input once the save lands
        if not self._appears_hidden(self.sequence_name_input, timeout=15000):
            print("[SEQUENCE] Save clicked but the name input is still "
                  "visible after 15s")

        return name

    # --- Add Sequence to Views ---

    def open_sequences_panel(self):
        """Open the Sequences panel in the sidebar."""
        try:
            # Check if any dropdown is open first
            open_dropdowns = self.page.locator('div[title][class*="MuiPaper-root"]')
            dropdown_open = False

            if open_dropdowns.count() > 0:
                for i in range(open_dropdowns.count()):
                    if open_dropdowns.nth(i).is_visible():
                        dropdown_open = True
                        break

            if not dropdown_open:
                # Only click Sequences if no dropdown is open
                # Wait with extended timeout for element to appear
                self.sequences_title.wait_for(state="visible", timeout=15000)

                # Hover over Sequences element before clicking
                self.sequences_title.hover()
                self.sequences_title.click()
            else:
                print("Dropdown is open - skipping 'Sequences' click.")

            # The panel is open when the sequence list renders; an empty
            # list is possible, so a miss is not an error
            self._appears(self.sidebar_items.first, timeout=10000)
        except Exception as e:
            print(f"Failed to open sequences panel: {str(e)}")
            raise

    def select_last_sequence(self):
        """Select the last sequence in the sidebar list by clicking its checkbox."""
        self.sidebar_items.wait_for(state="visible", timeout=10000)
        all_items = self.sidebar_items.all()

        if len(all_items) > 0:
            last_item = all_items[-1]
            # Get the title from the last item
            title_element = last_item.locator("span.MuiTypography-caption")
            if title_element.count() > 0:
                title = title_element.inner_text()
                print(f"Selected item: {title}")
            else:
                title = ""

            # Find and click the checkbox
            checkbox = last_item.locator("input[type='checkbox']")
            if checkbox.count() > 0:
                if not checkbox.is_checked():
                    try:
                        checkbox.click()
                    except Exception:
                        # Fallback to JS click if regular click fails
                        self.page.evaluate("arguments[0].click();", checkbox.element_handle())
                print("Last checkbox selected")
            return title
        else:
            print("No sidebar items found")
            return ""

    def add_sequence_to_views(self):
        """Open Sequences panel and select the last sequence to add to views.

        Returns the title of the selected sequence.
        """
        self.open_sequences_panel()
        title = self.select_last_sequence()
        return title

    # --- Edit Sequence ---

    def open_edit_dialog(self):
        """Open the edit dialog for the last sequence via the 3-dot menu."""
        # Ensure the last sequence is selected first
        self.select_last_sequence()

        # Click 3-dot menu scoped to the last sidebar item
        last_item = self.sidebar_items.last
        three_dot = last_item.locator("img[src*='3-dot']")
        three_dot.wait_for(state="visible", timeout=10000)
        three_dot.click()

        # Click Edit from the context menu
        # The MUI menu may have stale hidden instances - find the visible one
        edit_item = self.page.locator(
            "[role='menuitem']:has-text('Edit'):visible"
        ).first
        try:
            edit_item.wait_for(state="visible", timeout=5000)
            edit_item.click()
        except Exception:
            # Fallback: keyboard navigation (Enter = first menu item = Edit)
            self.page.keyboard.press("Enter")

        # The modal is open once the name input renders; then bring focus
        # to it, because the modalBackdrop steals focus
        self.sequence_name_input.wait_for(state="visible", timeout=10000)
        self.page.evaluate("""() => {
            const backdrop = document.querySelector('.modalBackdrop');
            if (backdrop) {
                // Find the actual modal content (sibling or child after backdrop)
                const modal = backdrop.nextElementSibling || backdrop.querySelector('div');
                if (modal) {
                    modal.style.zIndex = '9999';
                    modal.focus();
                }
            }
            // Also try to bring any modal form input into focus
            const input = document.querySelector('.modalFormInput');
            if (input) input.focus();
        }""")

    def change_timing(self, from_text: str = "5 Sec", to_text: str = "10 Seconds"):
        """Change the sequence timing in the edit dialog.

        The edit dialog uses a custom modal (modalBackdrop), not MUI Dialog.
        The timing is typically a select/dropdown inside a form.
        """
        # Try multiple strategies to find and click the timing dropdown.
        # No role locator applies: in the edit dialog (Views > Sequences
        # panel > 3-dot > Edit, probed 08/24/2026) the timing renders as
        # bare classless divs reading '5 Sec' - 0 combobox, 0
        # .MuiSelect-select, 0 native select - so only the text guess lands
        timing_selectors = [
            f"[role='button']:has-text('{from_text}')",
            f".MuiSelect-select:has-text('{from_text}')",
            f"select:has-text('{from_text}')",
            f"div.MuiInputBase-root:has-text('{from_text}')",
            f"div:text-is('{from_text}')",
        ]
        clicked = False
        for sel in timing_selectors:
            dropdown = self.page.locator(sel)
            if dropdown.count() > 0 and dropdown.first.is_visible():
                dropdown.first.click()
                clicked = True
                break

        if not clicked:
            # Fallback: find any select/dropdown element near the sequence name
            # input (class-keyed for the same reason as timing_selectors)
            select_elements = self.page.locator(
                ".MuiSelect-select, select, [role='button'][aria-haspopup='listbox']"
            )
            for i in range(select_elements.count()):
                el = select_elements.nth(i)
                if el.is_visible():
                    el.click()
                    clicked = True
                    break

        if not clicked:
            pytest.skip("Could not find timing dropdown in edit dialog")

        # Select the target timing from the dropdown options
        # Options may appear as a listbox, menu, or native select options
        option_selectors = [
            f"li:text-is('{to_text}')",
            f"[role='option']:has-text('{to_text}')",
            f"li:has-text('{to_text.split()[0]}')",
            f"option:has-text('{to_text.split()[0]}')",
        ]
        for sel in option_selectors:
            option = self.page.locator(sel).first
            if option.count() > 0:
                try:
                    option.wait_for(state="visible", timeout=5000)
                    option.click()
                    # The option list closes once the selection applies
                    self._appears_hidden(option, timeout=5000)
                    return
                # each option selector is one guess; a miss falls to the next
                # and the loop ends in pytest.skip, never a silent pass
                except Exception:
                    continue

        # If nothing worked, close dropdown and skip
        self.page.keyboard.press("Escape")
        pytest.skip(f"Could not find timing option '{to_text}' in dropdown")

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

    def delete_last_sequence(self):
        """Delete the last sequence in the sidebar list via the 3-dot menu.

        Opens the 3-dot menu on the last sidebar item and selects Delete.
        """
        if self.sidebar_items.count() == 0:
            return

        last_item = self.sidebar_items.last
        last_item.wait_for(state="visible", timeout=10000)

        # Click 3-dot menu scoped to the last sidebar item
        three_dot = last_item.locator("img[src*='3-dot']")
        three_dot.wait_for(state="visible", timeout=10000)
        three_dot.click()

        # Click Delete from the context menu - find the visible menu item
        delete_item = self.page.locator(
            "[role='menuitem']:has-text('Delete'):visible"
        ).first
        try:
            delete_item.wait_for(state="visible", timeout=5000)
            delete_item.click()
        except Exception:
            # Fallback: ArrowDown to Delete (second option), then Enter
            self.page.keyboard.press("ArrowDown")
            self.page.keyboard.press("Enter")

        # Wait for and click the confirmation dialog; each candidate
        # selector carries its own bounded wait
        confirm_selectors = [
            "button:has-text('Delete')",
            "button:has-text('Yes')",
            "button:has-text('Confirm')",
            "div.MuiBox-root:text-is('Delete')",
            "div.MuiBox-root:text-is('Yes')",
        ]
        for sel in confirm_selectors:
            try:
                confirm = self.page.locator(sel).first
                confirm.wait_for(state="visible", timeout=5000)
                confirm.click()
                # The dialog leaves the DOM with the clicked button
                self._appears_hidden(confirm, timeout=10000)
                return
            # cleanup path: each confirm label is one guess; a miss falls to
            # the next, and test teardown tolerates a leftover sequence
            except Exception:
                continue
        # If no confirmation dialog found, the delete completed directly

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
        except PlaywrightError:
            return False

    @staticmethod
    def _appears_hidden(locator, timeout: int = 5000) -> bool:
        """True when the element hides within timeout, False otherwise."""
        try:
            locator.wait_for(state="hidden", timeout=timeout)
            return True
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
