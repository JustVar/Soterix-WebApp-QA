# QA Things to Know - Soterix Test Automation

This document collects testing patterns, workarounds, and gotchas found while
automating the NexaiQ-Core UI. Each entry states the problem, the cause, and
the fix, with a minimal example.

Wait rules are not repeated here. New code follows the Waits section in
[CONVENTIONS.md](CONVENTIONS.md): no fixed sleeps when a DOM signal exists.
For failure debugging, read [FAILURE_TRIAGE.md](FAILURE_TRIAGE.md) first.
Failed tests save traces, so most gotchas below can now be diagnosed from a
trace instead of a rerun.

## Table of Contents

1. [Hover-revealed checkboxes](#hover-revealed-checkboxes)
2. [My Views - opening saved views](#my-views---opening-saved-views)
3. [Tab locators](#tab-locators)
4. [Click interception and viewport issues](#click-interception-and-viewport-issues)
5. [JavaScript workarounds](#javascript-workarounds)
6. [ReCAPTCHA handling](#recaptcha-handling)
7. [Environments and accounts](#environments-and-accounts)
8. [Email reporting](#email-reporting)
9. [Session caching](#session-caching)
10. [API vs UI tests](#api-vs-ui-tests)
11. [Drag and drop](#drag-and-drop)
12. [Live stream delivery](#live-stream-delivery)
13. [Debugging failures](#debugging-failures)
14. [Migration notes (Selenium)](#migration-notes-selenium)
15. [Updating this document](#updating-this-document)

---

## Hover-revealed checkboxes

**Problem:** many checkboxes (cameras, saved views) stay hidden until the user
hovers over the row. Playwright's `.hover()` does not always reveal them.

**Cause:** the UI listens for JavaScript `mouseenter`/`mouseover` events, not
CSS `:hover`. Playwright's hover fires real mouse events, but React sometimes
attaches the listeners to a parent that the pointer never crosses.

**Fix, in order:**

1. Try the plain path first. `camera.hover()` then click the checkbox. The
   click auto-waits for the checkbox to appear, so no sleep is needed. This
   works for the camera thumbnails in the Devices panel.
2. If the checkbox never appears, dispatch the hover events with JavaScript,
   then click:

```python
self.page.evaluate(
    """(title) => {
        const span = document.querySelector(`span[title='${title}']`);
        if (!span) return;

        // Trigger hover on the parent chain
        let parent = span.parentElement;
        for (let i = 0; i < 5; i++) {
            if (parent) {
                parent.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
                parent.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                parent = parent.parentElement;
            }
        }

        // Find and click the checkbox (search up the DOM tree)
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

**Files:** `tests/shared/pages/views_page.py`
(`add_first_camera_via_checkbox`, `open_saved_view_by_name`).

---

## My Views - opening saved views

**Problem:** reopening a saved view needs the hover-revealed checkbox above,
and the checkbox state becomes inconsistent after you save a view and close
its tab with the X button.

**Fix:** use `ViewsPage.open_saved_view_by_name(view_name)`. It opens the My
Views panel, dispatches the JS hover events, and clicks the checkbox. For the
inconsistent-state case, reload the page first. The reload clears the tab
state while the saved view persists in the backend.

```python
# Save a view, reload, then reopen
save_btn = self.page.locator("img[src*='save']").nth(1)
save_btn.evaluate("el => el.click()")
self.page.locator("text=View saved successfully").wait_for(state="visible", timeout=20000)

self.page.reload()
# No sleep needed: the next action's own wait covers the reload
self.views.open_saved_view_by_name("MyViewName")
```

**Panel-open signal:** the My Views panel shows its Presets / My Views toggle
even when the tenant has no saved views. Wait for `text=Presets` to know the
panel opened. Thumbnails only exist when saved views exist.

---

## Tab locators

**Problem:** tab names are stored in the `title` attribute of an inner div,
not as visible text.

```python
# Wrong - returns empty
tab = page.locator(f"button.tabItem:has-text('{view_name}')")

# Correct
tab = page.locator(f"button.tabItem:has(div[title='{view_name}'])")
```

The tab HTML:

```html
<button class="tabItem">
  <div class="tabInner" title="My View Name"></div>
</button>
```

**Ghost tabs:** the app keeps extra `button.tabItem` elements in the DOM.
Measured on 2026-08-07 via trace: after a tab close, the count of
`button.tabItem` (and even `button.tabItem:visible`) stays at 2 while the
screen shows 1 tab. So:

- Do not assert a tab count after closing a tab. Assert on the thing you
  need next (a success message, a specific tab by title).
- When you must enumerate tabs, filter by title:

```python
for i, t in enumerate(page.locator("button.tabItem").all()):
    inner = t.locator("div.tabInner").first
    title = inner.get_attribute("title") if inner.count() > 0 else "no title"
    print(f"Tab {i}: {title}")
```

---

## Click interception and viewport issues

Some elements time out on click because an overlay intercepts pointer events
or because the element sits outside the viewport with fixed positioning.
Known cases: `text=All Cameras` in the camera tree, `img[src*='save']` icons
on tabs.

**Escalation ladder, try in order:**

1. A plain `click()`. It auto-waits and scrolls. Most elements need nothing
   else.
2. `click(scroll="none")` (Playwright 1.62). Skips the auto scroll-into-view,
   which itself causes interception under sticky headers and lazy-load.
3. `click(force=True)`. Skips actionability checks.
4. JavaScript click as the last resort:

```python
save_btn = self.page.locator("img[src*='save']").nth(1)
save_btn.evaluate("el => el.click()")
```

A JS click bypasses every Playwright check, so pair it with an explicit wait
on the effect (for example the save success message).

`scroll_into_view_if_needed()` does not help for fixed-position elements.

---

## JavaScript workarounds

| Scenario | Use JS? | Reason |
|----------|---------|--------|
| Hover-triggered elements | Yes | Playwright hover may not reach the React listener |
| Fixed-position elements | Yes | Cannot scroll into view |
| Click intercepted | Last resort | Try `scroll="none"`, then `force=True` first |
| Quick state checks | Rarely | Prefer `expect()`, which retries |

Debugging a DOM neighborhood from a test:

```python
dom = self.page.evaluate(
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
```

For a failed test you do not need this: the saved trace contains the DOM at
every action (`playwright trace snapshot <action-id> snapshot`).

---

## ReCAPTCHA handling

ReCAPTCHA is present on the login pages and can block automated logins.

**Current workaround:** `_handle_recaptcha()` in
`tests/shared/pages/login_page.py` retries through the challenge during
`login()`. Allow 60 to 90 seconds for the worst case. The QA environment is
slower than the others.

**Planned fix:** whitelist the automation accounts so they skip ReCAPTCHA.
The request is drafted but not yet granted. Options, in order of preference:
email whitelist, IP whitelist, secret header, or an environment flag that
turns ReCAPTCHA off outside production.

---

## Environments and accounts

| ENV value | URL | Write access |
|-----------|-----|--------------|
| `qa` | qa.example.invalid | Full write and delete |
| `stage` (alias `staging`, `uat`) | staging.example.invalid | Write, no delete |
| `prod` (alias `production`, `user`, `demo`) | app.example.invalid | Read-only. Never run destructive tests here |

- `ENV` selects `config/env/{qa,stage,prod}.py`. `APP_TYPE=partner` appends
  `_pat` to the module path.
- Credentials come from `.env` (`QA_USER` / `QA_PASSWORD`), or per-box
  accounts via `BOX` (for example `BOX=india`). Each box names its own env
  vars in the config. See [CREDENTIALS_SETUP.md](CREDENTIALS_SETUP.md).
- Test data bindings (`test_site_name`, `test_camera_name`, and the optional
  `search_site_name` / `search_camera_name` for the drawing searches) live in
  the env config. The shared QA tenant drifts: on 2026-08-07 a site rename broke
  every site-selecting test. When the configured site is missing,
  `ViewsPage.click_site` now fails fast and lists the entries actually on
  screen, so the error itself names the fix. For other selectors, the
  failure trace shows the current names.
- Environment variables persist in a terminal session. Reset `ENV` and `BOX`
  explicitly when you switch.

---

## Email reporting

Test report emails go out from a dedicated `qa-reports@` mailbox through the
Microsoft Graph API with OAuth. Setup, mailbox rationale, and the Exchange
Application Access Policy are documented in
[EMAIL_REPORTS.md](EMAIL_REPORTS.md).

Points that bite:

- The sender must be a licensed user mailbox. OAuth `Mail.Send` does not work
  with a shared mailbox alone.
- An Application Access Policy restricts the app to this one mailbox. Without
  it the app could send as anyone.
- The Azure client secret expired on 2026-07-22 and is not yet rotated.
  Report email stays broken until it is. Rotation steps are in
  [../MAINTENANCE_REMINDERS.md](../MAINTENANCE_REMINDERS.md).

---

## Session caching

UI tests reuse a logged-in browser session instead of logging in per test.
The `authenticated_page` fixture in `conftest.py` saves Playwright storage
state to `.auth_state.json` (per-worker files under pytest-xdist) and reloads
it on later runs. A full login costs about 65 seconds. A cache load costs 2
to 3 seconds.

Details, history, and measured numbers:
[SESSION_CACHING_IMPLEMENTATION.md](archive/SESSION_CACHING_IMPLEMENTATION.md)
(archived - the live behaviour is in `docs/CONVENTIONS.md`, "Session caching").

**When to clear the cache:** after a password change, on unexpected auth
errors, or when switching accounts.

```powershell
del .auth_state.json
del .auth_state.*.json
```

The next run logs in fresh and rebuilds the cache.

---

## API vs UI tests

API tests live in the sibling repo **Soterix-API-QA** and stay browser-free.
This repo holds UI tests only. The split is documented in
[REPO_SPLIT_PLAN.md](REPO_SPLIT_PLAN.md).

Choosing where a new test belongs:

- Data validation, CRUD checks, auth and permission checks: API test, in
  Soterix-API-QA. API tests run 10 to 100 times faster and do not break on
  DOM changes.
- User workflows, visual elements, hover and drag interactions, end-to-end
  flows: UI test, here.
- Both possible: write the API test for speed and the UI test for the user
  path.

The hybrid pattern (API for setup and cleanup, UI for the test body) needs
clients from the API repo, so plan it as cross-repo work.

---

## Drag and drop

Use the visible-drag helper, never raw `drag_to()`. The helper highlights the
source (red border) and the target (green border) so a tester watching in
headed mode can see the drag. The convention is in
[CONVENTIONS.md](CONVENTIONS.md) under Drag and drop. The current
implementation is `_visible_drag()` in `tests/ui/views/test_views_subtabs.py`.

If a drag fails:

1. Check that the source is visible and the target is in the viewport.
2. Check for overlays over the drop target.
3. Fall back to the JS drag simulators in `views_page.py`
   (`_simulate_drag_via_js`, `_simulate_camera_drag_via_js`).

Open questions (untested): dragging to an occupied tile, tile-to-tile moves,
multi-item drags, and drag cancellation with ESC.

---

## Live stream delivery

Problem: a test that checks a camera's codec, resolution, frame rate or
audio needs a source of truth for what the tile receives. The player shows
none of it: there is no codec, bitrate or resolution overlay, and the full
screen settings gear opens "Image Parameters" only.

How a tile gets its video (probed on QA, 2026-08-25, camera "main gate",
channel 97 on site 16):

1. The app opens
   `wss://media.example.invalid/v3/api/ws?name=<site>/<channel>/<app>/<live>/<stream>/<timestamp>/<uuid>`
   from the main thread and sends `{"type":"mse","value":""}`. A tile uses
   stream index 1 (the minor stream). Full screen opens a second socket with
   stream index 0 (the major stream). The socket
   `/ws/timeline/site/<site>/channel/<channel>` carries the timeline bar only.
2. The server answers one text frame with the MediaSource mime type, for
   example `{"type":"mse","value":"video/mp4; codecs=\"hvc1.1.6.L153.B0,flac\""}`,
   then binary frames: an fMP4 init segment (`ftyp iso5` + `moov`) and one
   `moof` + `mdat` per frame. JSON text frames with per-frame counters
   (`timeStamp`, `vehicleCount`, `peopleCount`) arrive in between.
3. The app feeds the frames to a `MediaSource` on the tile's `<video>` (blob
   src). The hidden `canvas` in the tile is for snapshots, not decoding.
   `/REST/central/user/session` answers `"streamer":"webrtc"` and the v2
   `startlive` URL ends in `/webrtc`, but the page creates no
   `RTCPeerConnection`. That field does not describe the tile transport.

Solution: run `python tools/stream_probe.py --camera "main gate"`. Add
`--fullscreen` for the stream 0 socket and `--json out.json` for the raw
capture. It prints one row per fact with its source.

- Delivered facts come from the socket. Codec: the `moov` sample entry
  (`hev1`/`hvc1` = H.265, `avc1` = H.264) and the SPS inside `hvcC`/`avcC`.
  Resolution: the SPS after its conformance window. The sample entry holds
  the coded size (2592x1472 for a 2592x1458 stream), so do not compare that
  one with the configuration. Frame rate and bitrate: `tfdt` and `mdat`
  across the fragments. Audio: the `fLaC`/`mp4a` entry.
- Configured facts come from the internal API.
  `POST /REST/site/{siteid}/getCameraStreamingParameters` with
  `{"channelId": N, "streamType": 0|1}` is a read despite the verb and gives
  `codecType`, width, height, fps and bitrate.
  `POST /REST/site/{siteid}/camera/audio/streaming` gives the camera audio
  codec. `GET .../channel/{channelid}/config` returns the same block, takes
  about 45 s and embeds a snapshot. Do not call it from a test.
- The tool captures frames over CDP (`Network.enable` and
  `Network.webSocketFrameReceived` on `context.new_cdp_session(page)`).
  `page.on("websocket")` showed no frames in an earlier probe.

Facts that need care:

- `codecType` is a number. The OpenAPI spec has no enum text for it. Value 8
  was H.265 on channels 97 and 88. The value for H.264 is not verified.
  Probe an H.264 camera before you assert on it.
- Playwright's bundled Chromium answers
  `MediaSource.isTypeSupported('video/mp4; codecs="hvc1..."')` with `false`.
  An H.265 tile's `<video>` stays at `readyState 0` with a spinner while the
  frames arrive. A "stream plays" oracle cannot pass for an H.265 camera in
  that browser. The same tile in branded Chrome (`--channel chrome`)
  answered `true` and reached `readyState 4` with 95 decoded frames in 12 s.
- When the streaming host is down for the account, every media socket
  receives one frame and closes after about 30 s, and every tile - and the
  full screen player - shows "The camera failed to load" about 35 s after
  the drop (all four dropped cameras and the configured one, Chrome
  channel, 2026-08-25 10:40). That is not the intermittent single-camera
  failure. Run `python tools/stream_probe.py` before repairing a test that
  failed on that text.
- The init segment always carries a FLAC mono 8 kHz audio track (the server
  transcodes the camera's G.711), and audio fragments arrive when the
  channel has `audioGrabbing: false`. The track does not prove the camera
  sends audio. The tile and full screen start muted
  (`img[src*='volumn-mute-active-icon']`).
- PTZ: the full screen DOM had no `[class*='ptz']` element for the fixed
  Q1656-LE, but `GET .../channel/97/preset` still answered
  `["preset20","Home"]` and `getcurrentptzposition` answered zeros. Neither
  call is a PTZ flag on its own. `channelType` (0 here, 1 on "Training
  Area") is not verified as the PTZ marker.
  `GET /REST/dashboard/system/getcameraconfigtypes` counts `ptzCameras: 9`
  for the enterprise. Open until a PTZ camera on the QA site is probed.

### Health mode

`python tools/stream_probe.py --health --camera "main gate"` samples one
channel (default 20 s) and prints a per-channel row plus the delivered-vs-
configured numbers; `--all-cameras` does every channel on the site;
`--json path` writes the raw metrics. Each metric names how it is measured
(see `health_metrics()`):

- `online`: a `moof`/`mdat` video fragment arrived in the window.
- `first_frame_ms`: handshake request to first video fragment.
- `fps_measured` / `bitrate_kbps`: video track `tfdt` span and `mdat` bytes,
  next to `getCameraStreamingParameters` `fps` / `bitrate`.
- `resolution` / `codec`: SPS size and `moov` sample entry, next to the API.
- `keyframe_interval_s`: mean `tfdt` distance between keyframes. A keyframe
  is a fragment whose `mdat` holds an IRAP (H.265 NAL 16-21) or IDR (H.264
  NAL 5); the tool falls back to `sample_is_non_sync_sample == 0`, then to an
  `mdat` above 3x the median. `keyframe_method` says which was used.
- `timestamp_gaps`: `tfdt` deltas above 2x nominal (`1000 / configured fps`,
  else the median), plus any backwards step.
- `latency_ms`: wall clock at receipt minus the analytics frame `timeStamp`.
  The `timeStamp` is epoch ms (verified within a day of now); the number
  includes the clock offset between this machine and the encoder, so read it
  as an upper bound, not a pure pipeline delay.
- `reconnects`, `analytics_alive`, `audio_fragments`, socket `close`
  code/reason, and the timeline socket's message types round out the row.

Sample (QA, 2026-08-25, 20 s):

- Browser tile, "main gate" (channel 97, stream 1): online, first frame
  2650 ms, 183 video fragments, 10.07 fps (configured 10), 3455 kbps
  (configured 2560; the facts run read `adaptiveBitrate` off on this stream,
  so the delivered rate runs above the cap), 2592x1458 delivered and configured, H.265
  `hev1`, keyframe interval 0.99 s (exact IRAP method, ~1 s GOP), 0 timestamp
  gaps, latency median 2213 ms, 285 audio fragments, 182 analytics frames.
  The tile's `timeline` came back empty: bundled Chromium cannot decode
  H.265, so the player never reaches ready state and the app never issues
  the timeline query. `--no-browser` issues the query itself and does
  capture it (`humans`/`vehicles`/`recordings` rows).
- `--all-cameras --no-browser` (one run, JSON not kept): 2 online, 8 offline of 10. Online were
  "main gate" (188 fragments, 10.05 fps, 2878 kbps, 0.99 s keyframe, latency
  2218 ms) and "Hanwha" (channel 88, 180 fragments, 10.06 fps, 3102 kbps,
  2048x1536, 1.0 s keyframe, latency 1432 ms). Six of the eight offline
  channels have no live source right now: `getCameraStreamingParameters`
  answers `Cannot connect the analytic server` (status 1510) or
  `VMS server error` (status 2), and their media sockets deliver nothing.
  "Street#36" and "Training Area" have a stream config but still delivered
  no frames in the window. Offline here means "no media in the window", not
  a tool fault.

Browser-free collection (`python tools/stream_probe.py --no-browser --camera "main gate"`):

- A media socket opened straight from Python (`aiohttp`, declared in
  `requirements.txt`) delivers the full fMP4 H.265 + FLAC stream and the
  analytics JSON frames with no browser. Measured once on 2026-08-25 (main
  gate 482 and Hanwha 361 binary frames in 20 s); that run's JSON was not
  kept, so treat the numbers as one sample.
- What authorises the socket is a security question for the app team, not a
  QA fact to circulate: see `docs/TEST_REPAIRS.md` row 16. The exact
  connection recipe is kept out of this doc on purpose.
- Caveat, verified: frame delivery is intermittent. Opening several sockets
  to one channel in quick succession starves the later ones (upgrade
  accepted, zero frames, no close), and the host sometimes stops delivering
  to everything for a spell. A collector should open one socket per channel
  and reconnect on a dry socket rather than reading zero frames as
  "camera offline".

Decision: a lightweight browser-free collector is viable. It needs the login
to enumerate channels and read the configured parameters; the media socket
needs no session. `codecType` 8 = H.265 held on channels 88 and 97; the
H.264 value is still unverified.

## Debugging failures

**Read the trace first.** Every failed test saves one to `reports/artifacts/`.
`playwright trace errors` names the failing action, `actions` shows the
timing, `snapshot` shows the DOM at that moment. Full guide:
[FAILURE_TRIAGE.md](FAILURE_TRIAGE.md). Most reruns are unnecessary.

Quick state prints while developing a test:

```python
print(f"Tabs: {self.page.locator('button.tabItem').count()}")
print(f"Checkboxes: {self.page.locator('.sidebar-custom-checkbox').count()}")
self.page.screenshot(path="debug_screenshot.png")
```

Assertion rules (see the Waits section in CONVENTIONS.md):

- `expect()` retries. `count()`, `is_visible()`, and `get_attribute()` read
  once. Assert with `expect()` after any action.
- To verify an element is gone, use
  `expect(locator).to_have_count(0)`, not `assert locator.count() == 0`.

---

## Migration notes (Selenium)

| Selenium pattern | Playwright equivalent | Notes |
|------------------|----------------------|-------|
| `ActionChains.move_to_element()` | `.hover()`, or JS events | See Hover-revealed checkboxes |
| `WebDriverWait` | Built-in auto-wait + `expect()` | Explicit waits rarely needed |
| XPath-heavy selectors | CSS + `:has()` | Playwright prefers CSS |
| `driver.execute_script()` | `page.evaluate()` | Same concept, different syntax |

Test cases that needed special handling in the migration: camera and saved
view checkboxes (JS hover), tab verification (title attribute), save button
(JS click).

---

## Updating this document

When you find a new pattern, workaround, or gotcha, add a short entry so the
team can reuse it.

- State the problem in the header.
- Give the cause and the fix.
- Include a minimal Playwright/pytest snippet when it helps.
- Reference the related files with workspace paths.
- Commit message: `docs: add <short-description> to QA_THINGS_TO_KNOW.md`.

Template:

```markdown
### Short title
Problem: one line
Cause: brief explanation
Solution: steps or code
Files: tests/... or tests/shared/pages/...
```

## To be documented

- [ ] Video playback verification
- [ ] Fullscreen view testing
- [ ] Alert/toast message handling
- [ ] CI/CD integration patterns

---

*Last updated: 2026-08-25*
