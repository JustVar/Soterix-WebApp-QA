"""Pins for register row 63: the three QA Touch tool parameters callers passed
and the bodies never read are gone, so a caller cannot pass a knob that
does nothing. scroll_to_find_case's max_attempts and sync_case's title were
dead; cmd_sync_steps's csv_file was worse - the dispatcher forwarded --csv
and the body ignored it, so a CSV given to sync-steps silently did nothing.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import (  # noqa: E402
    qa_post_import_split_and_position as split_tool,
    qatouch_browser as browser,
)


def _params(fn) -> list[str]:
    return list(inspect.signature(fn).parameters)


def test_scroll_to_find_case_has_no_dead_attempts_knob():
    """The scroll and pagination loops carry their own caps; a max_attempts nobody read is gone."""
    assert _params(browser.scroll_to_find_case) == ["page", "title"]


def test_cmd_sync_steps_takes_no_csv():
    """sync-steps reads the step JSON files; a csv_file it ignored is gone from the signature."""
    assert "csv_file" not in _params(browser.cmd_sync_steps)
    assert "step_dir" in _params(browser.cmd_sync_steps)


def test_sync_case_takes_no_title():
    """The caller prints the title itself; the body never read it."""
    assert "title" not in _params(split_tool.sync_case)


def test_no_row_63_noqa_remains():
    """The three noqa markers that named the row are gone with the parameters."""
    for path in ("tools/qatouch_browser.py", "tools/qa_post_import_split_and_position.py"):
        text = (REPO_ROOT / path).read_text(encoding="utf-8")
        assert "noqa: ARG001 - " not in text, f"{path} still carries a row-63 noqa"


def test_sync_steps_refuses_a_csv_instead_of_ignoring_it(monkeypatch, capsys):
    """A --csv on sync-steps used to be forwarded and silently dropped; now the command
    says its input is the step JSON files and exits 2 before doing anything."""
    monkeypatch.setattr(sys, "argv", ["qatouch_browser.py", "sync-steps", "--csv", "cases.csv", "--dry-run"])
    with pytest.raises(SystemExit) as exc:
        browser.main()
    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "takes no --csv" in out
    assert "--step-dir" in out
