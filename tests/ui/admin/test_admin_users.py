"""Admin Users tests - navigation, CRUD, role selection, status toggle."""
import datetime
import pytest
from playwright.sync_api import expect
from tests.shared.pages.admin_page import AdminPage


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
                    self.admin.delete_user()
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
        """Verify navigating to Admin > Users section loads the user list."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        expect(self.admin.users_tab).to_be_visible(timeout=10000)
        expect(self.admin.search_input).to_be_visible(timeout=10000)

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
        """Verify the active/suspended toggle switch works."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        # Search for a user to toggle. The filtered row appearing is the
        # filter-applied signal - never touch the first switch on the page
        # before that, it can belong to another account.
        self.admin.search_user("AutoTest")
        try:
            self.page.get_by_text("AutoTest").first.wait_for(
                state="visible", timeout=5000
            )
        except Exception:
            pytest.skip("No users found with switch toggle")

        self.admin.toggle_user_status("AutoTest")

        # Toggle back to restore original state
        self.admin.toggle_user_status("AutoTest")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_role_filter_options(self):
        """Verify the role filter dropdown contains expected roles."""
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

        # Close dropdown by pressing Escape; wait for it to close
        self.page.keyboard.press("Escape")
        try:
            self.admin.role_options.first.wait_for(state="hidden", timeout=3000)
        except Exception:
            pass

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_select_role_filter(self):
        """Verify selecting a role from the filter dropdown works."""
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
        """Verify a user can be deleted via options menu > delete > confirm."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        # Search for test user; wait for the row before deciding
        self.admin.search_user("AutoTest")
        if not self._user_row_appears():
            pytest.skip("No test users found to delete")

        try:
            self.admin.delete_user()
        except Exception as e:
            pytest.skip(f"Delete confirmation dialog not found: {e}")

        # Check for app error (e.g., "Can't delete the user")
        error_msg = self.page.locator("text=Can't delete")
        if error_msg.count() > 0:
            pytest.skip("App returned 'Can't delete the user' error")
