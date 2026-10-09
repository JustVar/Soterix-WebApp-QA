"""The smoke set selects tests, and only tests that can run anywhere.

README step 9 and `run.py smoke` run `pytest -m smoke`. Until 10/09/2026
no test carried the marker, so the command a new reader runs second
collected 0 tests and reported nothing. Nobody saw it, because a run that
collects nothing looks like a run that found nothing.

The smoke set is 1 or 2 read-only tests per module: the 6 tests whose
QA Touch case carries the smoke tag, and the test that opens each other
module. A smoke test must give an answer on any machine and any server, so
it carries no marker that can skip it or change the server:

- `livestream`: the stream guard skips it on a Chrome that cannot decode.
- A write marker (conftest.py, WRITE_MARKERS): `allow_write` False skips it,
  and on a shared server it changes data.
- `slow` or `intermittent`: a smoke run is a quick yes or no.

These tests collect the real suite, so a marker set on a class or a module
counts too.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Fewer than this means the set was emptied or most of it was lost.
SMOKE_FLOOR = 12


def _write_markers() -> tuple[str, ...]:
    """WRITE_MARKERS as conftest.py defines it, read without importing it."""
    tree = ast.parse((REPO_ROOT / "conftest.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "WRITE_MARKERS" for t in node.targets):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("conftest.py no longer defines WRITE_MARKERS")


def _collect(expression: str) -> list[str]:
    """The node ids that `pytest -m EXPRESSION` collects under tests/ui."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/ui", "--collect-only",
         "-p", "no:cacheprovider", "-m", expression],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120)
    assert result.returncode in (0, 5), result.stdout[-2000:] + result.stderr[-2000:]
    return [line.strip() for line in result.stdout.splitlines() if "::" in line]


def test_the_smoke_marker_selects_tests():
    """pytest -m smoke collects at least the floor of tests."""
    smoke = _collect("smoke")
    assert len(smoke) >= SMOKE_FLOOR, (
        f"pytest -m smoke collects {len(smoke)} tests, fewer than {SMOKE_FLOOR}. "
        "README step 9 runs this set.")


def test_no_smoke_test_can_skip_or_write():
    """No smoke test carries a marker that can skip it or write data."""
    forbidden = ("livestream", "slow", "intermittent", *_write_markers())
    offenders = _collect(f"smoke and ({' or '.join(forbidden)})")
    assert offenders == [], (
        f"These smoke tests carry one of {forbidden}: {offenders}. "
        "Remove the smoke marker or the other marker.")


def test_the_forbidden_query_finds_a_test_when_one_exists():
    """The forbidden-marker query can find a test, so it can fail.

    A typo in a marker name would make it collect nothing for ever.
    """
    assert _collect("livestream"), "no livestream test was collected"
    assert _collect(" or ".join(_write_markers())), "no write-marked test was collected"
