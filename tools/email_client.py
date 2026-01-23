"""Microsoft Graph email client using MSAL.

Provides `send_email(to, subject, body_html, attachments=[])`.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
from typing import List, Optional

import requests
from msal import ConfidentialClientApplication
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_PATH = os.path.join(ROOT, ".env")
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)


class GraphEmailClient:
    def __init__(self):
        self.tenant_id = os.environ.get("AZURE_TENANT_ID")
        self.client_id = os.environ.get("AZURE_CLIENT_ID")
        self.client_secret = os.environ.get("AZURE_CLIENT_SECRET")
        self.email_from = os.environ.get("EMAIL_FROM")
        if not all((self.tenant_id, self.client_id, self.client_secret, self.email_from)):
            raise ValueError("Missing Azure OAuth environment variables (AZURE_TENANT_ID/AZURE_CLIENT_ID/AZURE_CLIENT_SECRET/EMAIL_FROM)")

        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.app = ConfidentialClientApplication(self.client_id, client_credential=self.client_secret, authority=authority)
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        scopes = ["https://graph.microsoft.com/.default"]
        resp = self.app.acquire_token_for_client(scopes=scopes)
        if not resp or "access_token" not in resp:
            raise RuntimeError(f"Failed to acquire access token: {resp}")
        self._token = resp["access_token"]
        expires_in = int(resp.get("expires_in", 3600))
        self._token_expiry = time.time() + expires_in
        return self._token

    def _build_attachments(self, attachments: List[str]):
        files = []
        for path in attachments:
            if not os.path.exists(path):
                continue
            with open(path, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode("ascii")
            name = os.path.basename(path)
            ctype, _ = mimetypes.guess_type(name)
            if not ctype:
                ctype = "application/octet-stream"
            files.append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": name,
                "contentType": ctype,
                "contentBytes": b64,
            })
        return files

    def send_email(self, to: List[str] | str, subject: str, body_html: str, attachments: List[str] = []):
        if isinstance(to, str):
            to = [to]
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        to_recipients = [{"emailAddress": {"address": addr}} for addr in to]

        message = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body_html},
            "toRecipients": to_recipients,
        }

        files = self._build_attachments(attachments)
        if files:
            message["attachments"] = files

        payload = {"message": message, "saveToSentItems": True}

        user = self.email_from
        url = f"https://graph.microsoft.com/v1.0/users/{user}/sendMail"
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        if r.status_code not in (200, 202):
            raise RuntimeError(f"Graph sendMail failed: {r.status_code} {r.text}")
        return r.status_code


# module-level client
_client: Optional[GraphEmailClient] = None


def get_client() -> GraphEmailClient:
    global _client
    if _client is None:
        _client = GraphEmailClient()
    return _client


def send_email(to: List[str] | str, subject: str, body_html: str, attachments: List[str] = []):
    c = get_client()
    return c.send_email(to, subject, body_html, attachments)
