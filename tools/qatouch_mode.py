#!/usr/bin/env python3
"""Read and set the Mode (Automation / Manual) on QA Touch test cases.

Public API only - no browser, no session that expires. Replaces
qatouch_set_mode.py (browser UI) and qatouch_api_mode_update.py (internal
API), both now in tools/archive/.

    python tools/qatouch_mode.py status                       # counts by mode
    python tools/qatouch_mode.py list --mode Automation       # keys in a mode
    python tools/qatouch_mode.py set --mode Automation --keys K1,K2
    python tools/qatouch_mode.py set --mode Manual --from-csv file.csv
    python tools/qatouch_mode.py sync                         # mapping vs mode report
    python tools/qatouch_mode.py sync --apply                 # flip mapped cases to Automation

Why `sync` exists
    A test that has a Playwright implementation should be Mode=Automation in
    QA Touch, and a case that is Mode=Automation should have a test. Two
    things record that today - config/qatouch_case_mapping.json and the
    case's Mode - and nothing kept them aligned. `sync` reports both
    mismatch directions and can fix one of them:

      mapped but Manual        -> --apply sets Automation (safe: a test exists)
      Automation but unmapped  -> reported only. A human decides whether to
                                  map a test to it or set it back to Manual.

Two things measured on 2026-08-17 that the docs get wrong
    - The mode filter is case-sensitive: `Automation` and `Manual` work,
      `automation` returns "Provided Mode not found".
    - The case list has no mode field. Mode is only visible by filtering,
      so a write is verified by re-reading the filtered set, not the case.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import functools
import json
import os
import sys
import time
from pathlib import Path

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == 'win32':
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env')

from tools.qatouch_client import QATouchClient, QATouchError  # noqa: E402

PROJECT_KEY = os.environ.get('QATOUCH_PROJECT_ID', 'JlW1')
MAPPING_PATH = ROOT / 'config' / 'qatouch_case_mapping.json'

MODES = ('Automation', 'Manual')   # exact spelling the API accepts
INTER_CALL_DELAY = 0.25
RETRY_DELAY = 30.0


def canonical_mode(value: str) -> str:
    """Accept any casing; return the spelling the API accepts."""
    for m in MODES:
        if value.strip().lower() == m.lower():
            return m
    raise SystemExit(f"Unknown mode {value!r}. Use one of: {', '.join(MODES)}")


# ---------------------------------------------------------------- reads

def _get(client, params: dict, attempts: int = 5) -> dict:
    """GET getAllTestCases with the given params, backing off on 429."""
    import requests
    url = client._url(f'/api/v1/getAllTestCases/{PROJECT_KEY}')
    for i in range(1, attempts + 1):
        resp = requests.get(url, params=params, headers=client.session.headers, timeout=60)
        if resp.status_code == 429 and i < attempts:
            print(f'  rate limited - waiting {RETRY_DELAY:.0f}s ({i}/{attempts})')
            time.sleep(RETRY_DELAY)
            continue
        if resp.status_code != 200:
            raise QATouchError(f'HTTP {resp.status_code}: {resp.text[:200]}')
        return resp.json()
    raise QATouchError('gave up after repeated 429s')


def count_mode(client, mode: str) -> int:
    data = _get(client, {'mode': mode, 'view': 'count'})
    if 'meta' not in data:
        raise QATouchError(f'unexpected reply for mode={mode}: {json.dumps(data)[:200]}')
    return int(data['meta'].get('total', 0))


def keys_in_mode(client, mode: str) -> dict[str, dict]:
    """case_key -> {code, title, module} for every case in a mode.

    Filtered lists page at 20 and `page=N` works - but the response's
    meta.last_page says 1 whatever the total, and link.next drops the filter
    (it points at the unfiltered list). Measured 2026-08-17. So the page count
    comes from meta.total / meta.per_page, and the loop also stops if a page
    adds nothing new, in case the page parameter is ever ignored.
    """
    out: dict[str, dict] = {}
    page = 1
    expected_pages = None
    while True:
        data = _get(client, {'mode': mode, 'page': page})
        rows = data.get('data') or []
        meta = data.get('meta') or {}
        if expected_pages is None:
            total = int(meta.get('total') or 0)
            per_page = int(meta.get('per_page') or 20) or 20
            expected_pages = max(1, -(-total // per_page))
        before = len(out)
        for r in rows:
            out[r['case_key']] = {'code': r.get('case_code', ''),
                                  'title': r.get('case_title', ''),
                                  'module': r.get('module_name') or r.get('module name', '')}
        if not rows or len(out) == before or page >= expected_pages:
            break
        page += 1
        time.sleep(INTER_CALL_DELAY)
    return out


def load_mapped_keys() -> dict[str, list[str]]:
    """case_key -> [nodeids] from the Playwright mapping."""
    if not MAPPING_PATH.exists():
        raise SystemExit(f'Mapping file missing: {MAPPING_PATH}')
    data = json.loads(MAPPING_PATH.read_text(encoding='utf-8'))
    out: dict[str, list[str]] = {}
    for nodeid, info in data.get('mappings', {}).items():
        out.setdefault(info['case_key'], []).append(nodeid)
    return out


# ---------------------------------------------------------------- writes

def set_mode(client, keys: list[str], mode: str, dry_run: bool) -> tuple[list[str], list[str]]:
    """Set mode on each key, then verify by membership in the filtered set.

    Returns (verified_ok, failed).
    """
    if dry_run:
        for k in keys:
            print(f'    would set {k} -> {mode}')
        return keys, []

    sent = []
    failed = []
    for i, k in enumerate(keys, 1):
        try:
            client.update_test_case(PROJECT_KEY, k, mode=mode)
            sent.append(k)
        except QATouchError as e:
            failed.append(k)
            print(f'    [{i}/{len(keys)}] {k}: {str(e)[:120]}')
        time.sleep(INTER_CALL_DELAY)

    if not sent:
        return [], failed

    # The API reports success for writes it drops. Confirm by re-reading.
    print(f'  Verifying {len(sent)} case(s) now show mode={mode}...')
    now_in_mode = keys_in_mode(client, mode)
    verified = [k for k in sent if k in now_in_mode]
    not_landed = [k for k in sent if k not in now_in_mode]
    if not_landed:
        print(f'  [FAIL] {len(not_landed)} update(s) reported success but the case is not '
              f'in the {mode} set: {not_landed[:8]}')
    return verified, failed + not_landed


# ---------------------------------------------------------------- commands

def cmd_status(client, _args):
    counts = {m: count_mode(client, m) for m in MODES}
    total = sum(counts.values())
    print(f'\n  Project {PROJECT_KEY}')
    for m in MODES:
        print(f'    {m:11s} {counts[m]:5d}')
    print(f'    {"total":11s} {total:5d}')
    mapped = load_mapped_keys()
    print(f'\n  Playwright mapping: {len(mapped)} case(s) mapped from '
          f'{sum(len(v) for v in mapped.values())} test(s)')
    if counts['Automation'] != len(mapped):
        print(f'  Automation ({counts["Automation"]}) != mapped ({len(mapped)}) - '
              f'run `sync` to see which cases disagree.')


def cmd_list(client, args):
    mode = canonical_mode(args.mode)
    rows = keys_in_mode(client, mode)
    print(f'\n  {len(rows)} case(s) with mode={mode}')
    for k, r in sorted(rows.items(), key=lambda kv: kv[1]['code']):
        print(f'    {k}  {r["code"]:8s}  {r["module"][:28]:28s}  {r["title"][:50]}')


def _resolve_keys(args) -> list[str]:
    keys: list[str] = []
    if args.keys:
        keys += [k.strip() for k in args.keys.split(',') if k.strip()]
    if args.from_csv:
        with open(args.from_csv, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                k = (row.get('case_key') or row.get('key') or '').strip()
                if k:
                    keys.append(k)
    if args.from_mapping:
        keys += list(load_mapped_keys())
    seen = set()
    return [k for k in keys if not (k in seen or seen.add(k))]


def cmd_set(client, args):
    mode = canonical_mode(args.mode)
    keys = _resolve_keys(args)
    if not keys:
        print('  Nothing to do - give --keys, --from-csv or --from-mapping.')
        return 2
    print(f'\n  Setting mode={mode} on {len(keys)} case(s)' + (' [dry run]' if args.dry_run else ''))
    ok, failed = set_mode(client, keys, mode, args.dry_run)
    print(f'\n  {len(ok)} verified, {len(failed)} failed.')
    return 1 if failed else 0


def cmd_sync(client, args):
    mapped = load_mapped_keys()
    automation = keys_in_mode(client, 'Automation')

    mapped_not_auto = sorted(k for k in mapped if k not in automation)
    auto_not_mapped = sorted(k for k in automation if k not in mapped)
    aligned = len(set(mapped) & set(automation))

    print(f'\n  Mapped cases:              {len(mapped)}')
    print(f'  Automation-mode cases:     {len(automation)}')
    print(f'  Aligned (both):            {aligned}')
    print(f'  Mapped but NOT Automation: {len(mapped_not_auto)}   <- --apply fixes these')
    print(f'  Automation but NOT mapped: {len(auto_not_mapped)}   <- needs a human')

    if mapped_not_auto:
        print('\n  Mapped but Manual (a test exists, mode is wrong):')
        for k in mapped_not_auto[:15]:
            print(f'    {k}  <- {mapped[k][0][:70]}')
        if len(mapped_not_auto) > 15:
            print(f'    ... and {len(mapped_not_auto) - 15} more')

    if auto_not_mapped:
        print('\n  Automation but no test maps to it (map a test, or set Manual):')
        for k in auto_not_mapped[:15]:
            r = automation[k]
            print(f'    {k}  {r["code"]:8s}  {r["module"][:24]:24s}  {r["title"][:45]}')
        if len(auto_not_mapped) > 15:
            print(f'    ... and {len(auto_not_mapped) - 15} more')

    if args.report:
        out = ROOT / 'config' / 'audit_reports' / 'mode_sync_report.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            'mapped_not_automation': [{'case_key': k, 'tests': mapped[k]} for k in mapped_not_auto],
            'automation_not_mapped': [{'case_key': k, **automation[k]} for k in auto_not_mapped],
        }, indent=2), encoding='utf-8')
        print(f'\n  Report: {out.relative_to(ROOT)}')

    if not args.apply:
        if mapped_not_auto:
            print('\n  Run with --apply to set Automation on the mapped-but-Manual cases.')
        return 0
    if not mapped_not_auto:
        print('\n  Nothing to apply.')
        return 0
    print(f'\n  Applying: setting Automation on {len(mapped_not_auto)} case(s)...')
    ok, failed = set_mode(client, mapped_not_auto, 'Automation', dry_run=False)
    print(f'  {len(ok)} verified, {len(failed)} failed.')
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(
        description='Read and set QA Touch case Mode through the public API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split('Why `sync`')[0].split('tools/archive/.')[-1])
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('status', help='Counts by mode, and whether they match the mapping')
    p = sub.add_parser('list', help='List cases in a mode')
    p.add_argument('--mode', required=True)
    p = sub.add_parser('set', help='Set mode on cases')
    p.add_argument('--mode', required=True)
    p.add_argument('--keys', default='', help='Comma-separated case keys')
    p.add_argument('--from-csv', default='', help='CSV with a case_key column')
    p.add_argument('--from-mapping', action='store_true',
                   help='Every case in config/qatouch_case_mapping.json')
    p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('sync', help='Compare the Playwright mapping with Automation mode')
    p.add_argument('--apply', action='store_true',
                   help='Set Automation on mapped cases that are Manual')
    p.add_argument('--report', action='store_true',
                   help='Write config/audit_reports/mode_sync_report.json')
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    client = QATouchClient()
    handler = {'status': cmd_status, 'list': cmd_list, 'set': cmd_set, 'sync': cmd_sync}[args.command]
    return handler(client, args) or 0


if __name__ == '__main__':
    sys.exit(main())
