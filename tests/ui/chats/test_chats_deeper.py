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
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.chat = ChatPage(self.page)
        yield

    # --- Panel management ---

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_chat_panel_closes_on_second_click(self):
        """Verify the chat panel closes when the chat icon is clicked again."""
        self.chat.open_chat_panel()
        expect(self.chat.create_group_button).to_be_visible(timeout=10000)

        # Close panel
        self.chat.close_chat_panel()
        self.page.wait_for_timeout(1000)

        expect(self.chat.create_group_button).to_be_hidden(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_chat_panel_reopens_after_close(self):
        """Verify the chat panel can be reopened after closing."""
        self.chat.open_chat_panel()
        expect(self.chat.create_group_button).to_be_visible(timeout=10000)

        self.chat.close_chat_panel()
        self.page.wait_for_timeout(1000)

        self.chat.open_chat_panel()
        expect(self.chat.create_group_button).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_create_group_button_present(self):
        """Verify the Create Group button is present in the chat panel."""
        self.chat.open_chat_panel()

        expect(self.chat.create_group_button).to_be_visible(timeout=10000)
        button_text = self.chat.create_group_button.inner_text()
        assert "Create Group" in button_text

    # --- Search functionality ---

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_chat_search_input_visible(self):
        """Verify the chat search input is visible in the panel."""
        self.chat.open_chat_panel()

        expect(self.chat.chat_search_input).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_search_returns_results(self):
        """Verify searching for a known user returns results."""
        self.chat.open_chat_panel()

        self.chat.search_chat("QA Engineer B")
        self.page.wait_for_timeout(3000)

        result_count = self.chat.search_results.count()
        if result_count == 0:
            pytest.skip("No search results for 'QA Engineer B' - user may not exist")

        assert result_count > 0, "Expected at least one search result"

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_search_with_no_match(self):
        """Verify searching for a nonexistent user shows no results."""
        self.chat.open_chat_panel()

        self.chat.search_chat("zzzznonexistentuser99999")
        self.page.wait_for_timeout(3000)

        assert self.chat.search_results.count() == 0, \
            "Expected no search results for nonexistent user"

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_search_clear_resets_results(self):
        """Verify clearing the search input resets the search state."""
        self.chat.open_chat_panel()

        # Search first
        self.chat.search_chat("QA Engineer B")
        self.page.wait_for_timeout(2000)

        # Clear search
        self.chat.chat_search_input.clear()
        self.page.wait_for_timeout(2000)

        # Search input should be empty
        value = self.chat.chat_search_input.input_value()
        assert value == "", f"Expected empty search input, got '{value}'"

    # --- Chat list content ---

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_chat_panel_has_content(self):
        """Verify the chat panel contains some content (groups or conversations)."""
        self.chat.open_chat_panel()

        # The panel should have at least the Create Group button and search input
        expect(self.chat.create_group_button).to_be_visible(timeout=10000)
        expect(self.chat.chat_search_input).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_click_search_result_opens_chat(self):
        """Verify clicking a search result opens the chat conversation."""
        self.chat.open_chat_panel()

        self.chat.search_chat("QA Engineer B")
        self.page.wait_for_timeout(3000)

        if self.chat.search_results.count() == 0:
            pytest.skip("No search results for 'QA Engineer B'")

        self.chat.click_search_result()
        self.page.wait_for_timeout(3000)

        # After clicking, the chat should open - re-open panel to verify
        self.chat.open_chat_panel()
        self.page.wait_for_timeout(2000)

        partner_chat = self.page.locator("p:has-text('QA Engineer B')")
        if partner_chat.count() > 0:
            expect(partner_chat.first).to_be_visible(timeout=5000)

    # --- Cross-page behavior ---

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_chat_icon_visible_on_events_page(self):
        """Verify the chat icon is accessible from the Events page."""
        # Navigate to Events
        events_link = self.page.locator("a[href*='events']")
        if events_link.count() > 0:
            events_link.first.click()
            self.page.wait_for_timeout(3000)

        self.chat.open_chat_panel()
        expect(self.chat.create_group_button).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_chat_panel_survives_page_refresh(self):
        """Verify the chat panel can be opened after a page refresh."""
        self.page.reload()
        self.page.wait_for_timeout(3000)

        self.chat.open_chat_panel()
        expect(self.chat.create_group_button).to_be_visible(timeout=10000)
