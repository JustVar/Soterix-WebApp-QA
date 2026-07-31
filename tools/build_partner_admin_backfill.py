#!/usr/bin/env python3
"""Build the metadata-backfill payload JSON for the 3 just-imported CSV files.

Reads each canonical CSV, fetches the live cases from the target project,
matches by title, and writes a single JSON file of update payloads (the
same shape the OTA backfill used). The browser-driven backfill runner then
just iterates the JSON.

CSV -> Target project:
  ldap_canonical.csv         -> JlW1 (LDAP module, 175 cases - TR3317+)
  sitedevice_canonical.csv   -> 70l1 (155 expected, 154 valid after parser bug)
  distributor_canonical.csv  -> 70l1 (91 cases)

Output: tools/.partner_admin_backfill.json
"""
from __future__ import annotations
import csv
import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_PATH = REPO / 'tools' / '.partner_admin_backfill.json'

# enc_id mappings (verified workspace-wide from OTA backfill)
TYPE_ENC = {
    'Functional': 'GNxna',
    'Negative': 'GNxna',
    'Security': 'EERzG',
    'Performance': 'l7PmX',
    'Regression': 'rg3rN',
    'Acceptance': 'zgryX',
    'Automation': 'nl7g6',
}
PRI_ENC = {
    'Critical': 'bkRmQ',
    'High': 'Z1BPp',
    'Medium': 'Rq6v1',
    'Low': 'dBxg0',
}
TAG_ENC = {
    'smoke': '99GQ',
    'sanity': 'X1zZ',
    'regression': 'MW0N',
    'future': 'ea5n',
}


def load_creds():
    """Read the QA Touch REST api-token + short domain from the environment / .env."""
    token = os.environ.get('QATOUCH_API_TOKEN') or os.environ.get('QATOUCH_API_KEY')
    domain = os.environ.get('QATOUCH_DOMAIN')
    if not token or not domain:
        raise SystemExit(
            'Missing QA Touch REST credentials.\n'
            'Set QATOUCH_API_TOKEN + QATOUCH_DOMAIN in your .env at the repo '
            'root (see .env.template).'
        )
    return token, domain


def fetch_cases(project_key, tok, dom):
    cases = []
    for page in range(1, 200):
        req = urllib.request.Request(
            f'https://api.qatouch.com/api/v1/getAllTestCases/{project_key}?page={page}',
            headers={'api-token': tok, 'domain': dom, 'Accept': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.load(r)
        data = j.get('data') or []
        if not data:
            break
        cases.extend(data)
        if not j.get('link', {}).get('next'):
            break
    return cases


def tags_to_enc(pipe_str):
    out = []
    for t in (pipe_str or '').split('|'):
        t = t.strip().lower()
        if t and t in TAG_ENC:
            out.append(TAG_ENC[t])
    return out


def build_payloads_for(csv_path, project_key, target_module_filter, all_cases):
    """target_module_filter: predicate (case_dict) -> bool; restricts which live cases we match against."""
    csv_rows = list(csv.DictReader(open(csv_path, encoding='utf-8')))
    # Filter live cases for this CSV (by module - to avoid cross-CSV title collisions)
    candidates = [c for c in all_cases if target_module_filter(c)]
    title_idx = {}
    for c in candidates:
        t = (c.get('case_title') or '').strip()
        # Track all candidates - handle duplicates as a list
        title_idx.setdefault(t, []).append(c)
    payloads = []
    unmatched = []
    for r in csv_rows:
        title = r['Test Case Title'].strip()
        matches = title_idx.get(title, [])
        if not matches:
            unmatched.append({'csv_ref': r['Reference'], 'title': title})
            continue
        # If multiple matches, pick the one with the closest module_name match
        target_module_leaf = r['Module_name'].split(' > ')[-1].strip()
        chosen = matches[0]
        for c in matches:
            if (c.get('module_name') or '').strip() == target_module_leaf:
                chosen = c
                break
        payloads.append({
            '_csv_ref': r['Reference'],
            '_csv_module': r['Module_name'],
            'projectKey': project_key,
            'caseKey': chosen['case_key'],
            'caseCode': chosen.get('case_code'),
            'caseTitle': title,
            'reference': r['Reference'],
            'description': r.get('Description', '') or '',
            'precondition': r.get('Precondition', '') or '',
            'test_data': r.get('Test Data', '') or '',
            'type': TYPE_ENC.get(r.get('Type', 'Functional'), 'GNxna'),
            'priority': PRI_ENC.get(r.get('Priority', 'Medium'), 'Rq6v1'),
            'mode': (r.get('Mode', 'Manual') or 'Manual').lower(),
            'newtags': tags_to_enc(r.get('Tags', 'regression')),
        })
    return payloads, unmatched


def main():
    tok, dom = load_creds()

    print('Fetching cases for JlW1 (NexaiQ-Core)...')
    jlw1_cases = fetch_cases('JlW1', tok, dom)
    print(f'  {len(jlw1_cases)} cases')

    print('Fetching cases for 70l1 (Partner Admin)...')
    p70l1_cases = fetch_cases('70l1', tok, dom)
    print(f'  {len(p70l1_cases)} cases')

    all_payloads = []
    all_unmatched = []

    # LDAP -> JlW1, restrict to LDAP module
    p, u = build_payloads_for(
        REPO / 'tests/data/ldap_canonical.csv',
        'JlW1',
        lambda c: (c.get('module_name') or '').strip() == 'LDAP',
        jlw1_cases,
    )
    print(f'LDAP -> JlW1: matched {len(p)}, unmatched {len(u)}')
    all_payloads.extend(p); all_unmatched.extend(u)

    # SiteDevice -> 70l1, all cases (skip corrupt TR0029)
    site_modules = set()
    p, u = build_payloads_for(
        REPO / 'tests/data/sitedevice_canonical.csv',
        '70l1',
        lambda c: (c.get('case_title') or '') != '>',  # skip the corrupt one
        p70l1_cases,
    )
    print(f'SiteDevice -> 70l1: matched {len(p)}, unmatched {len(u)}')
    all_payloads.extend(p); all_unmatched.extend(u)

    # Distributor -> 70l1
    p, u = build_payloads_for(
        REPO / 'tests/data/distributor_canonical.csv',
        '70l1',
        lambda c: True,
        p70l1_cases,
    )
    print(f'Distributor -> 70l1: matched {len(p)}, unmatched {len(u)}')
    all_payloads.extend(p); all_unmatched.extend(u)

    # Stats
    from collections import Counter
    by_project = Counter(p['projectKey'] for p in all_payloads)
    print(f'\nTotal payloads: {len(all_payloads)}  by project: {dict(by_project)}')
    print(f'Total unmatched: {len(all_unmatched)}')

    OUT_PATH.write_text(json.dumps(all_payloads, separators=(',', ':')), encoding='utf-8')
    print(f'Wrote {OUT_PATH.relative_to(REPO)} ({OUT_PATH.stat().st_size} bytes)')

    if all_unmatched:
        umpath = REPO / 'tools' / '.partner_admin_unmatched.json'
        umpath.write_text(json.dumps(all_unmatched, indent=2), encoding='utf-8')
        print(f'Wrote {umpath.relative_to(REPO)}')
        for u in all_unmatched[:10]:
            print(f'  UNMATCHED  {u["csv_ref"]:30}  {u["title"][:70]}')


if __name__ == '__main__':
    main()
