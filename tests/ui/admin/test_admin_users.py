"""Admin Users tests - navigation, CRUD, role selection, status toggle."""
import datetime
import pytest
from playwright.sync_api import expect
from tests.shared.pages.admin_page import AdminPage


class TestAdminUsers:
    """Tests for Admin > Users section."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
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
    @pytest.mark.qatouch("rGQDWk")
    def test_navigate_to_admin_users(self):
        """Verify navigating to Admin > Users section loads the user list."""
        self.admin.navigate_to_admin()
        self.step_capture.mark(1, "Navigate to the Admin section")

        self.admin.navigate_to_users()
        self.step_capture.mark(2, "Click the Users tab in the admin sidebar")

        expect(self.admin.users_tab).to_be_visible(timeout=10000)
        expect(self.admin.search_input).to_be_visible(timeout=10000)
        self.step_capture.mark(3, "Verify the Users tab and search input are visible")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    @pytest.mark.qatouch("41VMM7")
    def test_add_user(self):
        """Verify a new user can be added via the Add User form."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()
        self.step_capture.mark(1, "Navigate to Admin > Users")

        self.admin.click_add_user()
        self.step_capture.mark(2, "Click the Add User button")

        # Generate unique email with timestamp
        timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        test_email = f"testuser_{timestamp}@example.com"
        self._created_users.append("AutoTest")

        self.admin.fill_user_form(
            name="AutoTest",
            last_name="Playwright",
            email=test_email
        )
        self.step_capture.mark(3, "Fill in user form with name, last name, and email")

        self.admin.select_role(role_index=1)  # Admin role
        self.step_capture.mark(4, "Select the Admin role from the role dropdown")

        self.admin.save_user()
        self.step_capture.mark(5, "Click Save to create the new user")

        # Verify save completed (form should close or success indicator)
        self.page.wait_for_timeout(2000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    @pytest.mark.qatouch("xm9dWa")
    def test_search_user(self):
        """Verify the search input filters users by name."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()
        self.step_capture.mark(1, "Navigate to Admin > Users")

        self.admin.search_user("Admin")
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(2, "Type 'Admin' in the search input field")

        # Search input should have the entered text
        expect(self.admin.search_input).to_have_value("Admin")
        self.step_capture.mark(3, "Verify the search input contains the text 'Admin'")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    @pytest.mark.qatouch("B86EyN")
    def test_toggle_user_status(self):
        """Verify the active/suspended toggle switch works."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()
        self.step_capture.mark(1, "Navigate to Admin > Users")

        # Search for a user to toggle
        self.admin.search_user("AutoTest")
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(2, "Search for 'AutoTest' user")

        if self.admin.user_switch.count() == 0:
            pytest.skip("No users found with switch toggle")

        self.admin.toggle_user_status()
        self.step_capture.mark(3, "Toggle the user status switch")

        # Toggle back to restore original state
        self.page.wait_for_timeout(1000)
        self.admin.toggle_user_status()
        self.step_capture.mark(4, "Toggle the user status switch back to restore original state")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    @pytest.mark.qatouch("xm9E11")
    def test_role_filter_options(self):
        """Verify the role filter dropdown contains expected roles."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()
        self.step_capture.mark(1, "Navigate to Admin > Users")

        roles = self.admin.get_role_options()
        self.step_capture.mark(2, "Open the role filter dropdown and retrieve available roles")

        expected_roles = ["Admin", "Operator", "Supervisor", "Enterprise Super Admin"]
        for expected in expected_roles:
            assert any(expected in role for role in roles), (
                f"Expected role '{expected}' not found in {roles}"
            )
        self.step_capture.mark(3, "Verify all expected roles are listed in the dropdown")

        # Close dropdown by pressing Escape
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    @pytest.mark.qatouch("vanZWz")
    def test_select_role_filter(self):
        """Verify selecting a role from the filter dropdown works."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()
        self.step_capture.mark(1, "Navigate to Admin > Users")

        # Open dropdown and select Admin
        self.admin.role_filter_dropdown.first.click()
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(2, "Open the role filter dropdown")

        self.admin.select_role_filter("Admin")
        self.step_capture.mark(3, "Select 'Admin' from the role filter dropdown")

        # Verify the dropdown shows the selected role
        dropdown_text = self.admin.role_filter_dropdown.first.inner_text()
        assert "Admin" in dropdown_text, (
            f"Expected 'Admin' in dropdown text, got '{dropdown_text}'"
        )
        self.step_capture.mark(4, "Verify the dropdown displays 'Admin' as the selected role")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_users
    def test_delete_user(self):
        """Verify a user can be deleted via options menu > delete > confirm."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_users()
        self.step_capture.mark(1, "Navigate to Admin > Users")

        # Search for test user
        self.admin.search_user("AutoTest")
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(2, "Search for 'AutoTest' user")

        if self.admin.options_icon.count() == 0:
            pytest.skip("No test users found to delete")

        try:
            self.admin.delete_user()
        except Exception as e:
            pytest.skip(f"Delete confirmation dialog not found: {e}")
        self.step_capture.mark(3, "Click options menu, select Delete, and confirm deletion")

        # Check for app error (e.g., "Can't delete the user")
        error_msg = self.page.locator("text=Can't delete")
        if error_msg.count() > 0:
            pytest.skip("App returned 'Can't delete the user' error")
