#!/usr/bin/env python3
"""Check AZURE_SECRET_EXPIRES and exit non-zero if expiring soon.

Usage: python tools/check_oauth_expiration.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, date

import requests


def load_env_if_needed():
    if 'AZURE_SECRET_EXPIRES' in os.environ:
        return
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path)
        except Exception:
            pass


def post_slack(webhook: str, text: str) -> None:
    try:
        requests.post(webhook, json={"text": text}, timeout=10)
    except Exception as e:
        print('Slack notify failed:', e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slack', action='store_true', help='Send Slack alert when expiring (<30 days)')
    args = parser.parse_args()

    load_env_if_needed()
    s = os.environ.get('AZURE_SECRET_EXPIRES')
    if not s:
        print('ERROR: AZURE_SECRET_EXPIRES not set in environment or .env')
        sys.exit(2)
    try:
        exp = datetime.strptime(s.strip(), '%Y-%m-%d').date()
    except Exception:
        print(f"ERROR: Unable to parse AZURE_SECRET_EXPIRES='{s}' (expected YYYY-MM-DD)")
        sys.exit(2)

    today = date.today()
    days = (exp - today).days
    if days < 0:
        print(f'ERROR: Secret expired on {exp} ({-days} days ago)')
        sys.exit(1)
    # Slack notification logic
    webhook = os.environ.get('SLACK_WEBHOOK_URL')
    channel = os.environ.get('SLACK_ALERT_CHANNEL', '')

    if days < 7:
        msg = f"<!channel> ⚠️ OAuth Secret Expiring Soon\nDays remaining: {days}\nExpires: {exp}\nAction: See MAINTENANCE_REMINDERS.md"
        print(f'ERROR: Secret expires on {exp} ({days} days remaining) - renew within 7 days')
        if args.slack and webhook:
            post_slack(webhook, msg)
        sys.exit(1)
    if days < 30:
        msg = f"⚠️ OAuth Secret Expiring Soon\nDays remaining: {days}\nExpires: {exp}\nAction: See MAINTENANCE_REMINDERS.md"
        print(f'WARNING: Secret expires on {exp} ({days} days remaining)')
        if args.slack and webhook:
            post_slack(webhook, msg)
    elif days < 60:
        print(f'INFO: Secret expires on {exp} ({days} days remaining)')
    else:
        print(f'OK: Secret expires on {exp} ({days} days remaining)')
    sys.exit(0)


if __name__ == '__main__':
    main()
