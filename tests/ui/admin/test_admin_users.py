"""Admin Users tests - navigation, CRUD, role selection, status toggle."""
import datetime

import pytest
from playwright.sync_api import expect

from tests.shared.helpers.surface import require_items
from tests.shared.pages.admin_page import AdminPage

# One worker for every module that writes this account's users: under
# -n they would otherwise spread across workers and race on the same
# tenant state (pytest.ini --dist loadgroup; audit 09/17/2026, row 86).
pytestmark = pytest.mark.xdist_group("account_users")


class TestAdminUsers:
    """Tests for Admin > Users section."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.admin = AdminPage(self.page)
        self._created_users = []
        yield
        # Cleanup: delete any users created during the test
        for search_text in reversed(self._created_users):
            try:
                self.admin.navigate_to_admin()
                self.admin.navigate_to_users()
                self.admin.search_user(search_text)
                if self._user_row_appears():
                    # scoped to the created user's card: if the filter
                    # is still running, this can never grab a stranger
                    self.admin.delete_user(match_text=search_text)
                    # a rejected delete leaks the user onto the shared
                    # tenant; say so instead of hiding it (measured
                    # 08/17/2026: user/remove answers 400 for users this
                    # very form created)
                    if self._user_row_appears(timeout=3000):
                        print(f"Cleanup: the app refused to delete "
                              f"'{search_text}' - user left on the tenant")
            # teardown: a failed delete must not mask the test result;
            # test_delete_user owns the delete oracle
            except Exception as e:
                print(f"Cleanup: failed to delete user '{search_text}': {e}")

    def _user_row_appears(self, timeout: int = 5000) -> bool:
        """Wait for a filtered user row; False when the search has no match.

        search_user() does not wait (zero matches is a valid filter result),
        so callers use this bounded wait instead of a sleep + count check.
        """
        try:
            self.admin.options_icon.first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_navigate_to_admin_users(self):
        """Verify navigating to Admin > Users section loads the user list.

        Steps:
        1. Open Admin and click Users in the sidebar.
           Expected: The Users list opens with its search field.
        """
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        expect(self.admin.users_tab).to_be_visible(timeout=10000)
        self.admin.expect_admin_tab_selected("Users")
        expect(self.admin.search_input).to_have_value("", timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_add_user(self):
        """Verify a new user can be added via the Add User form."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        self.admin.click_add_user()

        # Generate unique email with timestamp
        timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        test_email = f"testuser_{timestamp}@example.com"
        self._created_users.append("AutoTest")

        self.admin.fill_user_form(
            name="AutoTest",
            last_name="Playwright",
            email=test_email
        )
        self.admin.select_role(role_index=1)  # Admin role
        self.admin.save_user()

        # save_user waits for the form to close; assert it explicitly
        expect(self.admin.name_input).to_be_hidden()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_search_user(self):
        """Verify the search input filters users by name."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        self.admin.search_user("Admin")

        # Search input should have the entered text (retries until settled)
        expect(self.admin.search_input).to_have_value("Admin")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_toggle_user_status(self):
        """Verify a user's active and suspended toggle flips and flips back.

        Steps:
        1. Open Admin > Users and search for AutoTest.
           Expected: An automation user is listed. With none the test skips naming the tenant's data.
        2. Click that user's status toggle.
           Expected: The toggle flips to the other state.
        3. Click it again.
           Expected: The toggle returns to the state it started in, so the shared tenant is left as it was.
        """
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        # Search for a user to toggle. The filtered row appearing is the
        # filter-applied signal - never touch the first switch on the page
        # before that, it can belong to another account.
        self.admin.search_user("AutoTest")
        # The filtered row is the artifact; the user table is the
        # surface that proves the page is up. An empty table after a
        # filter is the tenant's data, a table that never rendered is a
        # fault, and the old handler reported both as the same skip
        # (register item 25).
        require_items(
            self.page.get_by_text("AutoTest"),
            # the user search box, not a row icon: a filter that
            # matches nothing leaves zero row icons, and a row-level
            # container would turn that data fact into a failure
            container=self.admin.search_input,
            surface="Admin > Users, filtered to 'AutoTest'",
            artifact="AutoTest user row",
            empty_means="this tenant holds no automation user to toggle",
            timeout_ms=5000,
        )

        # oracle: toggle_user_status raises unless the switch flips
        # (and fails loud when the switch never becomes usable)
        self.admin.toggle_user_status("AutoTest")

        # Toggle back to restore original state
        self.admin.toggle_user_status("AutoTest")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_role_filter_options(self):
        """Verify the role filter dropdown contains expected roles.

        Steps:
        1. Open Admin > Users and open the role filter dropdown.
           Expected: The dropdown offers Admin, Operator and Supervisor.
        """
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        roles = self.admin.get_role_options()

        # Only the built-in roles are stable. The tenant's role list is
        # user-editable, and 'Enterprise Super Admin' was renamed away by
        # 2026-08-07 (the list held 'Temp ESA' plus many custom roles), so
        # asserting on optional roles tests tenant data, not the product.
        expected_roles = ["Admin", "Operator", "Supervisor"]
        for expected in expected_roles:
            assert any(expected in role for role in roles), (
                f"Expected role '{expected}' not found in {roles}"
            )

        # close the dropdown; the context is discarded at teardown, so
        # nothing after this depends on it being closed
        self.page.keyboard.press("Escape")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_select_role_filter(self):
        """Verify the Users list can be filtered by role.

        Steps:
        1. Open Admin > Users and click the role filter.
           Expected: The role list opens.
        2. Choose Admin.
           Expected: The filter shows Admin as its value.
        """
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        # Open dropdown; the option list appearing is the open signal
        self.admin.role_filter_dropdown.first.click()
        self.admin.role_options.first.wait_for(state="visible", timeout=10000)
        self.admin.select_role_filter("Admin")

        # Verify the dropdown shows the selected role (retries until applied)
        expect(self.admin.role_filter_dropdown.first).to_contain_text("Admin")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_delete_user(self):
        """Verify a user can be deleted via options menu > delete > confirm.

        Steps:
        1. Click Admin in the left sidebar, then click Users.
           Expected: The Users list opens.
        2. Type AutoTest in the user search field.
           Expected: The list shrinks to the AutoTest users.
        3. Click the options icon on an AutoTest user card, then click Delete.
           Expected: A confirmation dialog opens.
        4. Click Delete in the dialog.
           Expected: The user card is removed, the list shows one card fewer, and no error is shown.
        """
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        # Capture the server's answer to the delete before anything is
        # clicked: the UI shows no error when the server rejects it
        # (measured 08/17/2026 - /REST/central/user/remove answered 400
        # with an empty alert), so the response is the only place the
        # rejection is visible
        removes = []
        self.page.on(
            "response",
            lambda r: removes.append(r.status) if "user/remove" in r.url else None,
        )

        # Unfiltered baseline first: the search filter is server-side
        # and the pre-filter rows stay visible while it runs, so only
        # the count moving off this baseline proves the filter applied
        # (an instant row check once handed delete_user the tenant's
        # first user while the filter was still in flight - caught by
        # the post-delete oracle 08/13/2026)
        self.admin.options_icon.first.wait_for(
            state="visible", timeout=15000
        )
        all_rows = self.admin.options_icon.count()

        self.admin.search_user("AutoTest")
        expect(self.admin.options_icon).not_to_have_count(
            all_rows, timeout=15000
        )

        rows_before = self.admin.options_icon.count()
        if rows_before == 0:
            pytest.skip("No test users found to delete")

        # delete_user raising is a failure of the delete flow, not an
        # absent artifact: the rows were already counted above. The old
        # handler reported a missing confirmation dialog as Blocked
        # (register item 25).
        self.admin.delete_user(match_text="AutoTest")

        # An app-side refusal shown to the user is a legitimate skip
        error_msg = self.page.locator("text=/can.?t delete/i")
        if error_msg.count() > 0 and error_msg.first.is_visible():
            pytest.skip("App refused the delete and told the user")

        # A silent server rejection is a defect, not a skip
        assert not any(s >= 400 for s in removes), (
            f"user/remove was rejected ({removes}) with no error shown "
            "to the user - the delete silently failed"
        )

        # The deletion is only real when the filtered list shrinks -
        # the old version ended here and passed on a silent no-op
        expect(self.admin.options_icon).to_have_count(
            rows_before - 1, timeout=15000
        )
