"""QA Touch Suite Builder - identifies test cases for SMOKE, SANITY, and REGRESSION suites.

Fetches all test cases from QA Touch, applies selection criteria based on
module hierarchy and title keywords, and outputs case lists for manual
bulk-tagging in the QA Touch UI.

Usage:
  python tools/qatouch_suite_builder.py smoke      # List SMOKE candidates (~60 cases)
  python tools/qatouch_suite_builder.py sanity      # List SANITY candidates (~200 cases)
  python tools/qatouch_suite_builder.py all         # List both suites
  python tools/qatouch_suite_builder.py csv         # Generate CSV files for reference

Each command prints case codes grouped by module so you can find them quickly
in the QA Touch UI for bulk-tagging.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from tools.qatouch_client import QATouchClient

PROJECT_KEY = os.environ.get('QATOUCH_PROJECT_ID', 'JlW1')

# ---------------------------------------------------------------------------
# SMOKE suite: "does the app load and work at a basic level?"
#   ~60 cases covering login, navigation, and basic actions per module
# ---------------------------------------------------------------------------

# Module name -> list of sub-module name substrings to include for SMOKE
# None = include ALL cases in that module; [] = skip module entirely
SMOKE_MODULES = {
    # Authentication
    'Login UI': {
        'submodules': ['Authentication', 'Login UI', 'Session Management'],
        'title_keywords': ['valid credentials', 'login page', 'session', 'redirect', 'landing'],
        'max_cases': 8,
    },
    'Logout': {
        'submodules': ['Logout - Session', 'UX & Usability'],
        'title_keywords': ['logout', 'session', 'redirect', 'clear'],
        'max_cases': 6,
    },
    # Core modules - landing/load cases
    'Default Landing': {
        'submodules': None,  # include all
        'title_keywords': ['load', 'landing', 'default', 'login'],
        'max_cases': 2,
    },
    'Camera Grid': {
        'submodules': None,
        'title_keywords': ['load', 'display', 'grid', 'camera', 'render'],
        'max_cases': 4,
    },
    'Devices Tab': {
        'submodules': None,
        'title_keywords': ['load', 'display', 'list', 'device', 'tab'],
        'max_cases': 3,
    },
    'Left Navigation': {
        'submodules': None,
        'title_keywords': ['nav', 'menu', 'sidebar', 'click'],
        'max_cases': 2,
    },
    # Events
    'Landing Page': {
        'submodules': None,
        'title_keywords': ['load', 'landing', 'display', 'event'],
        'max_cases': 2,
    },
    'Search Results': {
        'submodules': None,
        'title_keywords': ['search', 'result', 'display', 'load'],
        'max_cases': 3,
    },
    # Maps
    'Landing & Navigation': {
        'submodules': None,
        'title_keywords': ['load', 'landing', 'navigate', 'map'],
        'max_cases': 3,
    },
    'Google Maps View': {
        'submodules': None,
        'title_keywords': ['load', 'render', 'display', 'map'],
        'max_cases': 3,
    },
    # Insights
    'My Dashboard': {
        'submodules': None,
        'title_keywords': ['load', 'display', 'dashboard', 'landing'],
        'max_cases': 3,
    },
    'Preset Dashboard': {
        'submodules': None,
        'title_keywords': ['load', 'display', 'preset'],
        'max_cases': 2,
    },
    # Media
    'Media Listing & Actions': {
        'submodules': None,
        'title_keywords': ['load', 'list', 'display', 'navigate', 'tab'],
        'max_cases': 3,
    },
    # Search
    'Search Landing Page': {
        'submodules': None,
        'title_keywords': ['load', 'landing', 'display', 'category', 'navigate'],
        'max_cases': 4,
    },
    # LPR
    'LPR Landing Page': {
        'submodules': None,
        'title_keywords': ['load', 'landing', 'lpr'],
        'max_cases': 2,
    },
    # Admin
    'Dashboard Landing': {
        'submodules': None,
        'title_keywords': ['load', 'landing', 'dashboard', 'widget'],
        'max_cases': 2,
    },
    'Sites Widget': {
        'submodules': None,
        'title_keywords': ['display', 'load', 'site', 'widget'],
        'max_cases': 2,
    },
    'Users Landing Page': {
        'submodules': None,
        'title_keywords': ['load', 'landing', 'user', 'display'],
        'max_cases': 2,
    },
    'Rules Module': {
        'submodules': None,
        'title_keywords': ['load', 'landing', 'rule', 'display', 'list'],
        'max_cases': 3,
    },
    # Notifications
    'Notification Panel': {
        'submodules': None,
        'title_keywords': ['open', 'display', 'panel', 'notification', 'bell'],
        'max_cases': 3,
    },
    'Notification Icon': {
        'submodules': None,
        'title_keywords': ['icon', 'badge', 'count', 'display'],
        'max_cases': 2,
    },
    # Chat
    'One-to-One Chat': {
        'submodules': None,
        'title_keywords': ['send', 'message', 'chat', 'open'],
        'max_cases': 2,
    },
}

# ---------------------------------------------------------------------------
# SANITY suite: SMOKE + deeper happy-path testing per module
#   ~200 cases covering primary workflows
# ---------------------------------------------------------------------------

SANITY_ADDITIONAL_MODULES = {
    # Deeper Auth
    'Forgot Password': {
        'submodules': None,
        'title_keywords': None,  # include all
        'max_cases': 5,
    },
    'Validation': {
        'submodules': None,
        'title_keywords': ['invalid', 'empty', 'error', 'required', 'valid'],
        'max_cases': 4,
    },
    'Session Security': {
        'submodules': None,
        'title_keywords': None,
        'max_cases': 3,
    },
    # Views deeper
    'Channels': {
        'submodules': None,
        'title_keywords': ['switch', 'channel', 'select', 'stream'],
        'max_cases': 4,
    },
    'Layouts': {
        'submodules': None,
        'title_keywords': ['layout', 'grid', 'change', 'select'],
        'max_cases': 4,
    },
    'My Views': {
        'submodules': None,
        'title_keywords': ['save', 'create', 'load', 'view', 'rename'],
        'max_cases': 5,
    },
    'Camera Search': {
        'submodules': None,
        'title_keywords': ['search', 'filter', 'find', 'result'],
        'max_cases': 3,
    },
    'Share Live View': {
        'submodules': None,
        'title_keywords': ['share', 'link', 'copy', 'generate'],
        'max_cases': 3,
    },
    'Snapshot': {
        'submodules': None,
        'title_keywords': ['snapshot', 'capture', 'save', 'download'],
        'max_cases': 3,
    },
    'Playback Controls': {
        'submodules': None,
        'title_keywords': ['play', 'pause', 'seek', 'control'],
        'max_cases': 3,
    },
    # Events deeper
    'Select Site Dropdown': {
        'submodules': None,
        'title_keywords': ['select', 'site', 'dropdown', 'filter'],
        'max_cases': 4,
    },
    'Time Range Filter': {
        'submodules': None,
        'title_keywords': ['time', 'range', 'filter', 'date', 'select'],
        'max_cases': 5,
    },
    'All Rules Filter': {
        'submodules': None,
        'title_keywords': ['rule', 'filter', 'select', 'dropdown'],
        'max_cases': 4,
    },
    'Export': {
        'submodules': None,
        'title_keywords': ['export', 'download', 'csv', 'report'],
        'max_cases': 3,
    },
    'Pinned Clips Panel': {
        'submodules': None,
        'title_keywords': ['pin', 'clip', 'panel', 'add', 'remove'],
        'max_cases': 4,
    },
    # Maps deeper
    'Camera Interaction & Preview': {
        'submodules': None,
        'title_keywords': ['click', 'preview', 'camera', 'interact'],
        'max_cases': 4,
    },
    'Static Maps': {
        'submodules': None,
        'title_keywords': ['static', 'map', 'view', 'load'],
        'max_cases': 4,
    },
    'Grid/List Toggle': {
        'submodules': None,
        'title_keywords': ['toggle', 'grid', 'list', 'switch'],
        'max_cases': 3,
    },
    # Insights deeper
    'Create New Widget': {
        'submodules': None,
        'title_keywords': ['create', 'widget', 'add', 'new'],
        'max_cases': 4,
    },
    'Graph Type': {
        'submodules': None,
        'title_keywords': ['graph', 'chart', 'type', 'select'],
        'max_cases': 4,
    },
    'Widget Search': {
        'submodules': None,
        'title_keywords': ['search', 'widget', 'find', 'filter'],
        'max_cases': 3,
    },
    'Report': {
        'submodules': None,
        'title_keywords': ['report', 'generate', 'export', 'download'],
        'max_cases': 4,
    },
    # Media deeper
    'Vault': {
        'submodules': None,
        'title_keywords': ['vault', 'folder', 'upload', 'browse'],
        'max_cases': 3,
    },
    'Tabs': {
        'submodules': None,
        'title_keywords': ['tab', 'switch', 'navigate', 'select'],
        'max_cases': 3,
    },
    # Search deeper
    'Category - Event': {
        'submodules': None,
        'title_keywords': ['event', 'category', 'select', 'search'],
        'max_cases': 5,
    },
    'Category - Person': {
        'submodules': None,
        'title_keywords': ['person', 'category', 'select', 'search'],
        'max_cases': 5,
    },
    'Category - Vehicle': {
        'submodules': None,
        'title_keywords': ['vehicle', 'category', 'select', 'search'],
        'max_cases': 4,
    },
    'Zone - Setup & Drawing': {
        'submodules': None,
        'title_keywords': ['zone', 'draw', 'setup', 'create'],
        'max_cases': 4,
    },
    # LPR deeper
    'Add License Plate': {
        'submodules': None,
        'title_keywords': ['add', 'plate', 'create', 'license'],
        'max_cases': 4,
    },
    'Events Panel': {
        'submodules': None,
        'title_keywords': ['event', 'panel', 'load', 'display'],
        'max_cases': 3,
    },
    'Notifications': {
        'submodules': None,
        'title_keywords': ['notification', 'alert', 'trigger'],
        'max_cases': 3,
    },
    # Admin deeper
    'Map Creation': {
        'submodules': None,
        'title_keywords': ['create', 'map', 'add', 'new'],
        'max_cases': 4,
    },
    'Map Editing': {
        'submodules': None,
        'title_keywords': ['edit', 'update', 'modify', 'save'],
        'max_cases': 4,
    },
    'Add New User': {
        'submodules': None,
        'title_keywords': ['add', 'create', 'user', 'new'],
        'max_cases': 4,
    },
    'Role Assignment': {
        'submodules': None,
        'title_keywords': ['role', 'assign', 'permission'],
        'max_cases': 3,
    },
    'Add New Rule': {
        'submodules': None,
        'title_keywords': ['add', 'create', 'rule', 'new'],
        'max_cases': 4,
    },
    'Fire-Smoke Detection': {
        'submodules': None,
        'title_keywords': ['fire', 'smoke', 'detection', 'configure'],
        'max_cases': 4,
    },
    'Intrusion Detection': {
        'submodules': None,
        'title_keywords': ['intrusion', 'detect', 'configure', 'zone'],
        'max_cases': 4,
    },
    'Audit Trail': {
        'submodules': None,
        'title_keywords': ['audit', 'trail', 'log', 'history'],
        'max_cases': 4,
    },
    'Event Wall': {
        'submodules': None,
        'title_keywords': ['event', 'wall', 'display', 'load'],
        'max_cases': 4,
    },
    'Multi-Factor Authentication': {
        'submodules': None,
        'title_keywords': ['mfa', 'multi-factor', '2fa', 'enable', 'setup'],
        'max_cases': 4,
    },
    'Storage': {
        'submodules': None,
        'title_keywords': ['storage', 'disk', 'capacity', 'usage'],
        'max_cases': 3,
    },
    'Site Actions (More Options Menu)': {
        'submodules': None,
        'title_keywords': ['site', 'action', 'menu', 'option'],
        'max_cases': 3,
    },
    'Webhooks': {
        'submodules': None,
        'title_keywords': ['webhook', 'configure', 'create', 'url'],
        'max_cases': 3,
    },
    # Chat deeper
    'Group Chat': {
        'submodules': None,
        'title_keywords': ['group', 'create', 'chat', 'add'],
        'max_cases': 4,
    },
    'Acknowledgement Status': {
        'submodules': None,
        'title_keywords': ['acknowledge', 'status', 'read', 'mark'],
        'max_cases': 3,
    },
}


def fetch_all_cases() -> list[dict]:
    """Fetch all test cases from QA Touch."""
    client = QATouchClient()
    print(f'Fetching all test cases from project {PROJECT_KEY}...')
    cases = client.list_all_test_cases(PROJECT_KEY)
    print(f'  Fetched {len(cases)} cases')
    return cases


def match_cases(cases: list[dict], module_config: dict) -> list[dict]:
    """Select test cases matching the module config criteria."""
    selected = []
    module_counts = defaultdict(int)

    for case in cases:
        mod_name = case.get('module name', '')
        title = case.get('case_title', '').lower()
        case_key = case.get('case_key', '')

        for target_module, config in module_config.items():
            max_cases = config.get('max_cases', 999)

            # Check if module name matches
            if mod_name != target_module:
                continue

            # Already have enough from this module
            if module_counts[target_module] >= max_cases:
                continue

            # Check title keywords if specified
            keywords = config.get('title_keywords')
            if keywords:
                if not any(kw.lower() in title for kw in keywords):
                    continue

            selected.append({
                'case_key': case_key,
                'module': mod_name,
                'title': case.get('case_title', ''),
                'priority': case.get('Priority', ''),
            })
            module_counts[target_module] += 1

    return selected


def print_suite(name: str, cases: list[dict]):
    """Print a suite summary grouped by module."""
    by_module = defaultdict(list)
    for c in cases:
        by_module[c['module']].append(c)

    print(f'\n{"="*70}')
    print(f'  {name} SUITE - {len(cases)} test cases')
    print(f'{"="*70}')

    for mod in sorted(by_module.keys()):
        mod_cases = by_module[mod]
        print(f'\n  [{mod}] ({len(mod_cases)} cases)')
        for c in mod_cases:
            print(f'    {c["case_key"]:>10s}  {c["title"][:70]}')

    # Print just the case codes for easy searching
    print(f'\n--- Case codes for bulk search (comma-separated) ---')
    all_codes = [c['case_key'] for c in cases]
    # Print in groups of 10 for readability
    for i in range(0, len(all_codes), 10):
        print(f'  {", ".join(all_codes[i:i+10])}')


def write_csv(name: str, cases: list[dict]):
    """Write CSV file for reference."""
    outpath = ROOT / 'tools' / f'qatouch_{name.lower()}_suite.csv'
    with open(outpath, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Case Key', 'Module', 'Title', 'Priority', 'Tag'])
        for c in cases:
            w.writerow([c['case_key'], c['module'], c['title'], c['priority'], name.upper()])
    print(f'  Written: {outpath} ({len(cases)} cases)')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    cases = fetch_all_cases()

    smoke_cases = match_cases(cases, SMOKE_MODULES)
    sanity_all_modules = {**SMOKE_MODULES, **SANITY_ADDITIONAL_MODULES}
    sanity_cases = match_cases(cases, sanity_all_modules)

    if cmd == 'smoke':
        print_suite('SMOKE', smoke_cases)
        print(f'\n  TAGGING INSTRUCTIONS:')
        print(f'  1. In QA Touch, go to Test Cases > Test Case Search Page')
        print(f'  2. Search by Case Id for each code above')
        print(f'  3. Select the cases, click Bulk Edit (or open individually)')
        print(f'  4. Add tag: SMOKE')
        print(f'  5. Save')
        print(f'\n  TIP: Work module-by-module. Click a module in the left tree,')
        print(f'       then select the matching cases in the right panel.')

    elif cmd == 'sanity':
        print_suite('SANITY', sanity_cases)
        print(f'\n  TAGGING INSTRUCTIONS: Same as SMOKE but use tag: SANITY')

    elif cmd == 'all':
        print_suite('SMOKE', smoke_cases)
        print_suite('SANITY', sanity_cases)

    elif cmd == 'csv':
        write_csv('SMOKE', smoke_cases)
        write_csv('SANITY', sanity_cases)
        print('CSVs generated for reference.')

    else:
        print(f'Unknown command: {cmd}')
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
