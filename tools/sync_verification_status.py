"""Sync verification verdicts from QA Ops Hub to local JSON file.

Pulls the latest verification verdicts from the Ops Hub API and writes
them to config/verification_status.json. This file provides developers
with rejection feedback (which step failed and why) without needing to
check the Ops Hub UI.

Usage:
    python tools/sync_verification_status.py
    python tools/sync_verification_status.py --ops-hub-url http://192.168.1.174/qa-ops

Prerequisites:
    - QA Ops Hub must expose GET /api/verification/export endpoint
    - Network access to the NUC (or wherever the Ops Hub is running)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = ROOT / 'config' / 'verification_status.json'
DEFAULT_OPS_HUB_URL = 'http://192.168.1.174/qa-ops'


def sync_from_ops_hub(base_url: str) -> dict:
    """Pull verification verdicts from the Ops Hub export endpoint.

    Args:
        base_url: Ops Hub base URL (e.g., http://192.168.1.174/qa-ops)

    Returns:
        Dict with verified, rejected, and pending lists.
    """
    if requests is None:
        print('ERROR: requests library not installed. Run: pip install requests')
        sys.exit(1)

    export_url = f'{base_url.rstrip("/")}/api/verification/export'
    print(f'Fetching verdicts from {export_url}...')

    try:
        resp = requests.get(export_url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        print(f'ERROR: Cannot connect to {export_url}')
        print('Is the QA Ops Hub running? Check: ssh nuc "systemctl status qa-dashboard"')
        sys.exit(1)
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            print(f'ERROR: Export endpoint not found at {export_url}')
            print('The GET /api/verification/export endpoint may not be deployed yet.')
            print('This endpoint needs to be built in the QA Ops Hub.')
        else:
            print(f'ERROR: HTTP {e.response.status_code} from {export_url}')
        sys.exit(1)


def write_status_file(data: dict) -> None:
    """Write the verification status JSON file."""
    status = {
        'version': 1,
        'last_synced': datetime.now(UTC).isoformat(),
        'synced_from_session': data.get('latest_session_id'),
        'note': (
            'This file is exported from the QA Ops Hub database. '
            'Do not edit manually. Run: python tools/sync_verification_status.py'
        ),
        'verified': data.get('verified', {}),
        'rejected': data.get('rejected', {}),
        'pending': data.get('pending', []),
    }

    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(status, f, indent=2, ensure_ascii=False)
        f.write('\n')

    verified_count = len(status['verified'])
    rejected_count = len(status['rejected'])
    pending_count = len(status['pending'])
    print(f'Written to {STATUS_FILE}')
    print(f'  Verified:  {verified_count}')
    print(f'  Rejected:  {rejected_count}')
    print(f'  Pending:   {pending_count}')

    if rejected_count > 0:
        print()
        print('Rejected tests (need fixes):')
        for nodeid, info in status['rejected'].items():
            reason = info.get('reject_reason', 'No reason given')
            short_id = nodeid.split('::')[-1] if '::' in nodeid else nodeid
            print(f'  ✗ {short_id}: {reason}')


def main():
    parser = argparse.ArgumentParser(
        description='Sync verification verdicts from QA Ops Hub to local JSON.'
    )
    parser.add_argument(
        '--ops-hub-url',
        default=DEFAULT_OPS_HUB_URL,
        help=f'QA Ops Hub base URL (default: {DEFAULT_OPS_HUB_URL})',
    )
    args = parser.parse_args()

    data = sync_from_ops_hub(args.ops_hub_url)
    write_status_file(data)
    print('\nSync complete.')


if __name__ == '__main__':
    main()
