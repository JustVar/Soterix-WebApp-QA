"""QA Touch <-> Playwright Test Case Mapper.

Builds and maintains a mapping between Playwright test node IDs and
QA Touch test case keys.  Provides:

  1. Auto-match: keyword-based matching (test name words vs case titles)
  2. Export mapping as JSON (config/qatouch_case_mapping.json)
  3. Generate tag CSV for bulk import in QA Touch UI
  4. Show unmatched tests / cases for manual review

Usage:
  python tools/qatouch_mapper.py build     # fetch cases + collect tests -> build mapping
  python tools/qatouch_mapper.py show      # print current mapping summary
  python tools/qatouch_mapper.py csv       # generate tag CSV for QA Touch import
  python tools/qatouch_mapper.py unmatched # show unmatched Playwright tests
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

from tools.qatouch_client import QATouchClient

MAPPING_PATH = ROOT / 'config' / 'qatouch_case_mapping.json'
PROJECT_KEY = os.environ.get('QATOUCH_PROJECT_ID', 'JlW1')

# Module name mapping: Playwright directory -> QA Touch module name
PLAYWRIGHT_TO_QT_MODULE = {
    'login': 'Login',
    'views': 'Views',
    'events': 'Search',      # Events are under Search module in QA Touch
    'search': 'Search',
    'insights': 'Insights',
    'media': 'Media',
    'admin': 'Admin',
    'notifications': 'Notifications',
    'maps': 'Maps',
    'chats': 'Chat',
    'sequences': 'Camera Sequence',
    'smoke': None,            # API smoke tests - no direct QA Touch module
}


def collect_playwright_tests() -> list[dict]:
    """Run pytest --collect-only to get all test node IDs."""
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '--collect-only'],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    tests = []
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if '::' in line and line.startswith('tests/'):
            parts = line.split('/')
            # Determine module from directory structure
            if len(parts) >= 3:
                if parts[1] == 'ui':
                    module_dir = parts[2]
                elif parts[1] == 'api':
                    module_dir = parts[2]  # e.g., 'smoke'
                else:
                    module_dir = parts[1]
            else:
                module_dir = 'other'

            # Extract test function name (strip class and parameters)
            func_name = line.split('::')[-1].split('[')[0]

            tests.append({
                'nodeid': line,
                'module_dir': module_dir,
                'func_name': func_name,
                'qt_module': PLAYWRIGHT_TO_QT_MODULE.get(module_dir),
            })
    return tests


def fetch_qt_cases() -> dict[str, list[dict]]:
    """Fetch all QA Touch test cases grouped by module."""
    client = QATouchClient()
    all_cases = client.list_all_test_cases(PROJECT_KEY)
    by_module = defaultdict(list)
    for case in all_cases:
        mod = case.get('module name', 'Unknown')
        by_module[mod].append({
            'key': case['case_key'],
            'title': case['case_title'],
            'module': mod,
        })
    return dict(by_module)


def normalize_test_name(func_name: str) -> list[str]:
    """Convert test_function_name to searchable keywords."""
    # Remove test_ prefix
    name = re.sub(r'^test_', '', func_name)
    # Split on underscores
    words = name.split('_')
    # Filter out very short/common words
    stop_words = {'to', 'the', 'a', 'an', 'is', 'in', 'on', 'for', 'with', 'and', 'or', 'of'}
    return [w.lower() for w in words if len(w) > 1 and w.lower() not in stop_words]


def score_match(test_keywords: list[str], case_title: str) -> float:
    """Score how well test keywords match a QA Touch case title."""
    title_lower = case_title.lower()
    title_words = set(re.findall(r'[a-z]+', title_lower))

    if not test_keywords:
        return 0.0

    matches = 0
    for kw in test_keywords:
        # Exact word match
        if kw in title_words:
            matches += 1
        # Partial/substring match
        elif kw in title_lower:
            matches += 0.5

    return matches / len(test_keywords)


def auto_match(
    tests: list[dict],
    qt_cases: dict[str, list[dict]],
    threshold: float = 0.5,
) -> dict[str, dict]:
    """Auto-match Playwright tests to QA Touch cases by keyword similarity.

    Returns: {nodeid: {case_key, case_title, score, module}} for matches above threshold.
    """
    mapping = {}
    for test in tests:
        keywords = normalize_test_name(test['func_name'])
        qt_mod = test.get('qt_module')

        # Search within the mapped module first, then all modules
        search_pools = []
        if qt_mod and qt_mod in qt_cases:
            search_pools.append(qt_cases[qt_mod])
        # Also search all cases as fallback
        all_cases_flat = [c for cases in qt_cases.values() for c in cases]
        search_pools.append(all_cases_flat)

        best_score = 0.0
        best_case = None
        for pool in search_pools:
            for case in pool:
                score = score_match(keywords, case['title'])
                if score > best_score:
                    best_score = score
                    best_case = case
            # If we found a good match in the preferred module, stop
            if best_score >= threshold:
                break

        if best_case and best_score >= threshold:
            mapping[test['nodeid']] = {
                'case_key': best_case['key'],
                'case_title': best_case['title'],
                'score': round(best_score, 2),
                'module': best_case['module'],
                'auto_matched': True,
            }

    return mapping


def load_mapping() -> dict:
    """Load existing mapping from JSON file."""
    if MAPPING_PATH.exists():
        with open(MAPPING_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {'version': 1, 'project_key': PROJECT_KEY, 'mappings': {}}


def save_mapping(data: dict) -> None:
    """Save mapping to JSON file."""
    MAPPING_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MAPPING_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f'Saved mapping to {MAPPING_PATH}')


def cmd_build():
    """Build/update the case mapping."""
    print('Collecting Playwright tests...')
    tests = collect_playwright_tests()
    print(f'  Found {len(tests)} test nodes')

    print('Fetching QA Touch test cases...')
    qt_cases = fetch_qt_cases()
    total_cases = sum(len(v) for v in qt_cases.values())
    print(f'  Found {total_cases} cases across {len(qt_cases)} modules')

    # Load existing mapping to preserve manual overrides
    existing = load_mapping()
    existing_mappings = existing.get('mappings', {})

    # Auto-match new tests only (don't overwrite manual mappings).
    # Floor raised 0.5 -> 0.75 (08/20): at 0.5 a third of the repo was
    # word-overlap guesses. New matches are PROPOSALS (reviewed=False) and a
    # case already claimed by an existing row is refused - one case, one
    # test function. tools/qatouch_mapping.py is the review flow.
    unmatched_tests = [t for t in tests if t['nodeid'] not in existing_mappings]
    print(f'\nAuto-matching {len(unmatched_tests)} unmapped tests...')
    new_matches = auto_match(unmatched_tests, qt_cases, threshold=0.75)
    claimed = {e['case_key'] for e in existing_mappings.values()}
    refused = {n: m for n, m in new_matches.items() if m['case_key'] in claimed}
    new_matches = {n: m for n, m in new_matches.items() if m['case_key'] not in claimed}
    for m in new_matches.values():
        m['reviewed'] = False
    print(f'  Auto-matched (as unreviewed proposals): {len(new_matches)}')
    if refused:
        print(f'  Refused {len(refused)} match(es) whose case is already claimed:')
        for n, m in list(refused.items())[:8]:
            print(f'    {m["case_key"]} <- {n}')

    # Merge
    merged = {**existing_mappings, **new_matches}
    data = {
        'version': 1,
        'project_key': PROJECT_KEY,
        'total_playwright_tests': len(tests),
        'total_mapped': len(merged),
        'mappings': merged,
    }
    save_mapping(data)

    # Summary
    matched_count = len(merged)
    unmatched_count = len(tests) - matched_count
    print('\n=== Mapping Summary ===')
    print(f'  Playwright tests: {len(tests)}')
    print(f'  Mapped:           {matched_count}')
    print(f'  Unmapped:         {unmatched_count}')
    if new_matches:
        print('\n  New auto-matches:')
        for nodeid, info in sorted(new_matches.items()):
            print(f'    {nodeid}')
            title = info['case_title'].encode('ascii', 'replace').decode('ascii')
            print(f'      -> [{info["case_key"]}] {title} (score={info["score"]})')


def cmd_show():
    """Show current mapping summary."""
    data = load_mapping()
    mappings = data.get('mappings', {})
    if not mappings:
        print('No mappings found. Run: python tools/qatouch_mapper.py build')
        return

    print(f'Project: {data.get("project_key", "?")}')
    print(f'Total mapped: {len(mappings)}')

    # Group by module
    by_module = defaultdict(list)
    for nodeid, info in mappings.items():
        mod = info.get('module', 'Unknown')
        by_module[mod].append((nodeid, info))

    for mod in sorted(by_module):
        items = by_module[mod]
        auto = sum(1 for _, i in items if i.get('auto_matched'))
        manual = len(items) - auto
        print(f'\n  {mod} ({len(items)} mapped, {auto} auto / {manual} manual):')
        for nodeid, info in sorted(items):
            marker = 'A' if info.get('auto_matched') else 'M'
            print(f'    [{marker}] {nodeid} -> {info["case_key"]} (score={info.get("score", "n/a")})')


def cmd_unmatched():
    """Show Playwright tests not yet mapped to QA Touch cases."""
    tests = collect_playwright_tests()
    data = load_mapping()
    mappings = data.get('mappings', {})

    unmatched = [t for t in tests if t['nodeid'] not in mappings]
    print(f'Unmatched Playwright tests: {len(unmatched)} / {len(tests)}')
    for t in sorted(unmatched, key=lambda x: x['nodeid']):
        print(f'  {t["nodeid"]}  (module_dir={t["module_dir"]})')


def cmd_csv():
    """Generate CSV files for QA Touch bulk tag import.

    Creates two CSVs:
    - qatouch_smoke_tags.csv: cases that should be tagged SMOKE
    - qatouch_automated_tags.csv: cases mapped to Playwright tests (AUTOMATED tag)
    """
    data = load_mapping()
    mappings = data.get('mappings', {})

    if not mappings:
        print('No mappings found. Run: python tools/qatouch_mapper.py build')
        return

    output_dir = ROOT / 'tools'

    # AUTOMATED tag CSV - all mapped cases
    automated_keys = set()
    for nodeid, info in mappings.items():
        automated_keys.add(info['case_key'])

    automated_csv = output_dir / 'qatouch_automated_tags.csv'
    with open(automated_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Case Key', 'Tags'])
        for key in sorted(automated_keys):
            writer.writerow([key, 'AUTOMATED'])
    print(f'Generated {automated_csv} ({len(automated_keys)} cases)')

    # SMOKE tag CSV - login + basic navigation tests
    smoke_nodeids = [
        nodeid for nodeid in mappings
        if any(kw in nodeid for kw in [
            'test_login_valid', 'test_valid_credentials', 'test_logout',
            'test_navigate_to_', 'test_camera_loads', 'test_open_my_views',
            '/smoke/', 'test_get_site_status', 'test_get_camera_tree',
        ])
    ]
    smoke_keys = set()
    for nodeid in smoke_nodeids:
        if nodeid in mappings:
            smoke_keys.add(mappings[nodeid]['case_key'])

    smoke_csv = output_dir / 'qatouch_smoke_tags.csv'
    with open(smoke_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Case Key', 'Tags'])
        for key in sorted(smoke_keys):
            writer.writerow([key, 'SMOKE'])
    print(f'Generated {smoke_csv} ({len(smoke_keys)} cases)')


if __name__ == '__main__':
    commands = {
        'build': cmd_build,
        'show': cmd_show,
        'unmatched': cmd_unmatched,
        'csv': cmd_csv,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(f'Usage: python tools/qatouch_mapper.py [{"|".join(commands)}]')
        sys.exit(1)

    commands[sys.argv[1]]()
