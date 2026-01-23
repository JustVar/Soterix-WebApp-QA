"""Simple script to test Slack incoming webhook from .env."""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ENV_PATH = os.path.join(ROOT, '.env')
if os.path.exists(ENV_PATH):
    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_PATH)
    except Exception:
        pass

import requests


def main():
    webhook = os.environ.get('SLACK_WEBHOOK_URL')
    if not webhook:
        print('SLACK_WEBHOOK_URL not set in environment or .env')
        sys.exit(2)
    text = 'QA Automation - Slack integration test'
    try:
        r = requests.post(webhook, json={'text': text}, timeout=10)
        if r.status_code == 200:
            print('Slack test message sent successfully')
            sys.exit(0)
        else:
            print('Slack webhook returned', r.status_code, r.text)
            sys.exit(1)
    except Exception as e:
        print('Slack webhook send failed:', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
