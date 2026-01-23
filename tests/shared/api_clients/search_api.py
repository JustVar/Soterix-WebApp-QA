"""Search API client for person/vehicle searches."""
from __future__ import annotations

from typing import Any, Dict, List

from .base_api_client import BaseAPIClient


class SearchAPI(BaseAPIClient):
    def _build_search_payload(self, site_id: int, channels: List[int], start_ts: int, end_ts: int, filters: Dict[str, Any] | None = None) -> Dict[str, Any]:
        payload = {
            "siteid": site_id,
            "channels": channels,
            "starttimestamp": start_ts,
            "endtimestamp": end_ts,
        }
        if filters:
            payload.update(filters)
        return payload

    def search_person(self, site_id: int, channels: List[int], start_ts: int, end_ts: int, filters: Dict[str, Any] | None = None) -> Dict[str, Any]:
        path = f"/REST/site/{site_id}/getattributeevents" if False else "/REST/site/search"
        payload = self._build_search_payload(site_id, channels, start_ts, end_ts, filters)
        r = self.post(path, json=payload)
        r.raise_for_status()
        return r.json()

    def search_vehicle(self, site_id: int, channels: List[int], start_ts: int, end_ts: int, filters: Dict[str, Any] | None = None) -> Dict[str, Any]:
        path = "/REST/site/search"
        payload = self._build_search_payload(site_id, channels, start_ts, end_ts, filters)
        r = self.post(path, json=payload)
        r.raise_for_status()
        return r.json()
