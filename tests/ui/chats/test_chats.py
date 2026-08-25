"""Chat tests - panel open, messaging, and the retired group CRUD.

The 2026-08 redesign made the panel a search-first overlay (see the
chats row in docs/TEST_REPAIRS.md): search a user, click the result to
land a conversation row, click the row to open the thread. Group
creation has no entry point in the redesigned panel (probed
08/13/2026), so the group CRUD tests skip honestly - and fail loud if
a creation affordance ever reappears.
"""
import datetime

import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.chat_page import ChatPage

# Config so tenant renames stay one-line fixes
CHAT_USER_SEARCH = config.get("test_chat_user_search", "QA Engineer B")
CHAT_USER_NAME = config.get("test_chat_user_name", "Chat Partner")

GROUPS_GONE = (
    "Group creation has no entry point in the redesigned chat panel "
    "(probed 08/13/2026, docs/TEST_REPAIRS.md chats row)"
)


class TestChats:
    """Tests for the redesigned Chat panel overlay."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.chat = ChatPage(self.page)
        return

    def _skip_unless_groups_returned(self):
        """Honest skip for the retired group CRUD, with a tripwire: if
        a creation affordance reappears, fail loud so the CRUD tests
        get rebuilt instead of skipping forever."""
        if self.chat.group_creation_affordance():
            pytest.fail(
                "A group-creation control is visible in the chat panel "
                "again - rebuild the group CRUD tests against it"
            )
        pytest.skip(GROUPS_GONE)

    def _open_partner_conversation(self):
        """Search the configured chat user and open their thread."""
        found = self.chat.search_chat(CHAT_USER_SEARCH)
        assert found > 0, (
            f"No chat user matches '{CHAT_USER_SEARCH}' - if the "
            "tenant user changed, update test_chat_user_search in "
            "config/env"
        )
        self.chat.start_conversation()
        self.chat.open_conversation(CHAT_USER_NAME)

    @pytest.mark.ui
    @pytest.mark.chats
    def test_open_chat_panel(self):
        """The panel opens from the header icon; the visible panel
        search input is the open marker."""
        self.chat.open_chat_panel()
        expect(self.chat.search_input).to_be_visible()

    @pytest.mark.ui
    @pytest.mark.chats
    def test_create_group(self):
        """Group creation retired with the search-first redesign."""
        self.chat.open_chat_panel()
        # oracle: _skip_unless_groups_returned always raises - skip
        # while the feature stays gone, fail on the tripwire
        self._skip_unless_groups_returned()

    @pytest.mark.ui
    @pytest.mark.chats
    def test_search_and_send_group_message(self):
        """Group messaging needs a group, which cannot be created in
        the redesigned panel."""
        self.chat.open_chat_panel()
        # oracle: _skip_unless_groups_returned always raises - skip
        # while the feature stays gone, fail on the tripwire
        self._skip_unless_groups_returned()

    @pytest.mark.ui
    @pytest.mark.chats
    def test_send_individual_message(self):
        """Search a user, open the conversation, send a message.

        The oracle lives in send_message: it raises unless the sent
        text renders in the thread. The run-unique text keeps the
        delivered-wait from matching an older run's message.
        """
        self.chat.open_chat_panel()
        self._open_partner_conversation()

        stamp = datetime.datetime.now().strftime("%H%M%S")
        self.chat.send_message(f"Individual chat check {stamp}")

    @pytest.mark.ui
    @pytest.mark.chats
    def test_edit_group_name(self):
        """Group editing needs a group, which the redesigned panel cannot create.

        Steps:
        1. Click the chat icon in the header.
           Expected: The chat panel opens with its search field.
        2. Look for a Create Group control in the panel.
           Expected: No Create Group control is shown. Group editing cannot be tested until the control returns.
        """
        self.chat.open_chat_panel()
        # oracle: _skip_unless_groups_returned always raises - skip
        # while the feature stays gone, fail on the tripwire
        self._skip_unless_groups_returned()

    @pytest.mark.ui
    @pytest.mark.chats
    def test_delete_group(self):
        """Group deletion needs a group, which cannot be created in
        the redesigned panel."""
        self.chat.open_chat_panel()
        # oracle: _skip_unless_groups_returned always raises - skip
        # while the feature stays gone, fail on the tripwire
        self._skip_unless_groups_returned()
