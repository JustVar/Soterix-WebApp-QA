"""User-related API client."""
from __future__ import annotations

from typing import Any, Dict, List

from .base_api_client import BaseAPIClient


class UserAPI(BaseAPIClient):
    def get_user_session(self) -> Dict[str, Any]:
        path = "/REST/central/user/session"
        r = self.get(path)
        r.raise_for_status()
        return r.json()

    def get_user_roles(self) -> List[Dict[str, Any]]:
        path = "/REST/central/userprofile/roles"
        r = self.get(path)
        r.raise_for_status()
        return r.json()

    def validate_session_response(self, data: Any) -> bool:
        return isinstance(data, dict) and ("userid" in data or "username" in data or "session" in data)
