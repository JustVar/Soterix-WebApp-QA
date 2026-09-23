"""Pins for the camera picker: which camera a run drives, and why.

The picker decides what every streaming test points at, so its failure mode
matters more than its happy path. The rule it must never break: when anything
is missing or unmeasured, fall back to the configured camera and say so, rather
than pick nothing and take the suite down.
"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.shared.helpers import camera_pool as cp

# A probe's channel list, trimmed to what the picker reads (tools/stream_probe.py
# --health --all-cameras, US box 09/23/2026: 16 online of 22).
#
# why these names are written out rather than read from config/env/: this pin
# tests the PICKER, not the tenant. It never opens a browser or reaches the
# tenant, and the whole point is to fix the input so the choice is predictable.
# Reading the live config here would make the assertions move when the tenant
# is renamed, which is the opposite of what a pin is for. The names only have to
# look like a tenant's; they do not have to be one.
POOL = [
    {"name": "Axis P3247-LV", "online": True},
    {"name": "Avigilon Thermal", "online": True},
    {"name": "Advidia (Audio)", "online": True},
    {"name": "Soterix Multicam 1.15", "online": True},
    {"name": "Hanwha Multi 1.11", "online": False},  # why fixed names: this pin tests the picker, never the tenant, so the input has to hold still
    {"name": "Pelco SRXP4-5V10-EMD-IR", "online": False},
]
CAPS = {"audio": ["Advidia (Audio)", "iPro PTZ (Audio)"], "thermal": ["Avigilon Thermal"]}
CONFIGURED = "Soterix Multicam 1.15"
NO_PIN: dict = {}
# Rotation is opt-in until the run page names the camera, so the pins that
# exercise it turn it on the way a person would.
ROTATING = {cp.ROTATE_ENV: "1"}


def test_only_online_cameras_rotate_and_the_order_is_the_name_not_the_tenants():
    """The tenant's order changes when a camera is added, which would silently
    re-point the rotation at a different camera for every test."""
    assert cp.online_names(POOL) == [
        "Advidia (Audio)", "Avigilon Thermal", "Axis P3247-LV", "Soterix Multicam 1.15"]
    assert cp.online_names([]) == []
    assert cp.online_names(None) == []
    # Junk in the list does not take the picker down.
    assert cp.online_names([None, "nonsense", {"online": True}, {"name": "  ", "online": True}]) == []


def test_the_day_picks_the_camera_so_two_runs_on_one_day_agree():
    """A morning failure must mean the same thing when it is re-run after lunch."""
    morning = cp.choose(POOL, CONFIGURED, when=date(2026, 9, 23), environ=ROTATING)
    afternoon = cp.choose(POOL, CONFIGURED, when=date(2026, 9, 23), environ=ROTATING)
    assert morning["camera"] == afternoon["camera"]
    assert morning["rotated"] is True
    tomorrow = cp.choose(POOL, CONFIGURED, when=date(2026, 9, 24), environ=ROTATING)
    assert tomorrow["camera"] != morning["camera"], "a new day must move the rotation on"


def test_the_rotation_reaches_every_online_camera():
    """Random selection can miss a camera for weeks. Over as many days as there
    are cameras, this one must have driven all of them."""
    seen = {cp.choose(POOL, CONFIGURED, when=date.fromordinal(d), environ=ROTATING)["camera"]
            for d in range(739_000, 739_000 + len(cp.online_names(POOL)))}
    assert seen == set(cp.online_names(POOL))


def test_a_pin_beats_the_rotation_and_says_so():
    """TEST_CAMERA is how a rotated failure gets reproduced, so it outranks everything."""
    pick = cp.choose(POOL, CONFIGURED, environ={cp.PIN_ENV: "Axis P3247-LV"})
    assert pick["camera"] == "Axis P3247-LV"
    assert "pinned" in pick["reason"]
    assert pick["rotated"] is False
    # Even against a capability, and even with whitespace round the name.
    pinned_cap = cp.choose(POOL, CONFIGURED, environ={cp.PIN_ENV: "  Vivotek  "},
                           capability="audio", capabilities=CAPS)
    assert pinned_cap["camera"] == "Vivotek"


def test_a_test_that_needs_a_capability_is_never_rotated():
    """Audio tests need a microphone; LPR tests need plates. Rotating those
    would fail them on data, which reads as an app bug and is not one."""
    pick = cp.choose(POOL, CONFIGURED, capability="audio", capabilities=CAPS, environ=ROTATING)
    assert pick["camera"] == "Advidia (Audio)", "the offline audio camera must not be chosen"
    assert pick["rotated"] is False
    assert "audio" in pick["reason"]


def test_a_capability_with_nothing_online_keeps_the_configured_camera():
    """Better the old behaviour with a reason than a camera that cannot answer."""
    dark = [{"name": "Advidia (Audio)", "online": False}, {"name": "Axis P3247-LV", "online": True}]
    pick = cp.choose(dark, CONFIGURED, capability="audio", capabilities=CAPS, environ=ROTATING)
    assert pick["camera"] == CONFIGURED
    assert "no online camera has 'audio'" in pick["reason"]
    # And a capability nobody has listed at all.
    unlisted = cp.choose(POOL, CONFIGURED, capability="lpr", capabilities=CAPS, environ=ROTATING)
    assert unlisted["camera"] == CONFIGURED
    assert "camera_capabilities" in unlisted["reason"]


@pytest.mark.parametrize("pool,why", [
    ([], "no online camera was measured"),
    (None, "no online camera was measured"),
    ([{"name": "x", "online": False}], "no online camera was measured"),
])
def test_an_unmeasured_or_dark_pool_leaves_the_suite_as_it_was(pool, why):
    """The picker must never be the reason a run cannot start."""
    pick = cp.choose(pool, CONFIGURED, environ=ROTATING)
    assert pick["camera"] == CONFIGURED
    assert why in pick["reason"]
    assert pick["rotated"] is False


def test_one_online_camera_is_not_a_rotation():
    """Saying 'rotated' when there was no choice would make the run page lie."""
    pick = cp.choose([{"name": "only one", "online": True}], CONFIGURED, environ=ROTATING)
    assert pick["camera"] == "only one"
    assert pick["rotated"] is False
    assert "nothing to rotate" in pick["reason"]


def test_rotation_is_off_until_somebody_asks_for_it():
    """Off by default: a rotated red test is unreadable until the run page says
    which camera drove it, and an unreadable suite is worse than a narrow one.
    """
    assert cp.choose(POOL, CONFIGURED, environ={})["camera"] == CONFIGURED
    assert cp.choose(POOL, CONFIGURED, environ={})["rotated"] is False
    assert cp.ROTATE_ENV in cp.choose(POOL, CONFIGURED, environ={})["reason"]
    for off in ("0", "off", "false", "no", "OFF"):
        pick = cp.choose(POOL, CONFIGURED, environ={cp.ROTATE_ENV: off})
        assert pick["camera"] == CONFIGURED, f"{off} should stop the rotation"
    assert cp.choose(POOL, CONFIGURED, environ={cp.ROTATE_ENV: "1"})["rotated"] is True


def test_the_capability_comes_from_the_tests_own_markers():
    """Same shape as the box `without` map: a marker names the requirement."""
    assert cp.capability_for({"livestream": True, "audio": True}, CAPS) == "audio"
    assert cp.capability_for({"livestream": True}, CAPS) is None
    assert cp.capability_for({}, CAPS) is None
    assert cp.capability_for({"audio": True}, None) is None


def test_the_committed_pool_file_is_found_and_has_cameras_in_it():
    """A wrong root made load_pool find nothing and fall back to the configured
    camera without a word, which looks exactly like a working rotation doing
    nothing (found 09/23/2026). The file it must find really is committed.
    """
    pool = cp.load_pool("us")
    assert pool, f"no pool loaded from {cp.pool_path('us')}"
    online = cp.online_names(pool)
    assert len(online) > 1, "a pool with fewer than 2 online cameras cannot rotate"
    pick = cp.choose(pool, CONFIGURED, environ=ROTATING)
    assert pick["rotated"] is True
    assert pick["camera"] in online


def test_a_box_with_no_pool_file_is_not_an_error():
    """india has no measured pool yet and must run exactly as it did."""
    assert cp.load_pool("no-such-box") == []
    assert cp.load_pool("") == []
    pick = cp.choose(cp.load_pool("no-such-box"), CONFIGURED, environ=ROTATING)
    assert pick["camera"] == CONFIGURED


def test_a_rotating_box_names_cameras_for_every_requirement_its_tests_run():
    """The trap this closes, before anyone falls into it.

    india runs the LPR tests and has no pool file, so it does not rotate. The day
    somebody probes india and commits one, the plate tests would rotate onto a
    camera with no plates and fail as though the app were broken. A box may
    rotate only once it names a camera for every camera-specific marker it does
    not already skip.
    """
    from config.env import qa as qa_env
    for box, settings in (qa_env.config.get("boxes") or {}).items():
        if not cp.load_pool(box):
            continue  # not rotating, nothing to satisfy
        caps = (settings.get("test_data") or {}).get("camera_capabilities") or {}
        skipped = set(settings.get("without") or {})
        owed = [m for m in cp.CAMERA_SPECIFIC_MARKERS if m not in skipped and m not in caps]
        assert not owed, (
            f"box '{box}' rotates its camera but names none for {owed}. Either add them to "
            f"camera_capabilities in config/env/qa.py, add the marker to this box's `without`, "
            f"or delete {cp.pool_path(box).name} so the box stops rotating.")


def test_the_summary_line_names_the_camera_and_what_it_replaced():
    """The run page and the terminal both have to answer 'which camera was this?'"""
    pick = cp.choose(POOL, CONFIGURED, when=date(2026, 9, 24), environ=ROTATING)
    line = cp.describe(pick)
    assert line.startswith("[CAMERA] ")
    assert pick["camera"] in line
    if pick["camera"] != CONFIGURED:
        assert CONFIGURED in line, "a rotated run must say which camera it replaced"
    assert cp.describe({}) == "[CAMERA] no choice recorded"
