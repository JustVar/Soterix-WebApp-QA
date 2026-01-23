"""Debug token acquisition and show Graph request/response details."""
from __future__ import annotations

import os
import sys
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ENV_PATH = os.path.join(ROOT, '.env')
if os.path.exists(ENV_PATH):
    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_PATH)
    except Exception:
        pass

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tools.email_client import GraphEmailClient


def main():
    try:
        client = GraphEmailClient()
    except Exception as e:
        print('Client init failed:', e)
        sys.exit(2)
    print('Client initialized. Tenant:', client.tenant_id)
    # Acquire token via MSAL lower-level call to show full response
    resp = client.app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    print('Acquire token response keys:', list(resp.keys()))
    safe = {k: (v if k != 'access_token' else f'<token length {len(resp.get("access_token","") )}>' ) for k, v in resp.items()}
    print('Acquire token response (safe):')
    print(json.dumps(safe, indent=2))
    if 'access_token' in resp:
        print('Token acquired OK')
    else:
        print('Token acquisition failed; inspect response above')


if __name__ == '__main__':
    main()
