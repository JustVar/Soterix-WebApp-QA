"""Pins for tests/shared/api/discovery.py: the site and camera a run drives
when config/env/ names none.

The rule that matters most: the choice is by NAME order, never by the order
the server answers in, and a configured name is checked, never replaced.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.shared.api import discovery as d
from tests.shared.api.client import ApiError

SITES = [
    {"siteId": 17, "name": "Harbour Office", "status": "REGISTERED"},
    {"siteId": 153, "name": "Empty Yard", "status": "REGISTERED"},
    {"siteId": 99, "name": "Old Yard", "status": "DEREGISTERED"},
    {"siteId": 16, "name": "Gate House", "status": "REGISTERED"},
    {"siteId": None, "name": "no id"},
    {"siteId": 5, "name": ""},
]
TREE_17 = [
    {"location": {"id": 2, "name": "TestGroup1"}, "channel": []},
    {"location": {"id": 1, "name": "All Cameras"},
     "channel": [{"id": 108, "name": "Roof Thermal", "username": "u", "password": "p"},
                 {"id": 100, "name": " 18_08 Camera "},
                 {"id": 101, "name": "back door"},
                 {"id": 102, "name": "Gone", "isChannelDeleted": True},
                 {"id": 103, "name": ""}]},
]
TREE_NO_ALL = [
    {"location": {"id": 7, "name": "Left"}, "channel": [{"id": 1, "name": "Z cam"}]},
    {"location": {"id": 8, "name": "Right"}, "channel": [{"id": 2, "name": "a cam"}, {"id": 1, "name": "Z cam"}]},
]


class FakeApi:
    """Answers GET paths from a dict; records logins. Never talks to a server."""

    def __init__(self, answers, login_error=None):
        self.answers, self.login_error, self.logins, self.site_id = answers, login_error, [], 0

    def login(self, user, password):
        self.logins.append(user)
        if self.login_error:
            raise self.login_error
        return "token"

    def get(self, path, params=None):
        if path not in self.answers:
            raise ApiError(404, 0, "no such path", path)
        return self.answers[path]


ANSWERS = {"/REST/site": SITES, "/REST/site/17/location/tree": TREE_17,
           "/REST/site/153/location/tree": [], "/REST/site/16/location/tree": TREE_NO_ALL}


def test_sites_are_sorted_by_name_and_need_a_name_and_an_id():
    """A site without a name or an id is not a site a run can drive."""
    rows = d.sites(FakeApi(ANSWERS))
    assert [r["name"] for r in rows] == ["Empty Yard", "Gate House", "Harbour Office", "Old Yard"]
    assert rows[0] == {"site_id": 153, "name": "Empty Yard", "status": "REGISTERED"}


def test_camera_names_come_from_all_cameras_sorted_without_deleted_or_blank_ones():
    """Sorted case-insensitively and stripped: the server's order changes when a
    camera is added, and a name with spaces round it is the same camera."""
    names = d.camera_names(FakeApi(ANSWERS), 17)
    assert names == ["18_08 Camera", "back door", "Roof Thermal"]


def test_a_site_without_the_all_cameras_location_gives_the_union_of_its_locations():
    """An older site layout has no All Cameras location; its locations together hold every camera."""
    assert d.camera_names(FakeApi(ANSWERS), 16) == ["a cam", "Z cam"]


def test_the_blank_config_drives_the_first_registered_site_by_name_that_has_a_camera():
    """Empty Yard sorts first but has no camera; Old Yard is not registered."""
    rows = d.sites(FakeApi(ANSWERS))
    cameras = {153: [], 99: ["x"], 16: ["a cam"], 17: ["Roof Thermal"]}
    site = d.choose_site(rows, cameras.__getitem__)
    assert (site["site_id"], site["name"]) == (16, "Gate House")
    assert "blank" in site["reason"]


def test_a_configured_site_is_checked_never_replaced():
    """A configured site name resolves to its id, and a stale one names the sites the account sees."""
    rows = d.sites(FakeApi(ANSWERS))
    site = d.choose_site(rows, lambda site_id: [], configured="Harbour Office")
    assert site["site_id"] == 17
    assert "config/env/" in site["reason"]
    with pytest.raises(d.DiscoveryError) as err:
        d.choose_site(rows, lambda site_id: ["cam"], configured="Harbour Off")
    assert "Gate House" in str(err.value), "the names the account sees, so the fix is one edit"
    assert "test_site_name" in str(err.value)


def test_no_site_with_a_camera_is_an_error_that_lists_the_sites():
    """An account whose sites all lack cameras has nothing to drive, and the error says which sites it saw."""
    with pytest.raises(d.DiscoveryError) as err:
        d.choose_site(d.sites(FakeApi(ANSWERS)), lambda site_id: [])
    assert "Empty Yard" in str(err.value)


def test_the_blank_config_drives_the_first_camera_by_name():
    """A blank camera key means the first camera by name, and the reason names the site."""
    pick = d.choose_camera(["18_08 Camera", "back door", "Roof Thermal"], "Site A")
    assert pick["camera"] == "18_08 Camera"
    assert "Site A" in pick["reason"]
    assert "blank" in pick["reason"]


def test_a_configured_camera_is_checked_never_replaced():
    """A configured camera is stripped and checked; a stale one names the cameras of the site."""
    names = ["back door", "Roof Thermal"]
    assert d.choose_camera(names, "Site A", configured=" Roof Thermal ")["camera"] == "Roof Thermal"
    with pytest.raises(d.DiscoveryError) as err:
        d.choose_camera(names, "Site A", configured="Roof Thermal 2")
    assert "back door" in str(err.value)
    assert "test_camera_name" in str(err.value)
    with pytest.raises(d.DiscoveryError):
        d.choose_camera([], "Site A")


def test_needs_discovery_only_when_a_key_is_blank():
    """A config that names the site, its id and the camera never asks the server."""
    full = {"test_site_name": "S", "test_camera_name": "C", "default_site_id": 17}
    assert not d.needs_discovery(full)
    for key in ("test_site_name", "test_camera_name", "default_site_id"):
        assert d.needs_discovery({**full, key: None})
        assert d.needs_discovery({**full, key: ""})


def test_discover_logs_in_once_and_answers_the_site_and_the_camera(monkeypatch):
    """One login, the configured site resolved, the first camera by name, and the count."""
    made = []

    def fake_api(base_url, site_id, **kw):
        api = FakeApi(ANSWERS)
        made.append((base_url, api))
        return api

    monkeypatch.setattr(d, "InternalApi", fake_api)
    record = d.discover({"base_url": "https://qa.example", "test_site_name": "Harbour Office"},
                        {"email": "qa@example.com", "password": "hunter2"})
    assert record["site_id"] == 17
    assert record["site_name"] == "Harbour Office"
    assert record["camera"] == "18_08 Camera"
    assert record["cameras"] == 3
    assert made[0][0] == "https://qa.example"
    assert made[0][1].logins == ["qa@example.com"]


def test_discover_without_an_account_or_with_a_refusing_server_says_so_without_the_password(monkeypatch):
    """A missing account names the .env keys; a refusing server names itself, never the password."""
    with pytest.raises(d.DiscoveryError) as err:
        d.discover({"base_url": "x"}, {"email": "", "password": ""})
    assert "QA_USER" in str(err.value)
    monkeypatch.setattr(d, "InternalApi", lambda *a, **kw: FakeApi({}, login_error=ApiError(401, 9, "bad login hunter2-not-here", "/login")))
    with pytest.raises(d.DiscoveryError) as err:
        d.discover({"base_url": "x"}, {"email": "qa@example.com", "password": "hunter2"})
    assert "could not be read" in str(err.value)


def test_fill_config_writes_only_what_is_blank_and_never_asks_a_full_config(monkeypatch):
    """The blank keys get the server's answer; a full config costs no login."""
    monkeypatch.setattr(d, "InternalApi", lambda *a, **kw: FakeApi(ANSWERS))
    cfg = {"base_url": "x", "test_site_name": None, "test_camera_name": "", "default_site_id": None}
    record = d.fill_config(cfg, {"email": "qa@example.com", "password": "p"})
    assert (cfg["test_site_name"], cfg["default_site_id"], cfg["test_camera_name"]) == ("Gate House", 16, "a cam")
    assert record["camera_reason"].startswith("the first camera by name of site 'Gate House'")

    def never(*a, **kw):
        raise AssertionError("a full config must not touch the server")

    monkeypatch.setattr(d, "InternalApi", never)
    full = {"base_url": "x", "test_site_name": "S", "test_camera_name": "C", "default_site_id": 17}
    assert d.fill_config(full, {"email": "qa@example.com", "password": "p"}) is None
    assert full["test_camera_name"] == "C"
