"""Media Page Object Model.

Models the Media page including navigation, date filter, tab switching,
grid/list view toggle, clip and folder operations (group, rename, move,
delete, create link, vault, share, export), and search.
"""
import datetime
from playwright.sync_api import Page, expect


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

        # Content area - media items (clips/folders displayed as cards)
        self.media_items = page.locator(".media-card, .media-item, [class*='media']").first

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
            "li:has-text('Create Link')"
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

        # Vault icons
        self.add_to_vault_icon = page.locator("img[alt='Add to Vault']").first
        self.remove_from_vault_icon = page.locator(
            "img[alt='Remove from Vault']"
        ).first

        # Share dialog
        self.share_icon = page.locator("img[alt='Image 1']").first
        self.email_input = page.locator(
            "input[placeholder='Add Email ID']"
        )
        self.share_button = page.locator("span:has-text('Share')").first
        self.share_success = page.locator(".successfull-container")

        # Export
        self.download_icon = page.locator(
            "img[alt='Image 1'][src*='icon-download']"
        ).first
        self.export_span = page.locator("span:has-text('Export')").first

        # Create link dialog
        self.create_button = page.locator("span:has-text('Create')").first

        # Rename input
        self.rename_input = page.locator(
            "input[class*='rename'], input[type='text']"
        ).first

        # Search
        self.search_input = page.locator(
            "input[placeholder*='Search by title']"
        )

        # Loader
        self.loader = page.locator(".MuiCircularProgress-root")

    # --- Navigation ---

    def navigate(self):
        """Navigate to the Media page via the nav link."""
        self.media_nav_link.click()
        self.page.wait_for_timeout(3000)
        self._wait_for_page_ready()

    def _wait_for_page_ready(self):
        """Wait for the Media page to finish loading."""
        try:
            if self.loader.count() > 0 and self.loader.first.is_visible():
                self.loader.first.wait_for(state="hidden", timeout=30000)
        except Exception:
            pass
        self.page.wait_for_timeout(1000)

    # --- Date filter ---

    def select_date_filter(self, option_text: str = "Last 30 Days"):
        """Open the date filter combobox and select an option."""
        self.date_filter.click()
        self.page.wait_for_timeout(1000)

        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=10000)

        option = listbox.locator(
            f"li[role='option']:has-text('{option_text}')"
        ).first
        option.click()
        self.page.wait_for_timeout(2000)
        self._wait_for_page_ready()

    # --- View toggle ---

    def switch_to_grid_view(self):
        """Switch to grid view."""
        self.grid_view_button.click()
        self.page.wait_for_timeout(2000)

    def switch_to_list_view(self):
        """Switch to list view."""
        self.list_view_button.click()
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
        self.page.wait_for_timeout(2000)
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
        self.page.wait_for_timeout(1000)

    # --- Clip operations ---

    def group_clips(self):
        """Click 'Group Clips' in the action bar, then confirm.

        Creates a folder with the default name from the selected clips.
        """
        self.group_clips_action.click()
        self.page.wait_for_timeout(1000)
        self.group_clips_confirm.click()
        self.page.wait_for_timeout(3000)
        self._wait_for_page_ready()

    def open_options_menu(self, index: int = 0):
        """Click the options (three-dot) icon on a media item.

        If index > 0, clicks the nth options icon.
        """
        icons = self.page.locator("img[src*='icon-options']")
        icons.nth(index).click()
        self.page.wait_for_timeout(1000)

    def click_menu_item(self, text: str):
        """Click a menu item by text in the currently open context menu."""
        item = self.page.locator(
            f"li[role='menuitem']:has-text('{text}')"
        ).first
        item.wait_for(state="visible", timeout=5000)
        item.click()
        self.page.wait_for_timeout(1000)

    def rename_item(self, new_name: str):
        """Rename a clip or folder after opening the Rename option.

        Opens options menu, clicks Rename, enters name, presses Enter.
        """
        self.open_options_menu()
        self.click_menu_item("Rename")

        self.rename_input.wait_for(state="visible", timeout=5000)
        self.rename_input.click()
        self.rename_input.fill(new_name)
        self.rename_input.press("Enter")
        self.page.wait_for_timeout(3000)

    def delete_item(self):
        """Delete a clip or folder via options menu > Delete > confirm.

        Opens options menu, clicks Delete, then confirms.
        """
        self.open_options_menu()
        self.click_menu_item("Delete")
        self.page.wait_for_timeout(1000)
        self.confirm_button.click()
        self.page.wait_for_timeout(3000)

    def create_link_for_item(self):
        """Create a link for a clip or folder via options menu.

        Opens options menu, clicks 'Create Link'. The app may either
        show a confirmation dialog with a 'Create' button or create
        the link immediately without a dialog.
        """
        self.open_options_menu()

        # Create Link may be in an li or a different menu structure
        create_link = self.page.locator(
            "li:has-text('Create Link')"
        ).first
        create_link.wait_for(state="visible", timeout=5000)
        create_link.click()
        self.page.wait_for_timeout(2000)

        # Check if a dialog with a Create/OK button appeared
        create_btn = self.page.locator(
            "button:has-text('Create'), "
            "[class*='modal'] button, "
            ".MuiDialog-root button"
        ).first
        try:
            create_btn.wait_for(state="visible", timeout=3000)
            create_btn.click()
            self.page.wait_for_timeout(2000)
        except Exception:
            # No dialog appeared - link was created immediately
            pass

    def move_clip_to_folder(self):
        """Move a selected clip to an existing folder.

        Clicks 'Move to folder', selects the first available folder
        from the native <select> dropdown, then clicks Move.

        Returns False if no folders are available (select has only the
        disabled placeholder option).
        """
        self.menu_move_to_folder.click()
        self.page.wait_for_timeout(2000)

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
        self.page.wait_for_timeout(1000)

        self.move_button.click()
        self.page.wait_for_timeout(3000)
        self._wait_for_page_ready()
        return True

    # --- Vault operations ---

    def add_to_vault(self):
        """Click the 'Add to Vault' icon on the first visible item."""
        self.add_to_vault_icon.wait_for(state="visible", timeout=10000)
        self.add_to_vault_icon.click()
        self.page.wait_for_timeout(2000)

    def remove_from_vault(self):
        """Click 'Remove from Vault' icon and confirm with 'Yes'."""
        self.remove_from_vault_icon.wait_for(state="visible", timeout=10000)
        self.remove_from_vault_icon.click()
        self.page.wait_for_timeout(1000)

        # Confirm removal
        yes_button = self.page.locator(
            "button:has-text('Yes')"
        ).first
        yes_button.wait_for(state="visible", timeout=5000)
        yes_button.click()
        self.page.wait_for_timeout(2000)

    # --- Share ---

    def share_folder(self, email: str = "test@example.com"):
        """Share a folder via the share icon and email dialog."""
        self.share_icon.click()
        self.page.wait_for_timeout(1000)

        self.email_input.wait_for(state="visible", timeout=10000)
        self.email_input.fill(email)
        self.page.wait_for_timeout(1000)

        self.share_button.click()
        self.page.wait_for_timeout(2000)

    # --- Export ---

    def export_folder(self):
        """Export a folder via the download icon."""
        self.download_icon.click()
        self.page.wait_for_timeout(1000)

        self.export_span.click()
        self.page.wait_for_timeout(2000)

    # --- Search ---

    def search_media(self, query: str):
        """Type a search query in the search input and press Enter."""
        self.search_input.wait_for(state="visible", timeout=10000)
        self.search_input.fill("")
        self.search_input.fill(query)
        self.search_input.press("Enter")
        self.page.wait_for_timeout(3000)
        self._wait_for_page_ready()
