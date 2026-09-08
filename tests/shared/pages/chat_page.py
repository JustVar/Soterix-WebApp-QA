"""Chat Page Object Model.

Models the redesigned Chat panel (2026-08): a search-first overlay
opened from the header chat icon. All mechanisms below were measured
08/13/2026 with tools/explore_app.py (docs/TEST_REPAIRS.md, chats row):

- The header icon TOGGLES the panel. The open marker is the visible
  panel search input (placeholder 'Search'); the old Create Group
  marker is gone, and waiting on it made the opener close the panel.
- Four inputs share the chat-search-input class: the visible panel
  search, a hidden member search ('Search1'), and two mounted thread
  message inputs ('Enter Message Here'). Every locator here scopes to
  the panel and filters by placeholder and visibility, never by the
  shared class alone.
- The search responds to real keystrokes only: a lone programmatic
  input event right after panel open is dropped (fill() produced zero
  results across probes; key-by-key typing always landed by the second
  pass). search_chat types with press_sequentially and retypes once.
- A search-result click behaves two ways (both measured): a first-ever
  contact lands a conversation row in the recent-chats list (the row
  click then opens the thread), while an existing conversation opens
  its thread directly. The thread-open marker is the visible message
  input.
- Sent text renders as span.sentMsg in the thread - the delivered
  oracle. Callers pass run-unique text or the wait can match an older
  run's message.
- Group creation is a BOX difference (both probed 09/04/2026). The
  india box has no entry point at all. The US box renders a real
  'Create Group' button, and the whole flow works: a Create New Group
  dialog (Group Name, Select Group members), a group thread with
  edit, delete and info icons. group_creation_affordance() reports
  which box this is; the group tests skip with proof on india and run
  on US (register item 29).
- Four group traps, each paid for with a probe: the panel SEARCH finds
  users only, never a group, so the conversation list is the one
  oracle for a created group; the member autocomplete popper stays
  open over the Create button after a pick and needs an Escape; the
  Delete Group confirm controls are div.MuiBox-root, not buttons; and
  the panel does not repaint after a delete, so a row is read only
  after refresh_panel() re-opens it (item 8's lesson again).
- The group thread's edit icon is inert on the current build: no
  input, no modal, no change (probed 09/08/2026). group_rename_control()
  is the tripwire that fails loud the day it opens something.
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect


class ChatPage:
    """Page object for the redesigned Chat panel overlay."""

    def __init__(self, page: Page):
        self.page = page

        # The header chat icon; it toggles the panel open/closed
        self.chat_icon = page.locator(".header-right-group .icon").first

        # Panel root; every panel locator scopes to it
        self.panel = page.locator("div.chat-popup-box")

        # Open marker: the visible panel search. Its hidden twin
        # ('Search1') is the mounted member-search view.
        self.search_input = self.panel.locator(
            "input.chat-search-input[placeholder='Search']"
        )

        # Header X. The in-input search icon shares the same
        # iconSmallCross alt, so scope to the popup head.
        self.close_icon = self.panel.locator(
            ".popup-head img[alt='iconSmallCross']"
        )

        # Search results render a hidden copy under the member-search
        # view; only the visible ones are real.
        self.search_results = self.panel.locator(
            ".related-result-item"
        ).filter(visible=True)

        # Recent conversations under the search bar
        self.recent_rows = self.panel.locator(
            ".recent-chat-item"
        ).filter(visible=True)

        # Empty state shown before any conversation exists; it stays
        # mounted alongside results, so it is not a no-results signal
        self.empty_state = self.panel.locator(
            ".chat-search-instruction"
        ).filter(visible=True)

        # Thread view: message input (two mounted copies exist, one
        # visible when a thread is open), back icon, sent messages
        self.message_input = self.panel.locator(
            "input.chat-search-input[placeholder='Enter Message Here']"
        ).filter(visible=True)
        self.back_icon = self.panel.locator(
            "img[alt='back icon']"
        ).filter(visible=True)
        self.sent_messages = self.panel.locator("span.sentMsg")

        # Groups (US box). The button is the entry point; the dialog's
        # two inputs each have a hidden mounted twin, so filter visible.
        self.group_create_button = self.panel.locator(
            "button.add-btn", has_text="Create Group"
        )
        self.group_name_input = page.locator(
            "input[placeholder='Enter Group Name']"
        ).filter(visible=True)
        self.group_members_input = page.locator(
            "input[placeholder='Select Group members']"
        ).filter(visible=True)
        self.group_member_options = page.locator(".group-result-item")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.thread_edit_icon = self.panel.locator("img[src*='edit']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.thread_delete_icon = self.panel.locator("img[src*='delete']")
        # Body-level confirm; its controls are divs, not buttons
        self.delete_group_modal = page.locator(".MuiModal-root").filter(
            has_text="delete this Group"
        )

    # --- Panel management ---

    def open_chat_panel(self, timeout: int = 10000):
        """Open the panel from the header icon.

        The icon is a toggle, so clicking while open would close it;
        only click when the open marker is absent.
        """
        if self.search_input.count() and self.search_input.is_visible():
            return
        self.chat_icon.click()
        self.search_input.wait_for(state="visible", timeout=timeout)

    def close_chat_panel(self):
        """Close via the header X; the marker leaving is the signal."""
        self.close_icon.click()
        self.search_input.wait_for(state="hidden", timeout=5000)

    def refresh_panel(self):
        """Close and re-open the panel so its list repaints.

        The list does not repaint after a group mutation: a deleted
        group's row stays on screen until the panel is re-opened, and
        a delete verified on the stale panel reads as refused
        (measured 09/04/2026 - the same trap the bookmarks panel has,
        register item 8).
        """
        self.close_chat_panel()
        self.open_chat_panel()

    def toggle_chat_icon(self):
        """Click the header icon with no open/close protection, for
        tests that verify the toggle behavior itself."""
        self.chat_icon.click()

    # --- Search ---

    def clear_search(self):
        """Clear the search with real key events (a programmatic clear
        can drop the same way a programmatic fill does)."""
        self.search_input.click()
        self.search_input.press("Control+a")
        self.search_input.press("Delete")

    def search_chat(self, text: str, timeout: int = 8000) -> int:
        """Type into the panel search and wait for visible results.

        Types key by key and retypes once when nothing lands (the app
        drops the first programmatic input event after open; the
        second typing pass has always landed). Returns the visible
        result count; 0 after both passes means no match.
        """
        for _attempt in range(2):
            self.clear_search()
            self.search_input.press_sequentially(text, delay=80)
            try:
                self.search_results.first.wait_for(
                    state="visible", timeout=timeout
                )
                return self.search_results.count()
            # timeout here means the first input event was dropped or
            # there is genuinely no match; the second pass decides
            except PlaywrightTimeoutError:
                continue
        return 0

    # --- Conversations ---

    def start_conversation(self, result_index: int = 0):
        """Click a search result.

        Measured both ways 08/13/2026: a first-ever contact lands a
        conversation row in the recent-chats list, while an existing
        conversation opens its thread directly. Either marker counts.
        """
        self.search_results.nth(result_index).click()
        either = self.recent_rows.first.or_(self.message_input.first)
        either.first.wait_for(state="visible", timeout=10000)

    def thread_open(self) -> bool:
        """True when a thread is open (visible message input)."""
        return (self.message_input.count() > 0
                and self.message_input.first.is_visible())

    def open_conversation(self, name: str):
        """Open the named conversation's thread; the visible message
        input is the thread-open marker. A no-op when the result click
        already opened the thread (existing conversations do)."""
        if not self.thread_open():
            row = self.recent_rows.filter(has_text=name)
            row.first.wait_for(state="visible", timeout=10000)
            row.first.click()
        self.message_input.first.wait_for(state="visible", timeout=10000)

    def back_to_list(self):
        """Return from the thread to the conversation list."""
        self.back_icon.first.click()
        self.recent_rows.first.wait_for(state="visible", timeout=10000)

    # --- Messaging ---

    def send_message(self, text: str):
        """Send a message in the open thread and wait for delivery.

        fill + Enter submits the message form (measured working; the
        keystroke requirement is specific to the panel search). The
        sent text rendering as span.sentMsg is the delivered oracle;
        callers pass run-unique text or the wait can match an older
        run's message.
        """
        self.message_input.first.fill(text)
        self.message_input.first.press("Enter")
        self.sent_messages.filter(has_text=text).first.wait_for(
            state="visible", timeout=15000
        )

    # --- Groups ---

    def group_creation_affordance(self) -> bool:
        """True when a visible Create Group control exists.

        This is a box difference, not a version one: US shows the
        button, india shows nothing (both probed 09/04/2026). The
        group tests use it to skip with proof on india and run on US.
        """
        # is_visible() is False, not an error, when nothing matches
        return self.group_create_button.first.is_visible()

    def group_rows(self, name: str):
        """The conversation-list rows for a group of this exact name.

        The panel search matches users only - a group never appears in
        its results - so this list is the only oracle for a group.
        """
        return self.panel.get_by_text(name, exact=True).filter(visible=True)

    def create_group(self, name: str, member_search: str):
        """Create a group with one member and wait for its row.

        The member autocomplete is multi-select and its popper stays
        open over the Create button after a pick, so it is dismissed
        with Escape. The Create button is matched by exact role name:
        a has-text('Create') also matches 'Create Group'. The row
        appearing after refresh_panel() is the created signal.
        """
        self.group_create_button.first.click()
        self.group_name_input.first.wait_for(state="visible", timeout=10000)
        self.group_name_input.first.fill(name)
        self.group_members_input.first.click()
        self.group_members_input.first.fill(member_search)
        self.group_member_options.first.wait_for(state="visible", timeout=10000)
        self.group_member_options.first.click()
        self.page.keyboard.press("Escape")
        self.page.get_by_role("button", name="Create", exact=True).last.click()
        self.refresh_panel()
        self.group_rows(name).first.wait_for(state="visible", timeout=15000)

    def open_group(self, name: str):
        """Open the group's thread; the visible message input is the marker."""
        self.group_rows(name).first.click()
        self.message_input.first.wait_for(state="visible", timeout=10000)

    def delete_group(self, name: str):
        """Delete the group and prove it is gone.

        Confirms in the body-level Delete Group modal, whose Delete
        control is a div (get_by_role finds nothing), then re-opens
        the panel and requires the row to be absent. Raises when it
        survives: a group left behind is a real user's clutter and,
        like every leftover on this tenant, a trap for the next run.
        """
        if not self.thread_open():
            self.open_group(name)
        self.thread_delete_icon.first.click()
        confirm = self.delete_group_modal.get_by_text("Delete", exact=True)
        confirm.first.wait_for(state="visible", timeout=10000)
        confirm.first.click()
        self.delete_group_modal.wait_for(state="hidden", timeout=10000)
        self.refresh_panel()
        # typed: a row that never leaves is what this reports
        try:
            self.group_rows(name).first.wait_for(state="hidden", timeout=10000)
        except PlaywrightTimeoutError:
            raise RuntimeError(
                f"The group '{name}' is still listed after its delete was "
                f"confirmed. Delete it by hand from the chat panel."
            ) from None

    def group_rename_control(self) -> bool:
        """Click the open thread's edit icon; True if it opens anything
        a name could be typed into.

        Inert on the current build (probed 09/08/2026): no input, no
        modal, no change. The rename test skips on False and fails
        loud on True, so the flow gets a real test the day it appears.
        """
        # Baseline first: the Views page behind the panel always has
        # visible inputs (the camera search, the tab title), so only
        # growth over this count is something the icon opened. The
        # first version read page-wide with no baseline and fired on
        # those (09/08/2026).
        editable = self.page.locator(
            "input, [contenteditable='true'], textarea"
        ).filter(visible=True)
        before = editable.count()
        self.thread_edit_icon.first.click()
        try:
            expect(editable).not_to_have_count(before, timeout=3000)
            return editable.count() > before
        # the timeout IS the measurement: nothing editable appeared
        except AssertionError:
            return False
