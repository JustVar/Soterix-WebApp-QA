"""Session preflight: is the tenant up, and does the account sign in?

Asked once, in the controlling process, before any browser opens. Without
it a tenant that is down, a wrong password or a locked account reads as a
wall: 420 of 432 tests use authenticated_page, and each one errors on its
own navigation or, after a rejected login, on its own 73-second wait while
submitting the form again (failure-mode audit, 09/18/2026, register row
93). The preflight uses the internal API's captcha-free login, the same
call the api fixtures make, so it costs one request.

The refusal is one line that names the cause, and no test runs:
  PREFLIGHT: <host> did not answer (...). No test ran.
  PREFLIGHT: the tenant refused <account> (...). No test ran, ...
PREFLIGHT=off skips it. It never runs for the offline suites, the camera
suite, collect-only or setup-plan sessions, or an xdist worker.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import PurePosixPath
from urllib.parse import urlparse

SWITCH = "PREFLIGHT"
EXIT_CODE = 7   # pytest's own codes stop at 5; nightly.sh prints the code it got
_OFF = {"0", "off", "false", "no"}
# Roots that never sign in to a tenant: the pins, and the cameras' own UIs.
NO_TENANT_ROOTS = ("tests/plugins", "tests/tools", "tests/helpers", "tests/c2c")


def enabled(environ: Mapping[str, str] | None = None) -> bool:
    environ = os.environ if environ is None else environ
    return (environ.get(SWITCH) or "").strip().lower() not in _OFF


def targets_a_tenant(args: list[str]) -> bool:
    """True when the session's targets can reach a tenant test.

    A path under a no-tenant root cannot; anything else can, including a
    bare `pytest` (testpaths covers tests/ui) and a node id under tests/ui.
    """
    paths = [PurePosixPath(str(a).replace("\\", "/").split("::")[0]) for a in args if not str(a).startswith("-")]
    if not paths:
        return True
    for path in paths:
        text = path.as_posix().lstrip("./")
        if not any(text == root or text.startswith(root + "/") for root in NO_TENANT_ROOTS):
            return True
    return False


def check(base_url: str, account: str, password: str, *, box: str = "",
          login: Callable[[str, str, str], object] | None = None) -> str | None:
    """None when the account signs in; else the one line that names why not.

    `login(base_url, account, password)` defaults to the internal API's
    captcha-free login; tests pass a fake.
    """
    host = urlparse(base_url).netloc or base_url
    who = f"{account or '<no account>'}" + (f" (box {box})" if box else "")
    if not account or not password:
        return (f"PREFLIGHT: no account to sign in with for {host}{f' (box {box})' if box else ''}: the user or the "
                f"password is empty in .env (README > Quick Setup). No test ran.")
    login = login or _api_login
    try:
        token = login(base_url, account, password)
    except Exception as e:  # why: every failure class gets its own line below; none may escape as a wall
        kind = type(e).__name__
        text = str(e).splitlines()[0][:200] if str(e) else ""
        if _is_refusal(e):
            return (f"PREFLIGHT: the tenant refused {who}: {text}. Check the account pair in .env. "
                    f"No test ran, so nothing retried the login.")
        if isinstance(e, (IndexError, KeyError, TypeError)):
            return (f"PREFLIGHT: {host} answered the login for {who} without a session token ({kind}). "
                    f"The internal API changed or the account has no session. No test ran.")
        return f"PREFLIGHT: {host} did not answer ({kind}: {text}). No test ran."
    if not token:
        return f"PREFLIGHT: {host} answered the login for {who} with an empty session token. No test ran."
    return None


def _is_refusal(error: Exception) -> bool:
    """An ApiError is the tenant answering no; anything else never reached an answer."""
    return type(error).__name__ == "ApiError"


def _api_login(base_url: str, account: str, password: str) -> object:
    from tests.shared.api.client import InternalApi
    return InternalApi(base_url, 0).login(account, password)


def skip_reason(config, environ: Mapping[str, str] | None = None) -> str | None:
    """Why this session gets no preflight, or None when it must run one."""
    if not enabled(environ):
        return f"{SWITCH}=off"
    if hasattr(config, "workerinput"):
        return "xdist worker (the controller asked once)"
    for option in ("collectonly", "setupplan", "setuponly"):
        if config.getoption(option, default=False):
            return f"--{option}: no test runs"
    if not targets_a_tenant(list(config.args)):
        return "no tenant test in the targets"
    return None
