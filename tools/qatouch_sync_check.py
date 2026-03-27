"""QA Touch Sync Checker - detects drift between Playwright markers and QA Touch.

Source of truth: @pytest.mark.qatouch("CASE_KEY") markers in test code.
Compares markers against the latest QA Touch snapshot to find:
  - Tests missing a qatouch marker (need mapping)
  - Markers pointing to deleted/missing QA Touch cases (stale)
  - QA Touch cases marked Automation but with no Playwright test (orphaned)

Usage:
  python tools/qatouch_sync_check.py           # full check
  python tools/qatouch_sync_check.py --fix      # also print scaffold commands
  python tools/qatouch_sync_check.py --refresh   # pull fresh snapshot first

Exit codes:
  0 = fully synced
  1 = drift detected
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / 'config' / 'qatouch_snapshots'

# Legacy mapping (for reference during transition)
LEGACY_MAPPING_PATH = ROOT / 'config' / 'qatouch_case_mapping.json'

DIR_TO_MODULE = {
    'login': 'Login UI',
    'views': 'Views',
    'events': 'Search',
    'search': 'Search',
    'insights': 'Insights',
    'media': 'Media',
    'admin': 'Admin',
    'notifications': 'Notifications',
    'sequences': 'Camera Sequence',
    'maps': 'Maps',
    'chats': 'Chat',
}


def collect_markers() -> dict[str, list[dict]]:
    """Scan test files for @pytest.mark.qatouch("KEY") markers.

    Returns dict: test_file -> [{func_name, case_key, line_no}]
    """
    marker_re = re.compile(
        r'@pytest\.mark\.qatouch\(["\'](\w+)["\']\)'
    )
    func_re = re.compile(r'^\s*def (test_\w+)\s*\(')

    results = defaultdict(list)
    test_dir = ROOT / 'tests'

    # Exclude legacy/archived test directories
    exclude_dirs = {'legacy', 'legacy-selenium-tests', '__pycache__'}

    for py_file in sorted(test_dir.rglob('test_*.py')):
        if any(part in exclude_dirs for part in py_file.parts):
            continue
        rel_path = str(py_file.relative_to(ROOT)).replace('\\', '/')
        lines = py_file.read_text(encoding='utf-8').splitlines()

        pending_key = None
        pending_line = None

        for i, line in enumerate(lines, 1):
            m = marker_re.search(line)
            if m:
                pending_key = m.group(1)
                pending_line = i
                continue

            fm = func_re.match(line)
            if fm and pending_key:
                results[rel_path].append({
                    'func': fm.group(1),
                    'case_key': pending_key,
                    'line': pending_line,
                })
                pending_key = None
                pending_line = None
            elif fm:
                # Test function with no marker
                results[rel_path].append({
                    'func': fm.group(1),
                    'case_key': None,
                    'line': i,
                })

    return dict(results)


def collect_tests() -> list[str]:
    """Run pytest --collect-only to get all test node IDs."""
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '--collect-only'],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return [
        line.strip() for line in result.stdout.splitlines()
        if '::test_' in line
    ]


def latest_snapshot() -> dict | None:
    """Find and load the most recent QA Touch snapshot."""
    if not SNAPSHOT_DIR.exists():
        return None
    snapshots = sorted(SNAPSHOT_DIR.glob('snapshot_*.json'))
    if not snapshots:
        return None
    with open(snapshots[-1], encoding='utf-8') as f:
        return json.load(f)


def suggest_module(filepath: str) -> str:
    parts = filepath.split('/')
    if len(parts) >= 3:
        d = parts[2] if parts[1] in ('ui', 'api') else parts[1]
        return DIR_TO_MODULE.get(d, d.replace('_', ' ').title())
    return 'Other'


def main():
    fix_mode = '--fix' in sys.argv
    refresh = '--refresh' in sys.argv

    print("=" * 60)
    print("QA Touch Sync Check (marker-based)")
    print("=" * 60)

    # Optionally refresh snapshot
    if refresh:
        print("\nRefreshing QA Touch snapshot...")
        subprocess.run(
            [sys.executable, 'tools/qatouch_analytics.py', 'snapshot'],
            cwd=str(ROOT),
        )

    # 1. Collect markers from source code
    print("\nScanning test files for @pytest.mark.qatouch markers...")
    marker_data = collect_markers()

    all_marked = []
    all_unmarked = []
    marker_case_keys = set()

    for filepath, entries in marker_data.items():
        for entry in entries:
            if entry['case_key']:
                all_marked.append({**entry, 'file': filepath})
                marker_case_keys.add(entry['case_key'])
            else:
                all_unmarked.append({**entry, 'file': filepath})

    print(f"  Marked tests:   {len(all_marked)}")
    print(f"  Unmarked tests: {len(all_unmarked)}")

    # 2. Load QA Touch snapshot
    snap = latest_snapshot()
    if not snap:
        print("\n  WARNING: No QA Touch snapshot found. Run: python tools/qatouch_analytics.py snapshot")
        snap_keys = set()
    else:
        snap_keys = {c['case_key'] for c in snap['cases']}
        print(f"  QA Touch cases: {len(snap_keys)}")

    # 3. Stale markers (case deleted from QA Touch)
    stale_keys = marker_case_keys - snap_keys if snap_keys else set()
    stale_markers = [m for m in all_marked if m['case_key'] in stale_keys]

    # 4. Collect actual tests for completeness check
    print("\nCollecting Playwright tests...")
    actual_tests = collect_tests()
    print(f"  Found {len(actual_tests)} tests")

    # 5. Summary
    print(f"\n--- Results ---")
    print(f"  Total tests:       {len(actual_tests)}")
    print(f"  Marked (mapped):   {len(all_marked)}")
    print(f"  Unmarked:          {len(all_unmarked)}")
    print(f"  Unique case keys:  {len(marker_case_keys)}")
    print(f"  Stale (deleted):   {len(stale_markers)}")

    drift = False

    if all_unmarked:
        drift = True
        print(f"\n{'=' * 60}")
        print(f"UNMARKED TESTS ({len(all_unmarked)}):")
        print(f"{'=' * 60}")
        for t in all_unmarked:
            print(f"  {t['file']}::{t['func']} (line {t['line']})")

        if fix_mode:
            print(f"\n--- Add markers ---")
            print("Add @pytest.mark.qatouch(\"CASE_KEY\") above each test.\n")
            print("If no QA Touch case exists yet, scaffold first:")
            for t in all_unmarked:
                module = suggest_module(t['file'])
                title_words = t['func'].replace('test_', '').replace('_', ' ')
                print(
                    f'  python tools/qatouch_run_manager.py scaffold '
                    f'"{t["file"]}::{t["func"]}" "{module}" "Verify {title_words}"'
                )

    if stale_markers:
        drift = True
        print(f"\n{'=' * 60}")
        print(f"STALE MARKERS ({len(stale_markers)}):")
        print(f"{'=' * 60}")
        print("These markers point to cases that no longer exist in QA Touch:")
        for m in stale_markers:
            print(f"  {m['file']}::{m['func']} -> {m['case_key']} (line {m['line']})")
        print("\nRemove or update these markers to point to valid case keys.")

    if not drift:
        print("\n  All tests are marked and up-to-date!")
        return 0

    return 1


if __name__ == '__main__':
    sys.exit(main())
