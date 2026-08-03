"""Parse pytest JUnit XML and update flaky_tests.json history.

CLI: python tools/update_failure_history.py --junit reports/junit.xml

The script updates `flaky_tests.json` in the repo root. For each testcase it
records a small object in `tests[<nodeid>].last_runs` and maintains the
most-recent `history_keep` entries (default 10).
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from typing import Any

try:
    # lxml is preferred but fallback to builtin xml.etree
    from lxml import etree as ET
except Exception:
    import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FLAKY_DB = os.path.join(ROOT, "flaky_tests.json")


def load_db(path: str = FLAKY_DB) -> dict[str, Any]:
    if not os.path.exists(path):
        return {"metadata": {"history_keep": 10}, "tests": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_db(db: dict[str, Any], path: str = FLAKY_DB) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, sort_keys=True)


def parse_junit(path: str) -> dict[str, dict[str, Any]]:
    """Return mapping nodeid -> result dict {result, ts, env}

    nodeid chosen as: classname + '::' + name if classname present else file + '::' + name
    """
    tree = ET.parse(path)
    root = tree.getroot()
    results: dict[str, dict[str, Any]] = {}
    for testcase in root.findall('.//testcase'):
        classname = testcase.get('classname') or testcase.get('file') or ''
        name = testcase.get('name') or 'unknown'
        nodeid = f"{classname}::{name}" if classname else name
        status = 'pass'
        if testcase.find('failure') is not None:
            status = 'fail'
        elif testcase.find('skipped') is not None:
            status = 'skip'
        ts = datetime.now(UTC).isoformat()
        results[nodeid] = {"result": status, "ts": ts, "env": os.environ.get('ENV', 'unknown')}
    return results


def update_history(db: dict[str, Any], results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    metadata = db.setdefault('metadata', {})
    history_keep = int(metadata.get('history_keep', 10))
    tests = db.setdefault('tests', {})
    for nodeid, rec in results.items():
        entry = tests.setdefault(nodeid, {})
        last_runs = entry.setdefault('last_runs', [])
        last_runs.append({'ts': rec['ts'], 'result': rec['result'], 'env': rec.get('env', 'unknown')})
        # trim to last N
        if len(last_runs) > history_keep:
            last_runs[:] = last_runs[-history_keep:]
        # update derived fields
        fails = sum(1 for r in last_runs if r['result'] == 'fail')
        entry['failure_rate'] = round(fails / len(last_runs), 3) if last_runs else 0.0
        # last_failure
        last_fail = next((r for r in reversed(last_runs) if r['result'] == 'fail'), None)
        entry['last_failure'] = last_fail['ts'] if last_fail else None
        entry['notes'] = entry.get('notes', '')
    return db


def main():
    parser = argparse.ArgumentParser(description='Update flaky_tests.json from pytest JUnit XML')
    parser.add_argument('--junit', required=True, help='Path to junit XML file')
    args = parser.parse_args()

    if not os.path.exists(args.junit):
        raise SystemExit(f'JUnit file not found: {args.junit}')

    db = load_db()
    results = parse_junit(args.junit)
    db = update_history(db, results)
    save_db(db)
    print(f'Updated {FLAKY_DB} with {len(results)} results')


if __name__ == '__main__':
    main()
