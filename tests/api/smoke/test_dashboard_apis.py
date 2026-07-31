"""
QA-API-DSH-01 - Dashboard APIs smoke (site status, shared widgets)
Spec: qa/Automation_QA.xlsx › Test Mapping › row "QA-API-DSH-01"
Section: I. API
Owner: JV
Deployment: After FT
"""
import pytest


@pytest.mark.api
@pytest.mark.smoke
def test_get_site_status(dashboard_api, test_site_id):
    r = dashboard_api.get_site_status(test_site_id)
    assert dashboard_api.validate_status_response(r)


@pytest.mark.api
@pytest.mark.smoke
def test_get_shared_widgets(dashboard_api):
    # use customer id same as 1 for smoke
    data = dashboard_api.get_shared_widgets(1)
    assert isinstance(data, (list, dict))