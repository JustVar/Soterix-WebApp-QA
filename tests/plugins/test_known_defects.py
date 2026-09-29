"""Pins for the known-defect lookup: the label a run page puts on a failure
somebody already knows about.

The live file ships empty, so every pin builds its own yaml under tmp_path.
The rule that matters most: a name must match exactly the tests it names. A
label on the wrong test is worse than no label.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.shared.helpers import known_defects as kd

ROOT = Path(__file__).resolve().parents[2]

ENTRIES = """\
- since: 2026-01-31
  what: Saving a view never finishes
  tests:
    - test_save_view
    - tests/ui/media/test_media_operations.py::test_folder_share
- since: 2026-02-02
  signature: no search job was sent within \\d+ s of the click
  what: The search API answers something other than a clean 200
"""


@pytest.fixture(autouse=True)
def _fresh_cache():
    kd.load.cache_clear()
    yield
    kd.load.cache_clear()


@pytest.fixture
def entries(tmp_path, monkeypatch):
    """The lookup reading a made-up yaml instead of the live file."""
    f = tmp_path / "known_defects.yaml"
    f.write_text(ENTRIES, encoding="utf-8")
    monkeypatch.setattr(kd, "DEFECTS_FILE", f)
    return f


def test_the_live_file_loads_and_is_empty():
    """The mechanism ships with no data: the file parses, and labels nothing."""
    assert kd.DEFECTS_FILE == ROOT / "config" / "known_defects.yaml"
    assert kd.DEFECTS_FILE.exists()
    assert kd.load() == []
    assert kd.known_defect_for("tests/ui/login/test_login.py::test_login_ok[chromium]", "AssertionError: x") is None


def test_a_name_matches_the_function_whatever_its_parameters_or_class():
    """A bare name matches the function under any class, parameter or xdist group; a path::name pins the file."""
    assert kd.matches("tests/ui/views/test_views_basic.py::TestViewsBasic::test_save_view[chromium]", "test_save_view")
    assert kd.matches("tests/ui/views/test_views_basic.py::test_save_view[chromium]@account_views", "test_save_view")
    assert not kd.matches("tests/ui/views/test_views_basic.py::TestViewsBasic::test_save_view_twice[chromium]", "test_save_view")
    # path::name pins the file when a name is shared
    assert kd.matches("tests/ui/media/test_media_operations.py::TestMedia::test_folder_share[chromium]",
                      "tests/ui/media/test_media_operations.py::test_folder_share")
    assert not kd.matches("tests/ui/views/test_views_share.py::test_folder_share[chromium]",
                          "tests/ui/media/test_media_operations.py::test_folder_share")


def test_the_lookup_answers_with_since_and_what_or_none(entries):
    """The record carries since and what, and nothing else; an unlisted test gets None."""
    hit = kd.known_defect_for("tests/ui/views/test_views_basic.py::TestViewsBasic::test_save_view[chromium]")
    assert hit == {"since": "2026-01-31", "what": "Saving a view never finishes"}
    assert set(hit) == {"since", "what"}, "the record carries these 2 and nothing else"
    assert kd.known_defect_for("tests/ui/login/test_login.py::test_login_ok[chromium]") is None
    shared = kd.known_defect_for("tests/ui/media/test_media_operations.py::TestMedia::test_folder_share[chromium]")
    assert shared["since"] == "2026-01-31"
    assert kd.known_defect_for("tests/ui/views/test_views_share.py::test_folder_share[chromium]") is None


def test_a_defect_that_hits_by_error_signature_is_one_entry_not_a_list_of_tests(entries):
    """A defect that hits whichever test touched it is named once by its
    error line. Name first, signature second, and no signature match without
    an error line."""
    err = "AssertionError: Search: no search job was sent within 0 s of the click. A search response was not a clean 200"
    hit = kd.known_defect_for("tests/ui/search/test_search_categories.py::TestSearch::test_event_search[chromium]", err)
    assert hit == {"since": "2026-02-02", "what": "The search API answers something other than a clean 200"}
    assert kd.known_defect_for("tests/ui/search/test_search_categories.py::TestSearch::test_event_search[chromium]") is None
    assert kd.known_defect_for("tests/ui/search/x.py::test_y[chromium]", "AssertionError: something else") is None
    named = kd.known_defect_for("tests/ui/views/test_views_basic.py::TestViewsBasic::test_save_view[chromium]", err)
    assert named["what"] == "Saving a view never finishes", "a name match wins over a signature match"


def test_a_missing_or_broken_file_labels_nothing_and_stops_nothing(tmp_path):
    """The label must never be why a run cannot archive: no file, a broken file and junk entries all read as no entries."""
    assert kd.load(tmp_path / "absent.yaml") == []
    bad = tmp_path / "bad.yaml"
    bad.write_text("- what: [unclosed", encoding="utf-8")
    kd.load.cache_clear()
    assert kd.load(bad) == []
    junk = tmp_path / "junk.yaml"
    junk.write_text("- tests: [test_x]\n- what: no tests here\n- 3\n", encoding="utf-8")
    kd.load.cache_clear()
    assert kd.load(junk) == [], "an entry with no what, or no tests, is not an entry"


def test_a_signature_that_does_not_compile_drops_its_entry_and_nothing_else(tmp_path):
    """One bad pattern must not take every label with it."""
    f = tmp_path / "d.yaml"
    f.write_text("- what: fine\n  tests: [test_a]\n- what: broken\n  signature: '(unclosed'\n- what: ok\n  signature: 'x+'\n", encoding="utf-8")
    assert [e["what"] for e in kd.load(f)] == ["fine", "ok"]


def test_the_header_explains_the_entry_shape():
    """A team adds entries from the header alone, so it must name every key."""
    text = kd.DEFECTS_FILE.read_text(encoding="utf-8")
    for key in ("since", "what", "tests", "signature"):
        assert f"`{key}`" in text or f"{key}:" in text, key
    assert "register" not in text.lower()
