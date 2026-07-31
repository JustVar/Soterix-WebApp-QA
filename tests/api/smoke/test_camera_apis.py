"""
QA-API-CAM-01 - Camera APIs smoke (channel tree, snapshot)
Spec: qa/Automation_QA.xlsx › Test Mapping › row "QA-API-CAM-01"
Section: I. API
Owner: JV
Deployment: After FT
"""
import pytest


@pytest.mark.api
@pytest.mark.smoke
def test_get_camera_tree(camera_api, test_site_id):
    tree = camera_api.get_camera_tree(test_site_id)
    assert camera_api.validate_camera_tree(tree)


@pytest.mark.api
@pytest.mark.smoke
def test_get_camera_snapshot(camera_api, test_site_id, test_channel_ids):
    # QA environment: use channel list from API and call the snapshot endpoint
    # Snapshot endpoint returns JSON: {"status":2000,"code":200,"result":{"content":[-1,-40,...]}}
    try:
        # fetch channel list and pick first available channel id
        ch_list_resp = camera_api.get(f"/REST/site/{test_site_id}/channel")
        ch_list_resp.raise_for_status()
        channels_json = ch_list_resp.json()
        # common wrappers: result, channels, data, or raw list
        if isinstance(channels_json, dict):
            candidates = channels_json.get("result") or channels_json.get("channels") or channels_json.get("data") or []
        elif isinstance(channels_json, list):
            candidates = channels_json
        else:
            candidates = []

        first_id = None
        for c in candidates:
            if isinstance(c, dict):
                for key in ("channelId", "id", "channel_id"):
                    if key in c:
                        first_id = c.get(key)
                        break
            if first_id is not None:
                break

        # fallback to provided fixture ids
        if first_id is None and test_channel_ids:
            first_id = test_channel_ids[0]

        assert first_id is not None, "No candidate channel id found"

        snap_resp = camera_api.get(f"/REST/site/{test_site_id}/channel/{first_id}/snap")
        snap_resp.raise_for_status()
        j = snap_resp.json()
        assert isinstance(j, dict)
        # assert standard response status
        assert j.get("status") in (2000, 200)
        # drill into result.content
        result = j.get("result")
        # Handle actual response format: result may be a LIST containing a dict with "content"
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            content = result[0].get("content")
        elif isinstance(result, dict):
            content = result.get("content")
        else:
            content = None
        assert isinstance(content, list) and len(content) >= 2
        # JPEG signature is 0xFF 0xD8 -> signed bytes [-1, -40]
        assert content[0:2] == [-1, -40]
    except Exception:
        # let test fail if any of the above assertions/requests fail
        raise
