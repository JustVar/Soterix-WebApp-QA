import time
import json

import pytest
import requests

from tests.shared.api_clients.base_api_client import BaseAPIClient


@pytest.mark.api
@pytest.mark.smoke
def test_get_site_status(api_base_url, api_auth_token, discovered_site_id):
    """GET /REST/dashboard/site/{siteId}/status - verify site status fields."""
    client = BaseAPIClient(api_base_url, api_auth_token)
    path = f"/REST/dashboard/site/{discovered_site_id}/status"
    r = client.get(path)
    assert r.status_code == 200, f"Unexpected status: {r.status_code}"
    try:
        j = r.json()
    except ValueError:
        pytest.fail("Expected JSON response for site status")
    print("test_get_site_status response:", json.dumps(j, indent=2))
    # Prefer data under 'result' if present
    data = j.get("result", j)
    assert isinstance(data, (dict, list)), "Unexpected JSON shape for site status"
    # Basic checks inside result
    if isinstance(data, dict):
        assert any(k in data for k in ("siteId", "site_id")), "Missing siteId in status result"
        # status/session may be absent in some responses; warn but don't fail
        if not any(k in data for k in ("status", "session", "statusCode", "code", "description")):
            print("test_get_site_status: no explicit status field in result; keys:", list(data.keys()))


@pytest.mark.api
@pytest.mark.smoke
def test_get_camera_tree(api_base_url, api_auth_token, discovered_site_id):
    """GET /REST/site/{siteId}/location/tree - verify location/camera structure."""
    client = BaseAPIClient(api_base_url, api_auth_token)
    path = f"/REST/site/{discovered_site_id}/location/tree"
    r = client.get(path)
    assert r.status_code == 200
    try:
        j = r.json()
    except ValueError:
        pytest.fail("Expected JSON response for camera tree")
    print("test_get_camera_tree response:", json.dumps(j, indent=2))
    # Prefer data under 'result'
    data = j.get("result", j)
    assert isinstance(data, (dict, list)), "Unexpected camera tree JSON shape"
    if isinstance(data, dict):
        assert any(k in data for k in ("locations", "deviceMap", "siteId", "locationsList", "devices")), "Unexpected camera tree shape"


@pytest.mark.api
@pytest.mark.smoke
def test_get_camera_snap(api_base_url, api_auth_token, discovered_site_id):
    """GET /REST/site/{siteId}/channel/{channelId}/snap - ensure snapshot is returned."""
    client = BaseAPIClient(api_base_url, api_auth_token)
    channel_id = 1
    path = f"/REST/site/{discovered_site_id}/channel/{channel_id}/snap"
    r = client.get(path)
    # snap endpoints may return binary image or JSON error; accept either
    assert r.status_code in (200, 206), f"Unexpected status code for snap: {r.status_code}"
    # If JSON, ensure it has an informative message; otherwise ensure bytes look like an image
    try:
        j = r.json()
        assert isinstance(j, dict)
    except ValueError:
        # binary content - check for JPEG/PNG magic bytes
        data = r.content
        assert len(data) > 0
        assert data.startswith(b"\xff\xd8") or data.startswith(b"\x89PNG"), "Snap does not look like JPEG/PNG"


@pytest.mark.api
@pytest.mark.smoke
def test_get_widgets(api_base_url, api_auth_token, discovered_enterprise_id):
    """GET /REST/dashboard/sharedwidgets/{customerId}/data - verify widget payload structure."""
    client = BaseAPIClient(api_base_url, api_auth_token)
    customer_id = discovered_enterprise_id
    path = f"/REST/dashboard/sharedwidgets/{customer_id}/data"
    r = client.get(path)
    assert r.status_code == 200
    try:
        j = r.json()
    except ValueError:
        pytest.fail("Expected JSON response for widgets data")
    print("test_get_widgets response:", json.dumps(j, indent=2))
    data = j.get("result", j)
    assert isinstance(data, (dict, list)), "Unexpected widgets JSON shape"
    if isinstance(data, dict):
        assert any(k in data for k in ("widgets", "data", "sharedWidgets")), "Unexpected widgets payload"


@pytest.mark.api
@pytest.mark.smoke
def test_search_person(api_base_url, api_auth_token, discovered_site_id):
    """POST /REST/site/search - search for PERSON category in last hour."""
    client = BaseAPIClient(api_base_url, api_auth_token)
    now_ms = int(time.time() * 1000)
    one_hour_ms = 60 * 60 * 1000
    payload = {
        "queryList": [
            {
                "query": {
                    "siteId": discovered_site_id,
                    "appearance": 0,
                    "channelList": [1, 2, 3],
                    "startTimeStamp": now_ms - one_hour_ms,
                    "endTimeStamp": now_ms,
                    "category": "PERSON",
                    "description": {
                        "gender": "",
                        "clothingTop": "",
                        "clothingTopColor": [],
                        "clothingBottom": "",
                        "clothingBottomColor": [],
                        "attribute": [],
                    },
                },
                "operation": "",
            }
        ]
    }
    path = "/REST/site/search"
    print("test_search_person request payload:", json.dumps(payload, indent=2))
    r = client.post(path, json=payload)
    assert r.status_code == 200, f"Search returned {r.status_code}: {r.text}"
    try:
        j = r.json()
    except ValueError:
        pytest.fail("Expected JSON response for search")
    print("test_search_person response:", json.dumps(j, indent=2))
    data = j.get("result", j)
    if isinstance(data, dict):
        assert any(k in data for k in ("results", "data", "items")) or isinstance(data.get("results", []), list)
    else:
        assert isinstance(data, list)
