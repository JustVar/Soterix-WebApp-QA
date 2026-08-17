#!/usr/bin/env python3
"""Update QA Touch case tags via internal API.

Uses the /v1/case/update endpoint (same as mode update) to add/remove tags.

Commands:
    test             Test on 1 case - add tag, verify, revert
    add-smoke        Add SMOKE tag to specified case keys
    add-regression   Add REGRESSION tag to 600 gap-analysis candidates
    count            Count cases by current tag state
    preview          Show what would be changed (dry run)

Usage:
    python tools/qatouch_api_tag_update.py test
    python tools/qatouch_api_tag_update.py count
    python tools/qatouch_api_tag_update.py add-smoke --keys KEY1,KEY2,...
    python tools/qatouch_api_tag_update.py add-smoke --from-area "Playback,Admin - Roles & Permissions" --limit 5
    python tools/qatouch_api_tag_update.py add-regression --dry-run
    python tools/qatouch_api_tag_update.py add-regression
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
REPORT_DIR = ROOT / "config" / "audit_reports"

INTER_CALL_DELAY = 0.2
BURST_PAUSE = 10.0
BURST_THRESHOLD = 50

# ── Tag ID mapping (hash IDs used by QA Touch newtags array) ─────────
TAG_IDS_FILE = ROOT / "config" / "qatouch_tag_ids.json"

def load_tag_ids() -> dict:
    """Load tag name -> hash ID mapping from config."""
    if TAG_IDS_FILE.exists():
        with open(TAG_IDS_FILE, encoding="utf-8") as f:
            return json.load(f)
    # Fallback to known IDs
    return {"smoke": "99GQ", "sanity": "X1zZ"}

TAG_IDS = load_tag_ids()


# ── Auth ──────────────────────────────────────────────────────────────

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


# ── Internal API calls ────────────────────────────────────────────────

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


def update_case_newtags(page, case_key: str, case_data: dict, newtags: list[str]) -> dict:
    """Update case newtags array via /v1/case/update.

    newtags: list of tag hash IDs, e.g. ["99GQ", "MW0N"]
    """
    payload = dict(case_data)
    # An empty list is silently ignored by QA Touch - [""] is the explicit
    # "clear all tags" signal. See tools/qatouch_suite_hold.py for the
    # measurement. Always read the tags back; HTTP 200 proves nothing here.
    payload["newtags"] = list(newtags) if newtags else [""]
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


def add_tag_to_case(page, case_key: str, tag: str) -> tuple[bool, str]:
    """Add a tag to a case via newtags array, preserving existing tags.

    tag: tag name (e.g. "regression") - resolved to hash ID via TAG_IDS.
    Returns (success, message).
    """
    tag_id = TAG_IDS.get(tag.lower())
    if not tag_id:
        return False, f"Unknown tag '{tag}' - not in config/qatouch_tag_ids.json"

    data = get_case_data(page, case_key)
    if not data:
        return False, "Failed to read case data"

    current_newtags = data.get("newtags") or []

    # Check if already tagged
    if tag_id in current_newtags:
        return True, f"Already has '{tag}'"

    # Add the new tag hash ID
    updated_newtags = list(current_newtags) + [tag_id]

    result = update_case_newtags(page, case_key, data, updated_newtags)
    if result.get("ok"):
        return True, f"Added '{tag}' ({tag_id})"
    return False, f"HTTP {result.get('status', '?')}: {result.get('body', result.get('error', '?'))[:200]}"


# ── Commands ──────────────────────────────────────────────────────────

def cmd_test(page, args):
    """Test tag update on a single case, then revert."""
    test_key = "5BRMnj"  # Known case with smoke+sanity tags
    print(f"\n  Testing tag update on case {test_key}...")
    print(f"  Tag IDs: {TAG_IDS}")

    data = get_case_data(page, test_key)
    if not data:
        print("  ERROR: Could not read case data")
        return

    original_newtags = data.get("newtags") or []
    print(f"  Current newtags: {original_newtags}")

    # Add regression tag
    ok, msg = add_tag_to_case(page, test_key, "regression")
    print(f"  Add regression: {ok} - {msg}")

    # Verify
    time.sleep(1)
    data2 = get_case_data(page, test_key)
    if data2:
        print(f"  After update: newtags={data2.get('newtags', [])}")

    # Revert
    time.sleep(1)
    result = update_case_newtags(page, test_key, data2 or data, original_newtags)
    print(f"  Reverted to: {original_newtags} (HTTP {result.get('status', '?')})")

    # Verify revert
    time.sleep(1)
    data3 = get_case_data(page, test_key)
    if data3:
        print(f"  Final state: newtags={data3.get('newtags', [])}")
    print("\n  Test complete!")


def cmd_count(page, args):
    """Count cases by tag state using snapshot."""
    snap_dir = ROOT / "config" / "qatouch_snapshots"
    latest = sorted(snap_dir.glob("snapshot_*.json"))[-1]
    with open(latest, encoding="utf-8") as f:
        snap = json.load(f)

    tags = {}
    no_tags = 0
    for c in snap["cases"]:
        t = (c.get("NewTags") or "").strip()
        if not t:
            no_tags += 1
        else:
            for tag in t.split(","):
                tag = tag.strip().lower()
                tags[tag] = tags.get(tag, 0) + 1

    print(f"\n  Total cases: {len(snap['cases'])}")
    print(f"  No tags: {no_tags}")
    print(f"  Tagged: {len(snap['cases']) - no_tags}")
    for tag in sorted(tags, key=lambda t: tags[t], reverse=True):
        print(f"    {tag}: {tags[tag]}")


def cmd_add_smoke(page, args):
    """Add SMOKE tag to cases in specified areas."""
    # Load gap analysis to find cases in target areas
    from tools.qatouch_gap_analysis import (
        classify_module,
        load_latest_snapshot,
    )

    snapshot = load_latest_snapshot()
    areas_to_tag = [a.strip() for a in args.from_area.split(",")] if args.from_area else []
    explicit_keys = [k.strip() for k in args.keys.split(",")] if args.keys else []

    # Find candidate cases
    smoke_candidates = []
    if explicit_keys:
        for c in snapshot["cases"]:
            if c["case_key"] in explicit_keys:
                smoke_candidates.append(c)
    elif areas_to_tag:
        for c in snapshot["cases"]:
            area = classify_module(c.get("module name", ""))
            if area in areas_to_tag:
                # Prefer Critical/High priority cases
                smoke_candidates.append(c)
        # Sort by priority
        prio_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        smoke_candidates.sort(key=lambda c: prio_order.get(c.get("Priority", ""), 4))

    limit = args.limit or len(smoke_candidates)
    smoke_candidates = smoke_candidates[:limit]

    print(f"\n  SMOKE candidates: {len(smoke_candidates)}")
    if args.dry_run:
        for c in smoke_candidates:
            area = classify_module(c.get("module name", ""))
            print(f"    [{area}] {c['case_key']}: {c['case_title'][:80]}")
        print("\n  Dry run -- no changes made. Remove --dry-run to apply.")
        return

    updated = 0
    skipped = 0
    failed = 0
    for i, c in enumerate(smoke_candidates):
        if i > 0 and i % BURST_THRESHOLD == 0:
            print(f"  Burst pause ({BURST_PAUSE}s)...")
            time.sleep(BURST_PAUSE)

        ok, msg = add_tag_to_case(page, c["case_key"], "smoke")
        if ok and "Already" in msg:
            skipped += 1
        elif ok:
            updated += 1
        else:
            failed += 1
            print(f"  FAIL {c['case_key']}: {msg}")

        if i % 10 == 0:
            print(f"  Progress: {i+1}/{len(smoke_candidates)} (updated={updated}, skipped={skipped}, failed={failed})")
        time.sleep(INTER_CALL_DELAY)

    print(f"\n  Done! Updated: {updated}, Skipped: {skipped}, Failed: {failed}")


def cmd_add_regression(page, args):
    """Add REGRESSION tag to gap-analysis candidates."""
    # Find latest regression candidates file
    candidate_files = sorted(REPORT_DIR.glob("regression_candidates_*.json"), reverse=True)
    if not candidate_files:
        print("  ERROR: No regression_candidates_*.json found in config/audit_reports/")
        print("  Run: python tools/qatouch_gap_analysis.py regression --target 600")
        return

    candidates_file = candidate_files[0]
    print(f"  Loading candidates: {candidates_file.name}")
    with open(candidates_file, encoding="utf-8") as f:
        data = json.load(f)

    candidates = data.get("candidates", [])
    print(f"  Total candidates: {len(candidates)}")

    if args.dry_run:
        # Summary by area
        from collections import Counter
        area_counts = Counter(c["area"] for c in candidates)
        print(f"\n  {'Area':<30} {'Count':>6}")
        print("  " + "-" * 40)
        for area, count in area_counts.most_common():
            print(f"  {area:<30} {count:>6}")
        print("\n  Dry run -- no changes made. Remove --dry-run to apply.")
        return

    updated = 0
    skipped = 0
    failed = 0
    start_time = time.time()

    for i, c in enumerate(candidates):
        if i > 0 and i % BURST_THRESHOLD == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(candidates) - i) / rate if rate > 0 else 0
            print(f"  Burst pause ({BURST_PAUSE}s)... [{i}/{len(candidates)}] "
                  f"rate={rate:.1f}/s ETA={eta/60:.1f}m")
            time.sleep(BURST_PAUSE)

        ok, msg = add_tag_to_case(page, c["key"], "regression")
        if ok and "Already" in msg:
            skipped += 1
        elif ok:
            updated += 1
        else:
            failed += 1
            if failed <= 5:
                print(f"  FAIL {c['key']}: {msg}")
            elif failed == 6:
                print("  (suppressing further failure messages)")

        if (i + 1) % 25 == 0:
            elapsed = time.time() - start_time
            print(f"  Progress: {i+1}/{len(candidates)} "
                  f"(updated={updated}, skipped={skipped}, failed={failed}) "
                  f"[{elapsed:.0f}s elapsed]")
        time.sleep(INTER_CALL_DELAY)

    elapsed = time.time() - start_time
    print(f"\n  Done in {elapsed:.0f}s!")
    print(f"  Updated: {updated}, Skipped: {skipped}, Failed: {failed}")

    # Save results
    result_path = REPORT_DIR / f"regression_tagging_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({
            "source": candidates_file.name,
            "total": len(candidates),
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "elapsed_seconds": round(elapsed, 1),
        }, f, indent=2)
    print(f"  Results saved: {result_path.name}")


def cmd_preview(page, args):
    """Preview regression candidates without changes."""
    args.dry_run = True
    cmd_add_regression(page, args)


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="QA Touch Tag Update via Internal API")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("test", help="Test tag update on 1 case (add + revert)")
    sub.add_parser("count", help="Count cases by tag state")

    smoke_p = sub.add_parser("add-smoke", help="Add SMOKE tag to cases")
    smoke_p.add_argument("--keys", default="", help="Comma-separated case keys")
    smoke_p.add_argument("--from-area", default="", help="Product areas to select from")
    smoke_p.add_argument("--limit", type=int, default=0, help="Max cases to tag")
    smoke_p.add_argument("--dry-run", action="store_true")

    reg_p = sub.add_parser("add-regression", help="Add REGRESSION tag from gap analysis")
    reg_p.add_argument("--dry-run", action="store_true")

    sub.add_parser("preview", help="Preview regression candidates (dry run)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    # Count doesn't need browser
    if args.command == "count":
        cmd_count(None, args)
        return

    print("Starting browser for QA Touch API access...")
    with sync_playwright() as p:
        browser, ctx, page = login(p)
        try:
            commands = {
                "test": cmd_test,
                "add-smoke": cmd_add_smoke,
                "add-regression": cmd_add_regression,
                "preview": cmd_preview,
            }
            commands[args.command](page, args)
        finally:
            ctx.close()
            browser.close()


if __name__ == "__main__":
    main()
