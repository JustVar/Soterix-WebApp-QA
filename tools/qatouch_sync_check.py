"""QA Touch Sync Checker - detects drift between Playwright tests and QA Touch mapping.

Run after creating, renaming, or deleting tests to verify the mapping is up-to-date.

Usage:
  python tools/qatouch_sync_check.py           # full check (unmapped + stale + summary)
  python tools/qatouch_sync_check.py --fix      # also print scaffold commands for unmapped tests

Exit codes:
  0 = fully synced
  1 = drift detected (unmapped tests or stale entries)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPPING_PATH = ROOT / 'config' / 'qatouch_case_mapping.json'

# Module resolution: test directory -> suggested QA Touch module name
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


def collect_tests() -> list[str]:
    """Run pytest --collect-only to get all test node IDs."""
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '--collect-only'],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    tests = []
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if '::' in line and line.startswith('tests/'):
            tests.append(line)
    return tests


def load_mapping() -> dict:
    """Load the current case mapping."""
    with open(MAPPING_PATH, encoding='utf-8') as f:
        return json.load(f)


def get_module_dir(nodeid: str) -> str:
    """Extract the module directory from a test node ID."""
    parts = nodeid.split('/')
    if len(parts) >= 3:
        return parts[2] if parts[1] in ('ui', 'api') else parts[1]
    return 'other'


def suggest_module(nodeid: str) -> str:
    """Suggest a QA Touch module name based on the test path."""
    d = get_module_dir(nodeid)
    return DIR_TO_MODULE.get(d, d.replace('_', ' ').title())


def main():
    fix_mode = '--fix' in sys.argv

    print("=" * 60)
    print("QA Touch Sync Check")
    print("=" * 60)

    # Collect actual tests
    print("\nCollecting Playwright tests...")
    actual_tests = collect_tests()
    print(f"  Found {len(actual_tests)} tests")

    # Load mapping
    mapping = load_mapping()
    mapped_nodeids = set(mapping.get('mappings', {}).keys())
    print(f"  Mapping has {len(mapped_nodeids)} entries")

    actual_set = set(actual_tests)

    # 1. Unmapped tests (exist in codebase, not in mapping)
    unmapped = sorted(actual_set - mapped_nodeids)
    # Filter out known infrastructure tests that don't need mapping
    unmapped_relevant = [t for t in unmapped if '/api/smoke/' not in t]

    # 2. Stale entries (in mapping but tests no longer exist)
    stale = sorted(mapped_nodeids - actual_set)

    # 3. Summary
    print("\n--- Results ---")
    print(f"  Total tests:       {len(actual_tests)}")
    print(f"  Mapped:            {len(mapped_nodeids & actual_set)}")
    print(f"  Unmapped:          {len(unmapped_relevant)}")
    print(f"  Stale (orphaned):  {len(stale)}")

    if unmapped_relevant:
        print(f"\n{'='*60}")
        print(f"UNMAPPED TESTS ({len(unmapped_relevant)}):")
        print(f"{'='*60}")
        for t in unmapped_relevant:
            print(f"  {t}")

        if fix_mode:
            print("\n--- Scaffold commands ---")
            print("Run these to create QA Touch cases + add mappings:\n")
            for t in unmapped_relevant:
                module = suggest_module(t)
                # Extract function name for title suggestion
                func = t.split('::')[-1].split('[')[0]
                title_words = func.replace('test_', '').replace('_', ' ')
                print(
                    f'python tools/qatouch_run_manager.py scaffold '
                    f'"{t}" "{module}" "Verify {title_words}"'
                )
            print(
                "\nAfter scaffolding, set Mode=Automation + Tags in QA Touch UI."
            )

    if stale:
        print(f"\n{'='*60}")
        print(f"STALE MAPPING ENTRIES ({len(stale)}):")
        print(f"{'='*60}")
        print("These tests no longer exist. Remove from mapping JSON:")
        for t in stale:
            print(f"  {t}")

    if not unmapped_relevant and not stale:
        print("\n  All tests are mapped and up-to-date!")
        return 0

    return 1


if __name__ == '__main__':
    sys.exit(main())
