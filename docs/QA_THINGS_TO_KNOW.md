# QA Things to Know - Soterix Test Automation

This document captures hard-won knowledge about testing patterns, workarounds, and gotchas discovered during test automation development.

 
## My Views - Opening Saved Views

### Problem
Playwright's native `.hover()` doesn't trigger React's mouseover handlers needed to reveal the checkbox on saved views in the My Views panel.

### Solution
Use `ViewsPage.open_saved_view_by_name(view_name)` helper which:
1. Opens My Views panel
2. Uses JavaScript to dispatch `mouseenter`/`mouseover` events (reveals checkbox)
3. Clicks the checkbox to open the view as a tab

### Additional Note
After saving a view and closing its tab via X button, the checkbox state becomes inconsistent. **Workaround:** Refresh the page before reopening the saved view. This clears the tab state while the saved view persists in the backend.

### Example Usage
```python
# Save a view, refresh, then reopen
self.page.locator("img[src*='save']").nth(1).click()
self.page.locator("text=View saved successfully").wait_for(state="visible", timeout=20000)

self.page.reload()
self.page.wait_for_timeout(3000)

self.views.open_saved_view_by_name("MyViewName")
```

---

## Tab Locators
## Table of Contents
1. [Checkbox Interactions](#checkbox-interactions)
2. [Tab Locators](#tab-locators)
3. [Element Visibility Issues](#element-visibility-issues)
4. [JavaScript Workarounds](#javascript-workarounds)
5. [Migration Notes](#migration-notes)

---

## Checkbox Interactions

### Problem: Checkboxes Only Appear on Hover

Many checkboxes in the Soterix UI (cameras, saved views) are hidden until the user hovers over the row. Playwright's `.hover()` method does NOT trigger the checkbox to appear.

**Why:** The UI uses JavaScript event listeners for `mouseenter`/`mouseover` events, not CSS `:hover` pseudo-selectors.

### Solution: JavaScript Event Dispatch
```python
# Trigger hover events via JavaScript
self.page.evaluate(
    """(title) => {
        const span = document.querySelector(`span[title='${title}']`);
        if (span) {
            let parent = span.parentElement;
            for (let i = 0; i < 5; i++) {
                if (parent) {
                    parent.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
                    parent.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                    parent = parent.parentElement;
                }
            }
        }
    }""",

    ## ReCAPTCHA Handling

    ### Current State
    ReCAPTCHA is present on login pages across all environments and blocks automated logins.

    ### Current Workaround: Retry Logic

    The login page object implements retry logic that attempts to work through ReCAPTCHA:
    ```python
    # From login_page.py
When checkbox disappears between hover and click, combine both in single JS:
        """Attempt login with ReCAPTCHA retry logic."""
        for attempt in range(max_retries):
            self.enter_email(email)
            self.enter_password(password)
            self.click_login()
        
            # Wait for either success or ReCAPTCHA challenge
            try:
                # Check for successful login (dashboard element)
                self.page.wait_for_selector(".dashboard", timeout=10000)
                return True
            except:
                # ReCAPTCHA may have appeared, wait and retry
                self.page.wait_for_timeout(5000)
                continue
        return False
    ```

    **Timing Notes:**
    - QA environment is generally slower than other environments
    - Current implementation works but timing could be optimized
    - Allow 60-90 seconds for ReCAPTCHA flows in worst case

    ### Planned Solution: ReCAPTCHA Bypass

    A request has been drafted to whitelist automation accounts (see `docs/RECAPTCHA_BYPASS_PLAN.md`).

    **Bypass Options (in order of preference):**
    1. **Email whitelist** - Skip ReCAPTCHA for automation account emails
    2. **IP whitelist** - Skip ReCAPTCHA from test server IPs
    3. **Secret header** - `X-Automation-Key` header bypasses check
    4. **Environment flag** - Disable ReCAPTCHA on non-prod environments

    **Accounts Requested:**
    | Environment | Account | Role |
    |-------------|---------|------|
    | QA | automation@soterixsystems.com | Admin |
    | QA | automation-supervisor@soterixsystems.com | Supervisor |
    | QA | automation-operator@soterixsystems.com | Operator |
    | Staging | automation-stage@soterixsystems.com | Admin |
    | Production | automation-prod@soterixsystems.com | Operator (read-only) |

    ---

    ## Session Caching

    ### How It Works

    The `AuthHelper` class caches authenticated sessions to avoid repeated logins:
    ```python
    # Session is cached in .session_cache directory
    # Default TTL: 8 hours
    # Cache includes: cookies + localStorage
    ```

    **Cache Location:** `.session_cache/` directory (git-ignored)

    **Cache Format:** JSON files with session data per environment/user

    ### When Sessions Are Reused

    1. Test starts
    2. AuthHelper checks for cached session
    3. If valid (< 8 hours old), injects cookies/localStorage
    4. If expired or missing, performs fresh login
    5. Saves new session to cache

    ### Clearing the Cache

    **When to clear:**
    - After password changes
    - When encountering unexpected auth errors
    - When switching between users
    - After environment configuration changes

    **How to clear:**
    ```powershell
    # Delete entire cache
    Remove-Item -Recurse -Force .session_cache

    # Or delete specific environment
    Remove-Item -Recurse -Force .session_cache/qa*
    ```

    **Programmatic clear:**
    ```python
    # In Python
    import shutil
    shutil.rmtree('.session_cache', ignore_errors=True)
    ```

    ### Future Improvements

    - [ ] Test cache behavior across longer periods
    - [ ] Add session validation before reuse (API health check)
    - [ ] Customer POV testing for session timeout scenarios
    - [ ] Handle session expiry mid-test gracefully

    ---

    ## Multi-Environment Configuration

    ### Supported Environments

    | Environment | URL | SSL Verify | Write Access |
    |-------------|-----|------------|--------------|
    | QA | qa.example.invalid | `false` (self-signed certs) | Yes |
    | Staging | staging.example.invalid | `true` | Yes |
    | Production | app.example.invalid | `true` | Read-only |

    ### Switching Environments

    **PowerShell:**
    ```powershell
    # Set environment
    $env:ENV='qa'      # or 'staging', 'prod'
    $env:BOX='us'      # or 'india'

    # Run tests
    pytest tests/ -v

    # Reset to default
    $env:ENV='qa'; $env:BOX='us'
    ```

    **For QA environment (self-signed certs):**
    ```powershell
    $env:SSL_VERIFY='false'; pytest tests/ -v
    ```

    ### Configuration Files
    config/
    ├── base_config.py      # Shared config logic
    ├── env/
    │   ├── qa.py           # QA environment settings
    │   ├── stage.py        # Staging settings
    │   └── prod.py         # Production settings (read-only)

    ### Environment-Specific Notes

    **QA Environment:**
    - Uses self-signed SSL certificates -> requires `SSL_VERIFY=false`
    - Generally slower than other environments
    - Full write/delete access for testing
    - Site ID: 110, Enterprise ID: 132

    **Staging Environment:**
    - Valid public SSL certificates
    - Write access, no delete access
    - ReCAPTCHA bypass needed for automation

    **Production Environment:**
    - Valid public SSL certificates
    - Read-only access only
    - Never run destructive tests here

    ### Known Gotchas

    - Environment variables persist in terminal session - restart terminal or explicitly reset
    - SSL_VERIFY setting affects all API calls in that session
    - More gotchas to be documented as we expand multi-environment testing

    ---

    ## API vs UI Test Trade-offs

    ### When to Use API Tests

    | Scenario | Why API? |
    |----------|----------|
    | Data validation | Faster, no UI rendering overhead |
    | CRUD operations | Direct verification of backend |
    | Performance-sensitive | Milliseconds vs seconds |
    | Setup/teardown | Create test data quickly |
    | Authentication checks | Verify tokens, sessions, permissions |

    **API Test Advantages:**
    - 10-100x faster than UI tests
    - More stable (no DOM changes)
    - Better error messages
    - Can run in parallel easily

    ### When to Use UI Tests

    | Scenario | Why UI? |
    |----------|----------|
    | User workflows | Validates actual user experience |
    | Visual elements | Layout, styling, visibility |
    | JavaScript interactions | Hover, drag-drop, animations |
    | Integration | Full stack verification |
    | Accessibility | Screen reader, keyboard nav |

    **UI Test Advantages:**
    - Tests what users actually see
    - Catches CSS/JS bugs
    - Validates end-to-end flows
    - Screenshots for debugging

    ### Hybrid Approach (Recommended)
    ```python
    # Use API for setup
    api_client.create_test_user()
    api_client.create_test_site()

    # Use UI for actual test
    ui.login()
    ui.navigate_to_site()
    ui.verify_site_visible()

    # Use API for cleanup
    api_client.delete_test_site()
    api_client.delete_test_user()
    ```

    ### Decision Guide for New Tests

    When tackling new test batches, ask:

    1. **Can this be verified via API?** -> Start with API test
    2. **Does it require visual verification?** -> UI test needed
    3. **Is it a user workflow?** -> UI test, possibly with API setup
    4. **Is it data validation?** -> API test
    5. **Both possible?** -> Write both - API for speed, UI for confidence

    ### Current Test Distribution

    | Type | Count | Purpose |
    |------|-------|---------|
    | API Smoke | 16 | Platform health, data validation |
    | Login UI | 10 | User auth workflows |
    | Views UI | 9 | Visual interactions, drag-drop |

    *Decision guidance will be provided as we tackle each new batch of tests.*

    ---

    ## Drag and Drop Interactions

    ### Working Pattern

    Playwright's built-in drag-to works for the Soterix tile grid:
    ```python
    # Drag camera/view to a specific tile
    source = page.locator("span[title='Camera Name']")
    target = page.locator(".tileItem").nth(0)

    source.drag_to(target)
    page.wait_for_timeout(1000)  # Allow UI to update
    ```

    ### Verified Use Cases

    | Action | Status | Notes |
    |--------|--------|-------|
    | Drag saved view to tile | ✅ Working | `test_drag_view_to_tile` |
    | Drag camera to tile | 🔄 To be tested | Expected to work same way |
    | Drag camera between tiles | 🔄 To be tested | Future test coverage |
    | Drag to reorder | 🔄 To be tested | May need different approach |

    ### Implementation in ViewsPage
    ```python
    def drag_view_to_tile(self, view_name: str, tile_index: int = 0):
        """Drag a saved view from My Views panel to a tile."""
        # Open My Views if not already open
        self.open_my_views_panel()
    
        # Find the view name element
        view_element = self.page.locator(f"span[title='{view_name}']").first
    
        # Find target tile
        tile = self.page.locator(".tileItem").nth(tile_index)
    
        # Perform drag
        view_element.drag_to(tile)
        self.page.wait_for_timeout(1000)
    ```

    ### Edge Cases to Explore

    - [ ] Dragging to occupied tile (should it swap or reject?)
    - [ ] Dragging from one tile to another
    - [ ] Dragging multiple items
    - [ ] Drag cancellation (ESC key)
    - [ ] Touch/mobile drag behavior

    ### Troubleshooting Drag-Drop

    If drag-drop fails:
    1. Ensure source element is visible
    2. Ensure target element is visible and in viewport
    3. Add wait before drag for element stability
    4. Try with `force=True` if element detection issues
    5. Check for overlays blocking the drop target

    ---

    ## Updating This Document

    When you discover a new testing pattern, workaround, or gotcha while writing or stabilizing tests, add a concise entry here so the team can reuse it.

    Guidelines:
    - Add a short header describing the problem.
    - Briefly state the cause and the recommended solution.
    - Include a minimal code snippet (Playwright/pytest) if helpful.
    - Reference any related files (POM, test file, or ticket) using workspace paths.
    - Use commit message: `docs: add <short-description> to QA_THINGS_TO_KNOW.md`.

    Template:
    ```markdown
    ### Short Title
    Problem: One-line description
    Cause: Brief explanation
    Solution: Steps or code snippet
    Files: tests/... or tests/shared/pages/...
    ```

    Small example:
    ```markdown
    ### Hover-triggered checkboxes
    Problem: Checkbox appears only after JS hover events
    Solution: Dispatch `mouseenter`/`mouseover` on parent then click checkbox via JS or locator
    Files: tests/shared/pages/views_page.py
    ```


    ## To Be Documented

    **Completed:**
    - [x] ReCAPTCHA handling patterns
    - [x] Session caching across tests
    - [x] Multi-environment configuration
    - [x] API vs UI test trade-offs
    - [x] Drag and drop to tiles

    **Pending:**
    - [ ] Video playback verification
    - [ ] Fullscreen view testing
    - [ ] Alert/toast message handling
    - [ ] Test data cleanup strategies
    - [ ] Parallel test execution
    - [ ] CI/CD integration patterns

    ---

    *Last updated: January 2025*
    *Maintainer: System QA/QC Lead*
```python
self.page.evaluate(
    """(title) => {
        const span = document.querySelector(`span[title='${title}']`);
        if (!span) return;
        
        # Trigger hover on parents
        let parent = span.parentElement;
        for (let i = 0; i < 5; i++) {
            if (parent) {
                parent.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
                parent.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                parent = parent.parentElement;
            }
        }
        
        # Find and click checkbox (search up DOM tree)
        let el = span;
        for (let level = 0; level < 6; level++) {
            if (el && el.parentElement) {
                el = el.parentElement;
                const checkbox = el.querySelector('.sidebar-custom-checkbox input[type="checkbox"]');
                if (checkbox) {
                    checkbox.click();
                    return;
                }
            }
        }
    }""",
    view_name
)
```

---

## Tab Locators

### Problem: Tab Text Not Visible

Tab names are stored in the `title` attribute of an inner div, NOT as visible text content.

**Wrong:**
```python
tab = page.locator(f"button.tabItem:has-text('{view_name}')")  # Returns empty!
```

**Correct:**
```python
tab = page.locator(f"button.tabItem:has(div[title='{view_name}'])")
```

### Tab HTML Structure
```html
<button class="tabItem">
  <div class="tabInner" title="My View Name">
    <!-- Title in attribute, not text content -->
  </div>
</button>
```

### Hidden Tabs
The application may have hidden/phantom tabs. Always verify expected count:
```python
all_tabs = page.locator("button.tabItem").all()
for i, t in enumerate(all_tabs):
    inner_div = t.locator("div.tabInner").first
    title = inner_div.get_attribute("title") if inner_div.count() > 0 else "no title"
    print(f"Tab {i}: {title}")
```

---

## Element Visibility Issues

### Save Button Outside Viewport

The save button in the tab header may be outside the viewport due to fixed positioning.

**Problem:** `scroll_into_view_if_needed()` doesn't work for fixed elements.

**Solution:** Use JavaScript click:
```python
self.page.evaluate("""
    const saveIcons = document.querySelectorAll("img[src*='save']");
    if (saveIcons.length > 1) {
        saveIcons[1].click();
    }
""")
```

### Element Intercepted by Overlay

When clicking fails with "subtree intercepts pointer events":
1. Try `force=True` parameter
2. If that fails, use JavaScript click
3. Check for modal dialogs or loading overlays

---

## JavaScript Workarounds

### When to Use JS Instead of Playwright

| Scenario | Use JS? | Reason |
|----------|---------|--------|
| Hover-triggered elements | Yes | Playwright hover doesn't trigger JS events |
| Fixed position elements | Yes | Can't scroll into view |
| Elements outside viewport | Yes | Direct DOM manipulation |
| Quick state checks | Yes | Faster than multiple Playwright calls |
| Click intercepted | Maybe | Try `force=True` first |

### Debugging DOM Structure
```python
dom_structure = self.page.evaluate(
    """(selector) => {
        const el = document.querySelector(selector);
        if (!el) return 'not found';
        
        let html = [];
        let current = el;
        for (let i = 0; i < 6; i++) {
            if (current) {
                html.push('Level ' + i + ': <' + current.tagName + ' class=' + current.className + '>');
                current = current.parentElement;
            }
        }
        return html.join(' | ');
    }""",
    "span[title='MyElement']"
)
print(f"DOM: {dom_structure}")
```

## Click Interception Workarounds

### Problem
Some elements (like "All Cameras", save icons) have overlapping elements that intercept pointer events, causing Playwright clicks to timeout.

### Solution
Use `wait_for` + `click(force=True)`:
```python
element = self.page.locator("text=All Cameras").first
element.wait_for(state="visible", timeout=10000)
element.click(force=True)
```

### Affected Elements
- `text=All Cameras` in camera tree
- `img[src*='save']` save icons on tabs


---

## Migration Notes

### Patterns That Don't Migrate Directly from Selenium

| Selenium Pattern | Playwright Equivalent | Notes |
|-----------------|----------------------|-------|
| `ActionChains.move_to_element()` | May need JS events | CSS hover works, JS hover may not |
| `WebDriverWait` | Built-in auto-wait | Usually not needed |
| XPath heavy selectors | CSS + `:has()` | Playwright prefers CSS |
| `driver.execute_script()` | `page.evaluate()` | Same concept, different syntax |

### Test Cases Requiring Special Handling

| Test | Issue | Solution |
|------|-------|----------|
| Camera checkbox selection | Hover-triggered visibility | JS event dispatch |
| Saved view checkbox | Same as camera | JS event dispatch |
| Tab verification | Title in attribute | Use `div[title='...']` selector |
| Save button click | Outside viewport | JS click |

---

## Debugging Tips

### Take Screenshot at Failure Point
```python
self.page.screenshot(path="debug_screenshot.png")
```

### Print Current State
```python
# Tab count
print(f"Tabs: {self.page.locator('button.tabItem').count()}")

# Checkbox count  
print(f"Checkboxes: {self.page.locator('.sidebar-custom-checkbox').count()}")

# Check if element exists
print(f"Found: {self.page.locator('selector').count() > 0}")
```

### Common Assertion Patterns
```python
# Wait for element then assert
element.wait_for(state="visible", timeout=10000)
assert element.count() > 0

# Verify element disappeared
assert element.count() == 0, f"Expected gone, found {element.count()}"
```

---

## To Be Documented

- [ ] ReCAPTCHA handling patterns
- [ ] Session caching across tests
- [ ] Multi-environment configuration
- [ ] API vs UI test trade-offs
- [ ] Drag and drop to tiles
- [ ] Video playback verification

---

*Last updated: January 2025*
*Maintainer: System QA/QC Lead*