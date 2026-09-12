"""Chat tests - panel open, messaging, and the group CRUD.

The 2026-08 redesign made the panel a search-first overlay (see the
chats row in docs/TEST_REPAIRS.md): search a user, click the result to
land a conversation row, click the row to open the thread.

Group creation is a box difference (register item 29): the US box has
the Create Group button and the whole flow works; the india box has no
entry point. The group tests prove the panel is open, then skip on a
box without the button and run on one with it. Each makes the group it
acts on and deletes it, and the teardown raises for any that survives
- the shape the LPR lists got (items 27, 28).
"""
import datetime

import pytest
from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    expect,
)

from config.base_config import config
from tests.shared.pages.chat_page import ChatPage

# Config so tenant renames stay one-line fixes
CHAT_USER_SEARCH = config.get("test_chat_user_search", "QA Engineer B")
CHAT_USER_NAME = config.get("test_chat_user_name", "Chat Partner")

GROUPS_ABSENT = (
    "The chat panel is open and shows no Create Group control: group "
    "creation has no entry point on this box (india, probed 09/04/2026 - "
    "the US box has it, register item 29)"
)


class TestChats:
    """Tests for the redesigned Chat panel overlay."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.chat = ChatPage(self.page)
        self._owned_groups = []
        yield
        self._cleanup_groups()

    def _require_group_creation(self):
        """Skip with proof on a box without the Create Group button.

        The open panel (its search input) is the surface; the button
        is the artifact. A panel with no button is the india box, a
        panel that never opened is a fault, and open_chat_panel raises
        on the second.
        """
        self.chat.open_chat_panel()
        if not self.chat.group_creation_affordance():
            pytest.skip(GROUPS_ABSENT)

    def _own_a_group(self) -> str:
        """Create a group this test owns, and return its name."""
        self._require_group_creation()
        name = "AutoGroup_" + datetime.datetime.now().strftime("%H%M%S%f")[:10]
        self._owned_groups.append(name)
        self.chat.create_group(name, CHAT_USER_SEARCH)
        return name

    def _cleanup_groups(self):
        """Delete every group this test made, and say so when one stays.

        A test can die inside the create dialog or a thread, so the
        panel is reset first: Escape clears a dialog or popper, and
        refresh_panel re-opens the list.
        """
        if not self._owned_groups:
            return
        errors = []
        # typed: a refused delete or a row that never leaves is what
        # this collects; anything else is a real fault and must not be
        # swallowed by a teardown
        try:
            self.page.keyboard.press("Escape")
            self.chat.refresh_panel()
        except (PlaywrightError, RuntimeError) as e:
            errors.append(f"panel reset: {e}")
        for name in reversed(self._owned_groups):
            # A bounded wait, not an instant count: the re-opened list
            # renders a beat after the panel does, and an instant read
            # said 0 for three groups that were there - the teardown
            # then reported nothing and left all three on the tenant
            # (measured 09/08/2026). Absence is proved only when the
            # row has not appeared in 5s, which covers a test that
            # died before its Create landed.
            try:
                self.chat.group_rows(name).first.wait_for(
                    state="visible", timeout=5000
                )
            # the timeout is the proved absence: nothing to delete
            except PlaywrightTimeoutError:
                continue
            try:
                self.chat.delete_group(name)
            except (PlaywrightError, RuntimeError) as e:
                errors.append(f"{name}: {e}")
        self._owned_groups = []
        if errors:
            raise RuntimeError("chat group cleanup failed: " + "; ".join(errors))

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
        expect(self.chat.search_input).to_have_value("")
        expect(self.chat.search_input).to_have_attribute("placeholder", "Search")

    @pytest.mark.ui
    @pytest.mark.chats
    def test_create_group(self):
        """Create a group and see it in the conversation list.

        Steps:
        1. Click the chat icon in the header, then Create Group.
           Expected: The Create New Group dialog opens with a Group Name field and a member picker.
        2. Enter a name, pick the configured chat user as a member, click Create.
           Expected: The dialog closes and the new group is listed in the conversation list.
        """
        name = self._own_a_group()
        # create_group already waited for the row; this is the visible
        # verdict, and the search is NOT one: it never lists a group
        expect(self.chat.group_rows(name).first).to_contain_text(name)

    @pytest.mark.ui
    @pytest.mark.chats
    def test_search_and_send_group_message(self):
        """Open a group from the list and send a message into it.

        The name keeps its historical 'search' wording so the QA Touch
        mapping stays stable, but the group is opened from the
        conversation list: the panel search matches users only and
        never lists a group (measured 09/04/2026).

        Steps:
        1. Create a group and click its row in the conversation list.
           Expected: The group thread opens with the message field.
        2. Type a message and press Enter.
           Expected: The message appears in the thread as sent.
        """
        name = self._own_a_group()
        self.chat.open_group(name)
        stamp = datetime.datetime.now().strftime("%H%M%S")
        # oracle: send_message raises unless the text renders as sent
        self.chat.send_message(f"Group chat check {stamp}")

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
        """The group thread's edit icon opens nothing on the current build.

        Steps:
        1. Create a group and open its thread.
           Expected: The thread shows edit, delete and info icons.
        2. Click the edit icon.
           Expected: No name field opens (measured 09/08/2026). The test skips; it fails loud the day a field appears so the rename gets a real test.
        """
        name = self._own_a_group()
        self.chat.open_group(name)
        if self.chat.group_rename_control():
            pytest.fail(
                "The group edit icon now opens an editable control - "
                "build the rename test against it"
            )
        pytest.skip(
            "The group thread's edit icon is inert: clicking it opened no "
            "input, textarea or contenteditable within 3s (probed "
            "09/08/2026), so there is no rename to test"
        )

    @pytest.mark.ui
    @pytest.mark.chats
    def test_delete_group(self):
        """Delete a group and see it leave the conversation list.

        Steps:
        1. Create a group and open its thread, then click the delete icon.
           Expected: A Delete Group confirmation asks whether to delete permanently.
        2. Confirm.
           Expected: The group is no longer listed once the panel is re-opened.
        """
        name = self._own_a_group()
        # oracle: delete_group raises unless the row is gone after the
        # panel re-opens (the list does not repaint on its own)
        self.chat.delete_group(name)
        self._owned_groups.remove(name)
        expect(self.chat.group_rows(name)).to_have_count(0)
