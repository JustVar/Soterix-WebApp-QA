"""Media Page Object Model.

Models the Media page including navigation, date filter, tab switching,
grid/list view toggle, clip and folder operations (group, rename, move,
delete, create link, vault, share, export), and search.
"""
import datetime

from playwright.sync_api import Error as PlaywrightError, Page, expect


class MediaPage:
    """Page object for the Media page."""

    def __init__(self, page: Page):
        self.page = page

        # Navigation
        self.media_nav_link = page.locator("a[href*='media']")

        # Date filter dropdown (MUI combobox)
        self.date_filter = page.locator("[role='combobox']").first

        # View toggle (grid/list)
        self.grid_view_button = page.locator("img[src*='icon-grid']").first
        self.list_view_button = page.locator("img[src*='icon-list']").first

        # Tabs
        self.tab_all = page.locator("button:has-text('All')").first
        self.tab_my_media = page.locator("button:has-text('My Media')")
        self.tab_shared = page.locator("button:has-text('Shared with me')")
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
        """Switch to grid view."""
        self.grid_view_button.click()
        # The toggle re-renders client-side: no loader and no DOM signal
        self.page.wait_for_timeout(2000)

    def switch_to_list_view(self):
        """Switch to list view."""
        self.list_view_button.click()
        # The toggle re-renders client-side: no loader and no DOM signal
        self.page.wait_for_timeout(2000)

    # --- Tab navigation ---

    def click_tab(self, tab_name: str):
        """Click a tab by name (All, My Media, Shared with me, Clips, Folders, Vault)."""
        tab_map = {
            "All": self.tab_all,
            "My Media": self.tab_my_media,
            "Shared with me": self.tab_shared,
            "Clips": self.tab_clips,
            "Folders": self.tab_folders,
            "Vault": self.tab_vault,
        }
        tab = tab_map.get(tab_name)
        assert tab is not None, f"Unknown tab name: {tab_name}"
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

        Index 0 is typically a header/all selector; individual clips
        start at index 1 in the Selenium tests.
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

    def open_create_link_dialog(self, name: str):
        """Open the Create Link dialog for a named item.

        The dialog carries Start/End/Duration, an optional link name,
        and Cancel/Create (measured 08/12/2026).
        """
        row = self.item_row(name)
        row.locator("img[src*='icon-options']").first.click()
        self.click_menu_item("Create Link")
        self.page.get_by_text("Add Link Name").first.wait_for(
            state="visible", timeout=10000
        )

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

        self.email_input.wait_for(state="visible", timeout=10000)
        self.email_input.fill(email)

        self.share_button.click()
        self.share_success.first.wait_for(state="visible", timeout=10000)

    # --- Export ---

    def export_item(self, name: str):
        """Export a named item via its row Export icon.

        The export control leaving the DOM is the started signal; a
        stuck control raises.
        """
        row = self.item_row(name)
        row.locator("img[alt='Export']").first.click()

        self.export_span.wait_for(state="visible", timeout=10000)
        self.export_span.click()
        self.export_span.wait_for(state="hidden", timeout=10000)

    # --- Search ---

    def search_media(self, query: str):
        """Type a search query in the search input and press Enter."""
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
