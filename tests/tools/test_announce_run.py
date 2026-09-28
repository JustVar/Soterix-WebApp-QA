"""Pins for tools/announce_run.py: the Slack message a day ends with, and the line
for a run that should have happened and did not.

The rule that must never break: the webhook is never printed, not on success,
not on failure, not in a dry run.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools import announce_run as ar

HOOK = "https://hooks.slack.com/services/T000/B000/secret-part-of-the-url"
LINK = "<http://10.2.0.2/qa-runs/{}/run.html|Run page>"


def _run(archive: Path, name: str, box: str, host: str, tests: list[dict], camera: str | None = "Axis P3247-LV"):
    folder = archive / name
    folder.mkdir(parents=True)
    counts = {k: sum(1 for t in tests if t["outcome"] == o)
              for k, o in (("passed", "passed"), ("failed", "failed"), ("errors", "error"), ("skipped", "skipped"))}
    (folder / "summary.json").write_text(json.dumps({
        "counts": counts, "tests": tests,
        "provenance": {"box": box, "host": host, "camera": camera}}), encoding="utf-8")
    return folder


def _t(name, outcome, known=None, with_field=True):
    t = {"nodeid": f"tests/ui/x.py::{name}[chromium]", "outcome": outcome}
    if with_field:
        t["known_defect"] = known
    return t


def test_the_line_leads_with_the_number_that_needs_a_person(tmp_path):
    """"N to look at" first and bold, then the known defects, the counts, the camera, the link."""
    tests = [_t("a", "passed"), _t("b", "failed", {"row": 56, "what": "CSP"}),
             _t("c", "failed", {"row": 83, "what": "bookmarks"}), _t("d", "failed"), _t("e", "skipped")]
    _run(tmp_path, "2026-09-25_09-40-01__tests-ui", "us", "spartan1", tests)
    text, names = ar.compose(tmp_path, "2026-09-25", [], set(), "11:00")
    assert names == ["2026-09-25_09-40-01__tests-ui"]
    assert text.split("\n") == [
        "*QA runs — Fri 25 Sep 2026*",
        ":red_circle: *US* — *1 to look at* · 2 known · 1 passed · 1 skipped · Axis P3247-LV · "
        + LINK.format("2026-09-25_09-40-01__tests-ui"),
    ]


def test_a_run_with_nothing_new_is_green_and_says_so(tmp_path):
    """Every failure known, or no failure at all: a green mark and no number to chase."""
    _run(tmp_path, "2026-09-25_09-00-05__tests-ui", "india", "spartan1",
         [_t("b", "failed", {"row": 56, "what": "CSP"}), _t("c", "error", {"row": 56, "what": "CSP"})], camera=None)
    _run(tmp_path, "2026-09-25_09-40-01__tests-ui", "us", "spartan1", [_t("a", "passed")])
    text, _ = ar.compose(tmp_path, "2026-09-25", [], set(), "11:00")
    lines = text.split("\n")[1:]
    assert lines[0].startswith(":large_green_circle: *India* — Nothing to look at · 2 known · 0 passed · 0 skipped · <")
    assert lines[1].startswith(":large_green_circle: *US* — Nothing to look at · 1 passed · 0 skipped · Axis")
    assert "camera" not in text
    assert "0 known" not in text


def test_a_record_without_the_known_defect_field_says_failed_not_to_look_at(tmp_path):
    """A run archived before v0.36.0 has no known_defect field; 'to look at' would claim a split nobody measured."""
    _run(tmp_path, "2026-09-25_09-40-01__tests-ui", "us", "spartan1",
         [_t("b", "failed", with_field=False), _t("a", "passed", with_field=False)])
    text, _ = ar.compose(tmp_path, "2026-09-25", [], set(), "11:00")
    assert ":red_circle: *US* — *1 failed* · 1 passed · 0 skipped ·" in text
    assert "known" not in text
    assert "to look at" not in text


def test_the_lines_are_ordered_and_the_windows_machine_names_its_box(tmp_path):
    """india, us, c2c, then the Windows machine's legs, each named by the box it drove:
    "us, from spartan20" hid an india leg behind a us label for 3 days (09/26-09/28/2026)."""
    _run(tmp_path, "2026-09-25_02-30-09__tests-ui-livestream", "india", "Spartan20", [_t("a", "passed")], camera="Thermal-14")
    _run(tmp_path, "2026-09-25_03-21-50__tests-ui-livestream", "us", "Spartan20", [_t("a", "passed")])
    _run(tmp_path, "2026-09-25_10-09-11__tests-c2c", "india", "spartan1", [_t("a", "passed")], camera="Thermal-14")
    _run(tmp_path, "2026-09-25_09-40-01__tests-ui", "us", "spartan1", [_t("a", "passed")])
    _run(tmp_path, "2026-09-25_09-00-05__tests-ui", "india", "spartan1", [_t("a", "passed")], camera="Thermal-14")
    text, _ = ar.compose(tmp_path, "2026-09-25", [], set(), "11:00")
    labels = [line.split("*")[1] for line in text.split("\n")[1:]]
    assert labels == ["India", "US", "C2C", "India · Spartan20", "US · Spartan20"]
    c2c = next(line for line in text.split("\n") if "*C2C*" in line)
    assert "Thermal-14" not in c2c, "no camera on the c2c line: the box default means nothing there"


def test_the_expected_runs_that_have_no_folder_today_are_named_as_missing(tmp_path):
    """The line for a run that never happened, which nothing else produces."""
    _run(tmp_path, "2026-09-25_09-00-05__tests-ui", "india", "spartan1", [_t("a", "passed")])
    _run(tmp_path, "2026-09-24_09-40-01__tests-ui", "us", "spartan1", [_t("a", "passed")])  # yesterday's does not count
    text, names = ar.compose(tmp_path, "2026-09-25", ["india", "us", "c2c", "spartan20"], set(), "11:00")
    assert ":warning: *Missing today:* US, C2C, Spartan20 — no run folder for 2026-09-25 in the archive at 11:00 UTC" in text
    assert "missing:2026-09-25" in names
    # once said, not said again that day, and nothing else to say means no header either
    text, names = ar.compose(tmp_path, "2026-09-25", ["us"], {"2026-09-25_09-00-05__tests-ui", "missing:2026-09-25"}, "12:00")
    assert text == ""
    assert names == []
    # all present: no such line
    _run(tmp_path, "2026-09-25_09-40-01__tests-ui", "us", "spartan1", [_t("a", "passed")])
    _run(tmp_path, "2026-09-25_10-09-11__tests-c2c", "us", "spartan1", [_t("a", "passed")])
    _run(tmp_path, "2026-09-25_07-30-00__tests-ui-livestream", "us", "Spartan20", [_t("a", "passed")])
    text, _ = ar.compose(tmp_path, "2026-09-25", ["india", "us", "c2c", "spartan20"], set(), "11:00")
    assert "Missing" not in text


def test_an_announced_run_is_not_announced_twice_and_a_dry_run_records_nothing(tmp_path, capsys):
    """The nightly announces at its end and the 11:00 sweep catches what it missed; neither may repeat the other."""
    _run(tmp_path, "2026-09-25_09-40-01__tests-ui", "us", "spartan1", [_t("a", "passed")])
    state = tmp_path / "announced.json"
    posted = []

    def sender(url, text):
        posted.append(text)
        return 200

    base = ["--archive", str(tmp_path), "--state", str(state), "--date", "2026-09-25"]
    assert ar.main([*base, "--dry-run"], environ={ar.WEBHOOK_ENV: HOOK}, sender=sender) == 0
    assert posted == [], "a dry run posts nothing"
    assert not state.exists(), "and records nothing"
    assert ar.main(base, environ={ar.WEBHOOK_ENV: HOOK}, sender=sender) == 0
    assert len(posted) == 1
    assert json.loads(state.read_text()) == ["2026-09-25_09-40-01__tests-ui"]
    assert ar.main(base, environ={ar.WEBHOOK_ENV: HOOK}, sender=sender) == 0
    assert len(posted) == 1, "already announced: nothing posted"
    assert "nothing new" in capsys.readouterr().out


def test_no_webhook_is_exit_2_a_refused_post_is_exit_1_and_neither_prints_the_url(tmp_path, capsys):
    """The nightly ignores both exit codes; the sweep repeats a refused post because nothing was recorded."""
    _run(tmp_path, "2026-09-25_09-40-01__tests-ui", "us", "spartan1", [_t("a", "passed")])
    state = tmp_path / "announced.json"
    base = ["--archive", str(tmp_path), "--state", str(state), "--date", "2026-09-25"]
    assert ar.main(base, environ={}, sender=lambda u, t: 200, env_file=tmp_path / "no.env") == 2
    out = capsys.readouterr().out
    assert ar.WEBHOOK_ENV in out
    assert "nothing posted" in out
    assert ar.main(base, environ={ar.WEBHOOK_ENV: HOOK}, sender=lambda u, t: 403) == 1
    out = capsys.readouterr().out
    assert "HTTP 403" in out
    assert "try again" in out
    assert not state.exists(), "a failed post records nothing, so the sweep repeats it"
    assert HOOK not in out
    assert "secret-part" not in out


@pytest.mark.parametrize("bad", ["not json", "[1, 2", ""])
def test_a_broken_state_file_is_a_fresh_start_not_a_crash(tmp_path, bad):
    """A fresh start repeats at most one day's lines, which beats a sweep that never runs again."""
    state = tmp_path / "announced.json"
    state.write_text(bad, encoding="utf-8")
    assert ar.load_state(state) == set()
    assert ar.load_state(None) == set()
