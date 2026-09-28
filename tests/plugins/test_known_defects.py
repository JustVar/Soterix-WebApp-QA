"""Pins for the known-defect lookup: the label a run page puts on a failure the
register already explains.

The rule that matters most: every name in config/known_defects.yaml must match
exactly one test. A label on the wrong test is worse than no label.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.shared.helpers import known_defects as kd

ROOT = Path(__file__).resolve().parents[2]


def _defined_tests() -> dict[str, list[str]]:
    """Every test function under tests/ui, by name, with the files that define it."""
    out: dict[str, list[str]] = {}
    for f in sorted((ROOT / "tests" / "ui").rglob("test_*.py")):
        for m in re.finditer(r"^\s*(?:async\s+)?def (test_\w+)\(", f.read_text(encoding="utf-8"), re.M):
            out.setdefault(m.group(1), []).append(f.relative_to(ROOT).as_posix())
    return out


def test_every_listed_test_exists_exactly_once():
    """A renamed or deleted test must break this, not silently lose its label;
    a shared name must be written as path::name so the label lands once."""
    defined = _defined_tests()
    entries = kd.load()
    assert entries, "config/known_defects.yaml loaded nothing"
    problems = []
    for entry in entries:
        for name in entry["tests"]:
            bare = name.rsplit("::", 1)[-1]
            files = defined.get(bare, [])
            if "::" in name:
                path = name.split("::", 1)[0]
                if path not in files:
                    problems.append(f"{name}: no such test in {path} (defined in {files or 'nowhere'})")
            elif len(files) != 1:
                problems.append(f"{name}: defined in {len(files)} files {files}; write it as path::name")
    assert not problems, "\n".join(problems)


def test_every_entry_says_what_and_when():
    """`what` in tester language, and a register row or a date, so the page can point at the register."""
    for entry in kd.load():
        assert entry.get("what"), entry
        assert entry.get("row") or entry.get("since"), f"neither row nor since: {entry['what']}"
        assert "NC-" not in str(entry), "no ticket keys here; they go stale (memory: no-tickets-in-code)"


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


def test_the_lookup_answers_with_row_since_and_what_or_none():
    """The record carries row, since and what, and nothing else; an unlisted test gets None."""
    hit = kd.known_defect_for("tests/ui/views/test_views_basic.py::TestViewsBasic::test_save_view[chromium]")
    assert hit
    assert hit["row"] == 56
    assert hit["since"] == "09/12/2026"
    assert "Content Security Policy" in hit["what"]
    assert set(hit) == {"row", "since", "what"}, "the record carries these 3 and nothing else"
    assert kd.known_defect_for("tests/ui/login/test_login.py::test_login_ok[chromium]") is None


def test_a_missing_or_broken_file_labels_nothing_and_stops_nothing(tmp_path):
    """The label must never be why a run cannot archive: no file, a broken file and junk entries all read as no entries."""
    kd.load.cache_clear()
    try:
        assert kd.load(tmp_path / "absent.yaml") == []
        bad = tmp_path / "bad.yaml"
        bad.write_text("- what: [unclosed", encoding="utf-8")
        kd.load.cache_clear()
        assert kd.load(bad) == []
        junk = tmp_path / "junk.yaml"
        junk.write_text("- tests: [test_x]\n- what: no tests here\n- 3\n", encoding="utf-8")
        kd.load.cache_clear()
        assert kd.load(junk) == [], "an entry with no what, or no tests, is not an entry"
    finally:
        kd.load.cache_clear()


def test_a_defect_that_hits_by_error_signature_is_one_entry_not_a_list_of_tests():
    """The tenant's search API failing hit 20 of 25 intermittent failures over 3 days,
    on different tests each night (audit 09/28/2026). Naming tests would chase it
    for ever; the error line names it once. Name first, signature second, and no
    signature match without an error line."""
    err = "AssertionError: Search: no search job was sent within 0 s of the click. A search response was not a clean 200"
    hit = kd.known_defect_for("tests/ui/search/test_search_categories.py::TestSearch::test_event_search[chromium]", err)
    assert hit
    assert hit["row"] == 131
    assert "search API" in hit["what"]
    assert kd.known_defect_for("tests/ui/search/test_search_categories.py::TestSearch::test_event_search[chromium]") is None
    assert kd.known_defect_for("tests/ui/search/x.py::test_y[chromium]", "AssertionError: something else") is None
    named = kd.known_defect_for("tests/ui/views/test_views_basic.py::TestViewsBasic::test_save_view[chromium]", err)
    assert named["row"] == 56, "a name match wins over a signature match"


def test_a_signature_that_does_not_compile_drops_its_entry_and_nothing_else(tmp_path):
    """One bad pattern must not take every label with it."""
    kd.load.cache_clear()
    try:
        f = tmp_path / "d.yaml"
        f.write_text("- what: fine\n  tests: [test_a]\n- what: broken\n  signature: '(unclosed'\n- what: ok\n  signature: 'x+'\n", encoding="utf-8")
        assert [e["what"] for e in kd.load(f)] == ["fine", "ok"]
    finally:
        kd.load.cache_clear()
