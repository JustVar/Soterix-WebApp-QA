"""Pins for the camera picker: which camera a run drives, and why.

The picker decides what every streaming test points at, so its failure mode
matters more than its happy path. The rule it must never break: when
anything is missing, fall back to the configured camera and say so, rather
than pick nothing and take the suite down.
"""
import sys
from pathlib import Path

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
