"""Unit tests for the environment guard in conftest.py.

The skip decisions run against fake items and fake env settings: no
browser, no tenant. Each config/env/ profile (qa, stage, prod, and a
partner file with no flags) is pinned per marker, and the collection hook
is exercised end to end with a fake pytest config so the wiring cannot
drift from the pure decision.

Living under tests/plugins/ to be picked up by the default discovery
without needing a new test root or collection config.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure the repo root is importable so the root conftest resolves the
# same way pytest itself loads it during a real run.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import conftest  # noqa: E402

# The flag values each config/env/ file carries today.
QA = {'allow_write': True, 'allow_delete': True}
STAGE = {'allow_write': True, 'allow_delete': False}
PROD = {'allow_write': False, 'allow_delete': False}
PARTNER = {}  # the *_pat.py files carry no flags at all

DELETE_MARKERS = ('destructive', 'mutating')
WRITE_MARKERS = ('admin_users', 'admin_rules', 'admin_sites', 'bookmark', 'sequences')
READ_MARKERS = ('smoke', 'views_myviews', 'events', 'search', 'lpr', 'licenses')


class FakeItem:
    """The two things the hook touches on a collected test."""

    def __init__(self, *marks: str) -> None:
        self.keywords = dict.fromkeys(marks, True)
        self.markers: list = []

    def add_marker(self, marker) -> None:
        self.markers.append(marker)

    @property
    def skip_reasons(self) -> list[str]:
        return [m.kwargs.get('reason', '') for m in self.markers if m.name == 'skip']


def _config(run_destructive: bool = False):
    return SimpleNamespace(getoption=lambda name: run_destructive if name == '--run-destructive' else None)


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('marker', DELETE_MARKERS + WRITE_MARKERS + READ_MARKERS)
def test_qa_allows_everything(marker):
    assert conftest.env_skip_reason({marker: True}, QA, 'qa') is None


@pytest.mark.parametrize('marker', DELETE_MARKERS)
def test_prod_refuses_delete_markers_by_allow_delete(marker):
    reason = conftest.env_skip_reason({marker: True}, PROD, 'prod')
    assert reason is not None
    assert 'env prod' in reason
    assert 'allow_delete' in reason
    assert f"'{marker}'" in reason


@pytest.mark.parametrize('marker', WRITE_MARKERS)
def test_prod_refuses_write_markers_by_allow_write(marker):
    reason = conftest.env_skip_reason({marker: True}, PROD, 'prod')
    assert reason is not None
    assert 'env prod' in reason
    assert 'allow_write' in reason
    assert f"'{marker}'" in reason


@pytest.mark.parametrize('marker', READ_MARKERS)
def test_prod_still_runs_read_only_tests(marker):
    assert conftest.env_skip_reason({marker: True}, PROD, 'prod') is None


@pytest.mark.parametrize('marker', DELETE_MARKERS)
def test_stage_refuses_delete_markers(marker):
    reason = conftest.env_skip_reason({marker: True}, STAGE, 'stage')
    assert reason is not None
    assert 'allow_delete' in reason


@pytest.mark.parametrize('marker', WRITE_MARKERS + READ_MARKERS)
def test_stage_runs_write_and_read_tests(marker):
    assert conftest.env_skip_reason({marker: True}, STAGE, 'stage') is None


@pytest.mark.parametrize('marker', DELETE_MARKERS + WRITE_MARKERS)
def test_missing_flags_count_as_false(marker):
    # Same default as base_config.is_write_allowed / is_delete_allowed.
    assert conftest.env_skip_reason({marker: True}, PARTNER, 'qa') is not None


def test_unmarked_test_runs_everywhere():
    for settings, env in ((QA, 'qa'), (STAGE, 'stage'), (PROD, 'prod'), (PARTNER, 'qa')):
        assert conftest.env_skip_reason({}, settings, env) is None


def test_delete_flag_wins_when_a_test_carries_both_kinds():
    reason = conftest.env_skip_reason({'destructive': True, 'admin_sites': True}, PROD, 'prod')
    assert 'allow_delete' in reason


# ---------------------------------------------------------------------------
# The hook
# ---------------------------------------------------------------------------

def test_hook_skips_by_env_and_leaves_read_tests_alone(monkeypatch):
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', PROD)
    monkeypatch.setenv('ENV', 'prod')
    items = [FakeItem('admin_users'), FakeItem('mutating'), FakeItem('smoke'), FakeItem()]
    conftest.pytest_collection_modifyitems(_config(), items)
    assert items[0].skip_reasons == [
        "env prod: allow_write is False in config/env/, so tests marked 'admin_users' do not run here"]
    assert items[1].skip_reasons == [
        "env prod: allow_delete is False in config/env/, so tests marked 'mutating' do not run here"]
    assert items[2].markers == []
    assert items[3].markers == []


def test_hook_run_destructive_does_not_lift_the_env_guard(monkeypatch):
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', PROD)
    monkeypatch.setenv('ENV', 'prod')
    item = FakeItem('destructive')
    conftest.pytest_collection_modifyitems(_config(run_destructive=True), [item])
    assert len(item.skip_reasons) == 1
    assert 'allow_delete' in item.skip_reasons[0]


def test_hook_keeps_the_destructive_opt_in_on_qa(monkeypatch):
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', QA)
    monkeypatch.setenv('ENV', 'qa')
    item = FakeItem('destructive')
    conftest.pytest_collection_modifyitems(_config(), [item])
    assert item.skip_reasons == [
        'destructive: disrupts real hardware. Pass --run-destructive to run it.']
    item = FakeItem('destructive')
    conftest.pytest_collection_modifyitems(_config(run_destructive=True), [item])
    assert item.markers == []


def test_hook_names_the_env_alias_the_user_typed(monkeypatch):
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', PROD)
    monkeypatch.setenv('ENV', ' Production ')
    item = FakeItem('bookmark')
    conftest.pytest_collection_modifyitems(_config(), [item])
    assert item.skip_reasons[0].startswith('env production:')


# ---------------------------------------------------------------------------
# The marker names exist
# ---------------------------------------------------------------------------

def test_guarded_markers_are_registered_in_pytest_ini():
    text = (REPO_ROOT / 'pytest.ini').read_text(encoding='utf-8')
    registered = set(re.findall(r'^\s+(\w+)(?:\(\w+\))?:', text, re.MULTILINE))
    missing = [m for m in conftest.DELETE_MARKERS + conftest.WRITE_MARKERS if m not in registered]
    assert missing == []
