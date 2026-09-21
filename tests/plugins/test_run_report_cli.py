"""Pin: `python -m plugins.run_report` does its work. The shim aliased the module and never called main(),
so the command printed nothing, wrote nothing and exited 0 (found 09/21/2026)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "plugins.run_report", *args], cwd=str(REPO_ROOT),
                          capture_output=True, text=True, timeout=120, check=False)


def test_the_command_answers_with_its_usage_and_not_with_silence():
    """No argument: exit 2 and the usage line on stderr."""
    done = _cli()
    assert done.returncode == 2
    assert "usage: python -m plugins.run_report" in done.stderr


def test_a_run_folder_that_is_not_there_is_named():
    """A wrong folder: exit 1 and a line that names it."""
    done = _cli("2001-01-01_00-00-00__no-such-run")
    assert done.returncode == 1
    assert "No run folder at 2001-01-01_00-00-00__no-such-run" in done.stderr
