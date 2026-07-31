"""Chat Page Object Model.

Models the Chat panel accessed via the header bar icon, including
group creation, search, messaging, editing, and deletion.
"""
import re

from playwright.sync_api import Page, expect


class ChatPage:
    """Page object for the Chat panel overlay."""

    def __init__(self, page: Page):
        self.page = page

        # Header bar chat access
        self.header_icons = page.locator(".header-right-group .icon")

        # Create Group
        self.create_group_button = page.locator(
            "button.add-btn.save-btn:has-text('Create Group')"
        )
        self.group_name_input = page.locator(
            "input[placeholder='Enter Group Name']"
        )
        self.autocomplete_options = page.locator(
            "ul.MuiAutocomplete-listbox li"
        )

        # Chat search
        self.chat_search_input = page.locator(
            "input.chat-search-input[placeholder='Search']"
        )
        self.search_results = page.locator(".related-result-item")

        # Group actions
        self.edit_icon = page.locator("img[alt='Edit icon']")
        self.delete_icon = page.locator("img[alt='Delete icon']")
        self.update_button = page.locator("button:has-text('Update')")
        self.delete_confirm = page.locator(
            "div.MuiBox-root"
        ).filter(has_text=re.compile(r"^Delete$"))

    # --- Panel management ---

    def open_chat_panel(self):
        """Open the chat panel by clicking the chat icon.

        Uses double-click pattern observed in Selenium tests:
        first click may wake/toggle, second ensures panel is open.
        If Create Group button is visible after first click, panel is open.
        """
        self.header_icons.first.wait_for(state="visible", timeout=10000)
        self.header_icons.first.click()
        self.page.wait_for_timeout(2000)

        # Check if panel opened; if not, click again
        if self.create_group_button.count() == 0:
            self.header_icons.first.click()
            self.page.wait_for_timeout(2000)

    def close_chat_panel(self):
        """Close the chat panel by clicking the chat icon."""
        self.header_icons.first.click()
        self.page.wait_for_timeout(1000)

    # --- Group CRUD ---

    def create_group(self, group_name: str, member_search: str):
        """Create a new chat group with a member.

        Args:
            group_name: Name for the new group
            member_search: Partial text to search for a member to add
        """
        self.create_group_button.wait_for(state="visible", timeout=10000)
        self.create_group_button.click()
        self.page.wait_for_timeout(2000)

        # Fill group name
        self.group_name_input.wait_for(state="visible", timeout=10000)
        self.group_name_input.fill(group_name)
        self.page.wait_for_timeout(500)

        # TAB to member field and search
        self.page.keyboard.press("Tab")
        self.page.wait_for_timeout(1000)
        self.page.keyboard.type(member_search, delay=100)
        self.page.wait_for_timeout(3000)

        # Select first autocomplete option
        if self.autocomplete_options.count() > 0:
            self.autocomplete_options.first.click()
            self.page.wait_for_timeout(1000)
            self.page.keyboard.press("Escape")
        else:
            self.page.keyboard.press("Escape")

        # TAB to Create button and press Enter
        self.page.keyboard.press("Tab")
        self.page.wait_for_timeout(500)
        self.page.keyboard.press("Tab")
        self.page.wait_for_timeout(500)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(3000)

    def open_group(self, group_name: str):
        """Find and click on a group by name in the chat list."""
        group = self.page.locator(f"p:has-text('{group_name}')")
        group.wait_for(state="visible", timeout=10000)
        group.click()
        self.page.wait_for_timeout(3000)

    def send_message(self, text: str):
        """Send a message in the currently open chat.

        Uses TAB to reach the message input from the current focus.
        """
        self.page.keyboard.press("Tab")
        self.page.wait_for_timeout(1000)
        self.page.keyboard.type(text, delay=50)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(2000)

    def edit_group_name(self, old_name: str, new_name: str):
        """Edit a group's name.

        Args:
            old_name: Current group name to find
            new_name: New name to set
        """
        self.edit_icon.wait_for(state="visible", timeout=10000)
        self.edit_icon.click()
        self.update_button.wait_for(state="visible", timeout=10000)
        self.page.wait_for_timeout(2000)

        # Locate the group name input by its value attribute (same as original Selenium test)
        # Locate by value attribute (as in original Selenium test)
        # fill() clears and replaces atomically - no need for two-step clear+fill
        input_field = self.page.locator(f"//input[@value='{old_name}']")
        input_field.wait_for(state="visible", timeout=5000)
        input_field.fill(new_name)
        self.page.wait_for_timeout(1000)

        # Exact text match for Update button
        update_btn = self.page.locator("//button[text()='Update']")
        update_btn.wait_for(state="visible", timeout=5000)
        update_btn.click()
        self.page.wait_for_timeout(5000)

    def delete_group(self):
        """Delete the currently open group."""
        self.delete_icon.wait_for(state="visible", timeout=10000)
        self.delete_icon.click()
        self.page.wait_for_timeout(3000)

        self.delete_confirm.wait_for(state="visible", timeout=5000)
        self.delete_confirm.click()
        self.page.wait_for_timeout(3000)

    # --- Search ---

    def search_chat(self, search_text: str):
        """Search for a user or group in the chat search."""
        self.chat_search_input.wait_for(state="visible", timeout=10000)
        self.chat_search_input.clear()
        self.chat_search_input.fill(search_text)
        self.page.wait_for_timeout(2000)

    def click_search_result(self, index: int = -1):
        """Click a search result by index. Default is the last result."""
        result_count = self.search_results.count()
        if result_count == 0:
            return False

        if index == -1:
            self.search_results.last.click()
        else:
            self.search_results.nth(index).click()

        # Handle "User is already added" dialog if it appears
        self.page.wait_for_timeout(1000)
        try:
            dialog = self.page.locator("text=User is already added")
            if dialog.is_visible():
                self.page.locator("button:has-text('OK')").click()
                self.page.wait_for_timeout(500)
        except Exception:
            pass

        return True
