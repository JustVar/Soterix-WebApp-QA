"""QA Touch Test Suite Analytics - snapshot, track, and report.

Pulls test case data from QA Touch API, saves timestamped snapshots,
computes deltas between snapshots, and generates metrics for the
management dashboard.

Usage:
    python tools/qatouch_analytics.py snapshot       # save today's snapshot
    python tools/qatouch_analytics.py report         # print current metrics
    python tools/qatouch_analytics.py dashboard-json # emit JSON for dashboard generator
    python tools/qatouch_analytics.py history        # show snapshot history
"""
from __future__ import annotations

import csv
import functools
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from tools.qatouch_client import QATouchClient

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SNAPSHOTS_DIR = ROOT / 'config' / 'qatouch_snapshots'
MAPPING_PATH = ROOT / 'config' / 'qatouch_case_mapping.json'
DASHBOARD_JSON_PATH = ROOT / 'config' / 'qatouch_dashboard_metrics.json'
PROJECT_KEY = 'JlW1'

SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Snapshot management
# ---------------------------------------------------------------------------
def take_snapshot() -> dict:
    """Pull all test cases from QA Touch and save a timestamped snapshot."""
    client = QATouchClient()
    print('Pulling all test cases from QA Touch...')
    all_cases = client.list_all_test_cases(PROJECT_KEY)
    print(f'  Fetched {len(all_cases)} cases')

    today = datetime.now().strftime('%Y-%m-%d')
    snapshot = {
        'snapshot_date': today,
        'snapshot_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_cases': len(all_cases),
        'cases': all_cases,
    }

    # Save with date-based filename (idempotent for same day)
    path = SNAPSHOTS_DIR / f'snapshot_{today}.json'
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'  Saved to {path.name}')
    return snapshot


def load_snapshot(date_str: str | None = None) -> dict | None:
    """Load a snapshot by date. None = latest."""
    if date_str:
        path = SNAPSHOTS_DIR / f'snapshot_{date_str}.json'
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
        return None

    # Find latest
    files = sorted(SNAPSHOTS_DIR.glob('snapshot_*.json'))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding='utf-8'))


def list_snapshots() -> list[str]:
    """Return sorted list of snapshot dates."""
    files = sorted(SNAPSHOTS_DIR.glob('snapshot_*.json'))
    dates = []
    for f in files:
        # snapshot_2026-02-20.json -> 2026-02-20
        name = f.stem.replace('snapshot_', '')
        dates.append(name)
    return dates


# ---------------------------------------------------------------------------
# Analytics from a single snapshot
# ---------------------------------------------------------------------------
def analyze_snapshot(snapshot: dict) -> dict:
    """Compute all analytics metrics from a snapshot."""
    cases = snapshot.get('cases', [])
    total = len(cases)

    # Module distribution
    by_module = Counter()
    for c in cases:
        by_module[c.get('module name', 'Unknown')] += 1

    # Type distribution
    by_type = Counter()
    for c in cases:
        by_type[c.get('Type', 'Unknown')] += 1

    # Priority distribution
    by_priority = Counter()
    for c in cases:
        by_priority[c.get('Priority', 'Unknown')] += 1

    # Tag analysis
    tag_counter = Counter()
    tagged_count = 0
    for c in cases:
        tags_raw = c.get('NewTags', '')
        if tags_raw and str(tags_raw).strip():
            tagged_count += 1
            for t in str(tags_raw).split(','):
                t = t.strip()
                if t:
                    tag_counter[t] += 1

    # Created date distribution
    by_date = Counter()
    for c in cases:
        cd = c.get('created date', '')
        if cd:
            by_date[cd[:10]] += 1

    # Created by
    by_creator = Counter()
    for c in cases:
        by_creator[c.get('created by', 'Unknown')] += 1

    # Automation coverage from Playwright mapping
    automation = _get_automation_metrics()

    # Top modules (sorted by count)
    top_modules = [
        {'module': mod, 'count': cnt}
        for mod, cnt in by_module.most_common(25)
    ]

    return {
        'snapshot_date': snapshot.get('snapshot_date', 'unknown'),
        'total_cases': total,
        'total_modules': len(by_module),
        'by_type': dict(by_type.most_common()),
        'by_priority': dict(by_priority.most_common()),
        'tags': {
            'tagged_cases': tagged_count,
            'untagged_cases': total - tagged_count,
            'tag_coverage_pct': round(tagged_count / total * 100, 1) if total else 0,
            'distribution': dict(tag_counter.most_common(20)),
        },
        'creation_dates': dict(sorted(by_date.items())),
        'created_by': dict(by_creator.most_common()),
        'top_modules': top_modules,
        'automation': automation,
    }


def _get_automation_metrics() -> dict:
    """Extract automation coverage metrics from the Playwright mapping file."""
    if not MAPPING_PATH.exists():
        return {
            'total_playwright_tests': 0,
            'mapped_to_qatouch': 0,
            'automation_coverage_pct': 0,
        }

    mapping = json.loads(MAPPING_PATH.read_text(encoding='utf-8'))
    total_tests = mapping.get('total_playwright_tests', 0)
    total_mapped = mapping.get('total_mapped', 0)
    mappings = mapping.get('mappings', {})

    # Count by module
    automated_by_module = Counter()
    for nodeid, info in mappings.items():
        mod = info.get('module', 'Unknown')
        automated_by_module[mod] += 1

    # Count auto_matched vs manually created
    auto_matched = sum(1 for m in mappings.values() if m.get('auto_matched', True))
    manually_mapped = len(mappings) - auto_matched

    # Count API vs UI tests
    api_tests = sum(1 for k in mappings if 'tests/api/' in k)
    ui_tests = sum(1 for k in mappings if 'tests/ui/' in k)

    return {
        'total_playwright_tests': total_tests,
        'mapped_to_qatouch': total_mapped,
        'unmapped_tests': total_tests - total_mapped,
        'auto_matched': auto_matched,
        'manually_mapped': manually_mapped,
        'api_tests': api_tests,
        'ui_tests': ui_tests,
        'by_module': dict(automated_by_module.most_common(25)),
    }


# ---------------------------------------------------------------------------
# Delta analysis between snapshots
# ---------------------------------------------------------------------------
def compute_delta(older: dict, newer: dict) -> dict:
    """Compare two snapshots and compute what changed."""
    old_cases = {c['case_key']: c for c in older.get('cases', [])}
    new_cases = {c['case_key']: c for c in newer.get('cases', [])}

    old_keys = set(old_cases.keys())
    new_keys = set(new_cases.keys())

    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys

    # Cases that changed (title, module, type, tags)
    modified = []
    for key in old_keys & new_keys:
        old = old_cases[key]
        new = new_cases[key]
        changes = {}
        for field in ['case_title', 'module name', 'Type', 'NewTags', 'Priority']:
            if str(old.get(field, '')) != str(new.get(field, '')):
                changes[field] = {'old': old.get(field, ''), 'new': new.get(field, '')}
        if changes:
            modified.append({'case_key': key, 'title': new.get('case_title', ''), 'changes': changes})

    # New cases by module
    added_by_module = Counter()
    for key in added_keys:
        mod = new_cases[key].get('module name', 'Unknown')
        added_by_module[mod] += 1

    return {
        'from_date': older.get('snapshot_date', '?'),
        'to_date': newer.get('snapshot_date', '?'),
        'net_new': len(added_keys) - len(removed_keys),
        'added': len(added_keys),
        'removed': len(removed_keys),
        'modified': len(modified),
        'added_by_module': dict(added_by_module.most_common()),
        'added_cases': [
            {'case_key': k, 'title': new_cases[k].get('case_title', ''),
             'module': new_cases[k].get('module name', '')}
            for k in sorted(added_keys)
        ],
        'removed_cases': [
            {'case_key': k, 'title': old_cases[k].get('case_title', ''),
             'module': old_cases[k].get('module name', '')}
            for k in sorted(removed_keys)
        ],
        'modified_cases': modified[:50],  # Cap for readability
    }


# ---------------------------------------------------------------------------
# Dashboard metrics JSON
# ---------------------------------------------------------------------------
def generate_dashboard_json(snapshot: dict | None = None) -> dict:
    """Generate the metrics JSON consumed by the dashboard generator."""
    if snapshot is None:
        snapshot = load_snapshot()
    if not snapshot:
        return {}

    metrics = analyze_snapshot(snapshot)

    # Build history from all snapshots
    history = []
    for date_str in list_snapshots():
        snap = load_snapshot(date_str)
        if snap:
            history.append({
                'date': date_str,
                'total_cases': snap.get('total_cases', 0),
            })

    # Automation coverage over time (from mapping - single point for now)
    auto = metrics['automation']
    total = metrics['total_cases']
    coverage_pct = round(auto['mapped_to_qatouch'] / total * 100, 1) if total else 0

    dashboard = {
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'snapshot_date': metrics['snapshot_date'],
        'total_cases': total,
        'total_modules': metrics['total_modules'],
        'automation': {
            'playwright_tests': auto['total_playwright_tests'],
            'mapped_to_qatouch': auto['mapped_to_qatouch'],
            'coverage_pct': coverage_pct,
            'api_tests': auto.get('api_tests', 0),
            'ui_tests': auto.get('ui_tests', 0),
        },
        'tags': {
            'smoke': metrics['tags']['distribution'].get('smoke', 0),
            'sanity': metrics['tags']['distribution'].get('sanity', 0),
            'tagged_pct': metrics['tags']['tag_coverage_pct'],
        },
        'by_type': metrics['by_type'],
        'top_modules': metrics['top_modules'][:15],
        'history': history,
        'creation_dates': metrics['creation_dates'],
    }

    # Compute delta from previous snapshot if available
    dates = list_snapshots()
    if len(dates) >= 2:
        prev = load_snapshot(dates[-2])
        curr = load_snapshot(dates[-1])
        if prev and curr:
            delta = compute_delta(prev, curr)
            dashboard['delta'] = {
                'from_date': delta['from_date'],
                'to_date': delta['to_date'],
                'net_new': delta['net_new'],
                'added': delta['added'],
                'removed': delta['removed'],
                'modified': delta['modified'],
            }

    # Write JSON for dashboard generator
    DASHBOARD_JSON_PATH.write_text(
        json.dumps(dashboard, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    print(f'Dashboard metrics written to {DASHBOARD_JSON_PATH.name}')
    return dashboard


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------
def cmd_snapshot():
    """Take a new snapshot and generate dashboard metrics."""
    snap = take_snapshot()
    metrics = analyze_snapshot(snap)
    _print_summary(metrics)
    generate_dashboard_json(snap)


def cmd_report():
    """Print a full report from the latest snapshot."""
    snap = load_snapshot()
    if not snap:
        print('No snapshots found. Run: python tools/qatouch_analytics.py snapshot')
        return
    metrics = analyze_snapshot(snap)
    _print_summary(metrics)

    # Delta from previous
    dates = list_snapshots()
    if len(dates) >= 2:
        prev = load_snapshot(dates[-2])
        if prev:
            delta = compute_delta(prev, snap)
            _print_delta(delta)


def cmd_dashboard_json():
    """Generate dashboard JSON from latest snapshot."""
    snap = load_snapshot()
    if not snap:
        print('No snapshots found. Run: python tools/qatouch_analytics.py snapshot')
        return
    dashboard = generate_dashboard_json(snap)
    print(json.dumps(dashboard, indent=2, ensure_ascii=False))


def cmd_history():
    """Show snapshot history."""
    dates = list_snapshots()
    if not dates:
        print('No snapshots found.')
        return
    print(f'\n{"=" * 50}')
    print(f'  QA Touch Snapshot History ({len(dates)} snapshots)')
    print(f'{"=" * 50}')
    for d in dates:
        snap = load_snapshot(d)
        if snap:
            print(f'  {d}  {snap.get("total_cases", "?"):>5} cases')


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------
def _print_summary(metrics: dict):
    auto = metrics['automation']
    total = metrics['total_cases']
    coverage_pct = round(auto['mapped_to_qatouch'] / total * 100, 1) if total else 0

    print(f'\n{"=" * 60}')
    print(f'  QA Touch Test Suite Analytics - {metrics["snapshot_date"]}')
    print(f'{"=" * 60}')
    print(f'\n  Total Test Cases:        {total:,}')
    print(f'  Total Modules:           {metrics["total_modules"]}')
    print(f'\n  --- Automation Coverage ---')
    print(f'  Playwright Tests:        {auto["total_playwright_tests"]}')
    print(f'  Mapped to QA Touch:      {auto["mapped_to_qatouch"]}')
    print(f'  Automation Coverage:     {coverage_pct}% ({auto["mapped_to_qatouch"]}/{total})')
    print(f'\n  --- Test Types ---')
    for t, cnt in metrics['by_type'].items():
        print(f'    {cnt:>5}  {t}')
    print(f'\n  --- Tags ---')
    print(f'  Tagged:                  {metrics["tags"]["tagged_cases"]} ({metrics["tags"]["tag_coverage_pct"]}%)')
    print(f'  Untagged:                {metrics["tags"]["untagged_cases"]}')
    for tag, cnt in list(metrics['tags']['distribution'].items())[:10]:
        print(f'    {cnt:>5}  {tag}')
    print(f'\n  --- Top 15 Modules ---')
    for m in metrics['top_modules'][:15]:
        bar = '#' * min(m['count'], 50)
        print(f'    {m["count"]:>4}  {m["module"][:40]:<40}  {bar}')
    print(f'\n  --- Creation Timeline ---')
    for d, cnt in sorted(metrics['creation_dates'].items()):
        print(f'    {d}  +{cnt} cases')


def _print_delta(delta: dict):
    print(f'\n  --- Changes: {delta["from_date"]} -> {delta["to_date"]} ---')
    print(f'  Net New:    {delta["net_new"]:+d}')
    print(f'  Added:      {delta["added"]}')
    print(f'  Removed:    {delta["removed"]}')
    print(f'  Modified:   {delta["modified"]}')
    if delta.get('added_by_module'):
        print(f'  Added by module:')
        for mod, cnt in delta['added_by_module'].items():
            print(f'    +{cnt}  {mod}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser(description='QA Touch Test Suite Analytics')
    parser.add_argument('command', nargs='?', default='report',
                        choices=['snapshot', 'report', 'dashboard-json', 'history'],
                        help='Command to run (default: report)')
    args = parser.parse_args()

    if args.command == 'snapshot':
        cmd_snapshot()
    elif args.command == 'report':
        cmd_report()
    elif args.command == 'dashboard-json':
        cmd_dashboard_json()
    elif args.command == 'history':
        cmd_history()


if __name__ == '__main__':
    main()
