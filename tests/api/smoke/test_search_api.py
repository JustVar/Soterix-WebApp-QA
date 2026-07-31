"""
QA-API-SRC-01 - Search APIs smoke (person, vehicle)
Spec: qa/Automation_QA.xlsx › Test Mapping › row "QA-API-SRC-01"
Section: I. API
Owner: JV
Deployment: After FT
"""
import time
import pytest


@pytest.mark.api
@pytest.mark.smoke
def test_search_person_basic(search_api, test_site_id, test_channel_ids):
    # last hour
    end_ts = int(time.time() * 1000)
    start_ts = end_ts - (60 * 60 * 1000)
    res = search_api.search_person(test_site_id, test_channel_ids, start_ts, end_ts)
    assert isinstance(res, (list, dict))


@pytest.mark.api
@pytest.mark.smoke
def test_search_vehicle_basic(search_api, test_site_id, test_channel_ids):
    end_ts = int(time.time() * 1000)
    start_ts = end_ts - (60 * 60 * 1000)
    res = search_api.search_vehicle(test_site_id, test_channel_ids, start_ts, end_ts)
    assert isinstance(res, (list, dict))
