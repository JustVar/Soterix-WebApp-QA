"""Pins for the search gap: the next search waits only the remainder of the
server's free window after the previous searching test's page closed."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.shared.helpers import search_gap  # noqa: E402


@pytest.fixture
def gap(tmp_path, monkeypatch):
    monkeypatch.setattr(search_gap, "STAMP_DIR", tmp_path)
    monkeypatch.setattr(search_gap, "_ran_this_test", False)
    return tmp_path / ".search_stopped.stamp"


def test_no_previous_search_means_no_wait(gap):
    """With no stamp the next search goes at once."""
    assert search_gap.seconds_until_free() == 0.0
    assert search_gap.wait_for_gap() == 0.0


def test_a_fresh_stop_means_the_full_window(gap):
    """Right after a search test's page closed, the whole window remains."""
    search_gap.mark_ran()
    search_gap.note_stopped()
    assert not search_gap.ran_this_test()
    assert search_gap.GAP_S - 1 < search_gap.seconds_until_free() <= search_gap.GAP_S


def test_an_old_stop_means_no_wait(gap):
    """A stop older than the window needs no wait: the slot has freed."""
    gap.write_text(repr(time.time() - search_gap.GAP_S - 5), encoding="utf-8")
    assert search_gap.seconds_until_free() == 0.0


def test_the_wait_is_only_the_remainder(gap, monkeypatch):
    """A stop 12 s ago waits about 5 s, not the full 17: the window overlaps setup."""
    gap.write_text(repr(time.time() - (search_gap.GAP_S - 5)), encoding="utf-8")
    slept = []
    monkeypatch.setattr(search_gap.time, "sleep", lambda s: slept.append(s))
    # time does not advance under the fake sleep, so cap the loop by
    # making each fake sleep move the stamp back
    calls = {"n": 0}

    def fake_until():
        calls["n"] += 1
        return max(0.0, 5.0 - 0.5 * calls["n"])

    monkeypatch.setattr(search_gap, "seconds_until_free", fake_until)
    waited = search_gap.wait_for_gap()
    assert 4.0 <= waited <= 5.5


def test_a_broken_stamp_does_not_block(gap):
    """An unreadable stamp reads as no previous search."""
    gap.write_text("not a number", encoding="utf-8")
    assert search_gap.seconds_until_free() == 0.0


def test_the_stamp_is_server_wide_not_per_box(gap):
    """The QA server runs one search job for every account, so every box waits on the same stamp."""
    assert search_gap.stamp_path().name == ".search_stopped.stamp"
