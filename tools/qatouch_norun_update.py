#!/usr/bin/env python3
"""Mark QA Touch test cases as NO_RUN with a reason in the precondition field.

Uses the /v1/case/update internal API to:
  1. Add the NO_RUN tag to the case's newtags array
  2. Set the precondition to "NOT RUNNABLE: <reason>"

Commands:
    discover-tag     Discover NO_RUN tag hash ID after creating it in QA Touch UI
    test             Test on 1 case - add NO_RUN + precondition, verify, revert
    mark             Mark cases as NO_RUN with a reason
    unmark           Remove NO_RUN tag and restore original precondition
    list             List all NO_RUN cases from snapshot
    count            Count NO_RUN vs runnable cases from snapshot

Usage:
    python tools/qatouch_norun_update.py discover-tag
    python tools/qatouch_norun_update.py test
    python tools/qatouch_norun_update.py mark --keys KEY1,KEY2 --reason "Logout via keyboard not supported"
    python tools/qatouch_norun_update.py mark --from-module "Authentication" --reason "Environment blocker" --dry-run
    python tools/qatouch_norun_update.py unmark --keys KEY1,KEY2
    python tools/qatouch_norun_update.py list
    python tools/qatouch_norun_update.py count

Workflow:
    1. Create "NO_RUN" tag in QA Touch UI (Test Cases > any case > New Tags > Add New)
    2. Run: python tools/qatouch_norun_update.py discover-tag
       (Opens browser, you apply NO_RUN tag to a case in UI, tool reads back the hash ID)
    3. Run: python tools/qatouch_norun_update.py test
    4. Run: python tools/qatouch_norun_update.py mark --keys ... --reason "..."
"""
from __future__ import annotations

import argparse
import functools
import json
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

INTER_CALL_DELAY = 0.2
BURST_PAUSE = 10.0
BURST_THRESHOLD = 50

NORUN_PREFIX = "NOT RUNNABLE: "
NORUN_SEPARATOR = "\n---\n"

# ── Tag ID mapping ───────────────────────────────────────────────────
TAG_IDS_FILE = ROOT / "config" / "qatouch_tag_ids.json"


def load_tag_ids() -> dict:
    if TAG_IDS_FILE.exists():
        with open(TAG_IDS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_tag_ids(tag_ids: dict):
    with open(TAG_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(tag_ids, f, indent=2)
    print(f"  Saved tag IDs to {TAG_IDS_FILE.name}")


TAG_IDS = load_tag_ids()


def get_norun_tag_id() -> str | None:
    return TAG_IDS.get("no_run")


# ── Auth (shared pattern with other qatouch_api tools) ───────────────

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


# ── Internal API calls ───────────────────────────────────────────────

def get_case_data(page, case_key: str) -> dict | None:
    """Read full case data via /v1/case/edit."""
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


def update_case(page, case_key: str, case_data: dict, field_updates: dict) -> dict:
    """Update case fields via /v1/case/update.

    Echoes back the full case data with field_updates applied.
    """
    payload = dict(case_data)
    payload.update(field_updates)
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
    """, {"caseKey": case_key, "payload": payload})
    return result


# ── Precondition helpers ─────────────────────────────────────────────

def build_norun_precondition(reason: str, original_precondition: str) -> str:
    """Build precondition text with NOT RUNNABLE prefix, preserving original."""
    norun_text = f"{NORUN_PREFIX}{reason}"
    if original_precondition and not original_precondition.startswith(NORUN_PREFIX):
        return f"{norun_text}{NORUN_SEPARATOR}{original_precondition}"
    return norun_text


def strip_norun_precondition(precondition: str) -> str:
    """Remove NOT RUNNABLE prefix, restoring original precondition."""
    if not precondition.startswith(NORUN_PREFIX):
        return precondition
    if NORUN_SEPARATOR in precondition:
        return precondition.split(NORUN_SEPARATOR, 1)[1]
    return ""


def is_norun_precondition(precondition: str) -> bool:
    return precondition.startswith(NORUN_PREFIX)


# ── Core operations ──────────────────────────────────────────────────

def mark_case_norun(page, case_key: str, reason: str) -> tuple[bool, str]:
    """Add NO_RUN tag and set precondition on a case."""
    tag_id = get_norun_tag_id()
    if not tag_id:
        return False, "NO_RUN tag ID not configured - run 'discover-tag' first"

    data = get_case_data(page, case_key)
    if not data:
        return False, "Failed to read case data"

    current_newtags = data.get("newtags") or []
    current_precondition = data.get("precondition") or ""

    # Check if already marked
    already_tagged = tag_id in current_newtags
    already_precond = is_norun_precondition(current_precondition)
    if already_tagged and already_precond:
        return True, f"Already marked NO_RUN"

    # Build updates
    updates = {}
    if not already_tagged:
        updates["newtags"] = list(current_newtags) + [tag_id]
    if not already_precond:
        updates["precondition"] = build_norun_precondition(reason, current_precondition)

    result = update_case(page, case_key, data, updates)
    if result.get("ok"):
        parts = []
        if not already_tagged:
            parts.append("tag added")
        if not already_precond:
            parts.append("precondition set")
        return True, f"Marked NO_RUN ({', '.join(parts)})"
    else:
        return False, f"HTTP {result.get('status', '?')}: {result.get('body', result.get('error', '?'))[:200]}"


def unmark_case_norun(page, case_key: str) -> tuple[bool, str]:
    """Remove NO_RUN tag and restore original precondition."""
    tag_id = get_norun_tag_id()
    if not tag_id:
        return False, "NO_RUN tag ID not configured - run 'discover-tag' first"

    data = get_case_data(page, case_key)
    if not data:
        return False, "Failed to read case data"

    current_newtags = data.get("newtags") or []
    current_precondition = data.get("precondition") or ""

    has_tag = tag_id in current_newtags
    has_precond = is_norun_precondition(current_precondition)
    if not has_tag and not has_precond:
        return True, "Not marked as NO_RUN"

    updates = {}
    if has_tag:
        updates["newtags"] = [t for t in current_newtags if t != tag_id]
    if has_precond:
        updates["precondition"] = strip_norun_precondition(current_precondition)

    result = update_case(page, case_key, data, updates)
    if result.get("ok"):
        parts = []
        if has_tag:
            parts.append("tag removed")
        if has_precond:
            parts.append("precondition restored")
        return True, f"Unmarked ({', '.join(parts)})"
    else:
        return False, f"HTTP {result.get('status', '?')}: {result.get('body', result.get('error', '?'))[:200]}"


# ── Commands ─────────────────────────────────────────────────────────

def cmd_discover_tag(page, args):
    """Discover the NO_RUN tag hash ID by diffing newtags before/after UI tagging."""
    test_key = "5BRMnj"  # Known test case
    print(f"\n  Reading case {test_key} to capture current tags...")

    data = get_case_data(page, test_key)
    if not data:
        print("  ERROR: Could not read case data")
        return

    before_tags = set(data.get("newtags") or [])
    print(f"  Current newtags: {sorted(before_tags)}")
    print(f"  Title: {data.get('title', '')[:80]}")

    print()
    print("=" * 60)
    print("  NOW: Go to QA Touch UI and add the 'NO_RUN' tag to this case.")
    print(f"  Case: {test_key}")
    print("  Steps:")
    print("    1. Open the case in QA Touch")
    print("    2. Click 'New Tags' field")
    print("    3. Click 'Add New' and type 'NO_RUN' (if not created yet)")
    print("    4. Select the NO_RUN tag and save the case")
    print("  Press Enter here when done...")
    print("=" * 60)
    input()

    print("  Re-reading case to find new tag ID...")
    data2 = get_case_data(page, test_key)
    if not data2:
        print("  ERROR: Could not re-read case data")
        return

    after_tags = set(data2.get("newtags") or [])
    print(f"  Updated newtags: {sorted(after_tags)}")

    new_ids = after_tags - before_tags
    if not new_ids:
        print("  No new tags detected. Did you save the case?")
        return

    if len(new_ids) > 1:
        print(f"  Multiple new tags detected: {new_ids}")
        print("  Please add only the NO_RUN tag and try again.")
        return

    tag_id = new_ids.pop()
    print(f"\n  Discovered NO_RUN tag ID: {tag_id}")

    # Save to config
    tag_ids = load_tag_ids()
    tag_ids["no_run"] = tag_id
    save_tag_ids(tag_ids)

    # Reload global
    global TAG_IDS
    TAG_IDS = tag_ids

    print(f"  Config updated: {TAG_IDS_FILE.name}")
    print(f"\n  Next: python tools/qatouch_norun_update.py test")


def cmd_test(page, args):
    """Test NO_RUN marking on a single case, then revert."""
    tag_id = get_norun_tag_id()
    if not tag_id:
        print("  ERROR: NO_RUN tag ID not configured.")
        print("  Run: python tools/qatouch_norun_update.py discover-tag")
        return

    test_key = "5BRMnj"
    reason = "Test - this will be reverted"
    print(f"\n  Testing NO_RUN on case {test_key}...")
    print(f"  NO_RUN tag ID: {tag_id}")

    # Save original state
    data = get_case_data(page, test_key)
    if not data:
        print("  ERROR: Could not read case data")
        return

    original_newtags = data.get("newtags") or []
    original_precondition = data.get("precondition") or ""
    print(f"  Original newtags: {original_newtags}")
    print(f"  Original precondition: {original_precondition[:100]!r}")

    # Mark as NO_RUN
    ok, msg = mark_case_norun(page, test_key, reason)
    print(f"  Mark result: {ok} - {msg}")

    # Verify
    time.sleep(1)
    data2 = get_case_data(page, test_key)
    if data2:
        print(f"  After mark - newtags: {data2.get('newtags', [])}")
        print(f"  After mark - precondition: {(data2.get('precondition') or '')[:100]!r}")

    # Revert
    time.sleep(1)
    print(f"\n  Reverting to original state...")
    result = update_case(page, test_key, data2 or data, {
        "newtags": original_newtags,
        "precondition": original_precondition,
    })
    print(f"  Revert: HTTP {result.get('status', '?')}")

    # Verify revert
    time.sleep(1)
    data3 = get_case_data(page, test_key)
    if data3:
        print(f"  Final newtags: {data3.get('newtags', [])}")
        print(f"  Final precondition: {(data3.get('precondition') or '')[:100]!r}")

    print("\n  Test complete!")


def cmd_mark(page, args):
    """Mark cases as NO_RUN with a reason."""
    tag_id = get_norun_tag_id()
    if not tag_id:
        print("  ERROR: NO_RUN tag ID not configured.")
        print("  Run: python tools/qatouch_norun_update.py discover-tag")
        return

    if not args.reason:
        print("  ERROR: --reason is required")
        return

    # Resolve target cases
    cases = resolve_target_cases(args)
    if not cases:
        print("  No cases to process.")
        return

    print(f"\n  Cases to mark: {len(cases)}")
    print(f"  Reason: {args.reason}")

    if args.dry_run:
        for c in cases:
            module = c.get("module name", c.get("module", ""))
            print(f"    {c['case_key']}: [{module}] {c['case_title'][:70]}")
        print(f"\n  Dry run - no changes made. Remove --dry-run to apply.")
        return

    updated = 0
    skipped = 0
    failed = 0
    consecutive_errors = 0
    start_time = time.time()

    for i, c in enumerate(cases):
        if i > 0 and i % BURST_THRESHOLD == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(cases) - i) / rate if rate > 0 else 0
            print(f"  Burst pause ({BURST_PAUSE}s)... [{i}/{len(cases)}] "
                  f"rate={rate:.1f}/s ETA={eta / 60:.1f}m")
            time.sleep(BURST_PAUSE)

        ok, msg = mark_case_norun(page, c["case_key"], args.reason)
        if ok and "Already" in msg:
            skipped += 1
            consecutive_errors = 0
        elif ok:
            updated += 1
            consecutive_errors = 0
        else:
            failed += 1
            consecutive_errors += 1
            if failed <= 5:
                print(f"  FAIL {c['case_key']}: {msg}")
            elif failed == 6:
                print(f"  (suppressing further failure messages)")
            if consecutive_errors >= 10:
                print("  ABORTING: 10 consecutive errors - session likely dead")
                break

        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            print(f"  Progress: {i + 1}/{len(cases)} "
                  f"(updated={updated}, skipped={skipped}, failed={failed}) "
                  f"[{elapsed:.0f}s elapsed]")
        time.sleep(INTER_CALL_DELAY)

    elapsed = time.time() - start_time
    print(f"\n  Done in {elapsed:.0f}s!")
    print(f"  Updated: {updated}, Skipped: {skipped}, Failed: {failed}")

    # Save results
    report_dir = ROOT / "config" / "audit_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    result_path = report_dir / f"norun_mark_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({
            "action": "mark",
            "reason": args.reason,
            "total": len(cases),
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "elapsed_seconds": round(elapsed, 1),
            "case_keys": [c["case_key"] for c in cases],
        }, f, indent=2)
    print(f"  Results saved: {result_path.name}")


def cmd_unmark(page, args):
    """Remove NO_RUN tag and restore original precondition."""
    tag_id = get_norun_tag_id()
    if not tag_id:
        print("  ERROR: NO_RUN tag ID not configured.")
        print("  Run: python tools/qatouch_norun_update.py discover-tag")
        return

    keys = [k.strip() for k in args.keys.split(",")] if args.keys else []
    if not keys:
        print("  ERROR: --keys is required for unmark")
        return

    print(f"\n  Cases to unmark: {len(keys)}")

    if args.dry_run:
        for key in keys:
            print(f"    {key}")
        print(f"\n  Dry run - no changes made. Remove --dry-run to apply.")
        return

    updated = 0
    skipped = 0
    failed = 0

    for i, key in enumerate(keys):
        ok, msg = unmark_case_norun(page, key)
        if ok and "Not marked" in msg:
            skipped += 1
        elif ok:
            updated += 1
        else:
            failed += 1
            print(f"  FAIL {key}: {msg}")

        if (i + 1) % 10 == 0:
            print(f"  Progress: {i + 1}/{len(keys)} "
                  f"(updated={updated}, skipped={skipped}, failed={failed})")
        time.sleep(INTER_CALL_DELAY)

    print(f"\n  Done! Updated: {updated}, Skipped: {skipped}, Failed: {failed}")


def _case_tags_lower(case: dict) -> str:
    """Return all tags joined into a single lowercase comma-separated string,
    reading from current 'Tags' (list) or legacy 'NewTags' (string) field."""
    raw = case.get("Tags")
    if raw is None:
        raw = case.get("NewTags", "")
    if isinstance(raw, list):
        parts = [str(x) for x in raw]
    else:
        parts = str(raw).split(",")
    return ",".join(p.strip().lower() for p in parts if p and p.strip())


def cmd_list(page, args):
    """List all NO_RUN cases from latest snapshot."""
    snap = load_latest_snapshot()
    if not snap:
        return

    norun_cases = []
    for c in snap["cases"]:
        tags = _case_tags_lower(c)
        if "no_run" in tags:
            norun_cases.append(c)

    if not norun_cases:
        print("\n  No cases tagged NO_RUN in snapshot.")
        return

    print(f"\n  NO_RUN cases: {len(norun_cases)}")
    print(f"  {'Key':<10} {'Module':<30} {'Title'}")
    print("  " + "-" * 80)
    for c in norun_cases:
        module = (c.get("module name") or "")[:28]
        title = (c.get("case_title") or "")[:50]
        print(f"  {c['case_key']:<10} {module:<30} {title}")


def cmd_count(page, args):
    """Count NO_RUN vs runnable cases."""
    snap = load_latest_snapshot()
    if not snap:
        return

    total = len(snap["cases"])
    norun = 0
    by_module = {}

    for c in snap["cases"]:
        tags = _case_tags_lower(c)
        if "no_run" in tags:
            norun += 1
            module = c.get("module name") or "(no module)"
            by_module[module] = by_module.get(module, 0) + 1

    runnable = total - norun
    print(f"\n  Total cases:    {total}")
    print(f"  Runnable:       {runnable}")
    print(f"  NO_RUN:         {norun}")

    if by_module:
        print(f"\n  NO_RUN by module:")
        for module in sorted(by_module, key=lambda m: by_module[m], reverse=True):
            print(f"    {module:<40} {by_module[module]:>4}")


# ── Helpers ──────────────────────────────────────────────────────────

def load_latest_snapshot() -> dict | None:
    """Load latest QA Touch case snapshot."""
    snap_dir = ROOT / "config" / "qatouch_snapshots"
    if not snap_dir.exists():
        print(f"  ERROR: Snapshot directory not found: {snap_dir}")
        return None

    snapshots = sorted(snap_dir.glob("snapshot_*.json"))
    if not snapshots:
        print("  ERROR: No snapshots found.")
        return None

    latest = snapshots[-1]
    print(f"  Loading snapshot: {latest.name}")
    with open(latest, encoding="utf-8") as f:
        return json.load(f)


def resolve_target_cases(args) -> list[dict]:
    """Resolve target cases from --keys or --from-module flags."""
    snap = load_latest_snapshot()
    if not snap:
        return []

    cases_by_key = {c["case_key"]: c for c in snap["cases"]}

    # Explicit keys
    if args.keys:
        keys = [k.strip() for k in args.keys.split(",")]
        found = []
        for k in keys:
            if k in cases_by_key:
                found.append(cases_by_key[k])
            else:
                print(f"  WARNING: Case key {k} not found in snapshot")
        return found

    # By module name
    if args.from_module:
        target_modules = [m.strip().lower() for m in args.from_module.split(",")]
        matched = []
        for c in snap["cases"]:
            module = (c.get("module name") or "").lower()
            if any(t in module for t in target_modules):
                matched.append(c)
        return matched

    print("  ERROR: Provide --keys or --from-module")
    return []


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="QA Touch NO_RUN Tag + Precondition Update",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Discover tag ID (one-time setup):
    python tools/qatouch_norun_update.py discover-tag

  Mark cases by key:
    python tools/qatouch_norun_update.py mark --keys KEY1,KEY2 --reason "Keyboard logout not supported"

  Mark all cases in a module:
    python tools/qatouch_norun_update.py mark --from-module "Authentication" --reason "Environment blocker"

  Preview before applying:
    python tools/qatouch_norun_update.py mark --from-module "Authentication" --reason "..." --dry-run

  Remove NO_RUN from cases:
    python tools/qatouch_norun_update.py unmark --keys KEY1,KEY2

  View NO_RUN cases:
    python tools/qatouch_norun_update.py list
    python tools/qatouch_norun_update.py count
""",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("discover-tag", help="Discover NO_RUN tag hash ID from QA Touch UI")
    sub.add_parser("test", help="Test on 1 case (mark + revert)")

    mark_p = sub.add_parser("mark", help="Mark cases as NO_RUN")
    mark_p.add_argument("--keys", default="", help="Comma-separated case keys")
    mark_p.add_argument("--from-module", default="", help="Module name(s) to match (comma-separated)")
    mark_p.add_argument("--reason", required=True, help="Reason the test cannot be run")
    mark_p.add_argument("--dry-run", action="store_true", help="Preview without changes")

    unmark_p = sub.add_parser("unmark", help="Remove NO_RUN tag and restore precondition")
    unmark_p.add_argument("--keys", required=True, help="Comma-separated case keys")
    unmark_p.add_argument("--dry-run", action="store_true", help="Preview without changes")

    sub.add_parser("list", help="List all NO_RUN cases from snapshot")
    sub.add_parser("count", help="Count NO_RUN vs runnable cases")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    # Commands that don't need browser
    if args.command in ("list", "count"):
        handler = {"list": cmd_list, "count": cmd_count}[args.command]
        handler(None, args)
        return

    # Dry-run mark/unmark don't need browser either (just reads snapshot)
    if args.command == "mark" and args.dry_run:
        cmd_mark(None, args)
        return

    print(f"\n{'=' * 60}")
    print(f"  QA TOUCH NO_RUN UPDATE")
    print(f"{'=' * 60}")
    print("Starting browser for QA Touch API access...")

    with sync_playwright() as p:
        browser, ctx, page = login(p)
        try:
            page.goto(f"{BASE_URL}/v2#/new-projects", timeout=30000)
            time.sleep(3)

            commands = {
                "discover-tag": cmd_discover_tag,
                "test": cmd_test,
                "mark": cmd_mark,
                "unmark": cmd_unmark,
            }
            commands[args.command](page, args)
        finally:
            ctx.close()
            browser.close()


if __name__ == "__main__":
    main()
