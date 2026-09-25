"""Pins for tools/announce_run.py: the Slack line a run ends with, and the line
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


def test_the_line_reads_like_the_run_pages_verdict(tmp_path):
    """Counts, the known-defect split, the camera and a link to the served page, in one breath."""
    tests = [_t("a", "passed"), _t("b", "failed", {"row": 56, "what": "CSP"}),
             _t("c", "failed", {"row": 83, "what": "bookmarks"}), _t("d", "failed"), _t("e", "skipped")]
    _run(tmp_path, "2026-09-25_09-40-01__tests-ui", "us", "spartan1", tests)
    text, names = ar.compose(tmp_path, "2026-09-25", [], set(), "11:00")
    assert names == ["2026-09-25_09-40-01__tests-ui"]
    assert text == ("*us* 1 passed · *3 failed* (2 known defects, *1 to look at*) · 1 skipped · camera Axis P3247-LV · "
                    "<http://10.2.0.2/qa-runs/2026-09-25_09-40-01__tests-ui/run.html|run page>")


def test_when_every_failure_is_known_the_line_says_nothing_new(tmp_path):
    """Errors count as failures here, the way the run page's verdict counts them."""
    tests = [_t("b", "failed", {"row": 56, "what": "CSP"}), _t("c", "error", {"row": 56, "what": "CSP"})]
    _run(tmp_path, "2026-09-25_09-00-05__tests-ui", "india", "spartan1", tests, camera=None)
    text, _ = ar.compose(tmp_path, "2026-09-25", [], set(), "11:00")
    assert "*india* 0 passed · *2 failed* (2 known defects, nothing new)" in text
    assert "camera" not in text, "no camera in the record, no camera in the line"


def test_a_record_without_the_known_defect_field_makes_no_claim_about_it(tmp_path):
    """A run archived before v0.36.0 has no known_defect field; '0 known defects' would be a lie."""
    tests = [_t("b", "failed", with_field=False), _t("a", "passed", with_field=False)]
    _run(tmp_path, "2026-09-25_09-40-01__tests-ui", "us", "spartan1", tests)
    text, _ = ar.compose(tmp_path, "2026-09-25", [], set(), "11:00")
    assert "*1 failed* ·" in text
    assert "known" not in text


def test_c2c_and_the_windows_machine_are_named_for_what_they_are(tmp_path):
    """The archive holds 4 kinds of run a day; the line says which without the reader decoding a folder name."""
    _run(tmp_path, "2026-09-25_10-09-11__tests-c2c", "us", "spartan1", [_t("a", "passed")])
    _run(tmp_path, "2026-09-25_08-50-41__tests-ui-livestream", "us", "Spartan20", [_t("a", "passed")])
    text, _ = ar.compose(tmp_path, "2026-09-25", [], set(), "11:00")
    assert "*c2c cameras* 1 passed · 0 failed · 0 skipped · <" in text, "no camera on the c2c line: the box default means nothing there"
    assert "*us, from spartan20* 1 passed" in text


def test_the_expected_runs_that_have_no_folder_today_are_named_as_missing(tmp_path):
    """The line for a run that never happened, which nothing else produces."""
    _run(tmp_path, "2026-09-25_09-00-05__tests-ui", "india", "spartan1", [_t("a", "passed")])
    _run(tmp_path, "2026-09-24_09-40-01__tests-ui", "us", "spartan1", [_t("a", "passed")])  # yesterday's does not count
    text, names = ar.compose(tmp_path, "2026-09-25", ["india", "us", "c2c", "spartan20"], set(), "11:00")
    assert "*Missing today:* us, c2c, spartan20 — no run folder for 2026-09-25 in the archive at 11:00 UTC" in text
    assert "missing:2026-09-25" in names
    # once said, not said again that day
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
