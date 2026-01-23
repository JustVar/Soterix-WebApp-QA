"""Test Microsoft Graph OAuth email sending.

Usage: python tools/test_oauth_email.py
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_PATH = os.path.join(ROOT, ".env")
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import tools.email_client as email_client


def main():
    to = os.environ.get('EMAIL_TO') or 'qa@soterixsystems.com'
    subject = 'QA Automation - OAuth Email Test'
    body = '<html><body><h3>QA Automation OAuth Email Test</h3><p>If you received this, OAuth email works.</p></body></html>'
    try:
        status = email_client.send_email(to, subject, body, attachments=[])
        print('Email sent, status:', status)
    except Exception as e:
        print('Email send failed:', str(e))


if __name__ == '__main__':
    main()
