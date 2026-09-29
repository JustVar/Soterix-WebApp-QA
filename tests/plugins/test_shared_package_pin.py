"""The shared package reaches this repo as a wheel under vendor/.

Three things must agree: the version on the `soterix-qa-shared==` line in
requirements.txt, the wheel file in vendor/, and the version pip installed.
When they drift apart, a run on this machine tests a pipeline the next
machine does not have, and the two results cannot be compared.

The drift is silent. `pip install -r requirements.txt` says nothing when the
installed version already matches the line, and an editable install of the
package repo overrides the pin until someone reinstalls. These tests fail
loudly in both cases.
"""
from __future__ import annotations

import importlib.metadata
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = REPO_ROOT / 'requirements.txt'
VENDOR = REPO_ROOT / 'vendor'
PACKAGE = 'soterix-qa-shared'
PIN_RE = re.compile(r'^soterix-qa-shared==(?P<version>[0-9][0-9A-Za-z.]*)\s*$', re.M)


def pinned_version() -> str:
    text = REQUIREMENTS.read_text(encoding='utf-8')
    pins = PIN_RE.findall(text)
    assert len(pins) == 1, f'requirements.txt must pin {PACKAGE} exactly once, found {pins}'
    return pins[0]


def test_requirements_find_the_wheel_in_vendor():
    """requirements.txt points pip at vendor/ and names no git URL."""
    text = REQUIREMENTS.read_text(encoding='utf-8')
    assert re.search(r'^--find-links vendor/?\s*$', text, re.M), (
        'requirements.txt needs a "--find-links vendor" line, or pip cannot find the wheel'
    )
    assert 'git+https' not in text, 'the shared package comes from vendor/, not from a git URL'


def test_wheel_of_the_pinned_version_is_in_vendor():
    """vendor/ holds exactly the wheel that requirements.txt pins."""
    version = pinned_version()
    wheel = VENDOR / f'soterix_qa_shared-{version}-py3-none-any.whl'
    present = sorted(p.name for p in VENDOR.glob('soterix_qa_shared-*.whl'))
    assert wheel.is_file(), f'requirements.txt pins {version} but vendor/ holds {present}'
    assert present == [wheel.name], f'vendor/ must hold one wheel of the package, found {present}'


def test_installed_version_matches_the_pin():
    """The installed package version is the one requirements.txt pins."""
    version = pinned_version()
    installed = importlib.metadata.version(PACKAGE)
    assert installed == version, (
        f'{PACKAGE} {installed} is installed but requirements.txt pins {version}. '
        'Run: python -m pip install -r requirements.txt'
    )
