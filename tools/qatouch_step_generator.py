#!/usr/bin/env python3
"""QA Touch Step Definition Generator.

Generates structured step definitions for all QA Touch test cases that don't
have Playwright automation. Steps are derived from case titles and module
context using pattern-based templates.

Usage:
    python tools/qatouch_step_generator.py generate [--snapshot FILE] [--output-dir DIR] [--dry-run]
    python tools/qatouch_step_generator.py preview --module "Add New Rule"
    python tools/qatouch_step_generator.py stats
    python tools/qatouch_step_generator.py review [--quality low] [--module NAME] [--format markdown]
    python tools/qatouch_step_generator.py seed-nav [--output FILE]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
SNAPSHOTS_DIR = CONFIG_DIR / "qatouch_snapshots"
MAPPING_FILE = CONFIG_DIR / "qatouch_case_mapping.json"
NAV_CONTEXT_FILE = CONFIG_DIR / "module_nav_context.json"
DEFAULT_OUTPUT_DIR = ROOT / "tests" / "steps" / "manual"

# ── Module area classification keywords ──────────────────────────────────

NAV_AREA_KEYWORDS: dict[str, list[str]] = {
    "admin": [
        "admin", "site detail", "site actions", "site name", "sites",
        "user", "role", "webhook", "channel", "integration",
        "audit trail", "system log", "license", "permission",
        "storage", "general", "rules", "delete user", "add new user",
        "add user", "edit user", "users landing", "users interaction",
        "users/roles", "role assignment", "role card", "role dropdown",
        "role filter", "role selection", "role switching", "roles",
        "access control", "group permissions", "deployment", "reboot",
        "configuration", "settings",
    ],
    "views": [
        "view", "camera", "grid", "tile", "drag", "layout",
        "fullscreen", "playback", "ptz", "sequence", "bookmark",
        "audio", "snapshot", "overlay", "video", "share live",
        "devices tab", "my views", "empty grid", "hover control",
        "live playback", "archive", "left navigation - views",
        "navigation - views", "page refresh - views",
        "navigation highlight - views", "remove video",
    ],
    "search": [
        "search", "category", "zone", "person", "vehicle",
        "description", "duration", "time range", "custom date",
        "line", "date search", "date & time", "date picker",
        "more filters", "reset search", "shared search",
        "camera search", "search in camera",
    ],
    "maps": [
        "map", "google maps", "static map", "validation - maps",
        "permissions - maps",
    ],
    "events": [
        "event", "intrusion", "fire-smoke", "aggression",
        "loitering", "occupancy", "entry-exit", "workplace safety",
        "acknowledgement", "pin/unpin", "pinned clips",
        "landing page - events",
    ],
    "media": [
        "media", "clip", "vault", "folder", "export",
        "group clips", "review pinned", "move to folder",
        "rename", "create link", "share - media",
        "navigation - media", "re-login - media",
        "tabs - media",
    ],
    "insights": [
        "insight", "widget", "dashboard", "preset", "report",
        "graph", "create new", "dashlet", "left navigation - insights",
        "tabs - insights", "page refresh - insights",
    ],
    "notifications": [
        "notification", "mute", "popup notification",
    ],
    "login": [
        "login", "logout", "authentication", "password",
        "session", "re-login", "forgot password", "multi-factor",
        "security", "token",
    ],
    "lpr": [
        "lpr", "license plate", "plate recognition",
    ],
}

# ── Title classification patterns ────────────────────────────────────────

# Pattern order: most specific first, broadest last.  First match wins.
CLASSIFICATION_PATTERNS: list[tuple[str, re.Pattern]] = [
    # ── Highly specific (multi-word phrases) ──────────────────────────
    ("field_input", re.compile(
        r"(?:field\s+(?:accept|does|handle|trim|cannot|enforce)|input\s+field|placeholder|character\s+limit"
        r"|does\s+not\s+(?:allow|accept)|leading\s+and\s+trailing|only\s+spaces)",
        re.I)),
    ("logging_audit", re.compile(
        r"(?:is\s+logged\b|action\s+is\s+logged|mark\s+all\s+as\s+read)",
        re.I)),
    ("drawing_zone", re.compile(
        r"(?:draw(?:ing|n)\s+|anchor\s+point"
        r"|(?<!ptz\s)(?<!PTZ\s)direction(?:al)\s+(?:arrow|line|up|down|left|right)"
        r"|line\s+cross|crossing\s+detect|zone\s+categor)",
        re.I)),
    ("chat_message", re.compile(
        r"(?:chat\b|(?<!error\s)(?<!camera\s)(?<!alert\s)(?<!warning\s)message\b"
        r"|send\s+(?:message|text)|chronolog|enter\s+key)",
        re.I)),
    ("schedule_time", re.compile(
        r"(?:schedule|timeout|dwell|calendar)",
        re.I)),
    ("performance_resilience", re.compile(
        r"(?:performance|concurrent|rapid|simultaneous|recovery|crash|cpu|memory|utiliz|slowdown|idle)",
        re.I)),

    # ── Domain-specific (media, buttons, config, drawing) ─────────────
    ("playback_media", re.compile(
        r"(?:playback|archive\s+(?:state|mode)|video\s+(?:stream|enter|playback)|(?<!time\s)frame\b|rewind|forward\b|backward\b"
        r"|pause\b|play\b|mute\b|volume|audio|stream(?:ing)?|fullscreen|record(?:ing|ed)?|(?<!link\s)preview)",
        re.I)),
    ("button_control", re.compile(
        r"(?:button|(?<!ptz\s)arrow|slider\b|(?<!access\s)(?<!quality\s)control\b|zoom)",
        re.I)),
    ("configure_set", re.compile(
        r"(?:configur|set(?:s|ting)?(?:\s+\w)|enabl|disabl|assign|unassign|suspend|reboot|initiat)",
        re.I)),
    ("ui_integrity", re.compile(
        r"(?:overlap|truncat|aligned|fit(?:s)?\s+within|distortion|break\b|render|broken|responsive"
        r"|width|contrast|resolution|coexist|empty\s+state|gracefully|stacked)",
        re.I)),

    # ── Original broad patterns ───────────────────────────────────────
    ("element_visibility", re.compile(
        r"(?:is\s+)?(?:visible|present|displayed|shown|rendered|appears|exists|accessible|available"
        r"|options?\b|menu\b|labels?\b|overlay|indicator|badge|crown|icons?\b|tooltip"
        r"|name\b|details?\b|format\b|key\b|row\b|columns?\b|headers?\b|convention)",
        re.I)),
    ("element_state", re.compile(
        r"(?:is\s+)?(?:enabled|disabled|checked|unchecked|selected|active|inactive|highlighted"
        r"|focused|focusable|readonly|editable|clickable|focus\b)",
        re.I)),
    ("navigation", re.compile(
        r"(?:loads?|opens?|navigat|redirect|land(?:s|ing)|launch)",
        re.I)),
    ("create", re.compile(
        r"(?:creat|add(?:s|ing)?(?:\s+new)?|generat|upload|insert)",
        re.I)),
    ("edit", re.compile(
        r"(?:edit|updat|modif|renam|chang)",
        re.I)),
    ("delete", re.compile(
        r"(?:delet|remov|discard|clear(?:s|ing)?(?:\s+all)?)",
        re.I)),
    ("search_filter", re.compile(
        r"(?:search|filter|sort|find|query|pagination|paginate|reorder)",
        re.I)),
    ("error_validation", re.compile(
        r"(?:error|invalid|fail|reject|block|prevent|mismatch|validation|mandatory|required field"
        r"|not\s+accepted|cannot\s+be\s+applied)",
        re.I)),
    ("data_display", re.compile(
        r"(?:display|show(?:s|ing)?|reflect|count|total|number|list|populate|contain|include"
        r"|accuracy|matches|consistent|aggregat|quantity)",
        re.I)),
    ("interaction", re.compile(
        r"(?:click|toggle|expand|collapse|scroll|drag|drop|hover|select|switch|tab|resize|close|open(?:s)?(?:\s+panel)?"
        r"|cancel|pin(?:ned|ning)?|trap(?:ped)?)",
        re.I)),
    ("persistence", re.compile(
        r"(?:persist|retain|save|remember|maintain|preserve|restore|survive)",
        re.I)),
    ("data_transfer", re.compile(
        r"(?:export|download|import|share|copy|link|csv)",
        re.I)),
    ("auth", re.compile(
        r"(?:login|logout|authenticat|session|permission|role|access|mfa|password|token|credential)",
        re.I)),
    ("reset_default", re.compile(
        r"(?:reset|default|revert|undo|rollback|refresh)",
        re.I)),
]

# ── Step templates ───────────────────────────────────────────────────────

STEP_TEMPLATES: dict[str, list[dict]] = {
    "element_visibility": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Wait for the page to fully render", "expected": "All page elements are loaded (no spinners or skeleton loaders)"},
        {"n": 4, "action": "Scroll to the area where {subject} should appear", "expected": "The relevant section of the page is in view"},
        {"n": 5, "action": "Locate {subject} on the page", "expected": "{subject} is visible on the page"},
        {"n": 6, "action": "Verify {subject} {predicate}", "expected": "{subject} {predicate}"},
    ],
    "element_state": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Wait for the page to fully render", "expected": "All page elements are loaded"},
        {"n": 4, "action": "Locate {subject} on the page", "expected": "{subject} is visible"},
        {"n": 5, "action": "Inspect the current state of {subject}", "expected": "{subject} {predicate}"},
        {"n": 6, "action": "Verify no console errors or unexpected behavior", "expected": "No errors in the browser console related to {subject}"},
    ],
    "navigation": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{action_phrase}", "expected": "Browser navigates to the target URL"},
        {"n": 3, "action": "Wait for the page to fully load", "expected": "{expected_page} loads successfully without errors"},
        {"n": 4, "action": "Verify the page title or header is correct", "expected": "Page heading or title matches the expected page name"},
        {"n": 5, "action": "Verify the left navigation highlights the correct menu item", "expected": "The corresponding sidebar item is highlighted/active"},
        {"n": 6, "action": "Verify main page content and controls are displayed", "expected": "Key UI elements (buttons, tables, panels) are present"},
        {"n": 7, "action": "Verify the page URL matches the expected route", "expected": "URL path corresponds to the expected page"},
    ],
    "create": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Verify the page displays any existing items", "expected": "Page content loads (list, table, or empty state)"},
        {"n": 4, "action": "Click the create/add button for {subject}", "expected": "Creation form or dialog opens"},
        {"n": 5, "action": "Verify all required form fields are present and empty/default", "expected": "Form fields are displayed with correct labels and placeholders"},
        {"n": 6, "action": "Fill in all required fields with valid test data", "expected": "All fields accept the input without errors"},
        {"n": 7, "action": "Fill in any optional fields if applicable", "expected": "Optional fields accept input"},
        {"n": 8, "action": "Review the filled form for correctness", "expected": "All entered data is displayed correctly in the form"},
        {"n": 9, "action": "Click the Save/Submit/Create button", "expected": "Form is submitted and a success message or indicator appears"},
        {"n": 10, "action": "Verify the newly created {subject} appears in the list or view", "expected": "The new {subject} is visible with the correct data"},
        {"n": 11, "action": "Verify no duplicate entries were created", "expected": "Only one instance of the new {subject} exists"},
    ],
    "edit": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Identify an existing {subject} to edit from the list", "expected": "At least one {subject} is visible in the list"},
        {"n": 4, "action": "Click on the {subject} or its edit button to open the edit form", "expected": "Edit form or dialog opens with pre-populated data"},
        {"n": 5, "action": "Verify the existing data is correctly pre-filled in the form", "expected": "All fields show the current values of the {subject}"},
        {"n": 6, "action": "Modify the target field(s) with new valid data", "expected": "The field(s) accept the new input"},
        {"n": 7, "action": "Verify the changes are reflected in the form before saving", "expected": "Updated values are displayed in the form fields"},
        {"n": 8, "action": "Click the Save/Update button", "expected": "Changes are saved and a success message or indicator appears"},
        {"n": 9, "action": "Verify the updated {subject} reflects the new values in the list or detail view", "expected": "The modified data is displayed correctly"},
        {"n": 10, "action": "Refresh the page and verify the changes persisted", "expected": "Updated values remain after page refresh"},
    ],
    "delete": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Identify the {subject} to be deleted from the list", "expected": "{subject} is visible and identifiable in the list"},
        {"n": 4, "action": "Note the current count of items in the list", "expected": "Current item count is recorded for later comparison"},
        {"n": 5, "action": "Click the delete button or action for the target {subject}", "expected": "A confirmation dialog or prompt appears"},
        {"n": 6, "action": "Verify the confirmation dialog displays the correct item being deleted", "expected": "Dialog shows the name or identifier of the {subject}"},
        {"n": 7, "action": "Click Confirm/Yes/Delete to proceed with the deletion", "expected": "Deletion is processed and a success message appears"},
        {"n": 8, "action": "Verify the {subject} no longer appears in the list", "expected": "{subject} is removed from the list view"},
        {"n": 9, "action": "Verify the item count decreased by one", "expected": "List count reflects the removal"},
        {"n": 10, "action": "Refresh the page and confirm the deletion persisted", "expected": "The deleted {subject} does not reappear after refresh"},
    ],
    "search_filter": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Verify the initial unfiltered list or data set is displayed", "expected": "All items are shown before applying any search or filter"},
        {"n": 4, "action": "Note the total count of items before filtering", "expected": "Initial item count is recorded"},
        {"n": 5, "action": "Locate the search input field or filter controls", "expected": "Search/filter UI is visible and accessible"},
        {"n": 6, "action": "Enter the search criteria or select the filter option for {subject}", "expected": "Search/filter input accepts the value"},
        {"n": 7, "action": "Trigger the search or apply the filter (press Enter or click Apply)", "expected": "The list updates to show filtered results"},
        {"n": 8, "action": "Verify the results match the search/filter criteria", "expected": "All displayed items match the applied criteria"},
        {"n": 9, "action": "Verify the result count updated to reflect the filtered set", "expected": "Item count is less than or equal to the original count"},
        {"n": 10, "action": "Clear the search/filter and verify all items return", "expected": "Clearing the filter restores the full unfiltered list"},
    ],
    "error_validation": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Locate the form, input, or control where validation applies", "expected": "The target input or form is visible"},
        {"n": 4, "action": "Enter invalid data or trigger the error condition for {subject}", "expected": "The invalid input is accepted into the field"},
        {"n": 5, "action": "Attempt to submit or trigger the validation", "expected": "Validation fires on submit or field blur"},
        {"n": 6, "action": "Verify an error message is displayed near the field or at the top of the form", "expected": "A clear, descriptive error message appears"},
        {"n": 7, "action": "Verify the error message text is correct and helpful", "expected": "Error message accurately describes the validation failure"},
        {"n": 8, "action": "Verify the form did not submit or the action was blocked", "expected": "No data was saved; the user remains on the form"},
        {"n": 9, "action": "Correct the invalid input with valid data", "expected": "The error message disappears when valid data is entered"},
        {"n": 10, "action": "Submit with the corrected data and verify success", "expected": "Form submits successfully after correction"},
    ],
    "data_display": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Wait for data to finish loading (spinners, skeleton loaders disappear)", "expected": "All data sections have loaded completely"},
        {"n": 4, "action": "Locate {subject} on the page", "expected": "{subject} is visible in the expected location"},
        {"n": 5, "action": "Verify the data values are populated and not empty or showing placeholders", "expected": "Actual data values are displayed (not 'N/A', 'Loading...', or '---')"},
        {"n": 6, "action": "Verify the data format is correct (numbers, dates, labels, etc.)", "expected": "Data is formatted according to the expected display format"},
        {"n": 7, "action": "Verify {subject} {predicate}", "expected": "{subject} {predicate}"},
        {"n": 8, "action": "Refresh the page and verify the data displays consistently", "expected": "Same data appears after page refresh"},
    ],
    "interaction": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Wait for the page to fully render", "expected": "All interactive elements are loaded and ready"},
        {"n": 4, "action": "Locate the target UI element for {subject}", "expected": "The element is visible and interactive"},
        {"n": 5, "action": "{action_phrase}", "expected": "{expected_result}"},
        {"n": 6, "action": "Verify the UI responded correctly to the interaction", "expected": "Visual feedback confirms the action was processed"},
        {"n": 7, "action": "Verify no unintended side effects occurred", "expected": "Other page elements remain in their expected state"},
    ],
    "persistence": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Note the current state of {subject} before making changes", "expected": "Initial state is observed and recorded"},
        {"n": 4, "action": "Perform the action that changes {subject}", "expected": "Action is completed and change is reflected in the UI"},
        {"n": 5, "action": "Verify the change is displayed correctly before leaving the page", "expected": "Updated state is visible on the current page"},
        {"n": 6, "action": "Refresh the page (F5 or browser reload)", "expected": "Page reloads completely"},
        {"n": 7, "action": "Verify {subject} retained the changes after refresh", "expected": "The change persisted through the page refresh"},
        {"n": 8, "action": "Navigate away to a different page", "expected": "Different page loads successfully"},
        {"n": 9, "action": "Navigate back to {app_page}", "expected": "{app_page} loads"},
        {"n": 10, "action": "Verify {subject} still reflects the saved changes", "expected": "Changes persist after navigating away and back"},
    ],
    "data_transfer": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Locate the export/download/share control for {subject}", "expected": "The transfer action button or link is visible"},
        {"n": 4, "action": "Click the transfer action (export, download, share, copy link, etc.)", "expected": "Transfer operation initiates"},
        {"n": 5, "action": "{action_phrase}", "expected": "Transfer operation progresses without errors"},
        {"n": 6, "action": "Wait for the transfer to complete", "expected": "Success indicator appears (download completes, link copied, share sent)"},
        {"n": 7, "action": "Verify the transferred data is correct and complete", "expected": "Exported/shared data matches the source data"},
        {"n": 8, "action": "Verify the transfer can be accessed at the destination", "expected": "File opens correctly, link resolves, or shared user can access"},
    ],
    "auth": [
        {"n": 1, "action": "Open the application login page", "expected": "Login page loads with username and password fields"},
        {"n": 2, "action": "Log in with the required user role/credentials", "expected": "User is authenticated and redirected to the default page"},
        {"n": 3, "action": "{nav_context}", "expected": "{app_page} loads (or access denied, depending on the test)"},
        {"n": 4, "action": "Verify the access behavior matches the expected permission level", "expected": "User can access or is correctly blocked from the feature"},
        {"n": 5, "action": "{action_phrase}", "expected": "{expected_result}"},
        {"n": 6, "action": "Verify no unauthorized data or controls are exposed", "expected": "Only permitted content is visible to the current user role"},
        {"n": 7, "action": "Log out and verify the session ends cleanly", "expected": "User is redirected to the login page after logout"},
    ],
    "reset_default": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Note the initial/default state of {subject}", "expected": "Default state is observed and recorded"},
        {"n": 4, "action": "Make a change to {subject} (modify a setting, apply a filter, etc.)", "expected": "The change is applied and visible in the UI"},
        {"n": 5, "action": "Verify the modified state is different from the default", "expected": "UI reflects the changed state"},
        {"n": 6, "action": "Perform the reset/revert/default action", "expected": "Reset action is triggered"},
        {"n": 7, "action": "{action_phrase}", "expected": "{expected_result}"},
        {"n": 8, "action": "Verify the state returned to the original default", "expected": "{subject} matches the initial default state recorded in step 3"},
        {"n": 9, "action": "Refresh the page to confirm the reset persisted", "expected": "Default state remains after page refresh"},
    ],
    "configure_set": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Note the current configuration state of {subject}", "expected": "Current setting/state is observed and recorded"},
        {"n": 4, "action": "Locate the configuration control for {subject}", "expected": "The setting, toggle, or configuration UI is visible"},
        {"n": 5, "action": "Change the {subject} setting to the desired value", "expected": "The control accepts the new value/state"},
        {"n": 6, "action": "Verify {subject} {predicate}", "expected": "{subject} reflects the new configuration"},
        {"n": 7, "action": "Save or confirm the configuration if a save action is required", "expected": "Success indicator or confirmation appears"},
        {"n": 8, "action": "Refresh the page and verify the configuration persisted", "expected": "Setting retains the configured value after refresh"},
    ],
    "button_control": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Wait for the page to fully render", "expected": "All interactive elements are loaded and ready"},
        {"n": 4, "action": "Locate the target control: {subject}", "expected": "The button, arrow, slider, or control is visible"},
        {"n": 5, "action": "Click or interact with {subject}", "expected": "{subject} responds to the click/interaction"},
        {"n": 6, "action": "Verify {subject} {predicate}", "expected": "{subject} {predicate}"},
        {"n": 7, "action": "Verify no unintended side effects occurred on the page", "expected": "Other page elements remain in their expected state"},
    ],
    "playback_media": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Navigate to a camera or media source with active video/audio", "expected": "A video feed or media player is displayed"},
        {"n": 4, "action": "Wait for the media to begin loading or streaming", "expected": "Video/audio stream is active or buffering indicator is shown"},
        {"n": 5, "action": "Interact with the playback control for {subject}", "expected": "The media player responds to the action"},
        {"n": 6, "action": "Verify {subject} {predicate}", "expected": "Media player state matches the expected outcome"},
        {"n": 7, "action": "Verify the playback controls remain responsive", "expected": "Other playback buttons and controls are still functional"},
        {"n": 8, "action": "Verify no audio/video artifacts, freezing, or desync occurred", "expected": "Playback is smooth with no quality degradation"},
    ],
    "ui_integrity": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Wait for the page to fully render including all dynamic content", "expected": "All page elements are loaded and positioned"},
        {"n": 4, "action": "Inspect the layout area related to {subject}", "expected": "The target area is visible in the viewport"},
        {"n": 5, "action": "Verify {subject} {predicate}", "expected": "{subject} {predicate}"},
        {"n": 6, "action": "Check that no elements overlap, are clipped, or overflow their containers", "expected": "All UI elements are properly contained within their boundaries"},
        {"n": 7, "action": "Resize the browser window or check at different viewport sizes if applicable", "expected": "Layout adjusts without breaking or creating overlaps"},
        {"n": 8, "action": "Verify text is readable and not truncated unexpectedly", "expected": "All text labels and content are fully legible"},
    ],
    "field_input": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Locate the input field: {subject}", "expected": "The input field is visible and editable"},
        {"n": 4, "action": "Clear any existing value in the field", "expected": "Field is empty"},
        {"n": 5, "action": "Enter a test value into {subject}", "expected": "The field accepts or rejects the input as expected"},
        {"n": 6, "action": "Verify {subject} {predicate}", "expected": "Field displays the correct value, validation, or constraint"},
        {"n": 7, "action": "Tab out of the field or click elsewhere to trigger blur validation", "expected": "Any inline validation fires correctly"},
        {"n": 8, "action": "Verify no unexpected changes occurred to other form fields", "expected": "Other fields retain their values"},
    ],
    "drawing_zone": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Select a camera or canvas area for drawing", "expected": "The drawing surface or camera feed is displayed"},
        {"n": 4, "action": "Activate the drawing tool (line, zone, or region)", "expected": "Drawing mode is active with cursor changed to crosshair or draw icon"},
        {"n": 5, "action": "Draw or modify {subject} on the canvas", "expected": "{subject} {predicate}"},
        {"n": 6, "action": "Verify the drawn element appears correctly on the canvas", "expected": "The line, zone, or region is visible with correct shape and position"},
        {"n": 7, "action": "Save the configuration if required", "expected": "Drawing is saved and persists"},
        {"n": 8, "action": "Verify the drawing is retained after navigating away and back", "expected": "The drawn element remains in place"},
    ],
    "chat_message": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Open or navigate to the chat panel or conversation", "expected": "Chat interface is displayed with message history or empty state"},
        {"n": 4, "action": "Locate the message input field", "expected": "Text input area is visible and focused/focusable"},
        {"n": 5, "action": "Type and send a message related to {subject}", "expected": "{subject} {predicate}"},
        {"n": 6, "action": "Verify the message appears in the conversation", "expected": "Sent message is displayed in the chat thread with correct content"},
        {"n": 7, "action": "Verify the input field is cleared after sending", "expected": "Message input is empty and ready for the next message"},
    ],
    "schedule_time": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Locate the schedule or time configuration for {subject}", "expected": "The schedule/time setting UI is visible"},
        {"n": 4, "action": "Set the schedule or time value for {subject}", "expected": "{subject} {predicate}"},
        {"n": 5, "action": "Save the schedule configuration", "expected": "Success indicator or confirmation appears"},
        {"n": 6, "action": "Verify the saved schedule is displayed correctly in the UI", "expected": "Schedule shows the configured time/days/intervals"},
        {"n": 7, "action": "Refresh the page and verify the schedule persisted", "expected": "Schedule retains the configured values after refresh"},
    ],
    "performance_resilience": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Note the baseline state and performance of the page", "expected": "Page is responsive and functioning normally"},
        {"n": 4, "action": "Apply the stress or load condition to {subject}", "expected": "The condition or load is applied to the system"},
        {"n": 5, "action": "Observe {subject} behavior under the condition", "expected": "{subject} {predicate}"},
        {"n": 6, "action": "Verify the UI remains responsive and usable", "expected": "No freezing, excessive lag, or unresponsive controls"},
        {"n": 7, "action": "Verify the application recovers gracefully once the condition is removed", "expected": "Application returns to normal operation without errors"},
        {"n": 8, "action": "Verify no data loss or corruption occurred", "expected": "All data remains intact and consistent"},
    ],
    "logging_audit": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Perform the action on {subject} that should be logged", "expected": "Action completes successfully"},
        {"n": 4, "action": "Navigate to the audit trail or activity log", "expected": "Log page loads with recent entries"},
        {"n": 5, "action": "Search or filter the log for the action just performed", "expected": "The log entry for the action is found"},
        {"n": 6, "action": "Verify the log entry shows {subject} {predicate}", "expected": "Log entry contains the correct action type, user, and timestamp"},
        {"n": 7, "action": "Verify the log entry details match the action parameters", "expected": "All logged details are accurate and complete"},
    ],
    "default": [
        {"n": 1, "action": "Log in to the application with valid credentials", "expected": "User is logged in and default page loads"},
        {"n": 2, "action": "{nav_context}", "expected": "{app_page} loads without errors"},
        {"n": 3, "action": "Wait for the page to fully render", "expected": "All page elements are loaded"},
        {"n": 4, "action": "Locate the relevant UI area for {subject}", "expected": "The target section or element is visible"},
        {"n": 5, "action": "{action_phrase}", "expected": "{expected_result}"},
        {"n": 6, "action": "Verify no errors or unexpected behavior occurred", "expected": "Page remains stable with no console errors"},
    ],
}


# ── Helper functions ─────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Convert a module name to a safe filename slug."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "unknown"


def classify_module_area(module_name: str) -> str:
    """Classify a module name into an app area using keyword matching."""
    name_lower = module_name.lower()
    for area, keywords in NAV_AREA_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return area
    return "other"


def derive_nav_path(module_name: str, app_area: str) -> str:
    """Derive a navigation path from the module name and area."""
    area_nav = {
        "admin": "Admin",
        "views": "Views",
        "search": "Search",
        "maps": "Maps",
        "events": "Events",
        "media": "Media",
        "insights": "Insights",
        "notifications": "Notifications header area",
        "login": "Login page",
        "lpr": "LPR",
    }
    prefix = area_nav.get(app_area, module_name)
    if app_area == "other":
        return f"Navigate to the {module_name} section"
    if module_name.lower().startswith(prefix.lower()):
        return f"Navigate to {module_name}"
    return f"Navigate to {prefix} > {module_name}"


def derive_app_page(module_name: str, app_area: str) -> str:
    """Derive a human-readable app page name."""
    return f"{module_name} page"


def load_nav_context() -> dict:
    """Load the module navigation context file, or return empty dict."""
    if NAV_CONTEXT_FILE.exists():
        with open(NAV_CONTEXT_FILE, encoding="utf-8") as f:
            return json.load(f).get("modules", {})
    return {}


def get_module_context(module_name: str, nav_context: dict) -> dict:
    """Get navigation context for a module (curated or auto-derived)."""
    if module_name in nav_context:
        ctx = nav_context[module_name]
        return {
            "app_area": ctx.get("app_area", classify_module_area(module_name)),
            "nav_path": ctx.get("nav_path", derive_nav_path(module_name, ctx.get("app_area", "other"))),
            "app_page": ctx.get("app_page", derive_app_page(module_name, ctx.get("app_area", "other"))),
        }
    area = classify_module_area(module_name)
    return {
        "app_area": area,
        "nav_path": derive_nav_path(module_name, area),
        "app_page": derive_app_page(module_name, area),
    }


# ── Title parsing ────────────────────────────────────────────────────────

# Imperative verbs that can START a title: "Cancel Add New User" -> subject="Add New User"
# These are base-form verbs (not 3rd-person). We extract the object after the verb.
IMPERATIVE_VERB_STARTERS: dict[str, str] = {
    "cancel": "is cancelled",
    "close": "closes",
    "open": "opens",
    "edit": "is edited",
    "enable": "is enabled",
    "disable": "is disabled",
    "mute": "is muted",
    "unmute": "is unmuted",
    "clear": "is cleared",
    "search": "returns results",
    "sync": "is synchronized",
    "select": "is selected",
    "deselect": "is deselected",
    "expand": "expands",
    "collapse": "collapses",
    "toggle": "is toggled",
    "reset": "is reset",
    "save": "is saved",
    "delete": "is deleted",
    "remove": "is removed",
    "add": "is added",
    "create": "is created",
    "update": "is updated",
    "drag": "responds to drag",
    "drop": "responds to drop",
    "resize": "is resized",
    "scroll": "scrolls",
    "filter": "returns filtered results",
    "sort": "is sorted",
    "validate": "passes validation",
    "submit": "is submitted",
    "refresh": "refreshes",
    "navigate": "navigates",
    "access": "is accessible",
    "adjust": "is adjusted",
    "apply": "is applied",
    "assign": "is assigned",
    "configure": "is configured",
    "click": "responds to the click",
    "hover": "responds to hover",
    "enter": "accepts the input",
    "upload": "is uploaded",
    "download": "is downloaded",
    "export": "is exported",
    "import": "is imported",
    "pause": "is paused",
    "resume": "resumes",
    "stop": "is stopped",
    "start": "is started",
    "play": "plays",
    "record": "is recorded",
    "seek": "seeks to position",
    "zoom": "is zoomed",
    "rename": "is renamed",
    "move": "is moved",
    "swap": "is swapped",
    "merge": "is merged",
    "restore": "is restored",
    "activate": "is activated",
    "deactivate": "is deactivated",
    "send": "is sent",
    "set": "is set",
    "load": "loads",
    "trigger": "is triggered",
    "display": "is displayed",
    "show": "is shown",
    "hide": "is hidden",
    "highlight": "is highlighted",
    "render": "is rendered",
    "populate": "is populated",
    "connect": "is connected",
    "disconnect": "is disconnected",
}

# 3rd-person singular present tense verbs for splitting "subject VERB rest"
# when copula/modal verbs are absent. Ordered by corpus frequency.
ACTION_VERB_SPLITTERS: list[str] = [
    "displays", "updates", "opens", "remains", "loads", "shows",
    "clears", "allows", "retains", "removes", "accepts", "returns",
    "prevents", "appears", "reflects", "supports", "enables",
    "closes", "matches", "contains", "hides", "creates", "persists",
    "triggers", "blocks", "navigates", "disables", "stops", "redirects",
    "starts", "includes", "populates", "rejects", "disappears", "requires",
    "saves", "moves", "adds", "collapses", "expands", "activates",
    "silences", "resets", "renders", "becomes", "fails",
    "handles", "initiates", "suggests", "occupies", "replaces",
    "generates", "resumes", "advances", "rewinds", "keeps",
    "overrides", "marks", "discards", "switches", "filters",
    "applies", "sets",
]


def parse_title(title: str, *, description: str | None = None) -> dict:
    """Parse a test case title into structured components."""
    original = title.strip()

    # Strip common prefixes
    verb_prefix = None
    cleaned = original
    for prefix in ("Verify that ", "Verify ", "Validate that ", "Validate ",
                    "Confirm that ", "Confirm ", "Ensure that ", "Ensure ",
                    "Check that ", "Check ",
                    "Verifying that ", "Verifying ", "Validating that ",
                    "Validating ", "Confirming that ", "Confirming ",
                    "Ensuring that ", "Ensuring ", "Checking that ", "Checking "):
        if cleaned.startswith(prefix):
            verb_prefix = prefix.strip()
            cleaned = cleaned[len(prefix):]
            break

    # Strip verbose QA Touch preamble patterns
    # "general functionality behaves as expected - <actual description>"
    for preamble in (
        "general functionality behaves as expected - ",
        "general functionality behaves as expected -",
        "general functionality - ",
        "basic functionality - ",
    ):
        if cleaned.lower().startswith(preamble.lower()):
            cleaned = cleaned[len(preamble):].strip()
            break

    # Strip trailing version/duplicate markers like "(2)", "(3)", etc.
    cleaned = re.sub(r"\s*\(\d+\)\s*\.?\s*$", "", cleaned).strip()
    # Strip trailing period
    cleaned = cleaned.rstrip(".")

    # Handle " - " separator (right side = expected result from QA Touch)
    # Uses rfind (last occurrence) to avoid false splits on "Admin - Sites".
    # Guards: right side must be >= 2 words and >= 10 chars.
    dash_expected = None
    if " - " in cleaned:
        idx = cleaned.rfind(" - ")
        left = cleaned[:idx].strip()
        right = cleaned[idx + 3:].strip()
        right = re.sub(r"\s*\(\d+\)\s*\.?\s*$", "", right).strip().rstrip(".")
        if len(right.split()) >= 2 and len(right) >= 10 and left:
            dash_expected = right
            cleaned = left

    # Split compound imperative clauses: "Cancel X and verify Y" -> keep only "Cancel X"
    # The "verify Y" part is redundant when dash_expected or templates already cover it.
    _COMPOUND_RE = re.compile(
        r"^(.+?)\s+and\s+(?:verify|verifying|confirm|confirming|check|checking|ensure|ensuring|validate|validating)\b",
        re.I,
    )
    _compound_m = _COMPOUND_RE.match(cleaned)
    if _compound_m:
        candidate = _compound_m.group(1).strip()
        # Guard: candidate must have at least 2 words
        if len(candidate.split()) >= 2:
            cleaned = candidate

    # Classify the action type BEFORE stripping context clauses.
    # Context clauses (when..., after..., with..., on...) often contain the
    # keywords that determine classification (e.g., "on hover", "when search
    # yields no matches", "after video removal"). Classifying first ensures
    # these keywords are not lost.
    action_type = "default"
    for atype, pat in CLASSIFICATION_PATTERNS:
        if pat.search(cleaned):
            action_type = atype
            break

    # Extract conditional context: "when...", "after...", "if...", "for..."
    context = None
    for pattern in (
        r"\s+(when\s+.+)$",
        r"\s+(after\s+.+)$",
        r"\s+(if\s+.+)$",
        r"\s+(for\s+.+)$",
        r"\s+(with\s+.+)$",
        r"\s+(without\s+.+)$",
        r"\s+(on\s+.+)$",
        r"\s+(during\s+.+)$",
    ):
        m = re.search(pattern, cleaned, re.I)
        if m:
            context = m.group(1).strip()
            cleaned = cleaned[:m.start()].strip()
            break

    # Strip parametrized suffix
    parametrized = None
    m = re.search(r"\s*\((?:parametrized|e\.g\.|incl\.|such as)[^)]*\)", cleaned, re.I)
    if m:
        parametrized = m.group(0).strip()
        cleaned = cleaned[:m.start()].strip()

    # Extract subject + predicate
    # Try to split on "is ", "are ", "can ", "does ", "has "
    subject = cleaned
    predicate = ""
    for splitter in (r"\s+is\s+", r"\s+are\s+", r"\s+can\s+be\s+",
                     r"\s+cannot\s+", r"\s+can\s+", r"\s+does\s+",
                     r"\s+has\s+", r"\s+should\s+", r"\s+must\s+"):
        parts = re.split(splitter, cleaned, maxsplit=1)
        if len(parts) == 2:
            subject = parts[0].strip()
            predicate = parts[1].strip()
            break

    if not predicate:
        # Layer 2: Action verb splitters (handles "camera tile displays live feed")
        for verb in ACTION_VERB_SPLITTERS:
            parts = re.split(rf"\s+{verb}\s+", cleaned, maxsplit=1)
            if len(parts) == 2 and len(parts[0].strip()) > 3:
                subject = parts[0].strip()
                predicate = f"{verb} {parts[1].strip()}"
                break

    if not predicate:
        # Layer 3: Imperative verb at start of title
        # "Cancel Add New User operation" -> subject="Add New User operation", predicate="is cancelled"
        first_word = cleaned.split()[0].lower() if cleaned.split() else ""
        # Also handle gerunds: "Cancelling X" -> base form "cancel" -> lookup
        base_form = first_word
        if first_word.endswith("ing") and len(first_word) > 5:
            # Strip -ing to get base form: cancelling->cancel, updating->updat->update
            base = first_word[:-3]
            if base.endswith("l") and len(base) > 3 and base[-2] == base[-1]:
                base = base[:-1]  # cancelling -> cancel
            elif base.endswith("t") or base.endswith("at"):
                base = base + "e"  # updating -> update, creating -> create
            elif base.endswith("i"):
                base = base[:-1] + "y"  # verifying -> verify
            # Check common -ing -> base mappings
            if base in IMPERATIVE_VERB_STARTERS:
                base_form = base
        if base_form in IMPERATIVE_VERB_STARTERS:
            rest = cleaned[len(first_word):].strip()
            if rest and len(rest) > 3:
                subject = rest
                predicate = IMPERATIVE_VERB_STARTERS[base_form]

    if not predicate:
        # Final fallback: use the full cleaned text as a descriptive phrase
        predicate = cleaned.lower()

    # Subject length safety cap (45 chars, word boundary)
    # Prevents overly long subjects in templates like "Scroll to {subject}"
    _MAX_SUBJECT_LEN = 45
    if len(subject) > _MAX_SUBJECT_LEN:
        words = subject.split()
        truncated = []
        length = 0
        for w in words:
            new_len = length + len(w) + (1 if truncated else 0)
            if new_len > _MAX_SUBJECT_LEN:
                break
            truncated.append(w)
            length = new_len
        if truncated:
            subject = " ".join(truncated)

    return {
        "verb_prefix": verb_prefix,
        "action_type": action_type,
        "subject": subject,
        "predicate": predicate,
        "context": context,
        "parametrized": parametrized,
        "original": original,
        "dash_expected": dash_expected,
    }


# ── Template fix helpers ──────────────────────────────────────────────────

_ACTION_VERBS: dict[str, str] = {
    "configure_set": "Configure",
    "playback_media": "Control playback of",
    "ui_integrity": "Inspect the layout of",
    "field_input": "Enter data in",
    "drawing_zone": "Draw on",
    "chat_message": "Send a message in",
    "schedule_time": "Set the schedule for",
    "performance_resilience": "Stress-test",
    "logging_audit": "Perform the logged action on",
}

_DEFAULT_PREDICATES: dict[str, str] = {
    "element_visibility": "is visible on the page",
    "element_state": "is in the expected state",
    "configure_set": "accepts the new configuration",
    "button_control": "responds to the click",
    "playback_media": "plays back correctly",
    "field_input": "accepts the input value",
    "create": "is created successfully",
    "edit": "is updated successfully",
    "delete": "is removed from the list",
    "interaction": "responds to the user action",
    "search_filter": "returns the expected results",
    "error_validation": "shows the correct error",
    "data_display": "displays the correct data",
    "navigation": "loads successfully",
    "persistence": "is retained after refresh",
    "data_transfer": "transfers successfully",
    "auth": "has the correct access",
    "reset_default": "returns to the default state",
    "drawing_zone": "is drawn correctly on the canvas",
    "chat_message": "appears in the conversation",
    "schedule_time": "saves the configured schedule",
    "performance_resilience": "remains responsive under load",
    "logging_audit": "is recorded in the audit log",
    "ui_integrity": "renders without layout issues",
}


def _build_action_phrase(parsed: dict, subject: str, predicate: str,
                         subject_is_predicate: bool, nav_context: str) -> str:
    """Build a clean action phrase without injecting the raw title."""
    action_type = parsed["action_type"]

    if action_type == "navigation":
        return nav_context

    if action_type in ("interaction", "button_control", "default"):
        if subject_is_predicate:
            return f"Verify {subject} functions correctly"
        if predicate != parsed["original"].lower():
            return f"Test that {subject} {predicate}"
        return f"Interact with {subject}"

    if action_type == "auth":
        if subject_is_predicate:
            return f"Verify {subject} has the correct access"
        return f"Verify {subject} {predicate}"

    if action_type in ("persistence", "reset_default"):
        if subject_is_predicate:
            return f"Verify {subject} is retained correctly"
        return f"Verify {subject} {predicate}"

    # For all other types: build from verb + subject (NO raw title)
    verb = _ACTION_VERBS.get(action_type, "Verify")
    if subject_is_predicate:
        return f"{verb} {subject}"
    return f"{verb} {subject}"


def generate_steps(parsed: dict, module_ctx: dict) -> list[dict]:
    """Generate step definitions from parsed title and module context."""
    template = STEP_TEMPLATES.get(parsed["action_type"], STEP_TEMPLATES["default"])

    nav_context = module_ctx["nav_path"]
    app_page = module_ctx["app_page"]
    subject = parsed["subject"] or "the target element"
    predicate = parsed["predicate"] or "behaves as expected"
    context = parsed["context"]

    # Detect when subject == predicate (no splitter found, both are the same text)
    subject_is_predicate = predicate == subject.lower() or predicate == subject
    if subject_is_predicate:
        # Use template-aware default instead of generic "is displayed as expected"
        predicate = _DEFAULT_PREDICATES.get(parsed["action_type"], "functions as expected")

    # Build action phrase from subject+verb (never inject raw title)
    action_phrase = _build_action_phrase(
        parsed, subject, predicate, subject_is_predicate, nav_context
    )

    # Build expected result
    if subject_is_predicate:
        expected_result = f"{subject.capitalize()} {predicate}"
    else:
        expected_result = f"{subject.capitalize()} {predicate}"
    if context:
        expected_result += f" ({context})"

    # Override with human-written expected result from " - " separator
    if parsed.get("dash_expected"):
        expected_result = parsed["dash_expected"]
        if context:
            expected_result += f" ({context})"

    # Build steps from template
    steps = []
    for t in template:
        step = {
            "n": t["n"],
            "action": t["action"].format(
                nav_context=nav_context,
                app_page=app_page,
                subject=subject,
                predicate=predicate,
                action_phrase=action_phrase,
                expected_result=expected_result,
                expected_page=app_page,
            ),
            "expected": t["expected"].format(
                nav_context=nav_context,
                app_page=app_page,
                subject=subject,
                predicate=predicate,
                expected_result=expected_result,
                expected_page=app_page,
            ),
        }
        steps.append(step)

    # Add context as a precondition step if present - insert after login+nav (pos 2)
    if context and len(steps) >= 2:
        setup_step = {
            "n": 3,
            "action": f"Set up precondition: {context}",
            "expected": f"Precondition is met: {context}",
        }
        steps.insert(2, setup_step)
        # Renumber all steps
        for i, s in enumerate(steps):
            s["n"] = i + 1

    return steps


def assess_quality(parsed: dict, module_ctx: dict, nav_context_curated: bool) -> str:
    """Assess quality of generated steps."""
    if nav_context_curated and parsed["action_type"] != "default":
        return "high"
    if parsed["action_type"] != "default":
        return "medium"
    return "low"


# ── Commands ─────────────────────────────────────────────────────────────

def cmd_seed_nav(args):
    """Auto-seed the module navigation context file."""
    snapshot = _load_snapshot(args.snapshot)
    cases = snapshot["cases"]

    modules = {}
    for c in cases:
        mod = c.get("module name", "Unknown")
        mod_key = c.get("module_key", "")
        if mod not in modules:
            modules[mod] = {"key": mod_key, "count": 0}
        modules[mod]["count"] += 1

    # Build nav context
    nav_modules = {}
    area_counts = defaultdict(int)
    for mod_name, info in sorted(modules.items(), key=lambda x: x[1]["count"], reverse=True):
        area = classify_module_area(mod_name)
        area_counts[area] += 1
        nav_modules[mod_name] = {
            "app_area": area,
            "nav_path": derive_nav_path(mod_name, area),
            "app_page": derive_app_page(mod_name, area),
        }

    output = {
        "_comment": "Module name -> navigation context for step generation. Auto-seeded, manually refinable.",
        "_generated_at": datetime.now().isoformat(timespec="seconds"),
        "_area_distribution": dict(sorted(area_counts.items(), key=lambda x: x[1], reverse=True)),
        "modules": nav_modules,
    }

    out_file = Path(args.output) if args.output else NAV_CONTEXT_FILE
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(nav_modules)} modules to {out_file}")
    print("\nArea distribution:")
    for area, count in sorted(area_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {area:20s} {count:4d} modules")


def cmd_generate(args):
    """Generate step definitions for all unmapped QA Touch cases."""
    snapshot = _load_snapshot(args.snapshot)
    cases = snapshot["cases"]

    # Load Playwright mapping to exclude already-mapped cases
    mapped_case_keys = set()
    if MAPPING_FILE.exists():
        with open(MAPPING_FILE, encoding="utf-8") as f:
            mapping = json.load(f)
        for entry in mapping.get("mappings", {}).values():
            ck = entry.get("case_key", "")
            if ck:
                mapped_case_keys.add(ck)

    include_pw = getattr(args, "include_playwright", False)
    only_pw = getattr(args, "only_playwright", False)
    if include_pw or only_pw:
        print(f"Loaded {len(mapped_case_keys)} Playwright-mapped case keys (INCLUDED)")
    else:
        print(f"Loaded {len(mapped_case_keys)} Playwright-mapped case keys (excluded)")

    # Load or auto-seed nav context
    nav_context = load_nav_context()
    if not nav_context:
        print("No module_nav_context.json found. Auto-seeding...")
        # Build temporary context
        for c in cases:
            mod = c.get("module name", "Unknown")
            if mod not in nav_context:
                area = classify_module_area(mod)
                nav_context[mod] = {
                    "app_area": area,
                    "nav_path": derive_nav_path(mod, area),
                    "app_page": derive_app_page(mod, area),
                }

    # Group cases by module (respecting --include-playwright / --only-playwright)
    module_cases: dict[str, list[dict]] = defaultdict(list)
    skipped = 0
    for c in cases:
        ck = c.get("case_key", "")
        is_pw = ck in mapped_case_keys
        if only_pw and not is_pw:
            skipped += 1
            continue
        if not include_pw and not only_pw and is_pw:
            skipped += 1
            continue
        mod = c.get("module name", "Unknown")
        module_cases[mod].append(c)

    print(f"Cases to generate: {sum(len(v) for v in module_cases.values())} across {len(module_cases)} modules")
    print(f"Skipped (Playwright-mapped): {skipped}")

    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate steps per module
    total_generated = 0
    total_files = 0
    quality_counts = defaultdict(int)
    classification_counts = defaultdict(int)

    for mod_name, mod_cases in sorted(module_cases.items()):
        mod_ctx = get_module_context(mod_name, nav_context)
        area = mod_ctx["app_area"]
        nav_curated = mod_name in nav_context and nav_context.get(mod_name, {}).get("nav_path")

        # Build output path
        area_dir = output_dir / area
        area_dir.mkdir(parents=True, exist_ok=True)
        filename = slugify(mod_name) + ".json"
        filepath = area_dir / filename

        # Check for manual override
        if filepath.exists():
            with open(filepath, encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("source") == "manual_reviewed":
                continue  # Don't overwrite manually reviewed files

        mod_key = mod_cases[0].get("module_key", "") if mod_cases else ""

        # Generate steps for each case
        tests = {}
        for c in mod_cases:
            case_key = c.get("case_key", "")
            title = c.get("case_title", "")
            if not case_key or not title:
                continue

            parsed = parse_title(title)
            steps = generate_steps(parsed, mod_ctx)
            quality = assess_quality(parsed, mod_ctx, bool(nav_curated))

            tests[case_key] = {
                "title": title,
                "case_key": case_key,
                "quality": quality,
                "classification": parsed["action_type"],
                "steps": steps,
            }
            quality_counts[quality] += 1
            classification_counts[parsed["action_type"]] += 1
            total_generated += 1

        if not tests:
            continue

        # Write module file
        file_data = {
            "source": "generated",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "module_name": mod_name,
            "module_key": mod_key,
            "app_area": area,
            "nav_context": mod_ctx["nav_path"],
            "test_file": None,
            "class": None,
            "tests": tests,
        }

        if not args.dry_run:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(file_data, f, indent=2, ensure_ascii=False)

        total_files += 1

    # Write metadata
    metadata = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "snapshot_source": args.snapshot or "latest",
        "total_cases_generated": total_generated,
        "total_modules": total_files,
        "cases_skipped_playwright_mapped": skipped,
        "classification_breakdown": dict(sorted(
            classification_counts.items(), key=lambda x: x[1], reverse=True
        )),
        "quality_stats": dict(sorted(
            quality_counts.items(), key=lambda x: x[1], reverse=True
        )),
    }

    if not args.dry_run:
        meta_path = output_dir / "generated_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Print summary
    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{prefix}Generation complete:")
    print(f"  Cases generated: {total_generated}")
    print(f"  Files written:   {total_files}")
    print("\n  Quality distribution:")
    for q, cnt in sorted(quality_counts.items()):
        pct = cnt / total_generated * 100 if total_generated else 0
        print(f"    {q:10s} {cnt:5d} ({pct:.1f}%)")
    print("\n  Classification breakdown:")
    for cls, cnt in sorted(classification_counts.items(), key=lambda x: x[1], reverse=True):
        pct = cnt / total_generated * 100 if total_generated else 0
        print(f"    {cls:25s} {cnt:5d} ({pct:.1f}%)")


def cmd_stats(args):
    """Show statistics for generated step files."""
    output_dir = DEFAULT_OUTPUT_DIR
    if not output_dir.exists():
        print("No generated step files found. Run 'generate' first.")
        return

    total_generated = 0
    meta_path = output_dir / "generated_metadata.json"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        total_generated = meta.get("total_cases_generated", 0)
        print("=== Generated Step Definition Stats ===")
        print(f"Generated at:    {meta.get('generated_at', 'unknown')}")
        print(f"Snapshot source: {meta.get('snapshot_source', 'unknown')}")
        print(f"Total cases:     {total_generated}")
        print(f"Total modules:   {meta.get('total_modules', 0)}")
        print(f"Playwright skip: {meta.get('cases_skipped_playwright_mapped', 0)}")
        print()
        print("Quality distribution:")
        for q, cnt in meta.get("quality_stats", {}).items():
            print(f"  {q:10s} {cnt}")
        print()
        print("Classification breakdown:")
        for cls, cnt in meta.get("classification_breakdown", {}).items():
            print(f"  {cls:25s} {cnt}")
    else:
        # Count from files
        files = list(output_dir.rglob("*.json"))
        files = [f for f in files if f.name != "generated_metadata.json"]
        for fp in files:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            total_generated += len(data.get("tests", {}))
        print(f"Files: {len(files)}, Cases: {total_generated}")

    # Also show Playwright step stats
    pw_dir = ROOT / "tests" / "steps" / "ui"
    if pw_dir.exists():
        pw_files = list(pw_dir.rglob("*.json"))
        pw_cases = 0
        for fp in pw_files:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            pw_cases += len(data.get("tests", {}))
        print(f"\nPlaywright step files: {len(pw_files)}, Tests: {pw_cases}")
        print(f"TOTAL coverage: {total_generated + pw_cases} cases")


def cmd_preview(args):
    """Preview generated steps for a specific module."""
    if not args.module:
        print("Error: --module is required for preview")
        return

    snapshot = _load_snapshot(args.snapshot)
    cases = snapshot["cases"]

    nav_context = load_nav_context()
    mod_cases = [c for c in cases if c.get("module name") == args.module]

    if not mod_cases:
        print(f"No cases found for module '{args.module}'")
        return

    mod_ctx = get_module_context(args.module, nav_context)
    print(f"Module: {args.module}")
    print(f"Area: {mod_ctx['app_area']}")
    print(f"Nav: {mod_ctx['nav_path']}")
    print(f"Cases: {len(mod_cases)}")
    print()

    for c in mod_cases[:10]:
        title = c.get("case_title", "")
        parsed = parse_title(title)
        steps = generate_steps(parsed, mod_ctx)
        quality = assess_quality(parsed, mod_ctx, args.module in nav_context)

        print(f"  [{quality:6s}] {c.get('case_key', '')}: {title}")
        print(f"           Type: {parsed['action_type']}")
        for s in steps:
            print(f"           Step {s['n']}: {s['action']}")
            print(f"                   -> {s['expected']}")
        print()

    if len(mod_cases) > 10:
        print(f"  ... and {len(mod_cases) - 10} more cases")


def cmd_review(args):
    """Review generated steps by quality or module."""
    output_dir = DEFAULT_OUTPUT_DIR
    if not output_dir.exists():
        print("No generated step files found.")
        return

    files = sorted(output_dir.rglob("*.json"))
    files = [f for f in files if f.name != "generated_metadata.json"]

    target_quality = args.quality
    target_module = args.module

    for fp in files:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)

        mod_name = data.get("module_name", "")
        if target_module and mod_name != target_module:
            continue

        tests = data.get("tests", {})
        filtered = {}
        for ck, td in tests.items():
            if target_quality and td.get("quality") != target_quality:
                continue
            filtered[ck] = td

        if not filtered:
            continue

        if args.format == "markdown":
            print(f"## {mod_name} ({len(filtered)} cases)")
            print()
            for ck, td in filtered.items():
                print(f"### {td['title']} (`{ck}`)")
                print(f"**Quality:** {td.get('quality', 'unknown')} | **Type:** {td.get('classification', 'unknown')}")
                print()
                print("| Step | Action | Expected |")
                print("|------|--------|----------|")
                for s in td.get("steps", []):
                    print(f"| {s['n']} | {s['action']} | {s['expected']} |")
                print()
        else:
            print(f"\n--- {mod_name} ({len(filtered)} cases) ---")
            for ck, td in list(filtered.items())[:5]:
                print(f"  [{td.get('quality','?'):6s}] {ck}: {td['title']}")
                for s in td.get("steps", []):
                    print(f"           Step {s['n']}: {s['action']} -> {s['expected']}")
            if len(filtered) > 5:
                print(f"  ... and {len(filtered) - 5} more")


# ── Utilities ────────────────────────────────────────────────────────────

def _load_snapshot(snapshot_arg: str | None) -> dict:
    """Load the specified or latest snapshot."""
    if snapshot_arg:
        path = Path(snapshot_arg)
    else:
        snapshots = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"))
        if not snapshots:
            print(f"No snapshots found in {SNAPSHOTS_DIR}")
            sys.exit(1)
        path = snapshots[-1]

    print(f"Loading snapshot: {path.name}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="QA Touch Step Definition Generator")
    sub = parser.add_subparsers(dest="command")

    # generate
    gen = sub.add_parser("generate", help="Generate step definitions for unmapped cases")
    gen.add_argument("--snapshot", help="Path to snapshot file (default: latest)")
    gen.add_argument("--output-dir", help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")
    gen.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    gen.add_argument("--include-playwright", action="store_true",
                     help="Include Playwright-mapped cases (normally excluded)")
    gen.add_argument("--only-playwright", action="store_true",
                     help="ONLY generate for Playwright-mapped cases")

    # seed-nav
    seed = sub.add_parser("seed-nav", help="Auto-seed module navigation context")
    seed.add_argument("--snapshot", help="Path to snapshot file")
    seed.add_argument("--output", help=f"Output file (default: {NAV_CONTEXT_FILE})")

    # preview
    prev = sub.add_parser("preview", help="Preview steps for a module")
    prev.add_argument("--module", required=True, help="Module name")
    prev.add_argument("--snapshot", help="Path to snapshot file")

    # stats
    sub.add_parser("stats", help="Show generation statistics")

    # review
    rev = sub.add_parser("review", help="Review generated steps")
    rev.add_argument("--quality", choices=["high", "medium", "low"], help="Filter by quality")
    rev.add_argument("--module", help="Filter by module name")
    rev.add_argument("--format", choices=["text", "markdown"], default="text")

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "seed-nav":
        cmd_seed_nav(args)
    elif args.command == "preview":
        cmd_preview(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "review":
        cmd_review(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
