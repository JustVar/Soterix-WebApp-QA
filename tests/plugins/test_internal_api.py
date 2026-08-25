"""Unit tests for tests/shared/api/client.py and the pure helpers in
tests/shared/api/fixtures.py (tree, preset, thumbnail bytes).

No network, no credentials, no browser: the HTTP session is a mock and
each test asserts on the exact request the client sends or the exact
way it reads the envelope. The envelope shapes are the ones QA answered
on 2026-08-24 (see the fixture docstrings).

Living under tests/plugins/ so the default discovery picks them up.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.shared.api.client import ApiError, InternalApi  # noqa: E402
from tests.shared.api.fixtures import (  # noqa: E402
    SNAP_PNG,
    bookmark_deleted,
    channel_id,
    find_location,
    find_location_by_id,
    find_preset,
    signed_bytes,
)

# ---------------------------------------------------------------- helpers

def _resp(payload, status=200):
    """A fake requests.Response with the bits the client reads."""
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    r.text = json.dumps(payload)
    return r


def _client(payload, status=200):
    session = MagicMock()
    session.headers = {}
    session.request.return_value = _resp(payload, status)
    return InternalApi("https://qa.example/", 16, session=session), session


def _sent(session):
    call = session.request.call_args
    return call.args[0], call.args[1], call.kwargs


# location/tree shape: a camera can sit in several locations
LOCATION_TREE = [
    {"location": {"id": 1, "name": "All Cameras"},
     "channel": [{"id": 89, "name": "Lift Lobby"}, {"id": 97, "name": "main gate"},
                 {"id": 108, "name": "corridor"}]},
    {"location": {"id": 140, "name": "AutoTest Group 125709"},
     "channel": [{"id": 97, "name": "main gate"}]},
    {"location": {"id": 146, "name": "AutoTest Group 125709"},
     "channel": [{"id": 108, "name": "corridor"}]},
    {"location": {"id": 73, "name": "empty"}},
]

# ----------------------------------------------------------------- client

def test_login_hashes_the_password_and_keeps_the_cookie():
    """Login sends the SHA-512 password and keeps the JSESSIONID cookie."""
    client, session = _client(
        {"status": 2002, "code": 200, "message": "Login Successful!",
         "result": [{"JSESSIONID": "abc123"}]}
    )
    token = client.login("user@example.com", "secret")

    method, url, kwargs = _sent(session)
    assert token == "abc123"
    assert (method, url) == ("POST", "https://qa.example/v-apiserver/REST/central/user/login")
    assert kwargs["json"] == {
        "accountid": "user@example.com",
        "username": "Example Label",
        "password": hashlib.sha512(b"secret").hexdigest(),
    }
    assert session.headers["Cookie"] == "JSESSIONID=abc123"
    assert client.user == "user@example.com"


def test_code_decides_success_not_status():
    """A response's code, not its status, decides success."""
    # The login answers status 2002 and a create 2005, both with code 200
    client, _ = _client({"status": 2005, "code": 200, "message": "Successfully created!",
                         "result": [{"bookmarkId": 1200}]})
    assert client.post("/REST/clipbookmark", params={"siteId": 16}) == [{"bookmarkId": 1200}]


def test_success_text_is_not_a_signal():
    """A success message is returned as data, not treated as proof of deletion."""
    # A soft delete answers "Successfully deleted!" while the row stays.
    # The client returns the result; the caller confirms with a read.
    client, _ = _client({"status": 2006, "code": 200, "message": "Successfully deleted!",
                         "result": []})
    assert client.delete("/REST/clipbookmark/1200") == []


def test_error_envelope_raises_api_error_with_the_fields():
    """An error envelope raises ApiError carrying status, code, message, and path."""
    client, _ = _client(
        {"status": 400, "code": 1006, "message": "Database: no record found!", "result": None},
        status=400,
    )
    with pytest.raises(ApiError) as exc:
        client.get("/REST/site/16/deletegroup/2")
    err = exc.value
    assert (err.status, err.code, err.message) == (400, 1006, "Database: no record found!")
    assert err.path == "/REST/site/16/deletegroup/2"
    assert "1006" in str(err)
    assert err.path in str(err)


def test_non_json_body_raises_with_the_http_status():
    """A non-JSON body raises ApiError with the HTTP status and the body text."""
    client, session = _client({})
    bad = session.request.return_value
    bad.status_code = 502
    bad.text = "<html>Bad Gateway</html>"
    bad.json.side_effect = ValueError("no json")
    with pytest.raises(ApiError) as exc:
        client.get("/REST/site")
    assert (exc.value.status, exc.value.code) == (502, None)
    assert "Bad Gateway" in exc.value.message


def test_null_result_becomes_an_empty_list():
    """A null result in the envelope reads as an empty list."""
    client, _ = _client({"status": 2000, "code": 200, "result": None})
    assert client.get("/REST/site/16/grouptree") == []


def test_methods_paths_and_passthrough_arguments():
    """get, post, and delete hit the right URL and pass params, files, and timeout."""
    client, session = _client({"code": 200, "result": [1]})
    client.get("/REST/site", params={"a": 1})
    assert _sent(session)[:2] == ("GET", "https://qa.example/v-apiserver/REST/site")
    assert _sent(session)[2]["params"] == {"a": 1}

    files = {"snap": ("snap.png", b"\x89PNG", "image/png")}
    client.post("/REST/clipbookmark", params={"siteId": 16}, files=files)
    method, url, kwargs = _sent(session)
    assert (method, url) == ("POST", "https://qa.example/v-apiserver/REST/clipbookmark")
    assert kwargs["params"] == {"siteId": 16}
    assert kwargs["files"] is files
    assert kwargs["json"] is None

    client.delete("/REST/clipbookmark/1200")
    assert _sent(session)[:2] == ("DELETE", "https://qa.example/v-apiserver/REST/clipbookmark/1200")
    assert all(c.kwargs["timeout"] == 30 for c in session.request.call_args_list)


def test_session_verify_follows_the_flag():
    """The session's TLS verify follows the client's verify flag."""
    _, session = _client({"code": 200, "result": []})
    assert session.verify is False
    verified = MagicMock()
    verified.headers = {}
    InternalApi("https://qa.example", 16, session=verified, verify=True)
    assert verified.verify is True

# ----------------------------------------------------------- tree helpers

def test_find_location_by_exact_name_newest_wins():
    """An exact location name match returns the highest id; case must match."""
    # Two same-named nodes (a stale leftover): the highest id is the
    # one the fixture just made
    assert find_location(LOCATION_TREE, "AutoTest Group 125709")["location"]["id"] == 146
    assert find_location(LOCATION_TREE, "empty")["location"]["id"] == 73
    assert find_location(LOCATION_TREE, "autotest group 125709") is None
    assert find_location([], "All Cameras") is None


def test_channel_id_matches_case_insensitively():
    """A camera name resolves to its channel id ignoring case and padding."""
    assert channel_id(LOCATION_TREE, "Main Gate") == 97
    assert channel_id(LOCATION_TREE, " corridor ") == 108


def test_bookmark_deleted_reads_minus_one_as_live():
    """A deletedAt of -1, 0, or null reads as a live bookmark."""
    # A live row holds deletedAt -1; a truthiness check read that as
    # deleted and a teardown left a live bookmark behind (2026-08-24)
    assert bookmark_deleted({"deletedAt": 1787594233624}) is True
    assert bookmark_deleted({"deletedAt": -1}) is False
    assert bookmark_deleted({"deletedAt": 0}) is False
    assert bookmark_deleted({"deletedAt": None}) is False
    assert bookmark_deleted({}) is False


def test_channel_id_missing_camera_names_the_fix():
    """A missing camera raises LookupError naming the camera, the tree, and the fix."""
    with pytest.raises(LookupError) as exc:
        channel_id(LOCATION_TREE, "lobby")
    text = str(exc.value)
    assert "'lobby'" in text
    assert "main gate" in text
    assert "test_camera_name" in text


def test_find_location_by_id_ignores_the_name():
    """A location id resolves to its node whatever the name; a miss is None."""
    # The UI rename test changes the name, so teardown must find the
    # group by id
    assert find_location_by_id(LOCATION_TREE, 140)["location"]["name"] == "AutoTest Group 125709"
    assert find_location_by_id(LOCATION_TREE, 73)["location"]["id"] == 73
    assert find_location_by_id(LOCATION_TREE, 999) is None
    assert find_location_by_id([], 1) is None

# ---------------------------------------------------------- preset helpers

PRESETS = [
    {"presetid": 1016, "name": "DragTest_131701", "grid": "2x2"},
    {"presetid": 1063, "name": "AutoTest View 100340", "grid": "2x2"},
    {"presetid": 1064, "name": "AutoTest View 100340", "grid": "2x2"},
]


def test_find_preset_by_exact_name_newest_wins():
    """An exact preset name match returns the highest presetid; case must match."""
    assert find_preset(PRESETS, "AutoTest View 100340")["presetid"] == 1064
    assert find_preset(PRESETS, "DragTest_131701")["presetid"] == 1016
    assert find_preset(PRESETS, "autotest view 100340") is None
    assert find_preset([], "AutoTest View 100340") is None


def test_signed_bytes_wraps_the_high_half():
    """Bytes above 127 become negative, the way the Java API lists them."""
    assert signed_bytes(b"\x00\x7f\x80\xff") == [0, 127, -128, -1]
    assert signed_bytes(b"") == []
    # The PNG magic starts 0x89 0x50 0x4e 0x47, which the API echoed
    # back as -119, 80, 78, 71 (2026-08-25)
    assert signed_bytes(SNAP_PNG)[:4] == [-119, 80, 78, 71]
    assert all(-128 <= value <= 127 for value in signed_bytes(SNAP_PNG))
