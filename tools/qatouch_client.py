"""QA Touch minimal API client wrapper.

Endpoints used (best-effort):
- GET /api/v1/projects
- POST /api/v1/projects
- POST /api/v1/modules
- POST /api/v1/test-cases
- POST /api/v1/test-runs

This client is defensive: QA Touch API variations exist, so calls return the
response JSON or raise a descriptive exception.
"""
from __future__ import annotations

import os
import sys
# Ensure repo root is on sys.path when run as a script
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import requests
from typing import Optional, Dict, Any, List


class QATouchError(Exception):
    pass


class QATouchClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 10):
        self.base_url = base_url or os.environ.get('QATOUCH_URL')
        self.api_key = api_key or os.environ.get('QATOUCH_API_KEY')
        if not self.base_url or not self.api_key:
            raise QATouchError('QATOUCH_URL and QATOUCH_API_KEY must be provided (env or args)')
        self.timeout = timeout
        self.session = requests.Session()
        # API key header for QA Touch (assumed `api_key` header)
        self.session.headers.update({'Content-Type': 'application/json', 'api_key': self.api_key})

    def _url(self, path: str) -> str:
        return self.base_url.rstrip('/') + path

    def list_projects(self) -> List[Dict[str, Any]]:
        url = self._url('/api/v1/projects')
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise QATouchError(f'list_projects failed: {resp.status_code} {resp.text}')
        return resp.json()

    def create_project(self, name: str, code: str, description: str = '') -> Dict[str, Any]:
        url = self._url('/api/v1/projects')
        payload = {'name': name, 'code': code, 'description': description}
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code not in (200, 201):
            raise QATouchError(f'create_project failed: {resp.status_code} {resp.text}')
        return resp.json()

    def create_module(self, project_id: int, name: str, parent_id: Optional[int] = None) -> Dict[str, Any]:
        url = self._url('/api/v1/modules')
        payload = {'project_id': project_id, 'name': name}
        if parent_id:
            payload['parent_id'] = parent_id
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code not in (200, 201):
            raise QATouchError(f'create_module failed: {resp.status_code} {resp.text}')
        return resp.json()

    def create_test_case(self, project_id: int, module_id: int, title: str, steps: str = '', priority: str = 'Medium', custom_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self._url('/api/v1/test-cases')
        payload = {'project_id': project_id, 'module_id': module_id, 'title': title, 'steps': steps, 'priority': priority}
        if custom_fields:
            payload['custom_fields'] = custom_fields
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code not in (200, 201):
            raise QATouchError(f'create_test_case failed: {resp.status_code} {resp.text}')
        return resp.json()

    def create_test_run(self, project_id: int, name: str, test_case_ids: List[int]) -> Dict[str, Any]:
        url = self._url('/api/v1/test-runs')
        payload = {'project_id': project_id, 'name': name, 'test_case_ids': test_case_ids}
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code not in (200, 201):
            raise QATouchError(f'create_test_run failed: {resp.status_code} {resp.text}')
        return resp.json()

    def create_custom_field(self, project_id: int, key: str, field_type: str = 'text', label: Optional[str] = None) -> Dict[str, Any]:
        """Best-effort: create a custom field. QA Touch custom field API varies.

        We try common endpoints and return the response JSON on success.
        """
        # Try a common endpoint
        url = self._url('/api/v1/custom-fields')
        payload = {'project_id': project_id, 'key': key, 'type': field_type, 'label': label or key}
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code in (200, 201):
            return resp.json()
        # fallback: try snake-case
        url2 = self._url('/api/v1/custom_fields')
        resp2 = self.session.post(url2, json=payload, timeout=self.timeout)
        if resp2.status_code in (200, 201):
            return resp2.json()
        raise QATouchError(f'create_custom_field failed: {resp.status_code} {resp.text}; fallback: {resp2.status_code} {resp2.text}')
