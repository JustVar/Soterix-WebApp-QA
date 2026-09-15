"""Chat deeper tests - panel toggle, search, conversation flow,
cross-page behavior.

Rebuilt 08/13/2026 against the redesigned search-first panel (see the
chats row in docs/TEST_REPAIRS.md). The open marker is the visible
panel search input; the old Create Group marker is gone.
"""
import re

import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.chat_page import ChatPage

CHAT_USER_SEARCH = config.get("test_chat_user_search", "QA Engineer B")
CHAT_USER_NAME = config.get("test_chat_user_name", "Chat Partner")

GROUPS_ABSENT = (
    "The chat panel is open and shows no Create Group control: group "
    "creation has no entry point on this box (india, probed 09/04/2026 - "
    "the US box has it, register item 29)"
)


class TestChatsDeeper:
    """Deeper tests for the redesigned Chat panel overlay."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.chat = ChatPage(self.page)
        return

    def _search_partner_or_fail(self):
        """Search the configured chat user; missing data is a failure
        pointing at config, not a silent skip."""
        found = self.chat.search_chat(CHAT_USER_SEARCH)
        assert found > 0, (
            f"No chat user matches '{CHAT_USER_SEARCH}' - if the "
            "tenant user changed, update test_chat_user_search in "
            "config/env"
        )

    # --- Panel management ---

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_chat_panel_closes_on_second_click(self):
        """The header's chat icon opens the panel on one click and closes it on the next.

        Steps:
        1. Click the chat icon in the header.
           Expected: The chat panel opens with its search field.
        2. Click the chat icon again.
           Expected: The panel closes and the search field is gone.
        """
        self.chat.open_chat_panel()
        expect(self.chat.search_input).to_be_visible()

        self.chat.toggle_chat_icon()
        expect(self.chat.search_input).to_be_hidden(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_chat_panel_reopens_after_close(self):
        """The panel reopens after closing via the header X.

        Steps:
        1. Open the chat panel, close it with the header X, then open it again.
           Expected: The panel is back with its empty Search field.
        """
        self.chat.open_chat_panel()
        self.chat.close_chat_panel()
        expect(self.chat.search_input).to_be_hidden(timeout=5000)
        self.chat.open_chat_panel()
        expect(self.chat.search_input).to_have_value("")
        expect(self.chat.search_input).to_have_attribute("placeholder", "Search")

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_create_group_button_present(self):
        """The Create Group button is in the open panel on a box that has it.

        Group creation is a box difference (register item 29): the US
        box shows the button, india shows nothing. The open panel is
        proved first, so the skip on india is the tenant's data and
        not a panel that failed to open.

        Steps:
        1. Open the chat panel.
           Expected: On a box with group chat, one enabled Create Group button is shown.
        """
        self.chat.open_chat_panel()
        if not self.chat.group_creation_affordance():
            pytest.skip(GROUPS_ABSENT)
        expect(self.chat.group_create_button).to_have_count(1)
        expect(self.chat.group_create_button).to_have_text("Create Group")
        expect(self.chat.group_create_button).to_be_enabled()

    # --- Search functionality ---

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_chat_search_input_visible(self):
        """The panel search input is ready once the panel opens.

        Steps:
        1. Open the chat panel.
           Expected: The Search field is shown, empty, and takes typing.
        """
        self.chat.open_chat_panel()
        expect(self.chat.search_input).to_have_value("")
        expect(self.chat.search_input).to_have_attribute("placeholder", "Search")
        expect(self.chat.search_input).to_be_editable()

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_search_returns_results(self):
        """Searching the configured user returns a visible result."""
        self.chat.open_chat_panel()
        self._search_partner_or_fail()
        expect(self.chat.search_results.first).to_contain_text(
            CHAT_USER_NAME.split()[0]
        )

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_search_with_no_match(self):
        """A chat search for a name nobody has lists no results.

        Steps:
        1. Click the chat icon in the header and search for the configured chat user.
           Expected: The user is listed, which proves the search works.
        2. Search for zzzznonexistentuser99999.
           Expected: The result list is empty.
        """
        self.chat.open_chat_panel()
        self._search_partner_or_fail()

        found = self.chat.search_chat("zzzznonexistentuser99999",
                                      timeout=4000)
        assert found == 0, (
            f"Expected no results for a nonsense term, got {found}"
        )

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_search_clear_resets_results(self):
        """Verify clearing the chat search empties the results and the field.

        Steps:
        1. Click the chat icon in the header and search for the configured chat user.
           Expected: The user is listed.
        2. Clear the search.
           Expected: No results are listed and the search field is empty.
        """
        self.chat.open_chat_panel()
        self._search_partner_or_fail()

        self.chat.clear_search()
        expect(self.chat.search_results).to_have_count(0, timeout=5000)
        expect(self.chat.search_input).to_have_value("")

    # --- Conversation flow ---

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_chat_panel_has_content(self):
        """An open panel shows the search input plus either the
        empty-state instruction or the recent-conversations list.

        Steps:
        1. Click the chat icon in the header.
           Expected: The panel opens with its search field and shows either the 'use the search bar' instruction or the recent conversations list, each row naming a conversation.
        """
        self.chat.open_chat_panel()
        expect(self.chat.search_input).to_be_visible()
        if self.chat.recent_rows.count():
            names = [" ".join(t.split()) for t in self.chat.recent_rows.all_inner_texts()]
            assert all(names), f"a recent conversation row is blank: {names}"
        else:
            expect(self.chat.empty_state.first).to_contain_text("search", ignore_case=True, timeout=5000)

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_click_search_result_opens_chat(self):
        """Clicking a search result reaches the conversation: a
        first-ever contact lands a row in the recent-chats list, an
        existing conversation opens its thread directly (both
        measured). Either way the thread opens and back returns to a
        list holding the conversation row.

        Steps:
        1. Open the chat panel, search the configured user and click the result.
           Expected: The conversation opens with its message field (placeholder Enter Message Here).
        2. Click back.
           Expected: The recent conversations list holds a row with the user's name.
        """
        self.chat.open_chat_panel()
        self._search_partner_or_fail()
        self.chat.start_conversation()
        self.chat.open_conversation(CHAT_USER_NAME)
        expect(self.chat.message_input.first).to_have_attribute("placeholder", "Enter Message Here")
        expect(self.chat.message_input.first).to_have_value("")
        self.chat.back_to_list()
        row = self.chat.recent_rows.filter(has_text=CHAT_USER_NAME)
        expect(row.first).to_contain_text(CHAT_USER_NAME, timeout=10000)

    # --- Cross-page behavior ---

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_chat_icon_visible_on_events_page(self):
        """The chat panel opens from the Events page too.

        Steps:
        1. Open Events, then click the chat icon in the header.
           Expected: The address ends in /events and the panel opens with its empty Search field.
        """
        events_link = self.page.locator("a[href*='events']")
        if events_link.count() > 0:
            events_link.first.click()
            self.page.wait_for_load_state("domcontentloaded")
        expect(self.page).to_have_url(re.compile(r"/events/?$"), timeout=10000)
        self.chat.open_chat_panel()
        expect(self.chat.search_input).to_have_value("")

    @pytest.mark.ui
    @pytest.mark.chats
    @pytest.mark.chats_deeper
    def test_chat_panel_survives_page_refresh(self):
        """The panel opens after a page refresh.

        Steps:
        1. Refresh the browser, then click the chat icon in the header.
           Expected: The address is unchanged by the refresh and the panel opens with its empty Search field.
        """
        before = self.page.url
        self.page.reload()
        # the app bootstrap has no ready signal; the opener's own
        # marker wait absorbs the remainder
        self.page.wait_for_load_state("domcontentloaded")
        expect(self.page).to_have_url(before)
        self.chat.open_chat_panel()
        expect(self.chat.search_input).to_have_value("")
