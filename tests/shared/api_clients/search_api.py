"""Search API client for person/vehicle searches."""
from __future__ import annotations

import json
import requests
from typing import Any, Dict, List

from .base_api_client import BaseAPIClient


class SearchAPI(BaseAPIClient):
    CATEGORY_PERSON = "PERSON"
    CATEGORY_VEHICLE = "VEHICLE"

    def _build_vsearch_request(self, site_id: int, channels: List[int], start_ts: int, end_ts: int, category: str) -> Dict[str, Any]:
        query = {
            "siteId": site_id,
            "channelList": channels,
            "startTimeStamp": start_ts,
            "endTimeStamp": end_ts,
        }
        # set category as a simple string and add description skeleton per UI
        query["category"] = category
        if category == self.CATEGORY_PERSON:
            query["description"] = {
                "gender": "",
                "clothingTop": "",
                "clothingTopColor": [],
                "clothingBottom": "",
                "clothingBottomColor": [],
                "attribute": [],
            }
        elif category == self.CATEGORY_VEHICLE:
            query["description"] = {
                "vehicleLicenseNumber": "",
                "vehicleType": [],
                "vehicleColor": [],
            }
        # Try to include enterpriseId if the site metadata exposes it
        try:
            r = self.get(f"/REST/site/{site_id}")
            if r.status_code == 200:
                body = r.json()
                if isinstance(body, dict):
                    res = body.get("result")
                    if isinstance(res, list) and res:
                        first = res[0]
                        if isinstance(first, dict) and "enterpriseId" in first:
                            query["enterpriseId"] = first.get("enterpriseId")
        except Exception:
            pass
        # Try to include enterpriseId if the site metadata exposes it
        return {"queryList": [{"query": query}], "isAddedByRule": False}

    def search_person(self, site_id: int, channels: List[int], start_ts: int, end_ts: int, filters: Dict[str, Any] | None = None) -> Dict[str, Any]:
        path = "/REST/site/search"
        payload = self._build_vsearch_request(site_id, channels, start_ts, end_ts, self.CATEGORY_PERSON)
        if filters:
            # merge filter keys into the top-level query object if present
            for k, v in (filters.items() if isinstance(filters, dict) else []):
                payload["queryList"][0]["query"][k] = v
        # Debug: print payload
        try:
            print(f"[SEARCH DEBUG] Payload: {json.dumps(payload, indent=2)}")
        except Exception:
            print(f"[SEARCH DEBUG] Payload: {payload}")

        # Build headers and ensure Content-Type is set
        headers = self._headers()
        headers["Content-Type"] = "application/json"
        print(f"[SEARCH DEBUG] Headers: {headers}")

        url = f"{self.base_url}{path}"
        # First try sending JSON via requests `json=` helper
        try:
            resp = requests.post(url, json=payload, headers=headers, verify=self.verify, timeout=self.timeout)
        except Exception as e:
            print(f"[SEARCH DEBUG] Request error: {e}")
            raise

        # If server claims payload missing, retry with raw JSON string in body
        body_text = resp.text or ""
        if resp.status_code >= 400 and "Required http POST request payload is not found" in body_text:
            try:
                print("[SEARCH DEBUG] Server rejected json= payload, retrying with data=json.dumps(payload)")
                resp = requests.post(url, data=json.dumps(payload), headers=headers, verify=self.verify, timeout=self.timeout)
            except Exception as e:
                print(f"[SEARCH DEBUG] Retry request error: {e}")
                raise

        print(f"[SEARCH DEBUG] Status: {resp.status_code}")
        print(f"[SEARCH DEBUG] Response: {resp.text[:1000]}")
        resp.raise_for_status()
        return resp.json()

    def search_vehicle(self, site_id: int, channels: List[int], start_ts: int, end_ts: int, filters: Dict[str, Any] | None = None) -> Dict[str, Any]:
        path = "/REST/site/search"
        payload = self._build_vsearch_request(site_id, channels, start_ts, end_ts, self.CATEGORY_VEHICLE)
        if filters:
            for k, v in (filters.items() if isinstance(filters, dict) else []):
                payload["queryList"][0]["query"][k] = v
        # Debug: print payload
        try:
            print(f"[SEARCH DEBUG] Payload: {json.dumps(payload, indent=2)}")
        except Exception:
            print(f"[SEARCH DEBUG] Payload: {payload}")

        # Build headers and ensure Content-Type is set
        headers = self._headers()
        headers["Content-Type"] = "application/json"
        print(f"[SEARCH DEBUG] Headers: {headers}")

        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(url, json=payload, headers=headers, verify=self.verify, timeout=self.timeout)
        except Exception as e:
            print(f"[SEARCH DEBUG] Request error: {e}")
            raise

        body_text = resp.text or ""
        if resp.status_code >= 400 and "Required http POST request payload is not found" in body_text:
            try:
                print("[SEARCH DEBUG] Server rejected json= payload, retrying with data=json.dumps(payload)")
                resp = requests.post(url, data=json.dumps(payload), headers=headers, verify=self.verify, timeout=self.timeout)
            except Exception as e:
                print(f"[SEARCH DEBUG] Retry request error: {e}")
                raise

        print(f"[SEARCH DEBUG] Status: {resp.status_code}")
        print(f"[SEARCH DEBUG] Response: {resp.text[:1000]}")
        resp.raise_for_status()
        return resp.json()
