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
    """On qa, every guarded marker runs."""
    assert conftest.env_skip_reason({marker: True}, QA, 'qa') is None


@pytest.mark.parametrize('marker', DELETE_MARKERS)
def test_prod_refuses_delete_markers_by_allow_delete(marker):
    """On prod, delete markers are skipped and the reason names allow_delete."""
    reason = conftest.env_skip_reason({marker: True}, PROD, 'prod')
    assert reason is not None
    assert 'env prod' in reason
    assert 'allow_delete' in reason
    assert f"'{marker}'" in reason


@pytest.mark.parametrize('marker', WRITE_MARKERS)
def test_prod_refuses_write_markers_by_allow_write(marker):
    """On prod, write markers are skipped and the reason names allow_write."""
    reason = conftest.env_skip_reason({marker: True}, PROD, 'prod')
    assert reason is not None
    assert 'env prod' in reason
    assert 'allow_write' in reason
    assert f"'{marker}'" in reason


@pytest.mark.parametrize('marker', READ_MARKERS)
def test_prod_still_runs_read_only_tests(marker):
    """On prod, read-only markers still run."""
    assert conftest.env_skip_reason({marker: True}, PROD, 'prod') is None


@pytest.mark.parametrize('marker', DELETE_MARKERS)
def test_stage_refuses_delete_markers(marker):
    """On stage, delete markers are skipped by allow_delete."""
    reason = conftest.env_skip_reason({marker: True}, STAGE, 'stage')
    assert reason is not None
    assert 'allow_delete' in reason


@pytest.mark.parametrize('marker', WRITE_MARKERS + READ_MARKERS)
def test_stage_runs_write_and_read_tests(marker):
    """On stage, write and read markers run."""
    assert conftest.env_skip_reason({marker: True}, STAGE, 'stage') is None


@pytest.mark.parametrize('marker', DELETE_MARKERS + WRITE_MARKERS)
def test_missing_flags_count_as_false(marker):
    """A profile with no flags refuses write and delete markers."""
    # Same default as base_config.is_write_allowed / is_delete_allowed.
    assert conftest.env_skip_reason({marker: True}, PARTNER, 'qa') is not None


def test_unmarked_test_runs_everywhere():
    """An unmarked test runs on every profile."""
    for settings, env in ((QA, 'qa'), (STAGE, 'stage'), (PROD, 'prod'), (PARTNER, 'qa')):
        assert conftest.env_skip_reason({}, settings, env) is None


def test_delete_flag_wins_when_a_test_carries_both_kinds():
    """A test with both marker kinds is refused by allow_delete first."""
    reason = conftest.env_skip_reason({'destructive': True, 'admin_sites': True}, PROD, 'prod')
    assert 'allow_delete' in reason


# ---------------------------------------------------------------------------
# The hook
# ---------------------------------------------------------------------------

def test_hook_skips_by_env_and_leaves_read_tests_alone(monkeypatch):
    """The collection hook skips guarded tests on prod and leaves read tests alone."""
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
    """--run-destructive does not override the env's allow_delete refusal."""
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', PROD)
    monkeypatch.setenv('ENV', 'prod')
    item = FakeItem('destructive')
    conftest.pytest_collection_modifyitems(_config(run_destructive=True), [item])
    assert len(item.skip_reasons) == 1
    assert 'allow_delete' in item.skip_reasons[0]


def test_hook_keeps_the_destructive_opt_in_on_qa(monkeypatch):
    """On qa, destructive tests still need --run-destructive to run."""
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
    """The skip reason names the ENV alias as the user typed it."""
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', PROD)
    monkeypatch.setenv('ENV', ' Production ')
    item = FakeItem('bookmark')
    conftest.pytest_collection_modifyitems(_config(), [item])
    assert item.skip_reasons[0].startswith('env production:')


# ---------------------------------------------------------------------------
# The box guard: what a tenant does not have, by marker
# ---------------------------------------------------------------------------

US_WITHOUT_LPR = {'without': {'lpr': 'Spartan0 has no LPR cameras (Justin, 09/08/2026)'}}
BOXES = {**QA, 'boxes': {'us': US_WITHOUT_LPR, 'india': {}}}


def test_box_without_refuses_only_its_markers():
    """A box's `without` map refuses tests carrying those markers, with the stated reason."""
    reason = conftest.box_skip_reason({'lpr': True, 'admin': True}, US_WITHOUT_LPR, 'us')
    assert reason == ("box us is without 'lpr': Spartan0 has no LPR cameras (Justin, 09/08/2026) "
                      "(config/env/ > boxes > us > without)")
    assert conftest.box_skip_reason({'admin': True, 'ui': True}, US_WITHOUT_LPR, 'us') is None
    assert conftest.box_skip_reason({}, US_WITHOUT_LPR, 'us') is None


def test_box_with_no_without_map_refuses_nothing():
    """A box entry without the map, or no entry at all, lets every test run."""
    assert conftest.box_skip_reason({'lpr': True}, {}, 'india') is None
    assert conftest.box_skip_reason({'lpr': True}, None, 'india') is None
    assert conftest.active_box_settings(QA, 'us') == {}
    assert conftest.active_box_settings(BOXES, 'us') == US_WITHOUT_LPR


def test_hook_skips_by_box_and_lets_the_other_box_run(monkeypatch):
    """With BOX=us the hook skips lpr tests naming the box; with BOX=india it does not."""
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', BOXES)
    monkeypatch.setenv('ENV', 'qa')
    monkeypatch.setenv('BOX', 'us')
    items = [FakeItem('lpr', 'admin', 'ui'), FakeItem('admin', 'ui')]
    conftest.pytest_collection_modifyitems(_config(), items)
    assert items[0].skip_reasons == [
        "box us is without 'lpr': Spartan0 has no LPR cameras (Justin, 09/08/2026) "
        "(config/env/ > boxes > us > without)"]
    assert items[1].markers == []
    monkeypatch.setenv('BOX', 'india')
    item = FakeItem('lpr', 'admin', 'ui')
    conftest.pytest_collection_modifyitems(_config(), [item])
    assert item.markers == []


def test_env_guard_speaks_before_the_box_guard(monkeypatch):
    """A test refused by the env is reported by the env, not the box."""
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', {**PROD, 'boxes': {'us': {'without': {'admin_users': 'x'}}}})
    monkeypatch.setenv('ENV', 'prod')
    monkeypatch.setenv('BOX', 'us')
    item = FakeItem('admin_users')
    conftest.pytest_collection_modifyitems(_config(), [item])
    assert len(item.skip_reasons) == 1
    assert item.skip_reasons[0].startswith('env prod:')


# ---------------------------------------------------------------------------
# The marker names exist
# ---------------------------------------------------------------------------

def test_guarded_markers_are_registered_in_pytest_ini():
    """Every guarded marker is registered in pytest.ini."""
    text = (REPO_ROOT / 'pytest.ini').read_text(encoding='utf-8')
    registered = set(re.findall(r'^\s+(\w+)(?:\(\w+\))?:', text, re.MULTILINE))
    missing = [m for m in conftest.DELETE_MARKERS + conftest.WRITE_MARKERS if m not in registered]
    assert missing == []


# ---------------------------------------------------------------------------
# The env-level `without` map (config/env/neurosen.py)
# ---------------------------------------------------------------------------

NEUROSEN = {'allow_write': True, 'allow_delete': False,
            'without': {'chats': 'Neurosen has no messaging (measured 2026-09-11)'}}


def test_env_without_refuses_only_its_markers():
    """An env's own `without` map skips the marked tests with the stated reason."""
    reason = conftest.env_skip_reason({'chats': True, 'ui': True}, NEUROSEN, 'neurosen')
    assert reason == ("env neurosen is without 'chats': Neurosen has no messaging (measured 2026-09-11) "
                      "(config/env/neurosen.py > without)")
    assert conftest.env_skip_reason({'views_myviews': True}, NEUROSEN, 'neurosen') is None
    assert conftest.env_skip_reason({'chats': True}, QA, 'qa') is None


def test_env_flags_speak_before_the_env_without_map():
    """A test refused by allow_delete is reported by the flag, not the map."""
    settings = {**NEUROSEN, 'without': {'mutating': 'x'}}
    assert conftest.env_skip_reason({'mutating': True}, settings, 'neurosen').startswith(
        'env neurosen: allow_delete is False')


def test_hook_applies_the_env_without_map(monkeypatch):
    """The collection hook reads the env's map and names the env in the skip reason."""
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', {**NEUROSEN, 'boxes': {'lab': {}}, 'default_box': 'lab'})
    monkeypatch.setenv('ENV', 'neurosen')
    monkeypatch.setenv('BOX', 'lab')
    items = [FakeItem('chats', 'ui'), FakeItem('ui')]
    conftest.pytest_collection_modifyitems(_config(), items)
    assert items[0].skip_reasons == [
        "env neurosen is without 'chats': Neurosen has no messaging (measured 2026-09-11) "
        "(config/env/neurosen.py > without)"]
    assert items[1].markers == []


def test_neurosen_env_file_has_the_shape_the_guards_read():
    """The env file's keys, so a rename there cannot silently switch a guard off."""
    import importlib
    mod = importlib.import_module('config.env.neurosen')
    cfg = mod.config
    assert cfg['qatouch_project'] == 'P0BK'
    assert isinstance(cfg['without'], dict)
    assert cfg['base_url_env'] == 'NEUROSEN_BASE_URL'
    assert set(cfg['boxes']) == {'lab'}
    assert cfg['default_box'] == 'lab'
    assert cfg['boxes']['lab']['email_env'] == 'NEUROSEN_USER'
    assert (cfg['allow_write'], cfg['allow_delete']) == (True, False)


def test_neurosen_refuses_to_load_without_its_address(monkeypatch):
    """ENV=neurosen with no NEUROSEN_BASE_URL fails at load, naming the variable."""
    import importlib

    from config import base_config
    monkeypatch.setenv('ENV', 'neurosen')
    monkeypatch.delenv('NEUROSEN_BASE_URL', raising=False)
    monkeypatch.delenv('BOX', raising=False)
    importlib.reload(importlib.import_module('config.env.neurosen'))
    with pytest.raises(RuntimeError, match='NEUROSEN_BASE_URL'):
        base_config.load_config()
    monkeypatch.setenv('NEUROSEN_BASE_URL', 'https://neurosen.lab.example/')
    importlib.reload(importlib.import_module('config.env.neurosen'))
    cfg = base_config.load_config()
    assert cfg['base_url'] == 'https://neurosen.lab.example'
    assert cfg['api_base_url'] == 'https://neurosen.lab.example/v-apiserver'
