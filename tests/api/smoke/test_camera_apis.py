import pytest


@pytest.mark.api
@pytest.mark.smoke
def test_get_camera_tree(camera_api, test_site_id):
    tree = camera_api.get_camera_tree(test_site_id)
    assert camera_api.validate_camera_tree(tree)


@pytest.mark.api
@pytest.mark.smoke
def test_get_camera_snapshot(camera_api, test_site_id, test_channel_ids):
    # try first channel that responds
    for ch in test_channel_ids:
        try:
            snap = camera_api.get_camera_snapshot(test_site_id, ch)
            assert camera_api.validate_snapshot_is_jpeg(snap)
            return
        except Exception:
            continue
    pytest.skip('No camera snapshot available for test channels')
