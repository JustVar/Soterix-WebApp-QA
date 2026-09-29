"""The product test roots of this repo, and the QA Touch project each one
reports to.

One place, read by the tools that walk the tree (run.py, the convention
checker, the step-stub and case generators, the mapping audit, the
inventory) and by plugins/products.py, which turns it into the archive's
path rules. Before 09/11/2026 every tool carried its own "tests/ui" root,
so a second product root meant touching six tools. A second product adds
one line here.

Order matters where prefixes overlap: the first match wins.

The Core root is shared: the same UI tests run against the QA server
(project JlW1) and against the Neurosen private cloud (P0BK). An env
file that names a `qatouch_project` re-points that root for the run
(path_rules), so the archive names the product and the reporter picks
each row's key for that project. home_project() answers for the
mapping file itself, where a row's plain `case_key` is always the
root's own project and other projects' keys live under `case_keys`.
"""
from __future__ import annotations

PRODUCT_ROOTS: dict[str, str] = {
    'tests/ui/': 'JlW1',     # NexaiQ-Core: the web app, run against the QA server
}


# The root whose tests run against more than one product.
SHARED_ROOT = 'tests/ui/'


def path_rules(env_settings=None) -> list[tuple[str, str]]:
    """The (prefix, project) rules for this run: the roots as listed, with
    the shared root re-pointed at the env's `qatouch_project` when the
    env file names one (config/env/neurosen.py does)."""
    rules = dict(PRODUCT_ROOTS)
    project = ((env_settings or {}).get('qatouch_project') or '').strip()
    if project:
        rules[SHARED_ROOT] = project
    return list(rules.items())


def home_project(path) -> str:
    """The project a test's plain mapping key belongs to: its root's own
    project, whatever env the run is under. Core for anything outside
    the roots (the mapping file's own default)."""
    root = product_root(path)
    return PRODUCT_ROOTS[root] if root else PRODUCT_ROOTS[SHARED_ROOT]


def _posix(path) -> str:
    return str(path).replace('\\', '/')


def product_root(path) -> str | None:
    """The root prefix ('tests/ui/') a test path sits under, else None."""
    p = _posix(path)
    for prefix in PRODUCT_ROOTS:
        if p.startswith(prefix):
            return prefix
    return None


def area_of(path) -> str | None:
    """The module a test file belongs to: the folder under the product root
    ('admin' for tests/ui/admin/test_x.py), or the root's own folder name
    when the files sit directly in it ('ui' for tests/ui/test_x.py).
    None outside the product roots."""
    root = product_root(path)
    if root is None:
        return None
    rest = _posix(path)[len(root):].split('/')
    return rest[0] if len(rest) > 1 else root.strip('/').split('/')[-1]
