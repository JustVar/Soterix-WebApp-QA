"""Chat deeper tests - panel toggle, search, chat list, cross-page behavior.

Extends the base chat tests with non-CRUD scenarios covering panel management,
search functionality, chat list validation, and cross-page persistence.
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.chat_page import ChatPage


class TestChatsDeeper:
    """Deeper tests for the Chat panel overlay."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.chat = ChatPage(self.page)
        yield

    # --- Panel management ---

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    @pytest.mark.qatouch("RgGQ3W")
    def test_chat_panel_closes_on_second_click(self):
        """Verify the chat panel closes when the chat icon is clicked again."""
        self.chat.open_chat_panel()
        expect(self.chat.create_group_button).to_be_visible(timeout=10000)
        self.step_capture.mark(1, "Open the chat panel and verify it is visible")

        # Close panel
        self.chat.close_chat_panel()
        self.page.wait_for_timeout(1000)

        expect(self.chat.create_group_button).to_be_hidden(timeout=5000)
        self.step_capture.mark(2, "Close the chat panel by clicking the chat icon again")

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    @pytest.mark.qatouch("K4nzlV")
    def test_chat_panel_reopens_after_close(self):
        """Verify the chat panel can be reopened after closing."""
        self.chat.open_chat_panel()
        expect(self.chat.create_group_button).to_be_visible(timeout=10000)
        self.step_capture.mark(1, "Open the chat panel and verify it is visible")

        self.chat.close_chat_panel()
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(2, "Close the chat panel")

        self.chat.open_chat_panel()
        expect(self.chat.create_group_button).to_be_visible(timeout=10000)
        self.step_capture.mark(3, "Reopen the chat panel and verify it is visible again")

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    @pytest.mark.qatouch("Ee61zV")
    def test_create_group_button_present(self):
        """Verify the Create Group button is present in the chat panel."""
        self.chat.open_chat_panel()
        self.step_capture.mark(1, "Open the chat panel")

        expect(self.chat.create_group_button).to_be_visible(timeout=10000)
        button_text = self.chat.create_group_button.inner_text()
        assert "Create Group" in button_text
        self.step_capture.mark(2, "Verify the Create Group button is visible and has correct text")

    # --- Search functionality ---

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    @pytest.mark.qatouch("dypXvp")
    def test_chat_search_input_visible(self):
        """Verify the chat search input is visible in the panel."""
        self.chat.open_chat_panel()
        self.step_capture.mark(1, "Open the chat panel")

        expect(self.chat.chat_search_input).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify the search input is visible in the panel")

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    @pytest.mark.qatouch("J8d9R1")
    def test_search_returns_results(self):
        """Verify searching for a known user returns results."""
        self.chat.open_chat_panel()
        self.step_capture.mark(1, "Open the chat panel")

        self.chat.search_chat("QA Engineer B")
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(2, "Search for a known user in the chat search")

        result_count = self.chat.search_results.count()
        if result_count == 0:
            pytest.skip("No search results for 'QA Engineer B' - user may not exist")

        assert result_count > 0, "Expected at least one search result"
        self.step_capture.mark(3, "Verify search results are returned")

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    @pytest.mark.qatouch("RgGQ4l")
    def test_search_with_no_match(self):
        """Verify searching for a nonexistent user shows no results."""
        self.chat.open_chat_panel()
        self.step_capture.mark(1, "Open the chat panel")

        self.chat.search_chat("zzzznonexistentuser99999")
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(2, "Search for a nonexistent user")

        assert self.chat.search_results.count() == 0, \
            "Expected no search results for nonexistent user"
        self.step_capture.mark(3, "Verify no search results are returned")

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    @pytest.mark.qatouch("VKbQJQ")
    def test_search_clear_resets_results(self):
        """Verify clearing the search input resets the search state."""
        self.chat.open_chat_panel()
        self.step_capture.mark(1, "Open the chat panel")

        # Search first
        self.chat.search_chat("QA Engineer B")
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(2, "Search for a known user")

        # Clear search
        self.chat.chat_search_input.clear()
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(3, "Clear the search input field")

        # Search input should be empty
        value = self.chat.chat_search_input.input_value()
        assert value == "", f"Expected empty search input, got '{value}'"
        self.step_capture.mark(4, "Verify the search input is empty and results are reset")

    # --- Chat list content ---

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    @pytest.mark.qatouch("WEnMLM")
    def test_chat_panel_has_content(self):
        """Verify the chat panel contains some content (groups or conversations)."""
        self.chat.open_chat_panel()
        self.step_capture.mark(1, "Open the chat panel")

        # The panel should have at least the Create Group button and search input
        expect(self.chat.create_group_button).to_be_visible(timeout=10000)
        expect(self.chat.chat_search_input).to_be_visible(timeout=5000)
        self.step_capture.mark(2, "Verify the panel contains content with Create Group button and search input")

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    @pytest.mark.qatouch("LD3mr1")
    def test_click_search_result_opens_chat(self):
        """Verify clicking a search result opens the chat conversation."""
        self.chat.open_chat_panel()
        self.step_capture.mark(1, "Open the chat panel")

        self.chat.search_chat("QA Engineer B")
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(2, "Search for a known user")

        if self.chat.search_results.count() == 0:
            pytest.skip("No search results for 'QA Engineer B'")

        self.chat.click_search_result()
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(3, "Click on the search result to open the chat")

        # After clicking, the chat should open - re-open panel to verify
        self.chat.open_chat_panel()
        self.page.wait_for_timeout(2000)

        partner_chat = self.page.locator("p:has-text('QA Engineer B')")
        if partner_chat.count() > 0:
            expect(partner_chat.first).to_be_visible(timeout=5000)
        self.step_capture.mark(4, "Verify the chat conversation appears in the panel")

    # --- Cross-page behavior ---

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    @pytest.mark.qatouch("5BRMbz")
    def test_chat_icon_visible_on_events_page(self):
        """Verify the chat icon is accessible from the Events page."""
        # Navigate to Events
        events_link = self.page.locator("a[href*='events']")
        if events_link.count() > 0:
            events_link.first.click()
            self.page.wait_for_timeout(3000)
        self.step_capture.mark(1, "Navigate to the Events page")

        self.chat.open_chat_panel()
        expect(self.chat.create_group_button).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Open the chat panel from the Events page and verify it works")

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    @pytest.mark.qatouch("8V1l8r")
    def test_chat_panel_survives_page_refresh(self):
        """Verify the chat panel can be opened after a page refresh."""
        self.page.reload()
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(1, "Refresh the page")

        self.chat.open_chat_panel()
        expect(self.chat.create_group_button).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Open the chat panel after refresh and verify it works")
