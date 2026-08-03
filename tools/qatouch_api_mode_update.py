#!/usr/bin/env python3
"""Update QA Touch case mode via internal API (no browser automation needed).

Uses the discovered /v1/case/update endpoint to set mode on cases.

Usage:
    python tools/qatouch_api_mode_update.py test           # Test on 1 case, revert
    python tools/qatouch_api_mode_update.py count           # Count blank-mode cases
    python tools/qatouch_api_mode_update.py update --dry-run # Preview all changes
    python tools/qatouch_api_mode_update.py update           # Update all blank-mode to Manual
"""
from __future__ import annotations

import argparse
import csv
import functools
import os
import sys
import time
from pathlib import Path

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from playwright.sync_api import sync_playwright

BASE_URL = "https://soterixsystems.qatouch.com"
PROJECT_KEY = "JlW1"
AUTH_STATE_FILE = str(ROOT / "tools" / ".qatouch_auth_state.json")

CSV_FILES = [
    os.path.expanduser("~/Downloads/QATouch_BulkUpdate_Part1.csv"),
    os.path.expanduser("~/Downloads/QATouch_BulkUpdate_Part2.csv"),
    os.path.expanduser("~/Downloads/QATouch_BulkUpdate_Part3.csv"),
]

INTER_CALL_DELAY = 0.2
BURST_PAUSE = 10.0
BURST_THRESHOLD = 50


def login(p):
    browser = p.chromium.launch(headless=False, slow_mo=50, args=["--start-maximized"])
    if os.path.exists(AUTH_STATE_FILE):
        print("  Loading saved auth state...")
        ctx = browser.new_context(
            storage_state=AUTH_STATE_FILE,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()
        page.goto(f"{BASE_URL}/v2#/new-projects", timeout=60000)
        time.sleep(5)
        url = page.url or ""
        if "/login" not in url and "qatouch.com" in url:
            print("  Auth state valid!")
            return browser, ctx, page
        print("  Auth expired -- need fresh login.")
        ctx.close()
        try:
            os.remove(AUTH_STATE_FILE)
        except OSError:
            pass

    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    page.goto(f"{BASE_URL}/login", timeout=60000)
    page.bring_to_front()
    print()
    print("=" * 60)
    print("  BROWSER OPENED -- Please log in to QA Touch")
    print("  Waiting up to 600 seconds...")
    print("=" * 60)
    for i in range(200):
        time.sleep(3)
        if i % 20 == 0 and i > 0:
            try:
                page.bring_to_front()
            except Exception:
                pass
            print(f"  Still waiting... ({i * 3}s elapsed)")
        url = page.url or ""
        if "/login" not in url and "qatouch.com" in url:
            print("  Login detected!")
            time.sleep(2)
            ctx.storage_state(path=AUTH_STATE_FILE)
            return browser, ctx, page
    browser.close()
    raise SystemExit("Login timeout after 600s")


def get_case_data(page, case_key: str) -> dict | None:
    """Read case data via /v1/case/edit."""
    result = page.evaluate("""
        async (caseKey) => {
            try {
                const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
                const resp = await fetch('/v1/case/edit/p/JlW1/cid/' + caseKey, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-XSRF-TOKEN': decodeURIComponent(token || '')
                    },
                    body: JSON.stringify({})
                });
                if (!resp.ok) return {error: 'HTTP ' + resp.status};
                const data = await resp.json();
                if (!data || !data.data) return {error: 'No data'};
                return data.data;
            } catch (e) {
                return {error: e.message};
            }
        }
    """, case_key)
    if result and result.get("error"):
        return None
    return result


def update_case_mode(page, case_key: str, case_data: dict, target_mode: str) -> dict:
    """Update case mode via /v1/case/update.

    Sends required fields (sectionId, title) plus the mode change.
    Returns {success: bool, status: int, body: str}.
    """
    # Echo back the FULL case data with only mode changed - this is how
    # the QA Touch UI does it (discovered via network interception)
    payload = dict(case_data)
    payload["mode"] = target_mode
    # Ensure required array fields exist
    for field in ["checkedRequirements", "gitlabcheckedRequirements", "detailArray"]:
        if field not in payload:
            payload[field] = []

    result = page.evaluate("""
        async ({caseKey, payload}) => {
            try {
                const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
                const resp = await fetch('/v1/case/update/p/JlW1/cid/' + caseKey, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json;charset=UTF-8',
                        'Accept': 'application/json',
                        'X-XSRF-TOKEN': decodeURIComponent(token || '')
                    },
                    body: JSON.stringify(payload)
                });
                const text = await resp.text();
                return {
                    status: resp.status,
                    ok: resp.ok,
                    body: text.substring(0, 500)
                };
            } catch (e) {
                return {error: e.message};
            }
        }
    """, {
        "caseKey": case_key,
        "payload": payload,
    })
    return result


def get_blank_mode_keys() -> list[str]:
    """Get case keys with blank mode from CSV files."""
    keys = []
    for csv_path in CSV_FILES:
        if not os.path.exists(csv_path):
            continue
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if len(row) > 15:
                    mode = row[15].strip()
                    if not mode:
                        keys.append(row[0].strip())
    return keys


def cmd_test(page):
    """Test the update endpoint on a single case, then revert."""
    test_key = "0rzJ8Q"
    print(f"\n  Testing update endpoint on case {test_key}...")

    # Read current state
    data = get_case_data(page, test_key)
    if not data:
        print("  ERROR: Could not read case data")
        return False

    original_mode = data.get("mode", "")
    print(f"  Current mode: '{original_mode}'")
    print(f"  Title: {data.get('title', '')[:60]}")
    print(f"  SectionId: {data.get('sectionId', '')}")
    print(f"  Template: {data.get('template')}")

    # Try updating mode to "manual"
    print("\n  Updating mode to 'manual'...")
    result = update_case_mode(page, test_key, data, "manual")
    print(f"  Response: status={result.get('status')} ok={result.get('ok')}")
    print(f"  Body: {result.get('body', '')[:200]}")

    if result.get("ok"):
        # Verify the change
        time.sleep(1)
        verify = get_case_data(page, test_key)
        new_mode = verify.get("mode", "") if verify else "ERROR"
        print(f"  Verification - mode after update: '{new_mode}'")

        if new_mode == "manual":
            print("  SUCCESS: Mode updated via API!")

            # Revert to original
            if original_mode and original_mode != "manual":
                print(f"  Reverting to original mode: '{original_mode}'...")
                update_case_mode(page, test_key, data, original_mode)
                time.sleep(1)
                revert_check = get_case_data(page, test_key)
                print(f"  Reverted mode: '{revert_check.get('mode', '')}'")
            return True
        print(f"  FAIL: Mode didn't change (still '{new_mode}')")
        return False
    print("  FAIL: Update request failed")
    # Print full error details
    print(f"  Full response: {result}")
    return False


def cmd_count():
    """Count blank-mode cases from CSV."""
    keys = get_blank_mode_keys()
    print(f"\n  Blank-mode cases from CSV: {len(keys)}")
    return keys


def cmd_update(page, dry_run: bool = False):
    """Update all blank-mode cases to Manual."""
    keys = get_blank_mode_keys()
    print(f"\n  Blank-mode cases to update: {len(keys)}")

    if dry_run:
        print("  DRY RUN - no changes will be made")
        # Sample a few to show what would happen
        for key in keys[:5]:
            data = get_case_data(page, key)
            if data:
                print(f"    {key}: mode='{data.get('mode', '')}' title='{data.get('title', '')[:50]}'")
            time.sleep(INTER_CALL_DELAY)
        print(f"  ... and {len(keys) - 5} more")
        return

    updated = 0
    failed = 0
    skipped = 0
    consecutive_errors = 0

    for i, key in enumerate(keys, 1):
        data = get_case_data(page, key)
        if not data:
            print(f"  [{i}/{len(keys)}] {key}: ERROR reading case data")
            failed += 1
            consecutive_errors += 1
            if consecutive_errors >= 10:
                print("  ABORTING: 10 consecutive errors - session likely dead")
                break
            continue

        current_mode = data.get("mode", "")
        if current_mode == "manual":
            skipped += 1
            consecutive_errors = 0
            continue

        result = update_case_mode(page, key, data, "manual")
        if result.get("ok"):
            updated += 1
            consecutive_errors = 0
        else:
            print(f"  [{i}/{len(keys)}] {key}: FAILED - {result.get('status')} {result.get('body', '')[:100]}")
            failed += 1
            consecutive_errors += 1
            if consecutive_errors >= 10:
                print("  ABORTING: 10 consecutive errors - session likely dead")
                break

        time.sleep(INTER_CALL_DELAY)

        if i % BURST_THRESHOLD == 0:
            pct = i / len(keys) * 100
            print(f"  [{i}/{len(keys)}] ({pct:.0f}%) updated={updated} skipped={skipped} failed={failed}")
            time.sleep(BURST_PAUSE)

    print(f"\n{'=' * 60}")
    print("  MODE UPDATE COMPLETE")
    print(f"  Updated: {updated}")
    print(f"  Skipped (already manual): {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Total processed: {updated + skipped + failed}/{len(keys)}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="QA Touch API Mode Update")
    parser.add_argument("command", choices=["test", "count", "update"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.command == "count":
        cmd_count()
        return

    print(f"\n{'=' * 60}")
    print("  QA TOUCH API MODE UPDATE")
    print(f"{'=' * 60}")

    with sync_playwright() as p:
        browser, ctx, page = login(p)

        # Navigate into project
        page.goto(f"{BASE_URL}/v2#/new-projects", timeout=30000)
        time.sleep(3)

        if args.command == "test":
            success = cmd_test(page)
            if success:
                print("\n  Test PASSED - API update endpoint works!")
                print("  Ready to run: python tools/qatouch_api_mode_update.py update")
            else:
                print("\n  Test FAILED - need to investigate")
        elif args.command == "update":
            cmd_update(page, dry_run=args.dry_run)

        # Re-save storage state - login() saves it BEFORE the test mutates,
        # but Laravel rotates the XSRF-TOKEN after any /v1/case/update call.
        # Saving again at the end captures the rotated XSRF so headless
        # urllib callers (backfill_qa_touch_metadata.py,
        # run_partner_admin_backfill.py) see a current token.
        ctx.storage_state(path=AUTH_STATE_FILE)
        print(f"  Saved fresh storage state -> {AUTH_STATE_FILE}")

        browser.close()


if __name__ == "__main__":
    main()
