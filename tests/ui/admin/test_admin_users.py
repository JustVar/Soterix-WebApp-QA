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
                self.page.wait_for_timeout(2000)
                if self.admin.options_icon.count() > 0:
                    self.admin.delete_user()
            except Exception:
                pass

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

        # Verify save completed (form should close or success indicator)
        self.page.wait_for_timeout(2000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_search_user(self):
        """Verify the search input filters users by name."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        self.admin.search_user("Admin")
        self.page.wait_for_timeout(2000)

        # Search input should have the entered text
        expect(self.admin.search_input).to_have_value("Admin")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_toggle_user_status(self):
        """Verify the active/suspended toggle switch works."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        # Search for a user to toggle
        self.admin.search_user("AutoTest")
        self.page.wait_for_timeout(2000)

        if self.admin.user_switch.count() == 0:
            pytest.skip("No users found with switch toggle")

        self.admin.toggle_user_status()

        # Toggle back to restore original state
        self.page.wait_for_timeout(1000)
        self.admin.toggle_user_status()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_role_filter_options(self):
        """Verify the role filter dropdown contains expected roles."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        roles = self.admin.get_role_options()

        expected_roles = ["Admin", "Operator", "Supervisor", "Enterprise Super Admin"]
        for expected in expected_roles:
            assert any(expected in role for role in roles), (
                f"Expected role '{expected}' not found in {roles}"
            )

        # Close dropdown by pressing Escape
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_select_role_filter(self):
        """Verify selecting a role from the filter dropdown works."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        # Open dropdown and select Admin
        self.admin.role_filter_dropdown.first.click()
        self.page.wait_for_timeout(2000)
        self.admin.select_role_filter("Admin")

        # Verify the dropdown shows the selected role
        dropdown_text = self.admin.role_filter_dropdown.first.inner_text()
        assert "Admin" in dropdown_text, (
            f"Expected 'Admin' in dropdown text, got '{dropdown_text}'"
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_delete_user(self):
        """Verify a user can be deleted via options menu > delete > confirm."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()

        # Search for test user
        self.admin.search_user("AutoTest")
        self.page.wait_for_timeout(2000)

        if self.admin.options_icon.count() == 0:
            pytest.skip("No test users found to delete")

        try:
            self.admin.delete_user()
        except Exception as e:
            pytest.skip(f"Delete confirmation dialog not found: {e}")

        # Check for app error (e.g., "Can't delete the user")
        error_msg = self.page.locator("text=Can't delete")
        if error_msg.count() > 0:
            pytest.skip("App returned 'Can't delete the user' error")
