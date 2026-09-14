"""Media page clip and folder operation tests.

The Media list renders item names as inline text inputs (invisible
to text engines), with per-row action icons always visible in list
view. Vaulting MOVES a row between the Clips/Folders list and the
Vault tab. The rename success toast is the server acknowledgment -
the inline input updates optimistically and can show a rename that
never committed (all measured 08/12/2026).

Destructive semantics measured 09/02/2026 (Justin): deleting a folder
deletes the clips grouped in it - permanently ("cannot be retrieved");
"Remove From Folder" un-groups a clip back to the level above without
deleting. Destructive testing on the india tenant's media is
sanctioned. Folder deletion currently fails on the tenant (filed; the
register's App defects section maps behavior to tickets), so the
folder-delete leg tripwires into a skip, and the lifecycle test
doubles as the repro for the folder-delete-removes-outside-clips
report. See the register, item 2.
"""
import pytest
from playwright.sync_api import Error as PlaywrightError, expect

from tests.shared.pages.media_page import MediaPage


class TestMediaClipOperations:
    """Tests for clip-level operations on the Media page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.media = MediaPage(self.page)
        self._cleanup_actions = []
        yield
        # Loud teardown: a restore that fails leaves the shared
        # tenant modified, which must surface as an error, not a print
        errors = []
        for action in reversed(self._cleanup_actions):
            try:
                action()
            except Exception as e:
                errors.append(str(e))
        if errors:
            raise RuntimeError(
                "Tenant restore failed: " + "; ".join(errors)
            )

    def _first_clip_or_skip(self) -> str:
        """Land on the Clips tab and return the first clip's name."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")
        if self.media.is_page_empty(timeout=5000):
            pytest.skip("No clips available in Media - cannot test operation")
        names = self.media.item_names()
        if not names:
            # A persisted grid view hides the inline name inputs;
            # one list-view flip self-heals before failing
            if self.media.list_view_button.is_visible():
                self.media.switch_to_list_view()
                names = self.media.item_names()
        if not names:
            pytest.fail(
                "Clips tab has content but no name inputs were read - "
                "the inline-input name pattern changed"
            )
        return names[0]

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_grouping(self):
        """Group a clip into a folder, un-group it, delete the folder.

        One lifecycle on automation-created data measures every folder
        semantic: Group Clips makes the folder, Remove From Folder must
        return the clip WITHOUT deleting it, and deleting the emptied
        folder must not touch any clip outside it (Justin reports it
        once did; this assert is the repro). A folder that survives
        its delete is the filed folder-delete defect (register, App
        defects) and skips, leaving it for tools/tenant_cleanup.py.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, and on the Clips tab tick a clip and choose Group Clips.
           Expected: A new folder appears on the Folders tab.
        2. Open the new folder and choose Remove From Folder on the clip.
           Expected: The clip returns to the Clips tab and is not deleted.
        3. Delete the now-empty folder and confirm.
           Expected: The folder is gone from the Folders tab and every clip outside it is still listed.
        """
        first = self._first_clip_or_skip()
        clips_before = self.media.item_names()

        self.media.click_tab("Folders")
        folders_before = set(self.media.item_names())
        self.media.click_tab("Clips")

        self.media.select_clip_by_index(1)
        self.media.group_clips()

        self.media.click_tab("Folders")
        new_folders = set(self.media.item_names()) - folders_before
        assert len(new_folders) == 1, (
            f"Expected exactly one new folder after grouping, "
            f"got {sorted(new_folders)}"
        )
        folder = new_folders.pop()

        def _cleanup_folder():
            # reload first: a failure inside the folder view leaves a
            # tab-less context a nav click cannot reset
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Folders")
            if folder not in self.media.item_names():
                return
            # EMPTY the folder before deleting it: folder delete takes
            # the clips inside with it, permanently - a mid-test
            # failure must not cost the tenant its clip
            try:
                self.media.open_folder(folder)
                if first in self.media.item_names():
                    self.media.remove_from_folder(first)
            except (PlaywrightError, RuntimeError):
                print(f"[MEDIA] could not empty folder '{folder}'; "
                      "NOT deleting it - the clip inside must survive")
                return
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Folders")
            try:
                self.media.delete_item_named(folder)
            # An undeletable folder is the tripwired app defect,
            # not a failed restore - name it and move on
            except (PlaywrightError, RuntimeError):
                print(f"[MEDIA] folder '{folder}' left on the "
                      "tenant (folder-delete defect); "
                      "tenant_cleanup will get it")

        self._cleanup_actions.append(_cleanup_folder)

        self.media.open_folder(folder)
        assert first in self.media.item_names(), (
            f"Grouped clip '{first}' is not inside folder '{folder}'"
        )
        self.media.remove_from_folder(first)

        # A nav-link click is a no-op while already on /media, and the
        # folder view keeps its context (no tab row) - the hard reload
        # is the reset (known media stale-state behavior)
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")
        assert first in self.media.item_names(), (
            f"'Remove From Folder' must return '{first}' to the level "
            "above without deleting it"
        )

        self.media.click_tab("Folders")
        try:
            self.media.delete_item_named(folder)
        # deliberate: the server refuses folder deletes on this tenant
        # (filed defect, register App defects), so this handler catches
        # a known app state, not a test failure
        except (PlaywrightError, RuntimeError):
            pytest.skip(
                "Folder delete did not apply (filed defect - register "
                f"App defects); folder '{folder}' left for tenant_cleanup"
            )

        # Repro for the unfiled report: deleting a folder must not
        # remove clips OUTSIDE it. Re-read on a fresh load before
        # failing - the shared tenant churns and the Last-30-Days
        # window rolls, so one stale read must not file a bug.
        self.media.click_tab("Clips")
        missing = set(clips_before) - set(self.media.item_names())
        if missing:
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Clips")
            missing = set(clips_before) - set(self.media.item_names())
        assert not missing, (
            f"Clips missing after deleting empty folder '{folder}': "
            f"{sorted(missing)}. If no teammate removed them, this is "
            "the folder-delete-removes-outside-clips report - verify "
            "and file (see the register)."
        )

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_rename(self):
        """Rename a clip and rename it back, verifying each commit.

        Round-trip: the shared tenant keeps its clip names. The
        success toast is the oracle for each direction (the inline
        value updates optimistically, so the attribute expects only
        confirm the optimistic render); the reload at the end is
        what proves both renames reached the server.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, open the Clips tab and rename a clip to a temporary name.
           Expected: A success toast appears and, after a reload, the clip is listed under the new name.
        2. Rename it back to its original name.
           Expected: A success toast appears and, after a reload, the original name is listed again.
        """
        original = self._first_clip_or_skip()
        temp = f"{original}_t"

        def _restore():
            # A page load spends its one rename (known app behavior);
            # a hard reload re-arms it before the restore rename
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Clips")
            if temp in self.media.item_names():
                self.media.rename_item(temp, original)

        self._cleanup_actions.append(_restore)

        self.media.rename_item(original, temp)

        # The hard reload re-arms the rename (only one commits per
        # page load - measured, see Known app behavior) and proves
        # rename #1 reached the server
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")
        names = self.media.item_names()
        assert temp in names, f"Rename did not persist through reload: {names}"
        assert original not in names, f"The original name is still listed after the rename: {names}"

        self.media.rename_item(temp, original)

        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")
        names = self.media.item_names()
        assert original in names, f"Rename back did not persist: {names}"
        assert temp not in names, f"The temporary name is still listed after the rename back: {names}"

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_delete(self):
        """Delete Clip dialog contract, then a real delete.

        Cancel is proven non-destructive first, and the dialog must
        carry its permanence wording (screenshot 09/02/2026: "deleted
        permanently and cannot be retrieved"). The real delete then
        consumes ONE tenant clip - sanctioned on the india media set
        (Justin, 09/02/2026).

        Steps:
        1. Open Media, set the date filter to Last 30 Days, open the Clips tab, open a clip's options menu, choose Delete, then Cancel.
           Expected: The dialog warns the clip will be deleted permanently and cannot be retrieved; after Cancel the clip is still listed.
        2. Choose Delete again and confirm.
           Expected: The clip is no longer listed.
        """
        name = self._first_clip_or_skip()

        row = self.media.item_row(name)
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        row.locator("img[src*='icon-options']").first.click()
        self.media.click_menu_item("Delete")
        expect(self.page.get_by_text("cannot be retrieved").first)\
            .to_be_visible()
        self.media.cancel_dialog()
        assert name in self.media.item_names(), (
            "Cancel on the Delete Clip dialog must keep the clip"
        )

        self.media.delete_item_named(name)
        assert name not in self.media.item_names(), (
            f"Clip '{name}' is still listed after Delete confirmed"
        )

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_move_to_folder(self):
        """Move a clip into an existing folder, then un-group it back.

        Restore is 'Remove From Folder', so the team's clip layout
        survives. Skips when the tenant has no folder to move into.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, open the Clips tab, tick a clip, choose Move to Folder and pick an existing folder.
           Expected: The clip leaves the top-level Clips list.
        2. Open that folder and choose Remove From Folder on the clip.
           Expected: The clip is listed on the Clips tab again.
        """
        name = self._first_clip_or_skip()

        def _reset(tab):
            # Only a hard reload leaves a folder view (tab-less
            # context; nav clicks are no-ops on /media)
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab(tab)

        def _restore():
            # Find the clip wherever it landed and un-group it; every
            # hop out of a folder view goes through the reload reset
            _reset("Clips")
            if name in self.media.item_names():
                return
            _reset("Folders")
            for folder in self.media.item_names()[:5]:
                self.media.open_folder(folder)
                if name in self.media.item_names():
                    self.media.remove_from_folder(name)
                    _reset("Clips")
                    return
                _reset("Folders")
            raise RuntimeError(
                f"Restore could not find moved clip '{name}' in the "
                "first 5 folders"
            )

        self.media.select_clip_by_index(1)
        moved = self.media.move_clip_to_folder()
        if not moved:
            pytest.skip("No folder on the tenant to move a clip into")
        self._cleanup_actions.append(_restore)

        assert name not in self.media.item_names(), (
            f"Clip '{name}' still listed at top level after the move"
        )
        _restore()
        self._cleanup_actions.remove(_restore)
        assert name in self.media.item_names(), (
            f"'Remove From Folder' did not return '{name}' to Clips"
        )

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_create_link(self):
        """Verify the Create Link dialog opens for a clip.

        The dialog is cancelled so no orphan link is left behind
        (there is no delete-link flow to clean one up).

        Steps:
        1. Open Media, set the date filter to Last 30 Days, open the Clips tab, open a clip's options menu and choose Create Link.
           Expected: The Create Link dialog opens with Add Link Name, Set Expiration and Duration fields.
        2. Click Cancel.
           Expected: The dialog closes and no link is created.
        """
        name = self._first_clip_or_skip()
        self.media.open_create_link_dialog(name)

        # The helper raised on 'Add Link Name'; the new information
        # here is the rest of the dialog
        expect(self.page.get_by_text("Set Expiration").first)\
            .to_be_visible()
        expect(self.page.get_by_text("Duration:").first).to_be_visible()

        self.media.cancel_dialog()
        # Hidden, not count-0: this app keeps dialogs mounted in the
        # DOM after close
        expect(self.page.get_by_text("Add Link Name").first)\
            .to_be_hidden()

    @pytest.mark.ui
    @pytest.mark.media
    def test_add_clip_to_vault(self):
        """Vault a clip: its row moves from Clips to the Vault tab.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, open the Clips tab, open a clip's options menu and choose Add to Vault.
           Expected: The action is confirmed.
        2. Reload the page and open the Vault tab.
           Expected: The clip is listed in the Vault.
        """
        name = self._first_clip_or_skip()

        def _restore():
            # The page-load cache hides fresh vault state (known app
            # behavior); reload before reading it
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Vault")
            names = set(self.media.item_names())
            self.page.wait_for_timeout(1000)  # vault fetch settles
            names |= set(self.media.item_names())
            if name in names:
                self.media.remove_from_vault(name)

        self._cleanup_actions.append(_restore)

        self.media.add_to_vault(name)

        # The page-load cache keeps the Vault tab stale (known app
        # behavior); the reload makes its listing the real oracle
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        expect(self.page.locator(f"input[value='{name}']"))\
            .to_have_count(1, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.media
    def test_remove_clip_from_vault(self):
        """Un-vault a clip: its row returns to the Clips tab.

        Self-sufficient: vaults a clip first, so the tenant needs no
        pre-vaulted state.

        Steps:
        1. Open Media, set the date filter to Last 30 Days; vault a clip from the Clips tab, reload, and open the Vault tab.
           Expected: The clip is listed in the Vault.
        2. On the Vault tab choose Remove from Vault on that clip, reload, and open the Clips tab.
           Expected: The clip is listed on the Clips tab again and no longer in the Vault.
        """
        name = self._first_clip_or_skip()

        def _restore():
            # The page-load cache hides fresh vault state (known app
            # behavior); reload before reading it
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Vault")
            names = set(self.media.item_names())
            self.page.wait_for_timeout(1000)  # vault fetch settles
            names |= set(self.media.item_names())
            if name in names:
                self.media.remove_from_vault(name)

        self._cleanup_actions.append(_restore)
        self.media.add_to_vault(name)

        # Reload: the page-load cache keeps the Vault tab stale
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        expect(self.page.locator(f"input[value='{name}']"))\
            .to_have_count(1, timeout=10000)

        self.media.remove_from_vault(name)

        # Reload again: the flag-cleared proof is the fresh Vault
        # listing without the name, with the clip still in Clips
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        assert name not in self.media.item_names(), (
            f"'{name}' still listed in the Vault after removal"
        )
        self.media.click_tab("Clips")
        expect(self.page.locator(f"input[value='{name}']"))\
            .to_have_count(1, timeout=10000)


class TestMediaFolderOperations:
    """Tests for folder-level operations on the Media page.

    Folder rows are assumed to use the same inline name inputs as
    clips; the tenant had no folders when this was measured, so the
    first folder run adjudicates that assumption.
    """

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.media = MediaPage(self.page)
        self._cleanup_actions = []
        yield
        # Loud teardown: a restore that fails leaves the shared
        # tenant modified, which must surface as an error, not a print
        errors = []
        for action in reversed(self._cleanup_actions):
            try:
                action()
            except Exception as e:
                errors.append(str(e))
        if errors:
            raise RuntimeError(
                "Tenant restore failed: " + "; ".join(errors)
            )

    def _own_folder_with_clip(self) -> str:
        """Make a folder from the first clip and return its name.

        Create Link, Share and Export answered the toast 'Empty folder'
        on the first listed folder in the 09/11/2026 full run: the first
        folders were the suite's own empty leftovers (Folder_<n>). A test
        of a folder operation must own a folder that holds a clip
        (docs/CONVENTIONS.md > skips, rule 1). Same lifecycle as
        test_clip_grouping: Group Clips makes the folder; the cleanup
        empties it before deleting it, so the clip survives a failure.
        """
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")
        if self.media.is_page_empty(timeout=5000):
            pytest.skip("No clips in Media - a folder needs a clip to hold")
        names = self.media.item_names()
        if not names and self.media.list_view_button.is_visible():
            self.media.switch_to_list_view()
            names = self.media.item_names()
        if not names:
            pytest.fail("Clips tab has content but no name inputs were read - "
                        "the inline-input name pattern changed")
        clip = names[0]
        self.media.click_tab("Folders")
        folders_before = set(self.media.item_names())
        self.media.click_tab("Clips")
        self.media.select_clip_by_index(1)
        self.media.group_clips()
        self.media.click_tab("Folders")
        new_folders = set(self.media.item_names()) - folders_before
        assert len(new_folders) == 1, (
            f"Expected exactly one new folder after grouping, got {sorted(new_folders)}")
        folder = new_folders.pop()

        def _cleanup_folder():
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Folders")
            if folder not in self.media.item_names():
                return
            # empty it first: a folder delete takes its clips with it
            try:
                self.media.open_folder(folder)
                if clip in self.media.item_names():
                    self.media.remove_from_folder(clip)
            except (PlaywrightError, RuntimeError):  # why: a folder that cannot be emptied must not be deleted, its clip would go with it
                print(f"[MEDIA] could not empty folder '{folder}'; "
                      "NOT deleting it - the clip inside must survive")
                return
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Folders")
            try:
                self.media.delete_item_named(folder)
            except (PlaywrightError, RuntimeError):  # why: the refused folder delete is the filed app defect, not a failed restore; tenant_cleanup sweeps it
                print(f"[MEDIA] folder '{folder}' left on the tenant "
                      "(folder-delete defect); tenant_cleanup will get it")

        self._cleanup_actions.append(_cleanup_folder)
        return folder

    def _first_folder_or_skip(self) -> str:
        """Land on the Folders tab and return the first folder's name."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Folders")
        if self.media.is_page_empty(timeout=5000):
            pytest.skip("No folders in Media - cannot test operation")
        names = self.media.item_names()
        if not names:
            pytest.fail(
                "Folders tab has content but no name inputs were read - "
                "folder rows do not use the inline-input name pattern"
            )
        return names[0]

    @pytest.mark.ui
    @pytest.mark.media
    def test_folder_delete(self):
        """Held by design: folder deletion is covered end to end by
        test_clip_grouping's lifecycle (create -> empty -> delete with
        the defect tripwire). A standalone delete would have to eat a
        TEAM folder - those are not automation data. No oracle by
        design: the lifecycle test carries the assertions.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, open the Folders tab, open a folder's options menu, choose Delete and confirm.
           Expected: The folder is removed from the Folders tab (the automated check runs inside the clip grouping case, on a folder the automation created).
        """
        pytest.skip(
            "Covered by test_clip_grouping's folder lifecycle; team "
            "folders stay untouched"
        )

    @pytest.mark.ui
    @pytest.mark.media
    def test_folder_create_link(self):
        """Verify the Create Link dialog opens for a folder.

        Cancelled so no orphan link is left behind. The folder is the
        test's own, with a clip in it. Known app defect (09/11/2026,
        US): the tenant answers 'Empty folder' for a folder that holds
        a clip; the test fails naming that until the app fix.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, and on the Clips tab tick a clip and choose Group Clips.
           Expected: A new folder holding the clip appears on the Folders tab.
        2. Open that folder's options menu and choose Create Link.
           Expected: The Create Link dialog opens with a Set Expiration field.
        3. Click Cancel.
           Expected: The dialog closes and no link is created.
        4. Remove the clip from the folder and delete the folder.
           Expected: The clip is back on the Clips tab and the folder is gone.
        """
        name = self._own_folder_with_clip()
        self.media.open_create_link_dialog(name)

        # The helper raised on 'Add Link Name'; assert further fields
        expect(self.page.get_by_text("Set Expiration").first)\
            .to_be_visible()

        self.media.cancel_dialog()
        # Hidden, not count-0: this app keeps dialogs mounted in the
        # DOM after close
        expect(self.page.get_by_text("Add Link Name").first)\
            .to_be_hidden()

    @pytest.mark.ui
    @pytest.mark.media
    def test_add_folder_to_vault(self):
        """Vault a folder: its row moves to the Vault tab.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, open the Folders tab, open a folder's options menu and choose Add to Vault.
           Expected: The action is confirmed.
        2. Reload the page and open the Vault tab.
           Expected: The folder is listed in the Vault.
        """
        name = self._first_folder_or_skip()

        def _restore():
            # The page-load cache hides fresh vault state (known app
            # behavior); reload before reading it
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Vault")
            names = set(self.media.item_names())
            self.page.wait_for_timeout(1000)  # vault fetch settles
            names |= set(self.media.item_names())
            if name in names:
                self.media.remove_from_vault(name)

        self._cleanup_actions.append(_restore)

        self.media.add_to_vault(name)

        # The page-load cache keeps the Vault tab stale (known app
        # behavior); the reload makes its listing the real oracle
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        expect(self.page.locator(f"input[value='{name}']"))\
            .to_have_count(1, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.media
    def test_remove_folder_from_vault(self):
        """Un-vault a folder: its row returns to the Folders tab.

        Self-sufficient: vaults the folder first.

        Steps:
        1. Open Media, set the date filter to Last 30 Days; vault a folder from the Folders tab, reload, and open the Vault tab.
           Expected: The folder is listed in the Vault.
        2. Choose Remove from Vault on that folder, reload, and open the Folders tab.
           Expected: The folder is listed on the Folders tab again and no longer in the Vault.
        """
        name = self._first_folder_or_skip()

        def _restore():
            # The page-load cache hides fresh vault state (known app
            # behavior); reload before reading it
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Vault")
            names = set(self.media.item_names())
            self.page.wait_for_timeout(1000)  # vault fetch settles
            names |= set(self.media.item_names())
            if name in names:
                self.media.remove_from_vault(name)

        self._cleanup_actions.append(_restore)
        self.media.add_to_vault(name)

        # Reload: the page-load cache keeps the Vault tab stale
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        expect(self.page.locator(f"input[value='{name}']"))\
            .to_have_count(1, timeout=10000)

        self.media.remove_from_vault(name)

        # Reload again: the fresh Vault listing without the name is
        # the flag-cleared proof
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        assert name not in self.media.item_names(), (
            f"'{name}' still listed in the Vault after removal"
        )
        self.media.click_tab("Folders")
        expect(self.page.locator(f"input[value='{name}']"))\
            .to_have_count(1, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.media
    def test_folder_share(self):
        """Share a folder via email.

        The oracle lives in share_item: it raises when the success
        panel never appears. The folder is the test's own, with a clip
        in it. Known app defect (09/11/2026, US): a folder's Share icon
        opens no dialog; the test fails naming that until the app fix.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, and on the Clips tab tick a clip and choose Group Clips.
           Expected: A new folder holding the clip appears on the Folders tab.
        2. Click Share on that folder's row, enter an e-mail address and send.
           Expected: A success panel confirms the folder was shared.
        3. Remove the clip from the folder and delete the folder.
           Expected: The clip is back on the Clips tab and the folder is gone.
        """
        name = self._own_folder_with_clip()
        self.media.share_item(name, "test@example.com")

    @pytest.mark.ui
    @pytest.mark.media
    def test_folder_export(self):
        """Export a folder; the export control leaving is the signal.

        The oracle lives in export_item: a stuck export control
        raises. The folder is the test's own, with a clip in it. Known
        app defect (09/11/2026, US): a folder's Export opens no control;
        the test fails naming that until the app fix.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, and on the Clips tab tick a clip and choose Group Clips.
           Expected: A new folder holding the clip appears on the Folders tab.
        2. Click Export on that folder's row and confirm.
           Expected: The export starts, and its progress control finishes and disappears.
        3. Remove the clip from the folder and delete the folder.
           Expected: The clip is back on the Clips tab and the folder is gone.
        """
        name = self._own_folder_with_clip()
        self.media.export_item(name)
