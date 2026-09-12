"""Media Page Object Model.

Models the Media page including navigation, date filter, tab switching,
grid/list view toggle, clip and folder operations (group, rename, move,
delete, create link, vault, share, export), and search.
"""
import datetime
import re
import time

from playwright.sync_api import Error as PlaywrightError, Page, expect

# The app's toast containers (react-toastify and MUI alerts), for naming
# what the page answered when an action opened no dialog.
TOASTS = ".Toastify__toast, [role='alert'], .MuiAlert-message, .MuiSnackbarContent-message"


class MediaPage:
    """Page object for the Media page."""

    def __init__(self, page: Page):
        self.page = page

        # Navigation
        self.media_nav_link = page.locator("a[href*='media']")

        # Date filter dropdown (MUI combobox)
        self.date_filter = page.locator("[role='combobox']").first

        # The view toggle is a MUI toggle group of two buttons, aria-label
        # 'table' and 'grid', aria-pressed on the active one (measured
        # 09/12/2026 on US; the list button carries icon-table, so the old
        # img[src*='icon-list'] locator never found it)
        self.list_view_button = page.locator("button[aria-label='table']")
        self.grid_view_button = page.locator("button[aria-label='grid']")

        # Tabs
        self.tab_all = page.locator("button:has-text('All')").first
        self.tab_my_media = page.locator("button:has-text('My Media')")
        self.tab_shared = page.locator("button:has-text('Shared with me')")
        # the type row's All: a span whose whole text is All (the scope
        # row's All above it is a button)
        self.tab_all_types = page.locator("span").filter(has_text=re.compile(r"^All$")).first
        self.tab_clips = page.locator("span:has-text('Clips')").first
        self.tab_folders = page.locator("span:has-text('Folders')").first
        self.tab_vault = page.locator("span:has-text('Vault')").first

        # Item names render as inline inputs (see item_names/item_row);
        # there is no card class on the current list layout

        # Empty state
        self.no_results_text = page.locator(
            "p:has-text('No results found for selected criteria')"
        )

        # Options menu (three-dot icon on each item)
        self.options_icon = page.locator("img[src*='icon-options']").first

        # Context menu items (MUI Menu)
        self.menu_rename = page.locator(
            "li[role='menuitem']:has-text('Rename')"
        )
        self.menu_delete = page.locator(
            "li[role='menuitem']:has-text('Delete')"
        )
        self.menu_create_link = page.locator(
            "li[role='menuitem']:has-text('Create Link')"
        )
        self.menu_move_to_folder = page.locator("p:has-text('Move to folder')")

        # Confirmation dialog
        self.confirm_button = page.locator(".btn-modalForm").first
        self.confirm_yes_button = page.locator(
            "button.btn-modalForm:has-text('Yes')"
        )

        # Clip selection (checkboxes - same MUI pattern as events)
        self.clip_checkboxes = page.locator(".PrivateSwitchBase-input")

        # Group Clips
        self.group_clips_action = page.locator("p:has-text('Group Clips')")
        self.group_clips_confirm = page.locator(
            "button:has-text('Group Clips')"
        )

        # Move to folder dialog
        self.folder_dropdown = page.locator(".modalForm-input-event")
        self.move_button = page.locator("button:has-text('Move')")

        # Share dialog
        self.email_input = page.locator(
            "input[placeholder='Add Email ID']"
        )
        # Exact text: a has-text substring also matches the
        # 'Shared With Me' tab label, which precedes the dialog
        self.share_button = page.get_by_text("Share", exact=True).first
        self.share_success = page.locator(".successfull-container")

        # Export
        # Exact text: has-text substring matches wrapper spans too
        self.export_span = page.get_by_text("Export", exact=True).first

        # Create link dialog
        self.create_button = page.locator("span:has-text('Create')").first

        # Search
        self.search_input = page.locator(
            "input[placeholder*='Search by title']"
        )

        # Loader
        self.loader = page.locator(".MuiCircularProgress-root")

    # --- Navigation ---

    def navigate(self):
        """Navigate to the Media page via the nav link."""
        self.media_nav_link.click(force=True)
        self._wait_for_page_ready()

    def _wait_for_page_ready(self):
        """Wait for the Media page to finish loading."""
        # Loader may take a beat to appear, then must disappear
        self._appears(self.loader.first, timeout=2000)
        self._appears_hidden(self.loader.first, timeout=30000)

    # --- Date filter ---

    def select_date_filter(self, option_text: str = "Last 30 Days"):
        """Open the date filter combobox and select an option."""
        self.date_filter.click()

        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=10000)

        option = listbox.locator(
            f"li[role='option']:has-text('{option_text}')"
        ).first
        option.click()
        # Listbox hidden = MUI applied the selection
        listbox.wait_for(state="hidden", timeout=10000)
        self._wait_for_page_ready()

    # --- View toggle ---

    def switch_to_grid_view(self):
        """Switch to grid view: the grid button reads pressed, then the items
        are back on screen (the toggle re-renders them, and a read taken on
        the pressed state alone saw none; measured 09/12/2026)."""
        self._switch_view(self.grid_view_button)

    def switch_to_list_view(self):
        """Switch to list view; same two signals as switch_to_grid_view."""
        self._switch_view(self.list_view_button)

    def _switch_view(self, button) -> None:
        before = len(self.item_names())
        button.click()
        expect(button).to_have_attribute("aria-pressed", "true", timeout=5000)
        deadline = time.monotonic() + 5
        while len(self.item_names()) != before:
            if time.monotonic() > deadline:
                raise AssertionError(
                    f"{before} item(s) were listed before the view switch, "
                    f"{len(self.item_names())} are after it")
            self.page.wait_for_timeout(100)  # poll tick for the re-render

    def view_mode(self) -> str:
        """'grid' or 'table', from the toggle group's pressed button."""
        return "grid" if self.grid_view_button.get_attribute("aria-pressed") == "true" else "table"

    def view_columns(self) -> int:
        """How many columns the item names sit in: 1 in the list view, 3 in
        the grid view at 1280 px (measured 09/12/2026); 0 with no items."""
        return self.page.evaluate(
            """() => new Set([...document.querySelectorAll("input[type='text']")]
                .filter(i => i.getClientRects().length > 0 && !i.className && i.value
                        && i.getAttribute('title') === i.value)
                .map(i => Math.round(i.getBoundingClientRect().left))).size"""
        )

    # Measured 09/12/2026 on US. The page has two tab rows: the scope
    # buttons (All / My Media / Shared With Me), whose selected one paints
    # its background rgb(0, 67, 77); and the type tabs under them (All /
    # Clips / Folders / Vault), whose selected one paints its text
    # rgb(24, 204, 231). Nothing else marks the selection (no aria-selected,
    # no class), so the colours are the signal.
    DATE_RANGES = ("Today", "Yesterday", "Last 7 Days", "Last 30 Days", "Custom")
    EMPTY_STATE = "No results found for selected criteria"
    SEARCH_PLACEHOLDER = "Search by title, tags, sites, etc."
    SEARCH_MIN_CHARS = 3
    SCOPE_SELECTED_BACKGROUND = "rgb(0, 67, 77)"
    TYPE_SELECTED_COLOR = "rgb(24, 204, 231)"
    # "All" is the scope button; the type row's own All is "All (types)"
    TYPE_TABS = ("All (types)", "Clips", "Folders", "Vault")

    def date_filter_text(self) -> str:
        return self.date_filter.inner_text().strip()

    def date_options(self) -> list[str]:
        """The date filter's options, read with the list open and closed again."""
        self.date_filter.click()
        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=10000)
        options = [o.strip() for o in listbox.locator("li[role='option']").all_inner_texts()]
        self.page.keyboard.press("Escape")
        listbox.wait_for(state="hidden", timeout=5000)
        return options

    def tab_is_selected(self, tab_name: str) -> bool:
        tab = self._tab(tab_name)
        if tab_name in self.TYPE_TABS:
            return tab.evaluate("e => getComputedStyle(e).color") == self.TYPE_SELECTED_COLOR
        return tab.evaluate("e => getComputedStyle(e).backgroundColor") == self.SCOPE_SELECTED_BACKGROUND

    def expect_tab_selected(self, tab_name: str, timeout_ms: int = 5000) -> None:
        """Fail, naming the paint, when the tab is not the selected one."""
        deadline = time.monotonic() + timeout_ms / 1000
        while not self.tab_is_selected(tab_name):
            if time.monotonic() > deadline:
                tab = self._tab(tab_name)
                paint = tab.evaluate(
                    "e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color]")
                raise AssertionError(
                    f"the {tab_name} tab is not selected: it paints background/text {paint}, "
                    f"a selected one paints {self.SCOPE_SELECTED_BACKGROUND} (scope) or "
                    f"{self.TYPE_SELECTED_COLOR} (type)")
            self.page.wait_for_timeout(100)  # poll tick for the tab paint

    def _tab(self, tab_name: str):
        tab_map = {
            "All": self.tab_all,
            "My Media": self.tab_my_media,
            "Shared with me": self.tab_shared,
            "All (types)": self.tab_all_types,
            "Clips": self.tab_clips,
            "Folders": self.tab_folders,
            "Vault": self.tab_vault,
        }
        tab = tab_map.get(tab_name)
        assert tab is not None, f"Unknown tab name: {tab_name}"
        return tab

    # --- Tab navigation ---

    def click_tab(self, tab_name: str):
        """Click a tab by name (All, My Media, Shared with me, Clips, Folders, Vault)."""
        tab = self._tab(tab_name)
        tab.click()
        # The tab fetch runs a loader cycle; page-ready covers it
        self._wait_for_page_ready()

    def is_page_empty(self, timeout: int = 5000) -> bool:
        """Check if the current page/tab shows 'No results found'.

        Returns True if empty, False if content exists.
        """
        try:
            self.no_results_text.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def has_content(self, timeout: int = 5000) -> bool:
        """Check whether the page/tab has some content (not empty)."""
        return not self.is_page_empty(timeout=timeout)

    # --- Clip selection ---

    def select_clip_by_index(self, index: int = 1):
        """Select a clip checkbox by index.

        Index 0 is the header select-all checkbox; individual clips
        start at index 1.
        """
        checkboxes = self.clip_checkboxes
        count = checkboxes.count()
        assert count > index, (
            f"Expected at least {index + 1} checkboxes, found {count}"
        )
        checkboxes.nth(index).click()

    # --- Clip operations ---

    def group_clips(self):
        """Click 'Group Clips' in the action bar, then confirm.

        Creates a folder with the default name from the selected clips.
        """
        self.group_clips_action.click()
        self.group_clips_confirm.click()
        # The confirm control leaves the DOM when grouping starts; a
        # stuck dialog raises
        self.group_clips_confirm.wait_for(state="hidden", timeout=15000)
        self._wait_for_page_ready()

    def open_options_menu(self, index: int = 0):
        """Click the options (three-dot) icon on a media item.

        If index > 0, clicks the nth options icon.
        """
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        icons = self.page.locator("img[src*='icon-options']")
        icons.nth(index).click()
        # The context menu popover carries the item actions. :visible
        # skips stale keepMounted menus left hidden in the DOM. Role
        # alone: the paper wraps a ul[role=menu], one visible open,
        # none once closed (probed 08/24/2026)
        self.page.locator(
            "[role='menu']:visible"
        ).first.wait_for(state="visible", timeout=10000)

    def click_menu_item(self, text: str):
        """Click a menu item by text in the currently open context menu.

        Visible-filtered: stale keepMounted menus stay in the DOM.
        """
        item = self.page.locator(
            f"li[role='menuitem']:has-text('{text}'):visible"
        ).first
        item.wait_for(state="visible", timeout=5000)
        item.click()
        # The menu closes once the action registers
        self._appears_hidden(item, timeout=10000)

    def item_names(self) -> list[str]:
        """Names of the visible list items.

        Names render as inline text inputs (invisible to text
        engines), bare of class, with the name as value. This reads
        the live value property; item_row and the applied-signal
        waits match the value ATTRIBUTE - the app mirrors the two
        (measured 08/12/2026), and a future divergence shows up as
        item_names returning a name item_row cannot find.
        """
        return self.page.evaluate(
            """() => [...document.querySelectorAll("input[type='text']")]
                .filter(i => i.getClientRects().length > 0
                        && !i.className && i.value
                        && i.getAttribute('title') === i.value)
                .map(i => i.value)"""
        )

    def item_row(self, name: str):
        """The list row of a named item (clip or folder)."""
        if "'" in name or '"' in name:
            raise ValueError(
                f"Item name {name!r} would break the value selector; "
                "quote-bearing names need an escaping strategy first"
            )
        return self.page.locator(f"input[value='{name}']").locator(
            "xpath=ancestor::*[.//img[contains(@src,'icon-options')]][1]"
        ).first

    def rename_item(self, current: str, new_name: str):
        """Rename a named item; the success toast is the server ack.

        The inline input updates optimistically, so only the toast
        proves the rename committed - a rename can look done in the
        DOM and never reach the server (measured 08/12/2026). The
        toast lingers for seconds, so back-to-back renames must
        serialize on its ABSENCE first or the second wait matches
        the first rename's toast (also measured, the hard way). The
        row anchor keys on the value being edited, so the input node
        is held as a handle across the fill. The toast text is
        measured for clips; folder renames are unmeasured.
        """
        toast = self.page.get_by_text("File name updated successfully")
        toast.first.wait_for(state="hidden", timeout=10000)
        row = self.item_row(current)
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        row.locator("img[src*='icon-options']").first.click()
        self.click_menu_item("Rename")
        handle = row.locator("input[type='text']").first.element_handle()
        handle.fill(new_name)
        # A maxlength (or a not-yet-editable input) truncates or drops
        # the fill silently; verify before committing
        typed = handle.evaluate("el => el.value")
        if typed != new_name:
            raise RuntimeError(
                f"Name input holds {typed!r} after filling {new_name!r}"
            )
        handle.press("Enter")
        toast.first.wait_for(state="visible", timeout=10000)

    def delete_item(self):
        """Delete a clip or folder via options menu > Delete > confirm.

        Opens options menu, clicks Delete, then confirms. The dialog
        leaving the DOM is the applied signal; a stuck dialog raises.
        """
        self.open_options_menu()
        self.click_menu_item("Delete")
        self.confirm_button.click()
        self.confirm_button.wait_for(state="hidden", timeout=15000)
        self._wait_for_page_ready()

    def delete_item_named(self, name: str):
        """Delete a NAMED clip or folder: row options > Delete > confirm.

        Row-scoped, unlike delete_item's page-first options icon. The
        named input detaching from the list is the applied signal.
        """
        row = self.item_row(name)
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        row.locator("img[src*='icon-options']").first.click()
        self.click_menu_item("Delete")
        # The dialog renders Cancel before Delete, so a bare
        # .btn-modalForm.first cancels (measured 09/02/2026)
        delete_btn = self.page.locator(
            "button:has-text('Delete'):visible"
        ).last
        delete_btn.click()
        # The server can refuse the delete outright - the app answers
        # with an error toast (probed 09/02/2026 on both a clip and an
        # empty folder). Name that, not a timeout.
        if self._appears(
            self.page.get_by_text("Data Not Deleted!").first, timeout=3000
        ):
            raise RuntimeError(
                f"Server refused to delete '{name}': 'Data Not "
                "Deleted!' (app defect - register, App defects)"
            )
        delete_btn.wait_for(state="hidden", timeout=15000)
        # No reload fallback here: a reload lands on the default
        # tab/filter, where the row's ABSENCE proves nothing. A row
        # that stays is either the stale-serving list or a refusal
        # without a toast - either way the caller must decide with the
        # view re-established, so fail loud with both readings.
        row_input = self.page.locator(f"input[value='{name}']").first
        if not self._appears_hidden(row_input, timeout=15000):
            raise RuntimeError(
                f"'{name}' still listed after Delete confirmed: stale "
                "view or a refusal without a toast. Re-establish the "
                "tab/filter and re-check before trusting either."
            )
        self._wait_for_page_ready()

    def open_folder(self, name: str):
        """Open a folder from the Folders tab by clicking its row.

        Entry is the row's THUMBNAIL image - a row click lands on the
        checkbox or the name input and stays on the list (probed
        09/02/2026). The breadcrumb rendering the folder name as TEXT
        is the opened signal (list names are inline inputs, invisible
        to text engines, so a text match can only be the breadcrumb).
        """
        row = self.item_row(name)
        row.locator("img:not([src*='icon'])").first.click()
        self.page.get_by_text(name, exact=True).first.wait_for(
            state="visible", timeout=10000
        )
        # Corroborate: the folder view is tab-less (measured 09/02), so
        # the Clips tab hiding rules out a stray text node elsewhere
        # satisfying the name wait
        self.tab_clips.wait_for(state="hidden", timeout=10000)
        self._wait_for_page_ready()

    def remove_from_folder(self, name: str):
        """Un-group a named clip from the open folder view.

        'Remove From Folder' returns the clip to the level above
        WITHOUT deleting it (confirmed by Justin, 09/02/2026). The row
        leaving the folder view is the applied signal.
        """
        row = self.item_row(name)
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        row.locator("img[src*='icon-options']").first.click()
        self.click_menu_item("Remove From Folder")
        self.page.locator(f"input[value='{name}']").first.wait_for(
            state="detached", timeout=15000
        )
        self._wait_for_page_ready()

    def open_create_link_dialog(self, name: str):
        """Open the Create Link dialog for a named item.

        The dialog carries Start/End/Duration, an optional link name,
        and Cancel/Create (measured 08/12/2026).
        """
        row = self.item_row(name)
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        row.locator("img[src*='icon-options']").first.click()
        self.click_menu_item("Create Link")
        # The tenant answers a folder with the toast 'Empty folder' even
        # when the folder holds a clip (probed 09/11/2026 on US, the clip
        # listed inside the folder): name that, not a timeout.
        self._dialog_or_answer(self.page.get_by_text("Add Link Name").first,
                               f"Create Link on '{name}'")

    def cancel_dialog(self):
        """Cancel the open dialog; its Cancel control leaving is the
        closed signal."""
        cancel = self.page.get_by_text("Cancel", exact=True).first
        cancel.click()
        cancel.wait_for(state="hidden", timeout=10000)

    def move_clip_to_folder(self):
        """Move a selected clip to an existing folder.

        Clicks 'Move to folder', selects the first available folder
        from the native <select> dropdown, then clicks Move.

        Returns False if no folders are available (select has only the
        disabled placeholder option).
        """
        self.menu_move_to_folder.click()

        select_el = self.page.locator("select.modalForm-input-event")
        select_el.wait_for(state="visible", timeout=10000)

        # Check if there are any selectable folder options
        option_count = self.page.evaluate("""() => {
            const sel = document.querySelector('select.modalForm-input-event');
            if (!sel) return 0;
            return Array.from(sel.options).filter(o => !o.disabled).length;
        }""")

        if option_count == 0:
            return False

        # Select the first non-disabled option
        self.page.evaluate("""() => {
            const sel = document.querySelector('select.modalForm-input-event');
            const opt = Array.from(sel.options).find(o => !o.disabled);
            if (opt) {
                sel.value = opt.value;
                sel.dispatchEvent(new Event('change', {bubbles: true}));
            }
        }""")

        self.move_button.click()
        # The move dialog leaves the DOM with its button; stuck raises
        self.move_button.wait_for(state="hidden", timeout=15000)
        self._wait_for_page_ready()
        return True

    # --- Vault operations ---

    def add_to_vault(self, name: str):
        """Vault a named item.

        Vaulting FLAGS the item: it appears in the Vault tab and
        stays in its list (measured 08/12/2026 - an earlier 'the row
        moves' reading was a name-desync artifact). The live signal
        is the row's Add icon detaching after its spinner cycle.
        """
        row = self.item_row(name)
        add_icon = row.locator("img[alt='Add to Vault']").first
        add_icon.click()
        add_icon.wait_for(state="detached", timeout=15000)

    def remove_from_vault(self, name: str):
        """Un-vault a named item from the Vault tab (Yes confirm).

        The row leaving the Vault list is the applied signal.
        """
        row = self.item_row(name)
        row.locator("img[alt='Remove from Vault']").first.click()
        # Visible-filtered: a stale keepMounted confirm from earlier
        # in the session can sit first in DOM order
        yes_button = self.page.locator(
            "button:has-text('Yes'):visible"
        ).first
        yes_button.wait_for(state="visible", timeout=5000)
        yes_button.click()
        self.page.locator(f"input[value='{name}']").wait_for(
            state="detached", timeout=15000
        )

    # --- Share ---

    def share_item(self, name: str, email: str = "test@example.com"):
        """Share a named item via its row Share icon and email dialog.

        The success panel is the shared signal; its absence raises.
        """
        row = self.item_row(name)
        row.locator("img[alt='Share']").first.click()

        # A folder's Share icon opens nothing on the tenant (probed
        # 09/11/2026 on US); a clip's opens the e-mail dialog.
        self._dialog_or_answer(self.email_input, f"Share on '{name}'")
        self.email_input.fill(email)

        self.share_button.click()
        # india 09/11: the e-mail dialog opened for a folder but no success
        # panel followed; name what the page answered instead of a timeout
        self._dialog_or_answer(self.share_success.first, f"Sharing '{name}'")

    # --- Export ---

    def export_item(self, name: str):
        """Export a named item via its row Export icon.

        The export control leaving the DOM is the started signal; a
        stuck control raises.
        """
        row = self.item_row(name)
        row.locator("img[alt='Export']").first.click()

        self._dialog_or_answer(self.export_span, f"Export on '{name}'")
        self.export_span.click()
        self.export_span.wait_for(state="hidden", timeout=10000)

    def _dialog_or_answer(self, control, action: str, timeout: int = 10000) -> None:
        """Wait for the control an action should open; when it never
        comes, raise with what the page answered instead (its toasts),
        so the report names the app's reply and not a bare timeout."""
        # Polled, not a single wait: a toast lives a few seconds and is
        # gone by the time a 10 s wait gives up, so it is read while waiting.
        seen: set[str] = set()
        deadline = time.monotonic() + timeout / 1000
        while time.monotonic() < deadline:
            if control.is_visible():
                return
            seen.update(t.inner_text().strip() for t in self.page.locator(TOASTS).all()
                        if t.is_visible() and t.inner_text().strip())
            self.page.wait_for_timeout(250)  # why: a poll tick; the toast is the only signal and it is transient
        answer = f"the toast {sorted(seen)}" if seen else "nothing, no toast"
        raise RuntimeError(
            f"{action} opened no dialog within {timeout // 1000} s; the page answered "
            f"{answer} (folder operations: app defect - register, App defects)"
        )

    # --- Search ---

    def search_media(self, query: str):
        """Type a search query in the search input and press Enter.

        The page ignores a query under three characters: '17' sent no
        request and left the list as it was, so two tests passed on
        nothing (measured 09/12/2026). An empty query clears the search."""
        if query and len(query) < self.SEARCH_MIN_CHARS:
            raise ValueError(
                f"the media search ignores queries under {self.SEARCH_MIN_CHARS} characters: {query!r}")
        self.search_input.wait_for(state="visible", timeout=10000)
        self.search_input.fill("")
        self.search_input.fill(query)
        self.search_input.press("Enter")
        # The search fetch runs a loader cycle; page-ready covers it
        self._wait_for_page_ready()

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
