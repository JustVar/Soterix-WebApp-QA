"""Pytest fixtures that build test data through the internal API.

Registered in conftest.py (`pytest_plugins`). Probed live on QA on
2026-08-24. Each fixture docstring records the exact requests and
responses it relies on.

Rules (docs/CONVENTIONS.md, "Test data through the API"):
- every name starts with "AutoTest " so a leftover is recognisable,
- every write is verified with a read before the test gets it,
- every fixture removes what it made and confirms the removal.
"""
from __future__ import annotations

import base64
import os
import time

import pytest
import requests

from config.base_config import config
from tests.shared.api.client import ApiError, InternalApi

NAME_PREFIX = "AutoTest "

# A 1x1 PNG: the bookmark POST requires a `snap` file part
SNAP_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def _stamp() -> str:
    return time.strftime("%H%M%S")


# ------------------------------------------------------------ tree helpers
# Pure functions over a location tree payload so they unit-test without
# network (tests/plugins/test_internal_api.py).

def find_location(tree: list[dict], name: str) -> dict | None:
    """The location/tree node whose location is called `name`, or None.

    With 2 nodes of the same name (a stale leftover) the newest wins,
    the one with the highest id.
    """
    matches = [node for node in tree if node.get("location", {}).get("name") == name]
    if not matches:
        return None
    return max(matches, key=lambda node: node["location"]["id"])


def channel_id(tree: list[dict], camera_name: str) -> int:
    """Channel id of the camera called `camera_name` (case-insensitive).

    Raises a clear error when it is absent: the shared tenant renames
    cameras, and the fix is test_camera_name in config/env/.
    """
    wanted = camera_name.strip().lower()
    names: list[str] = []
    for node in tree:
        for channel in node.get("channel", []):
            if str(channel.get("name", "")).strip().lower() == wanted:
                return int(channel["id"])
            if channel.get("name") not in names:
                names.append(channel.get("name"))
    raise LookupError(
        f"No camera named '{camera_name}' on this site. Cameras: {names}. "
        f"Update test_camera_name in config/env/ if the tenant renamed it."
    )


def bookmark_deleted(row: dict) -> bool:
    """True when a VClipBookmark row is soft-deleted.

    `deletedAt` is -1 while the bookmark is live and a timestamp after
    a DELETE (seen 2026-08-24). A truthiness check reads -1 as deleted,
    which made a teardown skip its DELETE and leave a live bookmark.
    """
    return (row.get("deletedAt") or 0) > 0


def location_tree(api: InternalApi) -> list[dict]:
    """GET /REST/site/{site}/location/tree.

    Answers [{location: {id, name}, channel: [VChannel, ...]}, ...].
    This is what the Admin > Sites detail reads for its Groups
    dropdown (seen in the page trace, 2026-08-24). A camera can sit in
    several locations. The "All Cameras" location (id 1) holds every
    camera on the site.
    """
    return api.get(f"/REST/site/{api.site_id}/location/tree")


# ----------------------------------------------------------------- fixtures

@pytest.fixture(scope="session")
def api() -> InternalApi:
    """A logged-in InternalApi for the configured test site.

    Needs QA_USER, QA_PASSWORD and TEST_SITE_ID. TEST_SITE_ID must be
    the site that `test_site_name` in config/env/ names, or the API
    writes to a site the UI tests never open. On QA the name
    "Newtown Action Area" resolved to siteId 16 while a local .env
    said 17 (2026-08-24). The fixture reads GET /REST/site and skips
    with both values when they disagree.
    """
    user = os.environ.get("QA_USER")
    password = os.environ.get("QA_PASSWORD")
    site_id = os.environ.get("TEST_SITE_ID")
    missing = [
        key for key, value in
        (("QA_USER", user), ("QA_PASSWORD", password), ("TEST_SITE_ID", site_id))
        if not value
    ]
    if missing:
        pytest.skip(f"API test data needs {', '.join(missing)} in .env")

    client = InternalApi(config["base_url"], site_id)
    try:
        client.login(user, password)
        sites = {int(site["siteId"]): site["name"] for site in client.get("/REST/site")}
    except (ApiError, requests.RequestException) as e:
        pytest.skip(f"API login or site list failed on {config['base_url']}: {e}")

    client.site_name = sites.get(client.site_id)
    expected = config.get("test_site_name")
    if expected and client.site_name != expected:
        by_name = [site_id for site_id, name in sites.items() if name == expected]
        pytest.skip(
            f"TEST_SITE_ID={site_id} is site '{client.site_name}' but test_site_name "
            f"is '{expected}' (siteId {by_name or 'not found'}). API-built data would "
            f"land on a site the UI tests do not open. Set TEST_SITE_ID to match."
        )
    return client


@pytest.fixture
def api_camera_group(api: InternalApi):
    """Factory: make(name=None, channel_ids=None) -> the created group.

    The dict holds id, name, channel_ids, site_id and site_name.
    channel_ids defaults to the configured test camera. Pass [] for an
    empty group.

    A "camera group" in Admin > Sites is a *location* in the API. The
    API also has groups (addgroup, grouptree, deletegroup), but the
    Admin UI never reads them: a group made that way never showed in
    the Groups dropdown (pilot run, 2026-08-24).

    Requests, probed 2026-08-24 on site 16:
      POST /REST/site/config/16/location
           {"name": "AutoTest Probe 131314", "siteId": 16, "channelList": [97]}
        -> code 200, status 2007 "Successfully Applied!", result echoes
           the request without an id. The id comes from location/tree,
           which then listed {"id": 146, "name": ...} with channel 97.
      GET /REST/site/16/deletelocation/146
        -> code 200, result [true]. The camera keeps its other
           locations. A second delete of the same id answers HTTP 400,
           code 1006 "Database: no record found!", so teardown reads
           the tree first and skips groups the test deleted.
    """
    created: list[str] = []

    def make(name: str | None = None, channel_ids: list[int] | None = None) -> dict:
        name = name or f"{NAME_PREFIX}Group {_stamp()}"
        assert name.startswith(NAME_PREFIX), (
            f"Test data names must start with '{NAME_PREFIX}': {name}"
        )
        if channel_ids is None:
            channel_ids = [channel_id(location_tree(api), config["test_camera_name"])]

        api.post(
            f"/REST/site/config/{api.site_id}/location",
            {"name": name, "siteId": api.site_id, "channelList": list(channel_ids)},
        )
        created.append(name)

        # Verify before use: the envelope text is not a signal, and the
        # create answers no id
        node = find_location(location_tree(api), name)
        assert node is not None, (
            f"The location create answered OK but location/tree does not list '{name}'"
        )
        got = sorted(channel["id"] for channel in node.get("channel", []))
        assert got == sorted(channel_ids), (
            f"Group '{name}' holds channels {got}, expected {sorted(channel_ids)}"
        )
        return {
            "id": node["location"]["id"], "name": name, "channel_ids": got,
            "site_id": api.site_id, "site_name": api.site_name,
        }

    yield make

    if not created:
        return
    tree = location_tree(api)
    leftover = []
    for name in created:
        node = find_location(tree, name)
        if node is None:
            continue  # the test deleted it (the UI delete test does)
        api.get(f"/REST/site/{api.site_id}/deletelocation/{node['location']['id']}")
        if find_location(location_tree(api), name) is not None:
            leftover.append(name)
    if leftover:
        pytest.fail(
            f"Groups still on site {api.site_id} after deletelocation: {leftover}. "
            f"Delete them by hand in Admin > Sites."
        )


@pytest.fixture
def api_bookmark(api: InternalApi):
    """Factory: make(comment=None, camera_id=None, timestamp_ms=None,
    retention_days=1) -> the created bookmark row without `snap`.

    camera_id defaults to the configured test camera.

    Requests, probed 2026-08-24 on site 16, camera 97:
      POST /REST/clipbookmark?timestamp=1787594232101&siteId=16
           &cameraId=97&retentionDays=1&comment=AutoTest+Probe+125709
           with a multipart part "snap" holding a PNG (required)
        -> code 200, status 2005 "Successfully created!",
           result [{"bookmarkId": 1200, "timestamp", "createdTime",
           "userId", "siteId", "cameraId", "snap": [bytes],
           "retentionDays", "comment", "deletedAt": -1, ...}]
      GET /REST/clipbookmark/16
        -> result [VClipBookmark, ...], soft-deleted rows included.
           A live row holds deletedAt -1.
      DELETE /REST/clipbookmark/1200
        -> code 200, status 2006 "Successfully deleted!", but the row
           stays in the list with deletedAt set to a timestamp. The
           delete is a soft delete: "gone" means deletedAt > 0
           (bookmark_deleted). The API has no hard delete, so each run
           leaves one soft-deleted row that expires with retentionDays.
    """
    created: list[int] = []

    def listed(bookmark_id: int) -> dict | None:
        for row in api.get(f"/REST/clipbookmark/{api.site_id}"):
            if row.get("bookmarkId") == bookmark_id:
                return row
        return None

    def make(
        comment: str | None = None, camera_id: int | None = None,
        timestamp_ms: int | None = None, retention_days: int = 1,
    ) -> dict:
        comment = comment or f"{NAME_PREFIX}Bookmark {_stamp()}"
        assert comment.startswith(NAME_PREFIX), (
            f"Test data names must start with '{NAME_PREFIX}': {comment}"
        )
        if camera_id is None:
            camera_id = channel_id(location_tree(api), config["test_camera_name"])
        params = {
            "timestamp": timestamp_ms or int(time.time() * 1000),
            "siteId": api.site_id, "cameraId": camera_id,
            "retentionDays": retention_days, "comment": comment,
        }
        bookmark = api.post(
            "/REST/clipbookmark", params=params,
            files={"snap": ("snap.png", SNAP_PNG, "image/png")},
        )[0]
        created.append(bookmark["bookmarkId"])

        # Verify before use: the envelope text is not a signal
        row = listed(bookmark["bookmarkId"])
        assert row is not None, (
            f"POST answered bookmark {bookmark['bookmarkId']} but the site list "
            f"does not show it"
        )
        assert not bookmark_deleted(row), (
            f"Bookmark {bookmark['bookmarkId']} is already soft-deleted: {row}"
        )
        return {key: value for key, value in row.items() if key != "snap"}

    yield make

    leftover = []
    for bookmark_id in created:
        row = listed(bookmark_id)
        if row is None or bookmark_deleted(row):
            continue  # the test deleted it
        api.delete(f"/REST/clipbookmark/{bookmark_id}")
        row = listed(bookmark_id)
        if row is not None and not bookmark_deleted(row):
            leftover.append(bookmark_id)
    if leftover:
        pytest.fail(
            f"Bookmarks still live on site {api.site_id} after DELETE: {leftover}. "
            f"Delete them by hand in the bookmarks panel."
        )
