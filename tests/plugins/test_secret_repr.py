"""Pins for config/secret.py: a password never prints itself. A fresh-login failure on 09/14/2026 printed login_data, password
included, into a published test log; every path that printed it goes
through repr()."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import conftest  # noqa: E402
from config.secret import Secret  # noqa: E402

VALUE = "not-a-real-password-7"


def test_repr_is_masked_and_the_value_still_works_as_a_string():
    """repr hides it; str, equality, formatting and JSON carry the real value."""
    s = Secret(VALUE)
    assert repr(s) == "'***'"
    assert VALUE not in repr({"username": "u", "password": s})
    assert VALUE not in f"{s!r}"
    assert str(s) == VALUE
    assert s == VALUE
    assert f"{s}" == VALUE
    assert json.dumps({"p": s}) == json.dumps({"p": VALUE})
    assert isinstance(s, str)
    assert not Secret("")


def test_pytests_own_traceback_repr_masks_it():
    """The frame-argument printer that leaked it is _pytest's saferepr."""
    from _pytest._io.saferepr import saferepr
    assert VALUE not in saferepr({"username": "u", "password": Secret(VALUE)})
    assert VALUE not in saferepr(Secret(VALUE))


def test_every_credential_source_returns_a_secret(monkeypatch, request):
    """The env module and the login fixture wrap the password where it leaves the environment."""
    from config.env import qa
    monkeypatch.setenv("QA_PASSWORD", VALUE)
    monkeypatch.setenv("QA_USER", "someone@example.test")
    creds = qa.get_credentials()
    assert isinstance(creds["password"], Secret)
    assert VALUE not in repr(creds)
    # login_data is a session fixture with no browser behind it. Ask for it
    # after the variables are set, so it reads these values.
    data = request.getfixturevalue("login_data")
    assert isinstance(data["password"], Secret)
    assert VALUE not in repr(data)


def test_no_module_reads_a_password_variable_without_wrapping_it():
    """A new os.environ read of a *_PASSWORD or *_PASS key in the run path must be wrapped."""
    import re
    offenders = []
    for rel in ("conftest.py", "config/env/qa.py", "config/env/stage.py",
                "config/env/prod.py", "config/env/neurosen.py"):
        for i, line in enumerate((REPO_ROOT / rel).read_text(encoding="utf-8").splitlines(), 1):
            reads = re.search(r"os\.environ(\.get)?[\[(].*(PASSWORD|_PASS\b|password_env)", line)
            if reads and "Secret(" not in line and "if not os.environ" not in line and "empty = [" not in line:
                offenders.append(f"{rel}:{i}")
    assert not offenders, "password read without Secret(...): " + ", ".join(offenders)
