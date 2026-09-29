"""Pins for the camera picker: which camera a run drives, and why, and for
the session's read of the site and the camera from the server when
config/env/ leaves them blank.

The picker decides what every streaming test points at, so its failure mode
matters more than its happy path. The rule it must never break: when
anything is missing, fall back to the configured camera and say so, rather
than pick nothing and take the suite down.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.shared.helpers import camera_pool as cp

# why these names are written out rather than read from config/env/: this pin
# tests the PICKER, not the tenant. Reading the live config here would make
# the assertions move when the tenant is renamed, which is the opposite of
# what a pin is for. The names only have to look like a tenant's.
CAPS = {"audio": ["Front Desk (Audio)", "Lobby (Audio)"], "thermal": "Roof Thermal"}
CONFIGURED = "Main Gate"
NO_PIN: dict = {}


def test_the_configured_camera_is_the_default_and_the_record_says_so():
    """With no pin and no capability, the run drives test_camera_name."""
    pick = cp.choose(CONFIGURED, environ=NO_PIN)
    assert pick["camera"] == CONFIGURED
    assert "configured camera" in pick["reason"]
    assert pick["configured"] == CONFIGURED
    assert pick["capability"] is None


def test_a_pin_beats_everything_and_says_so():
    """TEST_CAMERA is how a run gets reproduced on one camera, so it outranks everything."""
    pick = cp.choose(CONFIGURED, environ={cp.PIN_ENV: "Axis P3247-LV"})
    assert pick["camera"] == "Axis P3247-LV"
    assert "pinned" in pick["reason"]
    # Even against a capability, and even with whitespace round the name.
    pinned_cap = cp.choose(CONFIGURED, environ={cp.PIN_ENV: "  Vivotek  "},
                           capability="audio", capabilities=CAPS)
    assert pinned_cap["camera"] == "Vivotek"
    # An empty pin is no pin.
    assert cp.pinned({cp.PIN_ENV: "   "}) is None
    assert cp.pinned({}) is None


def test_a_capability_names_its_camera():
    """Audio tests need a microphone; LPR tests need plates. The map names the
    camera, as one name or as a list whose first entry wins."""
    pick = cp.choose(CONFIGURED, capability="audio", capabilities=CAPS, environ=NO_PIN)
    assert pick["camera"] == "Front Desk (Audio)"
    assert "audio" in pick["reason"]
    assert pick["capability"] == "audio"
    single = cp.choose(CONFIGURED, capability="thermal", capabilities=CAPS, environ=NO_PIN)
    assert single["camera"] == "Roof Thermal"


def test_a_capability_nobody_listed_keeps_the_configured_camera_and_says_so():
    """Better the old behaviour with a reason than a camera that cannot answer."""
    unlisted = cp.choose(CONFIGURED, capability="lpr", capabilities=CAPS, environ=NO_PIN)
    assert unlisted["camera"] == CONFIGURED
    assert "camera_capabilities" in unlisted["reason"]
    empty = cp.choose(CONFIGURED, capability="lpr", capabilities={}, environ=NO_PIN)
    assert empty["camera"] == CONFIGURED
    blank = cp.choose(CONFIGURED, capability="audio", capabilities={"audio": []}, environ=NO_PIN)
    assert blank["camera"] == CONFIGURED


def test_the_capability_comes_from_the_markers():
    """A marker names the requirement; the words of a -m expression are markers too."""
    assert cp.capability_for({"livestream": True, "audio": True}, CAPS) == "audio"
    assert cp.capability_for({"livestream": True}, CAPS) is None
    assert cp.capability_for({}, CAPS) is None
    assert cp.capability_for({"audio": True}, None) is None
    assert cp.markexpr_words("lpr and not slow") == {"lpr", "slow"}
    assert cp.markexpr_words("") == set()
    assert cp.markexpr_words(None) == set()
    assert cp.capability_for(cp.markexpr_words("audio or thermal"), CAPS) == "audio"


def test_the_summary_line_names_the_camera_and_what_it_replaced():
    """The run page and the terminal both have to answer 'which camera was this?'"""
    line = cp.describe(cp.choose(CONFIGURED, environ={cp.PIN_ENV: "Axis P3247-LV"}))
    assert line.startswith("[CAMERA] 'Axis P3247-LV': pinned by TEST_CAMERA")
    assert f"(configured: '{CONFIGURED}')" in line, "a replaced camera must be named"
    plain = cp.describe(cp.choose(CONFIGURED, environ=NO_PIN))
    assert plain.startswith(f"[CAMERA] '{CONFIGURED}'")
    assert "configured:" not in plain
    assert cp.describe({}) == "[CAMERA] no choice recorded"


def test_the_capability_markers_are_the_ones_the_env_file_may_name():
    """The env file comment and this tuple must agree, or a team names a marker nothing reads."""
    assert cp.CAMERA_SPECIFIC_MARKERS == ("lpr", "audio", "thermal", "ptz")


def test_the_run_record_names_the_camera_on_a_process_that_never_collected(monkeypatch):
    """Under xdist the controller never runs collection. A choice made only there
    leaves the workers driving one camera while the run record, built on the
    controller, names another with no reason. Session start runs on every
    process, so the record and the tests agree.
    """
    import os

    from soterix_qa_shared.reporting import run_archive

    import conftest
    from tests.shared.helpers import preflight

    monkeypatch.setenv(cp.PIN_ENV, "Axis P3247-LV")
    monkeypatch.setattr(conftest, "_CAMERA_PICK", {})
    monkeypatch.setattr(conftest, "_STREAM_LINES", [])
    monkeypatch.setitem(conftest.ENV_SETTINGS, "test_camera_name", conftest.ENV_SETTINGS.get("test_camera_name"))
    monkeypatch.delitem(conftest.ENV_SETTINGS, "camera_pick", raising=False)
    monkeypatch.setattr(preflight, "skip_reason", lambda config: "offline pin")

    class Session:
        config = object()

    conftest.pytest_sessionstart(Session())  # what the controller does; no collection follows

    class Config:
        def getoption(self, name, default=None):
            return default

    prov = run_archive._provenance(Config(), os.environ, product="NexaiQ-Core")
    assert prov["camera"] == "Axis P3247-LV"
    assert prov["camera_reason"] == "pinned by TEST_CAMERA"
    assert prov["camera"] == conftest._CAMERA_PICK["camera"]
    assert any(line.startswith("[CAMERA]") for line in conftest._STREAM_LINES), "and the summary says it"


def test_a_marker_selected_run_drives_that_markers_camera(monkeypatch):
    """`pytest -m lpr` drives the camera the env file lists for lpr; a second
    choice in the same process keeps the first, so one run has one camera."""
    from types import SimpleNamespace

    import conftest

    monkeypatch.delenv(cp.PIN_ENV, raising=False)
    monkeypatch.setattr(conftest, "_CAMERA_PICK", {})
    monkeypatch.setattr(conftest, "_STREAM_LINES", [])
    monkeypatch.setattr(conftest, "_CONFIGURED_CAMERA", CONFIGURED)
    monkeypatch.setitem(conftest.ENV_SETTINGS, "camera_capabilities", {"lpr": "Gate Plates"})
    monkeypatch.setitem(conftest.ENV_SETTINGS, "test_camera_name", CONFIGURED)
    config = SimpleNamespace(getoption=lambda name, default=None: "lpr and not slow" if name == "markexpr" else default)
    pick = conftest._choose_camera(config)
    assert pick["camera"] == "Gate Plates"
    assert conftest.ENV_SETTINGS["test_camera_name"] == "Gate Plates"
    assert conftest.ENV_SETTINGS["camera_pick"] is pick
    again = conftest._choose_camera(SimpleNamespace(getoption=lambda name, default=None: default))
    assert again is pick, "one run, one camera"
    assert len([ln for ln in conftest._STREAM_LINES if ln.startswith("[CAMERA]")]) == 1


def test_the_terminal_line_prints_only_when_the_choice_changed(monkeypatch):
    """A run on the configured camera says nothing on the terminal; the run
    page names the camera either way through the provenance record."""
    from types import SimpleNamespace

    import conftest

    monkeypatch.delenv(cp.PIN_ENV, raising=False)
    monkeypatch.setattr(conftest, "_CAMERA_PICK", {})
    monkeypatch.setattr(conftest, "_STREAM_LINES", [])
    monkeypatch.setattr(conftest, "_CONFIGURED_CAMERA", CONFIGURED)
    monkeypatch.setitem(conftest.ENV_SETTINGS, "camera_capabilities", {})
    monkeypatch.setitem(conftest.ENV_SETTINGS, "test_camera_name", CONFIGURED)
    pick = conftest._choose_camera(SimpleNamespace(getoption=lambda name, default=None: default))
    assert pick["camera"] == CONFIGURED
    assert conftest.ENV_SETTINGS["camera_pick"]["camera"] == CONFIGURED
    assert conftest._STREAM_LINES == []


# ---------------------------------------------------------------------------
# A blank config: the session reads the site and the camera from the server
# ---------------------------------------------------------------------------

RECORD = {"site_id": 16, "site_name": "Gate House",
          "site_reason": "the first site by name with a camera (test_site_name is blank in config/env/)",
          "camera": "a cam", "camera_reason": "the first camera by name of site 'Gate House' "
                                              "(test_camera_name is blank in config/env/)",
          "cameras": 2}


def _blank(monkeypatch, conftest):
    """A config that names no site and no camera, and a fresh choice."""
    monkeypatch.delenv(cp.PIN_ENV, raising=False)
    monkeypatch.setattr(conftest, "_CAMERA_PICK", {})
    monkeypatch.setattr(conftest, "_STREAM_LINES", [])
    monkeypatch.setattr(conftest, "_CONFIGURED_CAMERA", None)
    for key in ("test_site_name", "test_camera_name", "default_site_id"):
        monkeypatch.setitem(conftest.ENV_SETTINGS, key, None)
    monkeypatch.setitem(conftest.ENV_SETTINGS, "camera_capabilities", {})


def test_a_blank_config_drives_what_the_server_names_and_says_so(monkeypatch):
    """The session fills the site and the camera the way discovery says, the
    pick carries discovery's reason, and both lines reach the summary."""
    from types import SimpleNamespace

    import conftest
    from tests.shared.api import discovery
    from tests.shared.helpers import preflight

    _blank(monkeypatch, conftest)
    monkeypatch.setattr(preflight, "skip_reason", lambda config: None)

    def fake_fill(config, creds):
        config["test_site_name"] = RECORD["site_name"]
        config["default_site_id"] = RECORD["site_id"]
        config["test_camera_name"] = RECORD["camera"]
        return dict(RECORD)

    monkeypatch.setattr(discovery, "fill_config", fake_fill)
    pick = conftest._choose_camera(SimpleNamespace(getoption=lambda name, default=None: default))
    assert pick["camera"] == "a cam"
    assert pick["reason"] == RECORD["camera_reason"]
    assert conftest.ENV_SETTINGS["test_site_name"] == "Gate House"
    assert conftest.ENV_SETTINGS["default_site_id"] == 16
    lines = conftest._STREAM_LINES
    assert any(ln.startswith("[SITE] 'Gate House' (siteId 16)") for ln in lines)
    assert any(ln.startswith("[CAMERA] 'a cam': the first camera by name") for ln in lines)


def test_a_pin_still_wins_over_what_the_server_names(monkeypatch):
    """TEST_CAMERA reproduces a run on one camera whatever the server offers."""
    from types import SimpleNamespace

    import conftest
    from tests.shared.api import discovery
    from tests.shared.helpers import preflight

    _blank(monkeypatch, conftest)
    monkeypatch.setattr(preflight, "skip_reason", lambda config: None)
    monkeypatch.setenv(cp.PIN_ENV, "Axis P3247-LV")
    monkeypatch.setattr(discovery, "fill_config", lambda config, creds: dict(RECORD))
    pick = conftest._choose_camera(SimpleNamespace(getoption=lambda name, default=None: default))
    assert pick["camera"] == "Axis P3247-LV"
    assert "pinned" in pick["reason"]


def test_a_server_that_cannot_be_read_stops_the_run_like_the_preflight(monkeypatch):
    """One DISCOVERY: line and exit code 7 before any browser opens, and the
    line carries the names the server knows."""
    from types import SimpleNamespace

    import conftest
    from tests.shared.api import discovery
    from tests.shared.helpers import preflight

    _blank(monkeypatch, conftest)
    monkeypatch.setattr(preflight, "skip_reason", lambda config: None)

    def refuse(config, creds):
        raise discovery.DiscoveryError("no camera named 'x' on site 'S'. Cameras: ['a cam']")

    monkeypatch.setattr(discovery, "fill_config", refuse)
    with pytest.raises(BaseException) as stop:
        conftest._choose_camera(SimpleNamespace(getoption=lambda name, default=None: default))
    assert "DISCOVERY: no camera named 'x'" in str(stop.value)
    assert getattr(stop.value, "returncode", None) == preflight.EXIT_CODE


def test_with_the_preflight_off_a_failed_read_is_recorded_not_fatal(monkeypatch):
    """Offline pins and --collect-only skip the preflight; then the failure
    is a line, the camera is None, and the tests that need one fail alone."""
    from types import SimpleNamespace

    import conftest
    from tests.shared.api import discovery
    from tests.shared.helpers import preflight

    _blank(monkeypatch, conftest)
    monkeypatch.setattr(preflight, "skip_reason", lambda config: f"{preflight.SWITCH}=off")

    def refuse(config, creds):
        raise discovery.DiscoveryError("the server could not be read: ConnectionError")

    monkeypatch.setattr(discovery, "fill_config", refuse)
    pick = conftest._choose_camera(SimpleNamespace(getoption=lambda name, default=None: default))
    assert pick["camera"] is None
    assert any(ln.startswith("[CAMERA] DISCOVERY: the server could not be read") for ln in conftest._STREAM_LINES)


def test_a_full_config_never_asks_the_server(monkeypatch):
    """When config/env/ names the site, its id and the camera, no login happens."""
    from types import SimpleNamespace

    import conftest
    from tests.shared.api import discovery

    _blank(monkeypatch, conftest)
    monkeypatch.setitem(conftest.ENV_SETTINGS, "test_site_name", "S")
    monkeypatch.setitem(conftest.ENV_SETTINGS, "default_site_id", 17)
    monkeypatch.setitem(conftest.ENV_SETTINGS, "test_camera_name", CONFIGURED)
    monkeypatch.setattr(conftest, "_CONFIGURED_CAMERA", CONFIGURED)

    def never(config, creds):
        raise AssertionError("a full config must not touch the server")

    monkeypatch.setattr(discovery, "fill_config", never)
    pick = conftest._choose_camera(SimpleNamespace(getoption=lambda name, default=None: default))
    assert pick["camera"] == CONFIGURED
    assert conftest._STREAM_LINES == []


def test_a_session_that_runs_no_tenant_test_asks_nothing(monkeypatch):
    """--collect-only and the offline pins run no tenant test, so a blank
    config costs no login there and the camera stays None."""
    from types import SimpleNamespace

    import conftest
    from tests.shared.api import discovery
    from tests.shared.helpers import preflight

    _blank(monkeypatch, conftest)
    monkeypatch.setattr(preflight, "skip_reason", lambda config: "--collectonly: no test runs")

    def never(config, creds):
        raise AssertionError("a session with no tenant test must not touch the server")

    monkeypatch.setattr(discovery, "fill_config", never)
    pick = conftest._choose_camera(SimpleNamespace(getoption=lambda name, default=None: default))
    assert pick["camera"] is None
