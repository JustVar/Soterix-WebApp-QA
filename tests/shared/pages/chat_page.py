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
- Group creation has no entry point in the redesigned panel (probed
  across fresh, search, result-click, thread, and hover states). The
  mounted 'Add Members'/Update view serves group conversations, which
  this account cannot create, so the group CRUD methods are retired
  with the feature. group_creation_affordance() is the tripwire the
  skipped CRUD tests check so the feature's return fails loud.
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


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

    # --- Group-creation tripwire ---

    def group_creation_affordance(self) -> bool:
        """True when a visible group-creation control exists.

        The redesign removed group creation; the skipped CRUD tests
        call this so the feature's return fails loud and forces a
        rebuild instead of skipping forever.
        """
        candidates = self.panel.get_by_text("Create Group", exact=False)
        return any(
            candidates.nth(i).is_visible()
            for i in range(candidates.count())
        )
