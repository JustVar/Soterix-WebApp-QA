"""
QA-API-EVT-01 - Events page API smoke (event search)
Spec: qa/Automation_QA.xlsx › Test Mapping › row "QA-API-EVT-01"
Section: I. API
Owner: JV
Deployment: After FT

The existing test_search_api.py covers /REST/site/search for person and
vehicle payloads. This module adds the event-specific search endpoint that
the Events page hits when a rule type + site is selected.

Catalog rows:
- POST /REST/site/search/event
"""
import time

import pytest


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-EVT-01")
def test_event_search_returns_results_or_empty(user_api, test_site_id, test_enterprise_id):
    """POST /REST/site/search/event returns either matching events or an empty list.

    Payload mirrors the SPA's Events page on initial search: a rule-type
    filter ("Camera Tamper") over the last hour against the discovered site.
    A 200 with a list/dict result is success; the list may be empty.
    """
    now_ms = int(time.time() * 1000)
    one_hour_ms = 60 * 60 * 1000
    payload = {
        "enterpriseId": test_enterprise_id,
        "siteId": test_site_id,
        "startTime": now_ms - one_hour_ms,
        "endTime": now_ms,
        # Rule type "Camera Tamper" was observed in capture. Other rule types
        # are valid; we pick one with broad coverage across staging sites.
        "ruleType": "Camera Tamper",
    }
    r = user_api.post("/REST/site/search/event", json=payload)
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}, body: {str(body)[:400]}"
    assert "result" in body, "Response missing 'result'"
    assert isinstance(body["result"], (list, dict)), f"Unexpected result type: {type(body['result'])}"


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-EVT-01")
def test_event_search_validates_required_filters(user_api):
    """POST /REST/site/search/event with empty body must NOT return success+data.

    Guards against a regression where the endpoint silently returns the full
    enterprise event firehose on missing filters.
    """
    r = user_api.post("/REST/site/search/event", json={})
    # The endpoint may legitimately reject with 4xx, or return code != 200 in
    # the body. Either is fine; what we don't want is a 200 with a populated
    # result list (which would mean filters aren't being enforced).
    if r.status_code == 200:
        body = r.json()
        result = body.get("result")
        if isinstance(result, list):
            assert result == [], (
                "Empty-filter event search returned populated result list; "
                "filter enforcement may be broken"
            )
