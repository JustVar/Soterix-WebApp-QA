#!/usr/bin/env python3
"""Simple SMTP test script: reads SMTP creds from .env and sends a test HTML email."""
import os
import sys
import traceback
from os.path import exists

try:
    from dotenv import load_dotenv
except Exception:
    print("Missing dependency: python-dotenv. Install with `pip install python-dotenv`.")
    raise

import smtplib
from email.message import EmailMessage


def load_env():
    env_path = os.path.join(os.getcwd(), ".env")
    if exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded .env from {env_path}")
    else:
        print("No .env file found in repo root; attempting to read environment variables.")


def get_env(name, required=False):
    v = os.getenv(name)
    if required and not v:
        print(f"Required environment variable {name} is not set")
    return v


def main():
    load_env()

    host = get_env('SMTP_HOST', required=True)
    port = int(get_env('SMTP_PORT') or 587)
    user = get_env('SMTP_USER', required=True)
    password = get_env('SMTP_PASSWORD', required=True)
    use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
    email_from = get_env('EMAIL_FROM', required=True)
    email_to = get_env('EMAIL_TO', required=True)

    if not (host and user and password and email_from and email_to):
        print('Missing required SMTP configuration. Aborting.')
        sys.exit(2)

    print(f"Connecting to SMTP server {host}:{port} (TLS={use_tls})...")
    try:
        server = smtplib.SMTP(host, port, timeout=30)
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        server.login(user, password)
        print('Authenticated successfully.')
    except Exception:
        print('Failed to connect/authenticate to SMTP server:')
        traceback.print_exc()
        sys.exit(3)

    msg = EmailMessage()
    msg['From'] = email_from
    msg['To'] = email_to
    msg['Subject'] = 'QA Automation - SMTP Test'
    msg.set_content('This is a plain-text fallback for the SMTP test.')
    msg.add_alternative("""
    <html>
      <body>
        <h3>QA Automation - SMTP Test</h3>
        <p>If you received this, SMTP is working.</p>
      </body>
    </html>
    """, subtype='html')

    try:
        server.send_message(msg)
        print(f"Email sent successfully to {email_to}.")
    except Exception:
        print('Failed to send test email:')
        traceback.print_exc()
    finally:
        try:
            server.quit()
        except Exception:
            pass


if __name__ == '__main__':
    main()
