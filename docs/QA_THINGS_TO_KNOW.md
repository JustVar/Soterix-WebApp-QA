# QA things to know

Facts about the app under test, NexaiQ-Core, that a test writer needs.
Each entry states the fact, then what the tests do about it. Wait rules
are in [CONVENTIONS.md](CONVENTIONS.md). For a failed test, read
[FAILURE_TRIAGE.md](FAILURE_TRIAGE.md) first.

## How the app behaves

These are measured facts, not bugs to fix in the tests.

- **The server runs 1 search job at a time.** A second
  `POST /REST/site/search` answers code 400 while the first job runs, from
  any session and any account. The job has no cancel. It frees about 16 s
  after the client stops polling, or when it completes, which takes
  minutes for an analytics scan over a busy site. The searching tests
  share the `account_search` xdist group, and
  `tests/shared/helpers/search_gap.py` spaces them.
- **A session expires fast, and the expiry reads as a locator timeout.**
  The server answers 401 to a live session, the app goes back to
  `/auth/login`, and the next locator waits on the login form. The
  traceback then ends with a `[SESSION]` section. The internal API answers
  status 3113 (`Session expired! Re-login required!`), and the API client
  signs in again once.
- **The rule wizard hides a camera that is at rule capacity.** One
  leftover rule on the test camera makes it vanish from Select Devices for
  every later run. The admin page raises when a delete did not land, and
  `tools/tenant_cleanup.py` removes leftover `AutoTest` rules.
- **`Successfully deleted!` is not a delete.** A bookmark `DELETE` answers
  status 2006 with that text, and the row stays in the list with
  `deletedAt` set. The delete is soft. Gone means `deletedAt > 0`. The
  same applies to any envelope text: check the `code`, then read the list.
- **Group chat is a server setting.** A server without it shows no Create
  Group control at all. The group tests skip with proof on such a server
  and run where the button renders.
- **Toggle controls open and close with the same click.** The chat icon,
  the notification bell, the LPR panel header and the view tabs are
  toggles. Click only when the open marker is absent.
- **The chat search drops a single programmatic input event after it
  opens.** Type key by key with `press_sequentially`, and type again once
  if the text is absent.
- **The live player sometimes shows "The camera failed to load" over a
  frame that renders.** The page objects click the refresh link once. A
  stream that stays down fails loud.
- **A new login is not complete when the URL leaves `/auth/login`.** The
  landing page then runs its session check about 3 s later. A `goto` in
  that time drops the cookie. The `authenticated_page` fixture waits for
  the API to go quiet first.
- **The app keeps hidden copies in the DOM.** Ghost `button.tabItem`
  elements survive a tab close. `.first` on a union can pick a hidden
  element. Filter on visibility, or start from the container.

## Hover-revealed checkboxes

**Problem:** many checkboxes (cameras, saved views) stay hidden until the
user hovers over the row. Playwright's `.hover()` does not always reveal
them.

**Cause:** the UI listens for JavaScript `mouseenter` and `mouseover`
events, not CSS `:hover`. React sometimes attaches the listeners to a
parent that the pointer never crosses.

**Fix, in order:**

1. Try the plain path first. `camera.hover()` then click the checkbox. The
   click waits for the checkbox to appear, so no sleep is needed. This
   works for the camera thumbnails in the Devices panel.
2. If the checkbox never appears, dispatch the hover events with
   JavaScript, then click. `ViewsPage.add_first_camera_via_checkbox` and
   `ViewsPage.open_saved_view_by_name` do this.

## My Views: opening saved views

Reopening a saved view needs the hover-revealed checkbox above, and the
checkbox state becomes inconsistent after you save a view and close its
tab with the X button.

**Fix:** use `ViewsPage.open_saved_view_by_name(view_name)`. For the
inconsistent-state case, reload the page first. The reload clears the tab
state while the saved view persists in the backend.

**Panel-open signal:** the My Views panel shows its Presets / My Views
toggle even when the account has no saved views. Wait for `text=Presets`
to know the panel opened. Thumbnails only exist when saved views exist.

## Tab locators

Tab names are stored in the `title` attribute of an inner div, not as
visible text.

```python
# Wrong: returns empty
tab = page.locator(f"button.tabItem:has-text('{view_name}')")

# Correct
tab = page.locator(f"button.tabItem:has(div[title='{view_name}'])")
```

**Ghost tabs:** after a tab close, the count of `button.tabItem` (and even
`button.tabItem:visible`) stays at 2 while the screen shows 1 tab. Do not
assert a tab count after closing a tab. Assert on the thing you need next
(a success message, a specific tab by title).

## Click interception and viewport issues

Some elements time out on click because an overlay intercepts pointer
events or because the element sits outside the viewport with fixed
positioning. Known cases: `text=All Cameras` in the camera tree,
`img[src*='save']` icons on tabs.

**Escalation ladder, try in order:**

1. A plain `click()`. It waits and scrolls. Most elements need nothing
   else.
2. `click(scroll="none")`. Skips the scroll into view, which itself causes
   interception under sticky headers and lazy loading.
3. `click(force=True)`. Skips the actionability checks.
4. A JavaScript click as the last resort:
   `locator.evaluate("el => el.click()")`.

A JS click bypasses every Playwright check, so pair it with an explicit
wait on the effect (for example the save success message).
`scroll_into_view_if_needed()` does not help for fixed-position elements.

## JavaScript workarounds

| Scenario | Use JS? | Reason |
|----------|---------|--------|
| Hover-triggered elements | Yes | Playwright hover may not reach the React listener |
| Fixed-position elements | Yes | Cannot scroll into view |
| Click intercepted | Last resort | Try `scroll="none"`, then `force=True` first |
| Quick state checks | Rarely | Prefer `expect()`, which retries |

For a failed test you do not need a DOM dump: the saved trace contains the
DOM at every action (`playwright trace snapshot <action-id> snapshot`).

## ReCAPTCHA

ReCAPTCHA is present on the login page. `_handle_recaptcha()` in
`tests/shared/pages/login_page.py` retries through the challenge during
`login()`. Allow 60 to 90 seconds for the worst case. The tests sign in
through the browser only once per cached session. The preflight and the
API fixtures use the internal API's captcha-free login.

Nobody has proven that a datacenter IP gets past the captcha. Browser runs
stay on a machine of the team's, not on GitHub's.

## Server and account

- `config/env/qa.py` holds the server (`base_url`, `api_base_url`), the
  site (`default_site_id`, `test_site_name`), the camera
  (`test_camera_name`) and the chat partner. `.env` holds `QA_USER` and
  `QA_PASSWORD`. No test names any of them.
- The server renames sites and cameras. When the configured site is
  missing, `ViewsPage.click_site` fails fast and lists the entries on
  screen, so the error names the fix. For other locators, the trace shows
  the current names.
- Every test signs in as the 1 account. Tests that create data name it
  `AutoTest...`, and `tools/tenant_cleanup.py` removes what a crashed run
  left.
- Environment variables persist in a terminal session. Reset `ENV` when
  you switch env files.

## Session caching

UI tests reuse a logged-in browser session instead of logging in per
test. The `authenticated_page` fixture in `conftest.py` saves Playwright
storage state to a file named by server and worker
(`tests/shared/auth_state.py`) and reloads it on later runs. A full login
costs about 65 seconds. A cache load costs 2 to 3 seconds.

**When to clear the cache:** after a password change, on unexpected auth
errors, or when switching accounts.

```powershell
del .auth_state*.json
```

The next run logs in fresh and rebuilds the cache.

## API tests and UI tests

API tests live in the sibling repo Soterix-API-QA and stay browser-free.
This repo holds UI tests only.

Choosing where a new test belongs:

- Data validation, CRUD checks, auth and permission checks: API test, in
  Soterix-API-QA. API tests run 10 to 100 times faster and do not break
  on DOM changes.
- User workflows, visual elements, hover and drag interactions, end-to-end
  flows: UI test, here.
- Both possible: write the API test for speed and the UI test for the user
  path.

Test data that a UI test needs but does not prove comes from the internal
API through the fixtures in `tests/shared/api/` (CONVENTIONS.md, "Test
data through the API").

## Drag and drop

Use the visible-drag helper, never raw `drag_to()`. The helper highlights
the source (red border) and the target (green border) so a tester watching
in headed mode can see the drag. The convention is in
[CONVENTIONS.md](CONVENTIONS.md) under Drag and drop.

If a drag fails:

1. Check that the source is visible and the target is in the viewport.
2. Check for overlays over the drop target.
3. Fall back to the JS drag simulators in `views_page.py`
   (`_simulate_drag_via_js`, `_simulate_camera_drag_via_js`), or to
   `drop()` in `tests/shared/helpers/drag.py`.

## Live stream delivery

The facts a test writer needs:

1. A tile gets its video as fMP4 fragments over a websocket, fed to a
   `MediaSource` on the tile's `<video>`. The player shows no codec,
   bitrate or resolution overlay.
2. The server streams H.265 (`hev1`/`hvc1`). Playwright's bundled Chromium
   cannot decode it: the tile stays at `readyState 0` with a spinner
   while the frames arrive. Google Chrome (`--browser-channel chrome`)
   decodes it. That is why `pytest.ini` drives branded Chrome.
3. On Windows, headless Chrome answers `isTypeSupported` true for H.265
   and never decodes it. The livestream tests run headed on Windows. On
   Linux, Chrome decodes H.265 only through a GPU's VA-API on a Wayland
   display ([LINUX_H265.md](LINUX_H265.md)).
4. The stream guard measures the test camera once per session and prints
   a `[STREAM]` line. It skips the tests marked `livestream` when the
   camera sent 0 frames or this browser cannot decode the codec. The
   guard, the test session and `tools/stream_probe.py` read the same
   `CHROME_ARGS`, so they see the same browser.
5. When the streaming host is down for the account, every tile shows "The
   camera failed to load" about 35 s after the drop. That is not the
   intermittent single-camera failure. Run
   `python tools/stream_probe.py --camera "<name>"` before you repair a
   test that failed on that text.
6. The init segment always carries a FLAC audio track. It does not prove
   the camera sends audio. Tiles start muted.

`tools/stream_probe.py --health` samples 1 channel and prints delivered
facts (fps, bitrate, resolution, codec, keyframe interval, latency) next
to what the API says it should send. `--all-cameras` does every channel
on the site. The tool's docstring explains each metric.

## Debugging failures

**Read the trace first.** Every failed test saves one to
`reports/artifacts/`. `playwright trace errors` names the failing action,
`actions` shows the timing, `snapshot` shows the DOM at that moment. Full
guide: [FAILURE_TRIAGE.md](FAILURE_TRIAGE.md). Most reruns are unnecessary.

Assertion rules (see the Waits section in CONVENTIONS.md):

- `expect()` retries. `count()`, `is_visible()`, and `get_attribute()`
  read once. Assert with `expect()` after any action.
- To verify an element is gone, use `expect(locator).to_have_count(0)`,
  not `assert locator.count() == 0`.

## Updating this document

When you find a new fact about the app, add a short entry so the team can
reuse it. State the fact, the cause when you know it, and what the tests
do about it. Point at the file that holds the code. Write a measurement,
not a guess.
