"""Unit tests for the environment guard in conftest.py.

The skip decisions run against fake items and fake env settings: no
browser, no tenant. Each config/env/ profile (qa, stage, prod, and a file
with no flags) is pinned per marker, and the collection hook is exercised
end to end with a fake pytest config so the wiring cannot drift from the
pure decision.

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
QA = {'allow_write': True}
STAGE = {'allow_write': True}
PROD = {'allow_write': False}
NO_FLAGS = {}  # an env file that says nothing about writes

WRITE_MARKERS = ('admin_users', 'admin_rules', 'admin_sites', 'bookmark', 'sequences')
READ_MARKERS = ('smoke', 'views_myviews', 'events', 'search', 'lpr', 'licenses')

# The keys every config/env/ file carries, so a rename there cannot
# silently switch a guard or a fixture off.
FLAT_KEYS = {'base_url', 'media_host', 'allow_write', 'default_site_id',
             'test_site_name', 'test_camera_name', 'test_chat_user_search',
             'test_chat_user_name', 'camera_capabilities', 'without'}


class FakeItem:
    """What the hook touches on a collected test: its markers, and the
    markers it adds. `keywords` carries a parametrize id too, the way
    pytest's does, so a pin can prove the hook never reads it."""

    def __init__(self, *marks: str, param_id: str | None = None) -> None:
        self._marks = [SimpleNamespace(name=m) for m in marks]
        self.keywords = dict.fromkeys(marks, True)
        if param_id:
            self.keywords[param_id] = True
        self.markers: list = []

    def iter_markers(self):
        return iter(self._marks)

    def add_marker(self, marker) -> None:
        self.markers.append(marker)

    @property
    def skip_reasons(self) -> list[str]:
        return [m.kwargs.get('reason', '') for m in self.markers if m.name == 'skip']


def _config():
    def getoption(name, default=None):
        return default
    return SimpleNamespace(getoption=getoption)


@pytest.fixture(autouse=True)
def _camera_already_chosen(monkeypatch):
    """The session chose its camera at start. The hook must not choose again
    here, against a fake config and a fake env, and ask a server."""
    monkeypatch.setattr(conftest, '_CAMERA_PICK', {'camera': 'x', 'reason': 'chosen at session start'})


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('marker', WRITE_MARKERS + READ_MARKERS)
def test_qa_allows_everything(marker):
    """On qa, every guarded marker runs."""
    assert conftest.env_skip_reason({marker}, QA, 'qa') is None


@pytest.mark.parametrize('marker', WRITE_MARKERS)
def test_prod_refuses_write_markers_by_allow_write(marker):
    """On prod, write markers are skipped and the reason names allow_write."""
    reason = conftest.env_skip_reason({marker}, PROD, 'prod')
    assert reason is not None
    assert 'env prod' in reason
    assert 'allow_write' in reason
    assert f"'{marker}'" in reason


@pytest.mark.parametrize('marker', READ_MARKERS)
def test_prod_still_runs_read_only_tests(marker):
    """On prod, read-only markers still run."""
    assert conftest.env_skip_reason({marker}, PROD, 'prod') is None


@pytest.mark.parametrize('marker', WRITE_MARKERS + READ_MARKERS)
def test_stage_runs_write_and_read_tests(marker):
    """On stage, write and read markers run."""
    assert conftest.env_skip_reason({marker}, STAGE, 'stage') is None


@pytest.mark.parametrize('marker', WRITE_MARKERS)
def test_missing_flags_count_as_false(marker):
    """A profile with no flags refuses the write markers."""
    # Same default as base_config.is_write_allowed.
    assert conftest.env_skip_reason({marker}, NO_FLAGS, 'qa') is not None


def test_unmarked_test_runs_everywhere():
    """An unmarked test runs on every profile."""
    for settings, env in ((QA, 'qa'), (STAGE, 'stage'), (PROD, 'prod'), (NO_FLAGS, 'qa')):
        assert conftest.env_skip_reason(set(), settings, env) is None


# ---------------------------------------------------------------------------
# The hook
# ---------------------------------------------------------------------------

def test_hook_skips_by_env_and_leaves_read_tests_alone(monkeypatch):
    """The collection hook skips guarded tests on prod and leaves read tests alone."""
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', PROD)
    monkeypatch.setenv('ENV', 'prod')
    items = [FakeItem('admin_users'), FakeItem('bookmark'), FakeItem('smoke'), FakeItem()]
    conftest.pytest_collection_modifyitems(_config(), items)
    assert items[0].skip_reasons == [
        "env prod: allow_write is False in config/env/, so tests marked 'admin_users' do not run here"]
    assert items[1].skip_reasons == [
        "env prod: allow_write is False in config/env/, so tests marked 'bookmark' do not run here"]
    assert items[2].markers == []
    assert items[3].markers == []


def test_hook_reads_markers_not_keywords(monkeypatch):
    """A parametrize id that spells a marker name is not a marker. Keywords
    hold both, and a guard that read them once skipped the pins that prove
    it, under CI, for a day."""
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', PROD)
    monkeypatch.setenv('ENV', 'prod')
    item = FakeItem('smoke', param_id='bookmark')
    conftest.pytest_collection_modifyitems(_config(), [item])
    assert item.markers == []
    assert conftest.marker_names(item) == {'smoke'}


def test_hook_names_the_env_alias_the_user_typed(monkeypatch):
    """The skip reason names the ENV alias as the user typed it."""
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', PROD)
    monkeypatch.setenv('ENV', ' Production ')
    item = FakeItem('bookmark')
    conftest.pytest_collection_modifyitems(_config(), [item])
    assert item.skip_reasons[0].startswith('env production:')


# ---------------------------------------------------------------------------
# The marker names exist
# ---------------------------------------------------------------------------

def test_guarded_markers_are_registered_in_pytest_ini():
    """Every guarded marker is registered in pytest.ini."""
    text = (REPO_ROOT / 'pytest.ini').read_text(encoding='utf-8')
    registered = set(re.findall(r'^\s+(\w+)(?:\(\w+\))?:', text, re.MULTILINE))
    missing = [m for m in conftest.WRITE_MARKERS if m not in registered]
    assert missing == []


def test_no_hardware_markers_remain():
    """The hardware suite left with its markers. A `destructive` or
    `mutating` marker in pytest.ini would promise a guard nothing enforces."""
    text = (REPO_ROOT / 'pytest.ini').read_text(encoding='utf-8')
    registered = set(re.findall(r'^\s+(\w+)(?:\(\w+\))?:', text, re.MULTILINE))
    assert not {'destructive', 'mutating'} & registered


# ---------------------------------------------------------------------------
# The env-level `without` map: what the server lacks, by marker
# ---------------------------------------------------------------------------

LACKING = {'allow_write': False,
           'without': {'chats': 'this server has no messaging (measured 2026-09-11)'}}


def test_env_without_refuses_only_its_markers():
    """The env's `without` map skips the marked tests with the stated reason."""
    reason = conftest.env_skip_reason({'chats', 'ui'}, LACKING, 'lab')
    assert reason == ("env lab is without 'chats': this server has no messaging (measured 2026-09-11) "
                      "(config/env/lab.py > without)")
    assert conftest.env_skip_reason({'views_myviews'}, LACKING, 'lab') is None
    assert conftest.env_skip_reason({'chats'}, QA, 'qa') is None


def test_env_with_no_without_map_refuses_nothing():
    """A missing or empty map lets every marked test run."""
    assert conftest.env_skip_reason({'lpr'}, {**QA, 'without': {}}, 'qa') is None
    assert conftest.env_skip_reason({'lpr'}, {**QA, 'without': None}, 'qa') is None


def test_env_flags_speak_before_the_env_without_map():
    """A test refused by allow_write is reported by the flag, not the map."""
    settings = {**LACKING, 'without': {'bookmark': 'x'}}
    assert conftest.env_skip_reason({'bookmark'}, settings, 'lab').startswith(
        'env lab: allow_write is False')


def test_hook_applies_the_env_without_map(monkeypatch):
    """The collection hook reads the env's map and names the env in the skip reason."""
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', LACKING)
    monkeypatch.setenv('ENV', 'lab')
    items = [FakeItem('chats', 'ui'), FakeItem('ui')]
    conftest.pytest_collection_modifyitems(_config(), items)
    assert items[0].skip_reasons == [
        "env lab is without 'chats': this server has no messaging (measured 2026-09-11) "
        "(config/env/lab.py > without)"]
    assert items[1].markers == []


# ---------------------------------------------------------------------------
# The env files have the flat shape the guards and fixtures read
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('name', ['qa', 'stage', 'prod', 'neurosen'])
def test_every_env_file_has_the_flat_shape(name):
    """One shape for every server: the keys, the flag and get_credentials()."""
    import importlib
    mod = importlib.import_module(f'config.env.{name}')
    cfg = mod.config
    assert set(cfg) >= FLAT_KEYS, f'config/env/{name}.py is missing {sorted(FLAT_KEYS - set(cfg))}'
    for gone in ('boxes', 'default_box', 'api_base_url', 'allow_delete'):
        assert gone not in cfg, f'config/env/{name}.py still carries {gone}, which nothing reads'
    assert isinstance(cfg['without'], dict)
    assert isinstance(cfg['camera_capabilities'], dict)
    assert callable(getattr(mod, 'get_credentials', None))


def test_get_credentials_reads_the_one_account_pair(monkeypatch):
    """QA_USER and QA_PASSWORD, and the site is the file's default_site_id."""
    from config.env import qa
    from config.secret import Secret
    monkeypatch.setenv('QA_USER', 'someone@example.test')
    monkeypatch.setenv('QA_PASSWORD', 'not-a-real-password')
    creds = qa.get_credentials()
    assert creds['email'] == 'someone@example.test'
    assert creds['password'] == 'not-a-real-password'
    assert isinstance(creds['password'], Secret)
    assert creds['site_id'] == qa.config['default_site_id']
    monkeypatch.delenv('QA_USER')
    monkeypatch.delenv('QA_PASSWORD')
    assert (qa.get_credentials()['email'], qa.get_credentials()['password']) == ('', '')


def test_prod_is_read_only_by_config():
    """The production file keeps allow_write False, so the write markers skip there."""
    from config.env import prod
    assert prod.config['allow_write'] is False


def test_the_qa_file_names_what_a_run_needs_and_leaves_the_rest_to_the_server():
    """base_url and media_host are named. The site and the camera may be blank,
    and then the run reads them from the server; the file says so."""
    from config.env import qa
    assert qa.config['base_url'].startswith('https://')
    assert qa.config['media_host'].startswith('wss://')
    header = (REPO_ROOT / 'config' / 'env' / 'qa.py').read_text(encoding='utf-8')
    assert 'blank' in header.lower()
    assert 'discovery' in header


def test_neurosen_refuses_to_load_without_its_address(monkeypatch):
    """ENV=neurosen with no NEUROSEN_BASE_URL fails at load, naming the variable."""
    import importlib

    from config import base_config
    monkeypatch.setenv('ENV', 'neurosen')
    monkeypatch.delenv('NEUROSEN_BASE_URL', raising=False)
    importlib.reload(importlib.import_module('config.env.neurosen'))
    with pytest.raises(RuntimeError, match='NEUROSEN_BASE_URL'):
        base_config.load_config()
    monkeypatch.setenv('NEUROSEN_BASE_URL', 'https://neurosen.lab.example/')
    importlib.reload(importlib.import_module('config.env.neurosen'))
    cfg = base_config.load_config()
    assert cfg['base_url'] == 'https://neurosen.lab.example'
    assert cfg['media_host'] is None
    assert cfg['qatouch_project'] == 'P0BK'


def test_an_unknown_env_is_refused_by_name(monkeypatch):
    """A typo in ENV stops the run and lists the valid names."""
    from config import base_config
    monkeypatch.setenv('ENV', 'nowhere')
    with pytest.raises(RuntimeError, match="Unknown ENV 'nowhere'"):
        base_config.load_config()
    assert set(base_config.ENV_ALIAS) == {'qa', 'neurosen', 'stage', 'staging', 'prod', 'production'}
