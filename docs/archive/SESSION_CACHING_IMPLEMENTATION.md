# Session Caching Implementation

**Date:** 2025-01-27
**Goal:** Reduce UI test setup time by caching authenticated session state

## Problem

Each UI test was logging in via the browser, taking ~65 seconds per test setup.
- 6 Views tests × 65s = ~390s just on login
- Total test run: 841s (14 minutes)

## Solution

Use Playwright's native `storage_state` feature to:
1. Login once, save all cookies/localStorage/sessionStorage to a file
2. Subsequent tests load the saved state (~2-3s instead of 65s)

## Implementation Details

### Fixtures (current, in `conftest.py`)

1. **`auth_state_path`** (session) - Path to the cached auth state JSON file.
   Returns `.auth_state.json`, or `.auth_state.<worker>.json` under
   pytest-xdist so parallel workers do not race on one file.
2. **`authenticated_page`** (function) - Page in a context created from the
   cached state. Logs in and saves the state when no valid cache exists.

Earlier versions used session-scoped `session_browser` / `session_context`
fixtures. Those are gone: the fixture now builds on pytest-playwright's
`browser` fixture and creates one context per test.

### How It Works

```
First test run:
  1. Create browser
  2. Login via UI (one time)
  3. Save storage_state to .auth_state.json
  4. Return authenticated page

Subsequent tests:
  1. Check if .auth_state.json exists
  2. Create context with storage_state=".auth_state.json"
  3. Return page (already logged in!)
```

## If the cache misbehaves

Delete the cache files and rerun. The next run logs in fresh and saves a new
state:

```powershell
del .auth_state.json
del .auth_state.*.json
```

## Expected Performance Improvement

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| Views setup (6 tests) | ~390s | ~45s | ~345s |
| Login tests | ~180s | ~180s | 0s (expected) |
| Total estimated | ~840s | ~500s | ~340s |

## Testing Checklist

- [x] Views tests pass (4/6 - 2 failures are pre-existing flakiness)
- [x] Login tests still work (they use default `page` fixture, not cached state)
- [x] Auth state file created after first run
- [x] Second run is significantly faster

## Actual Results (2025-01-27)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Views tests setup (6 tests) | ~391s | ~16s | **375s saved** |
| Views tests total | ~433s | ~60s | **373s saved (86%)** |
| Per-test setup | ~65s | ~1-10s | **~55-64s saved** |

### First run (fresh login):
- Setup: ~30s (login via UI, save state)
- Subsequent tests: ~1s setup each

### Cached run (session reused):
- First test setup: ~10s (load cache, verify, navigate)
- Subsequent tests: ~1s setup each

## Notes

- Login tests intentionally bypass the cache (they use pytest-playwright's `page` fixture)
- Cache files (`.auth_state.json`, `.auth_state.*.json`) are in `.gitignore`
- If auth expires, delete the cache files to force re-login
- The `authenticated_page` fixture navigates to `base_url` after loading cached session

## Updates (2026-08-07)

- The fixture records a Playwright trace for every test and keeps it only on
  failure (`reports/artifacts/<test>-trace.zip`). A failed login saves a
  trace too. See `docs/FAILURE_TRIAGE.md`.
- Session validation waits for the nav element instead of sleeping 1.5 s for
  hydration. An invalid session shows the login form, so the nav wait is both
  the readiness wait and the validity check.
- Per-worker cache files under pytest-xdist (see `auth_state_path` above).
