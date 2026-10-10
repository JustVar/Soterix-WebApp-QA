"""Pins for the session preflight (tests/shared/helpers/preflight.py, register
row 93): one named line and no test run when the tenant is down or the
account is refused; never in a session that cannot reach a tenant."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import conftest  # noqa: E402
from tests.shared.api.client import ApiError, LoginConfigError  # noqa: E402
from tests.shared.helpers import preflight as pf  # noqa: E402

URL = "https://tenant.example.test"


def _config(args, worker=False, **options):
    ns = SimpleNamespace(args=args, getoption=lambda name, default=False: options.get(name, default))
    if worker:
        ns.workerinput = {}
    return ns


def test_only_sessions_that_can_reach_a_tenant_get_a_preflight():
    """The pins, collect-only, setup-plan and xdist workers never ask."""
    assert pf.targets_a_tenant([]) is True
    assert pf.targets_a_tenant(["tests/ui"]) is True
    assert pf.targets_a_tenant(["tests/ui/maps/test_maps.py::TestMaps::test_x"]) is True
    assert pf.targets_a_tenant(["tests/plugins", "tests/ui/login"]) is True
    assert pf.targets_a_tenant(["tests/plugins", "tests/tools", "tests/helpers"]) is False
    assert pf.targets_a_tenant(["tests\\helpers"]) is False
    # absolute paths too: a pin launched by absolute path once read as a tenant target
    assert pf.targets_a_tenant(["C:/work/repo/tests/plugins/xdist_crash_scenario.py"]) is False
    assert pf.targets_a_tenant(["/data/qa/repo/tests/tools/test_x.py::test_x"]) is False
    assert pf.targets_a_tenant(["/data/qa/repo/tests/ui/maps"]) is True
    assert pf.skip_reason(_config(["tests/ui"]), {}) is None
    assert pf.skip_reason(_config(["tests/ui"]), {"PREFLIGHT": "off"}) == "PREFLIGHT=off"
    assert "worker" in pf.skip_reason(_config(["tests/ui"], worker=True), {})
    assert "collectonly" in pf.skip_reason(_config(["tests/ui"], collectonly=True), {})
    assert "setupplan" in pf.skip_reason(_config([], setupplan=True), {})
    # the listing commands start a session and run no test
    for option in ("showfixtures", "show_fixtures_per_test", "cacheshow"):
        assert option in pf.skip_reason(_config(["tests/ui"], **{option: True}), {})
    assert "no tenant test" in pf.skip_reason(_config(["tests/plugins"]), {})


def test_a_sign_in_that_works_says_nothing():
    """A token back means no line, and the run goes on."""
    assert pf.check(URL, "someone@example.test", "pw", login=lambda *a: "JSESSION") is None


def test_each_failure_class_gets_its_own_named_line():
    """Down, refused, no token, no account: four causes, four lines, all saying no test ran."""
    def down(*a):
        raise ConnectionError("HTTPSConnectionPool(host=x): Max retries exceeded (NameResolutionError)")

    def refused(*a):
        raise ApiError(3001, 401, "Invalid credentials!", "/REST/central/user/login")

    def no_token(*a):
        raise IndexError("list index out of range")

    line = pf.check(URL, "u@example.test", "pw", login=down)
    assert line.startswith("PREFLIGHT: tenant.example.test did not answer (ConnectionError:")
    line = pf.check(URL, "u@example.test", "pw", login=refused)
    assert "the tenant refused u@example.test" in line
    assert "Invalid credentials!" in line
    assert "nothing retried the login" in line
    assert "without a session token (IndexError)" in pf.check(URL, "u@example.test", "pw", login=no_token)
    assert "empty session token" in pf.check(URL, "u@example.test", "pw", login=lambda *a: "")
    empty = pf.check(URL, "", "", login=lambda *a: pytest.fail("asked"))
    assert "no account to sign in with" in empty
    assert "QA_USER or QA_PASSWORD" in empty
    for text in (line, empty):
        assert "No test ran" in text


def test_a_missing_login_setting_is_named_as_itself():
    """A blank login label reads as a setting to fill, not as a refused account."""
    def no_label(*a):
        raise LoginConfigError("LOGIN_USERNAME_LABEL is empty in .env, and the login needs it")

    line = pf.check(URL, "u@example.test", "pw", login=no_label)
    assert line == "PREFLIGHT: LOGIN_USERNAME_LABEL is empty in .env, and the login needs it. No test ran."


def test_the_password_never_appears_in_a_refusal_line():
    """The refusal quotes the tenant, never the password it was given."""
    def refused(base, account, password):
        raise ApiError(3001, 401, f"bad {password}"[:4], "/login")
    assert "hunter-two" not in pf.check(URL, "u@example.test", "hunter-two", login=refused)


def test_the_hook_exits_with_the_line_and_its_own_code(monkeypatch):
    """A refusal ends the session before any test, with exit code 7; a skip reason or a clean check runs on."""
    monkeypatch.setattr(conftest, "_session_account", lambda: ("u@example.test", "pw"))
    monkeypatch.setattr(conftest, "ENV_SETTINGS", {"base_url": URL})
    monkeypatch.setattr(pf, "skip_reason", lambda config, environ=None: None)
    monkeypatch.setattr(pf, "check", lambda *a, **k: "PREFLIGHT: down. No test ran.")
    with pytest.raises(pytest.exit.Exception) as exc:
        conftest.pytest_sessionstart(SimpleNamespace(config=_config(["tests/ui"])))
    assert exc.value.returncode == pf.EXIT_CODE == 7
    assert "PREFLIGHT: down" in str(exc.value.msg)
    monkeypatch.setattr(pf, "check", lambda *a, **k: None)
    conftest.pytest_sessionstart(SimpleNamespace(config=_config(["tests/ui"])))
    monkeypatch.setattr(pf, "skip_reason", lambda config, environ=None: "no tenant test in the targets")
    monkeypatch.setattr(pf, "check", lambda *a, **k: pytest.fail("asked"))
    conftest.pytest_sessionstart(SimpleNamespace(config=_config(["tests/plugins"])))


class _FakeLogin:
    def __init__(self, message=None, captcha=False, lockout=False):
        self._m, self._c, self._l = message, captcha, lockout

    def get_error_message(self):
        return self._m

    def has_captcha(self):
        return self._c

    def has_lockout_message(self):
        return self._l


def test_a_refused_login_is_named_with_what_the_form_shows():
    """The app's own message, the captcha and the lockout text make the line; a bare slow form makes none."""
    page = SimpleNamespace(url=URL + "/auth/login")
    line = conftest._login_refusal(_FakeLogin("Invalid username or password"), page, "u@example.test")
    assert line.startswith("[LOGIN] https://tenant.example.test/auth/login kept the login form after submit.")
    assert "'Invalid username or password'" in line
    assert "Captcha shown: no" in line
    assert "do not submit the form again" in line
    assert "Captcha shown: yes" in conftest._login_refusal(_FakeLogin(captcha=True), page, "u")
    assert conftest._login_refusal(_FakeLogin(), page, "u") is None
    assert conftest._login_refusal(_FakeLogin("x"), SimpleNamespace(url=URL + "/dashboard"), "u") is None
