"""The scenario tests/plugins/test_xdist_crash_recovery.py runs in a
subprocess: nine tests in five groups plus two ungrouped, one of which
kills its worker; a second dies too when XDIST_SCENARIO_TWO_DEATHS is set.
Not collected by the offline suites (no test_ prefix); pytest collects it
only when given its path."""
import os
import time

import pytest


@pytest.mark.xdist_group("a")
def test_a1():
    """Runs before its group-mate dies."""
    time.sleep(0.5)  # why: pacing so both workers are mid-run when one dies; no DOM here


@pytest.mark.xdist_group("a")
def test_a2_dies():
    """Kills its worker; the pin expects one crash failure for it."""
    os._exit(3)


@pytest.mark.xdist_group("b")
def test_b1():
    """Runs on the other worker."""
    time.sleep(0.5)  # why: pacing so both workers are mid-run when one dies; no DOM here


@pytest.mark.xdist_group("b")
def test_b2_dies_when_asked():
    """Kills the second worker only under XDIST_SCENARIO_TWO_DEATHS."""
    if os.environ.get("XDIST_SCENARIO_TWO_DEATHS"):
        os._exit(3)


@pytest.mark.xdist_group("c")
def test_c1():
    """Queued work that must still run after a crash."""
    time.sleep(1)  # why: pacing so both workers are mid-run when one dies; no DOM here


@pytest.mark.xdist_group("d")
def test_d1():
    """Queued work that must still run after a crash."""
    time.sleep(1)  # why: pacing so both workers are mid-run when one dies; no DOM here


@pytest.mark.xdist_group("e")
def test_e1():
    """Queued work that must still run after a crash."""
    time.sleep(1)  # why: pacing so both workers are mid-run when one dies; no DOM here


def test_ungrouped_1():
    """Ungrouped work that must still run after a crash."""
    time.sleep(0.5)  # why: pacing so both workers are mid-run when one dies; no DOM here


def test_ungrouped_2():
    """Ungrouped work that must still run after a crash."""
    time.sleep(0.5)  # why: pacing so both workers are mid-run when one dies; no DOM here
