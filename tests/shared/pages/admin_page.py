"""Admin Page Object Model.

Shared page object for Admin section navigation, user management,
rules management, and sites/camera group management.
Used by Admin Users, Admin Sites, and Admin Rules test modules.
"""
import datetime
from playwright.sync_api import Page, expect


class AdminPage:
    """Page object for the Admin section."""

    def __init__(self, page: Page):
        self.page = page

        # Navigation
        self.admin_nav_link = page.locator("a[href*='admin']")
        self.users_tab = page.locator("p:text-is('Users')")
        self.sites_tab = page.locator("p:text-is('Sites')")
        self.general_tab = page.locator("p:text-is('General')")
        self.rules_tab = page.locator("p:text-is('Rules')")

        # User management - buttons
        self.add_user_button = page.locator("button.add-btn").first
        self.save_button = page.locator("button.add-btn.save-btn")

        # User form fields
        self.name_input = page.locator("input[name='name'].modalForm-input")
        self.last_name_input = page.locator(
            "input[name='lastName'].modalForm-input"
        )
        self.email_input = page.locator(
            "input[name='mailId'].modalForm-input"
        )
        self.role_dropdown = page.locator(
            "div.MuiStack-root.modalForm-input"
        )

        # Search
        self.search_input = page.locator("input[placeholder='Search']")

        # User row actions
        self.options_icon = page.locator("img[src*='optionIcon']")
        self.delete_icon = page.locator("img[src*='delete-icon']")
        self.delete_confirm = page.locator(
            "button:has-text('Delete'), div.MuiBox-root:text-is('Delete')"
        )

        # User status toggle
        self.user_switch = page.locator(".MuiSwitch-root")

        # Role filter
        self.role_filter_dropdown = page.locator("div[role='combobox']")
        self.role_options = page.locator("li.MuiMenuItem-root")

        # Rules management
        self.add_new_rule_button = page.locator(
            "button:has-text('Add New Rule')"
        )
        self.next_button = page.locator(
            "button.btn-primary:has-text('Next')"
        )
        self.save_rule_button = page.locator("button:has-text('Save')")
        self.rule_search_input = page.locator("input.input-search-bar")
        self.rule_edit_icons = page.locator("img[aria-label='Edit']")
        self.rule_delete_icons = page.locator("img[aria-label='Delete']")
        self.rule_delete_confirm = page.locator(
            "button.btn-primary:has-text('Delete')"
        )
        self.notification_tab = page.locator(
            "button.btn-modalTab:has-text('Notification')"
        )
        self.update_and_close_button = page.locator(
            "button.btn-primary:has-text('Update & Close')"
        )
        self.popup_checkbox = page.locator("input[name='popUp']")
        self.push_checkbox = page.locator("input[name='push']")
        self.mute_notification_icons = page.locator(
            "img[aria-label='Mute Notification']"
        )
        self.canvas = page.locator("canvas.upper-canvas")
        self.site_checkbox_wizard = page.locator(
            "input[type='checkbox']"
        )

        # Sites management
        self.list_view_toggle = page.locator("img[alt='tableIcon']")
        self.grid_view_toggle = page.locator("img[src*='icon-grid']")
        self.online_status_icons = page.locator("img[alt='Online']")
        self.offline_status_icons = page.locator("img[alt='Offline']")
        self.sort_az_icon = page.locator("img[src*='a-to-z-sort']")
        self.sort_za_icon = page.locator("img[src*='z-to-a-sort']")
        self.accordion_icon = page.locator(
            "img[src*='downAccordionIcon']"
        )
        self.create_new_button = page.locator(
            "div.MuiBox-root:has-text('Create New')"
        )
        self.group_name_input = page.locator(
            "input[placeholder='Type here...']"
        )
        self.camera_search_input = page.locator(
            "input#outlined-adornment-search"
        )
        self.camera_checkbox = page.locator(
            "input.PrivateSwitchBase-input[type='checkbox']"
        )
        self.create_button = page.locator(
            "div.MuiBox-root:text-is('Create')"
        )
        self.group_edit_icons = page.locator(
            "img[alt='edit'].edit-icon"
        )
        self.group_delete_icons = page.locator(
            "img[alt='delete'].delete-icon"
        )
        self.group_delete_confirm = page.locator(
            "div.MuiBox-root:text-is('Yes')"
        )

    # --- Navigation ---

    def navigate_to_admin(self):
        """Navigate to the Admin section via sidebar nav link."""
        self.admin_nav_link.click()
        self.page.wait_for_url("**/admin**", timeout=15000)
        self.page.wait_for_timeout(3000)

    def navigate_to_users(self):
        """Click the Users tab in the Admin sidebar.

        Uses .first because 'Users' text appears twice on the Admin page
        (sidebar tab + page header).
        """
        self.users_tab.first.wait_for(state="visible", timeout=10000)
        self.users_tab.first.click()
        self.page.wait_for_timeout(3000)

    def navigate_to_sites(self):
        """Click the Sites tab in the Admin sidebar.

        Uses .first because 'Sites' text appears twice on the Admin page
        (sidebar tab + page header).
        """
        self.sites_tab.first.wait_for(state="visible", timeout=10000)
        self.sites_tab.first.click()
        self.page.wait_for_timeout(3000)

    # --- User CRUD ---

    def click_add_user(self):
        """Click the Add User button to open the form."""
        self.add_user_button.wait_for(state="visible", timeout=10000)
        self.add_user_button.click()
        self.page.wait_for_timeout(2000)

    def fill_user_form(self, name: str, last_name: str, email: str):
        """Fill out the Add User form fields."""
        self.name_input.wait_for(state="visible", timeout=10000)
        self.name_input.fill(name)
        self.last_name_input.fill(last_name)
        self.email_input.fill(email)

    def select_role(self, role_index: int = 1):
        """Open the role dropdown in the form and select a role by index.

        Default index 1 = Admin (0-based in the sitesBox list, but li[2] in Selenium = index 1 here).
        """
        self.role_dropdown.click()
        self.page.wait_for_timeout(2000)

        # The role options appear in #sitesBox container
        options = self.page.locator("#sitesBox li")
        options.nth(role_index).wait_for(state="visible", timeout=10000)
        options.nth(role_index).click()
        self.page.wait_for_timeout(1000)

    def save_user(self):
        """Click the Save button to submit the user form."""
        self.save_button.click()
        self.page.wait_for_timeout(3000)

    def search_user(self, search_text: str):
        """Search for a user by typing in the search input."""
        self.search_input.wait_for(state="visible", timeout=10000)
        self.search_input.clear()
        self.search_input.fill(search_text)
        self.page.wait_for_timeout(2000)

    def delete_user(self):
        """Delete the first user shown in the current view.

        Assumes search has already been performed to filter to the target user.
        Clicks options icon > delete icon > confirm delete.
        """
        self.options_icon.first.wait_for(state="visible", timeout=10000)
        self.options_icon.first.click()
        self.page.wait_for_timeout(1000)

        self.delete_icon.wait_for(state="visible", timeout=5000)
        self.delete_icon.click()
        self.page.wait_for_timeout(2000)

        # Click the confirm Delete button in the dialog - try multiple selectors
        confirm = self.page.get_by_role("button", name="Delete", exact=True)
        if confirm.count() > 0:
            confirm.first.click()
        else:
            # Fallback: broader text match for MUI styled "buttons" (div-based)
            fallback = self.page.locator(
                "div.MuiBox-root:text-is('Delete'), "
                "button:text-is('Delete'), "
                "span:text-is('Delete')"
            )
            if fallback.count() > 0:
                fallback.first.click()
            else:
                # Last resort: click any visible "Delete" text in a dialog
                self.page.locator("[role='dialog'] >> text=Delete").first.click()
        self.page.wait_for_timeout(3000)

    def toggle_user_status(self):
        """Toggle the active/suspended switch for the first user in view."""
        self.user_switch.first.wait_for(state="visible", timeout=10000)
        self.user_switch.first.click()
        self.page.wait_for_timeout(2000)

    # --- Role filter ---

    def get_role_options(self) -> list[str]:
        """Open the role filter dropdown and return available role names."""
        self.role_filter_dropdown.first.click()
        self.page.wait_for_timeout(2000)

        options = self.role_options
        options.first.wait_for(state="visible", timeout=10000)

        role_names = []
        for i in range(options.count()):
            role_names.append(options.nth(i).inner_text().strip())
        return role_names

    def select_role_filter(self, role_name: str):
        """Select a role from the filter dropdown by name."""
        option = self.page.get_by_role(
            "option", name=role_name, exact=True
        )
        option.scroll_into_view_if_needed()
        option.click()
        self.page.wait_for_timeout(2000)

    # --- Rules management ---

    def navigate_to_rules(self):
        """Navigate to Admin > General > Rules."""
        self.general_tab.wait_for(state="visible", timeout=10000)
        self.general_tab.click()
        self.page.wait_for_timeout(2000)
        self.rules_tab.wait_for(state="visible", timeout=10000)
        self.rules_tab.click()
        self.page.wait_for_timeout(3000)

    def click_add_new_rule(self):
        """Click the Add New Rule button to open the rule wizard."""
        self.add_new_rule_button.wait_for(state="visible", timeout=10000)
        self.add_new_rule_button.click()
        self.page.wait_for_timeout(2000)

    def select_rule_type(self, rule_type: str):
        """Select a rule type in the wizard (e.g., 'Entry-Exit', 'Heat Map')."""
        rule_label = self.page.locator(f"p:text-is('{rule_type}')")
        rule_label.wait_for(state="visible", timeout=10000)
        rule_label.click()
        self.page.wait_for_timeout(1000)

    def click_next(self):
        """Click the Next button in the rule creation wizard."""
        self.next_button.wait_for(state="visible", timeout=10000)
        self.next_button.click()
        self.page.wait_for_timeout(2000)

    def select_site_checkbox(self):
        """Toggle the first site checkbox in the rule wizard."""
        self.site_checkbox_wizard.first.wait_for(
            state="visible", timeout=10000
        )
        self.site_checkbox_wizard.first.click()
        self.page.wait_for_timeout(1000)

    def fill_rule_name(self, name: str):
        """Fill the rule name input in the wizard."""
        rule_name_input = self.page.locator(
            "input[placeholder*='name'], input[placeholder*='Name']"
        )
        rule_name_input.wait_for(state="visible", timeout=10000)
        rule_name_input.fill(name)

    def save_rule(self):
        """Click the Save button to save the rule."""
        self.save_rule_button.click()
        self.page.wait_for_timeout(3000)

    def search_rule(self, search_text: str):
        """Search for a rule by name in the rules list."""
        self.rule_search_input.wait_for(state="visible", timeout=10000)
        self.rule_search_input.clear()
        self.rule_search_input.fill(search_text)
        self.page.wait_for_timeout(2000)

    def edit_rule(self, index: int = -1):
        """Click the edit icon for a rule at the given index.

        Default index -1 clicks the last edit icon in the list.
        """
        self.rule_edit_icons.first.wait_for(
            state="visible", timeout=10000
        )
        count = self.rule_edit_icons.count()
        target = count + index if index < 0 else index
        self.rule_edit_icons.nth(target).scroll_into_view_if_needed()
        self.rule_edit_icons.nth(target).click()
        self.page.wait_for_timeout(5000)

    def click_notification_tab(self):
        """Switch to the Notification tab in the rule edit modal."""
        self.notification_tab.wait_for(state="visible", timeout=15000)
        self.notification_tab.scroll_into_view_if_needed()
        self.notification_tab.click()
        self.page.wait_for_timeout(3000)

    def toggle_popup_notification(self):
        """Toggle the popUp notification checkbox."""
        self.popup_checkbox.wait_for(state="attached", timeout=10000)
        self.popup_checkbox.click(force=True)
        self.page.wait_for_timeout(1000)

    def toggle_push_notification(self):
        """Toggle the push notification checkbox."""
        self.push_checkbox.wait_for(state="attached", timeout=10000)
        self.push_checkbox.click(force=True)
        self.page.wait_for_timeout(1000)

    def click_update_and_close(self):
        """Click the Update & Close button in the rule edit modal."""
        self.update_and_close_button.wait_for(
            state="visible", timeout=10000
        )
        self.update_and_close_button.click()
        self.page.wait_for_timeout(3000)

    def delete_rule(self, index: int = -1):
        """Delete a rule at the given index.

        Clicks the delete icon, then confirms the deletion.
        Default index -1 deletes the last rule in the list.
        """
        self.rule_delete_icons.first.wait_for(
            state="visible", timeout=10000
        )
        count = self.rule_delete_icons.count()
        target = count + index if index < 0 else index
        self.rule_delete_icons.nth(target).click()
        self.page.wait_for_timeout(2000)

        self.rule_delete_confirm.wait_for(state="visible", timeout=5000)
        self.rule_delete_confirm.click()
        self.page.wait_for_timeout(3000)

    def mute_rule_notification(self, index: int = -1):
        """Click the mute notification icon for a rule.

        Default index -1 clicks the last mute icon.
        """
        self.mute_notification_icons.first.wait_for(
            state="visible", timeout=10000
        )
        count = self.mute_notification_icons.count()
        target = count + index if index < 0 else index
        self.mute_notification_icons.nth(target).click()
        self.page.wait_for_timeout(2000)

    def draw_line_on_canvas(self, start: tuple, end: tuple):
        """Draw a line on the canvas element using mouse actions.

        Args:
            start: (x_offset, y_offset) from canvas center
            end: (x_offset, y_offset) from canvas center
        """
        box = self.canvas.bounding_box()
        if not box:
            return
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        self.page.mouse.move(cx + start[0], cy + start[1])
        self.page.mouse.down()
        self.page.mouse.move(cx + end[0], cy + end[1])
        self.page.mouse.up()
        self.page.wait_for_timeout(1000)

    # --- Sites management ---

    def search_site(self, search_text: str):
        """Search for a site by name.

        Sites page may use a different search placeholder than Users page.
        Tries multiple selectors.
        """
        site_search = self.page.locator(
            "input[placeholder*='Search']"
        ).first
        site_search.wait_for(state="visible", timeout=10000)
        site_search.clear()
        site_search.fill(search_text)
        self.page.wait_for_timeout(2000)

    def toggle_to_list_view(self):
        """Switch to list view on the Sites page."""
        self.list_view_toggle.wait_for(state="visible", timeout=10000)
        self.list_view_toggle.click()
        self.page.wait_for_timeout(2000)

    def toggle_to_grid_view(self):
        """Switch to grid view on the Sites page."""
        self.grid_view_toggle.wait_for(state="visible", timeout=10000)
        self.grid_view_toggle.click()
        self.page.wait_for_timeout(2000)

    def get_site_statuses(self) -> list[dict]:
        """Return a list of {name, status} for all visible site cards.

        Looks for Online/Offline status icons adjacent to site names.
        """
        statuses = []
        online_count = self.online_status_icons.count()
        offline_count = self.offline_status_icons.count()
        statuses.append({
            "online": online_count,
            "offline": offline_count,
            "total": online_count + offline_count,
        })
        return statuses

    def get_site_versions(self) -> list[dict]:
        """Return a list of {name, version} for visible sites.

        Looks for Version: text near site name elements.
        """
        versions = []
        version_elements = self.page.locator(
            "p:has-text('Version:')"
        )
        for i in range(version_elements.count()):
            text = version_elements.nth(i).inner_text().strip()
            versions.append(text)
        return versions

    def click_site(self, site_name: str):
        """Click a site card to navigate into the site detail view."""
        site = self.page.locator(
            f"p.MuiTypography-root:text-is('{site_name}')"
        )
        site.wait_for(state="visible", timeout=10000)
        site.click()
        self.page.wait_for_timeout(3000)

    def get_camera_names(self) -> list[str]:
        """Return a list of camera names visible in the site detail view."""
        camera_elements = self.page.locator(
            "div.site-card .MuiTypography-root"
        )
        camera_elements.first.wait_for(state="visible", timeout=10000)
        names = []
        for i in range(camera_elements.count()):
            text = camera_elements.nth(i).inner_text().strip()
            if text:
                names.append(text)
        return names

    def click_sort_az(self):
        """Click the A-Z sort icon."""
        self.sort_az_icon.wait_for(state="visible", timeout=10000)
        self.sort_az_icon.click()
        self.page.wait_for_timeout(2000)

    def click_sort_za(self):
        """Click the Z-A sort icon."""
        self.sort_za_icon.wait_for(state="visible", timeout=10000)
        self.sort_za_icon.click()
        self.page.wait_for_timeout(2000)

    def expand_camera_groups(self):
        """Click the accordion icon to expand camera groups section."""
        self.accordion_icon.wait_for(state="visible", timeout=10000)
        self.accordion_icon.click()
        self.page.wait_for_timeout(2000)

    def create_camera_group(self, name: str, camera_search: str):
        """Create a new camera group.

        Clicks Create New, fills name, searches camera, selects first,
        and clicks Create.
        """
        self.create_new_button.wait_for(state="visible", timeout=10000)
        self.create_new_button.click()
        self.page.wait_for_timeout(2000)

        self.group_name_input.wait_for(state="visible", timeout=10000)
        self.group_name_input.fill(name)

        self.camera_search_input.wait_for(state="visible", timeout=10000)
        self.camera_search_input.fill(camera_search)
        self.page.wait_for_timeout(2000)

        if self.camera_checkbox.count() > 0:
            self.camera_checkbox.first.click(force=True)
            self.page.wait_for_timeout(1000)

        self.create_button.wait_for(state="visible", timeout=10000)
        self.create_button.click()
        self.page.wait_for_timeout(3000)

    def edit_camera_group(self, new_name: str):
        """Edit the last camera group's name.

        Clicks last edit icon, clears name, fills new name, and submits.
        """
        self.group_edit_icons.last.wait_for(
            state="visible", timeout=10000
        )
        self.group_edit_icons.last.click()
        self.page.wait_for_timeout(2000)

        self.group_name_input.wait_for(state="visible", timeout=10000)
        self.group_name_input.clear()
        self.group_name_input.fill(new_name)
        self.page.wait_for_timeout(1000)

        # Click Update button (same position as Create button)
        update_btn = self.page.locator(
            "div.MuiBox-root:has-text('Update')"
        )
        if update_btn.count() > 0:
            update_btn.first.click()
        else:
            self.create_button.click()
        self.page.wait_for_timeout(3000)

    def delete_camera_group(self):
        """Delete the last camera group via its delete icon + Yes confirmation."""
        self.group_delete_icons.last.wait_for(
            state="visible", timeout=10000
        )
        self.group_delete_icons.last.click()
        self.page.wait_for_timeout(2000)

        self.group_delete_confirm.wait_for(state="visible", timeout=5000)
        self.group_delete_confirm.click()
        self.page.wait_for_timeout(3000)

    def search_inside_site(self, search_text: str):
        """Search for cameras within a site detail view.

        Uses the search input inside the site detail page to filter cameras.
        """
        site_search = self.page.locator(
            "input[placeholder*='Search']"
        ).first
        site_search.wait_for(state="visible", timeout=10000)
        site_search.clear()
        site_search.fill(search_text)
        self.page.wait_for_timeout(2000)

    # --- Full rule creation wizard ---

    CANVAS_RULES = {"Entry-Exit", "Line Crossing"}
    NON_CANVAS_RULES = {
        "Heat Map", "Intrusion Detection", "Loitering", "Occupancy",
    }

    def select_site_for_rule(self, site_name: str):
        """Select a site from the MuiSelect dropdown in the rule wizard."""
        # Check if site already shown
        site_text = self.page.locator(
            f"text=/{site_name}/i"
        )
        if site_text.count() > 0 and site_text.first.is_visible():
            return

        dropdown = self.page.locator(".MuiSelect-select").first
        dropdown.wait_for(state="visible", timeout=10000)
        dropdown.click()
        self.page.wait_for_timeout(2000)

        site_option = self.page.locator(
            f"li:has-text('{site_name}'), "
            f"div:text-is('{site_name}'), "
            f"span:text-is('{site_name}')"
        ).first
        site_option.wait_for(state="visible", timeout=10000)
        site_option.click()
        self.page.wait_for_timeout(2000)

    def wait_for_snapshots(self, timeout: int = 60000):
        """Wait for camera snapshot images to load in the rule wizard."""
        self.page.locator("img[src*='data:image']").first.wait_for(
            state="visible", timeout=timeout
        )
        self.page.wait_for_timeout(2000)

    def maximize_snapshot(self):
        """Click the maximize button on a camera snapshot."""
        maximize_btn = self.page.locator("img[alt='maximize']")
        maximize_btn.wait_for(state="visible", timeout=10000)
        maximize_btn.click()
        self.page.wait_for_timeout(3000)

        # Wait for enlarged snapshot (at least 2 data:image elements)
        for _ in range(10):
            snaps = self.page.locator("img[src*='data:image']")
            if snaps.count() >= 2:
                break
            self.page.wait_for_timeout(3000)

    def draw_zone_on_canvas(self):
        """Draw a 4-point polygon zone on the canvas element.

        Uses mouse click offsets from canvas center to create a closed polygon,
        then Tab×4 + Enter to confirm the zone.
        """
        self.canvas.wait_for(state="visible", timeout=10000)
        box = self.canvas.bounding_box()
        if not box:
            return

        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        # 4-point polygon clicks with pauses
        offsets = [(-100, -150), (100, 20), (10, -20), (-10, 20)]
        for ox, oy in offsets:
            self.page.mouse.click(cx + ox, cy + oy)
            self.page.wait_for_timeout(1000)

        self.page.wait_for_timeout(3000)

        # Confirm the zone: Tab×4 then Enter
        for _ in range(4):
            self.page.keyboard.press("Tab")
        self.page.wait_for_timeout(1000)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(2000)

    def toggle_mui_switch(self):
        """Toggle the MuiSwitch checkbox used in non-canvas rule types."""
        switch_input = self.page.locator(
            "input[type='checkbox'].MuiSwitch-input, "
            "input[aria-label='ant design']"
        ).first
        switch_input.wait_for(state="attached", timeout=10000)
        switch_input.click(force=True)
        self.page.wait_for_timeout(1000)

    def click_ripple_button(self):
        """Click the MUI ripple button that appears after MuiSwitch toggle."""
        button = self.page.locator(
            "button.MuiButtonBase-root:not([disabled])"
        ).first
        button.wait_for(state="visible", timeout=10000)
        button.click()
        self.page.wait_for_timeout(1000)

    def complete_rule_wizard(
        self, rule_type: str, site_name: str, rule_name: str | None = None
    ):
        """Complete the full rule creation wizard end-to-end.

        Handles both canvas rules (Entry-Exit, Line Crossing) and
        non-canvas rules (Heat Map, Intrusion Detection, Loitering, Occupancy).

        Args:
            rule_type: One of the 6 rule types.
            site_name: Site to select in the wizard.
            rule_name: Optional name for the rule (filled if name input exists).
        """
        # Step 1: Select rule type and click Next
        self.select_rule_type(rule_type)
        self.click_next()

        # Step 2: Select site and camera checkbox, then Next
        self.select_site_for_rule(site_name)
        self.select_site_checkbox()
        self.page.wait_for_timeout(2000)
        self.click_next()

        # Step 3: Configure rule (canvas vs non-canvas)
        if rule_type in self.CANVAS_RULES:
            self.wait_for_snapshots()
            self.maximize_snapshot()
            self.draw_zone_on_canvas()
            # 3 more Next clicks through remaining wizard steps
            for _ in range(3):
                self.click_next()
        else:
            # Non-canvas: toggle switch + ripple button, then advance
            self.toggle_mui_switch()
            self.click_ripple_button()
            self.page.wait_for_timeout(1000)
            # 4 more Next clicks through remaining wizard steps
            for _ in range(4):
                self.click_next()

        # Fill rule name if the wizard has a name field visible
        if rule_name:
            name_input = self.page.locator(
                "input[placeholder*='name'], input[placeholder*='Name']"
            )
            if name_input.count() > 0 and name_input.first.is_visible():
                name_input.first.fill(rule_name)
                self.page.wait_for_timeout(1000)

        # Save
        self.page.wait_for_timeout(3000)
        self.save_rule()
