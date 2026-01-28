"""Base API client with simple schema validation and logging."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

import requests
import urllib3
from jsonschema import validate as jsonschema_validate, ValidationError

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LOG_PATH = os.path.join(ROOT, "logs", "api_requests.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s %(message)s")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class BaseAPIClient:
    def __init__(self, base_url: str, token: Optional[str] = None, timeout: int = 15, max_seconds: float = 2.0):
        # Normalize base_url and ensure API server prefix present.
        # Many deployments mount the API under `/v-apiserver`; if the
        # provided `base_url` does not already include that segment,
        # append it so client code can use paths like `/REST/...`.
        b = (base_url or "").rstrip("/")
        if not b.endswith("/v-apiserver"):
            b = b + "/v-apiserver"
        self.base_url = b
        self.token = token
        self.timeout = timeout
        self.max_seconds = max_seconds
        # SSL verification: Check SSL_VERIFY env var first, then fall back to ENV-based logic
        ssl_verify_env = os.getenv("SSL_VERIFY", "").lower()
        if ssl_verify_env in ("false", "0", "no"):
            self.verify = False
        elif ssl_verify_env in ("true", "1", "yes"):
            self.verify = True
        else:
            # Default: disable SSL verification for non-production environments
            # This matches auth_helper.py logic and avoids SSL errors with self-signed certs
            env = os.getenv("ENV", "").lower()
            self.verify = False if env not in ("prod", "production") else True

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json"}
        if self.token:
            # If token looks like a JSESSIONID (hex-like session id), send it as a Cookie
            import re
            t = str(self.token)
            if re.fullmatch(r"[0-9a-fA-F]{16,128}", t) or "=" in t:
                # If token includes '=', assume it's raw cookie string like 'JSESSIONID=...'
                if "=" in t:
                    # token may be e.g. 'JSESSIONID=abc; Path=/'
                    h["Cookie"] = t
                else:
                    h["Cookie"] = f"JSESSIONID={t}"
            else:
                h["Authorization"] = f"Bearer {self.token}"
        return h

    def _log(self, method: str, path: str, status: int, elapsed: float):
        logging.info(f"{method} {path} -> {status} ({elapsed:.3f}s)")

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        start = time.time()
        r = requests.request(method, url, headers=self._headers(), timeout=self.timeout, verify=self.verify, **kwargs)
        elapsed = time.time() - start
        self._log(method, url, r.status_code, elapsed)
        return r

    def get(self, path: str, params: Dict[str, Any] | None = None) -> requests.Response:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: Any | None = None, data: Any | None = None) -> requests.Response:
        return self._request("POST", path, json=json, data=data)

    def put(self, path: str, json: Any | None = None) -> requests.Response:
        return self._request("PUT", path, json=json)

    def delete(self, path: str) -> requests.Response:
        return self._request("DELETE", path)

    def load_schema(self, schema_name: str) -> Optional[Dict[str, Any]]:
        if not schema_name:
            return None
        path = os.path.join(ROOT, "tests", "shared", "schemas", "responses", f"{schema_name}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def validate_schema(self, response_json: Any, schema: Optional[Dict[str, Any]]):
        if not schema:
            return True
        try:
            jsonschema_validate(instance=response_json, schema=schema)
            return True
        except ValidationError as e:
            raise AssertionError(f"Schema validation failed: {e.message}")

    def assert_response_time(self, response: requests.Response, max_seconds: Optional[float] = None):
        ms = max_seconds or self.max_seconds
        elapsed = response.elapsed.total_seconds()
        if elapsed > ms:
            raise AssertionError(f"Response time {elapsed:.3f}s exceeded max {ms}s")
        return True
