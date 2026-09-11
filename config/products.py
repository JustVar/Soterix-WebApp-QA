"""The product test roots of this repo, and the QA Touch project each one
reports to.

One place, read by the tools that walk the tree (run.py, the convention
checker, the step-stub and case generators, the mapping audit, the
inventory) and by plugins/products.py, which turns it into the archive's
path rules. Before 09/11/2026 the Camera 2 Cloud tests sat under
tests/ui/c2c/ and every tool carried its own "tests/ui" root; moving them
to tests/c2c/ (a product of their own in QA Touch, run against the lab
cameras rather than a tenant) meant touching six tools. A third product
(Neurosen) adds one line here.

Order matters where prefixes overlap: the first match wins.
"""
from __future__ import annotations

PRODUCT_ROOTS: dict[str, str] = {
    'tests/ui/': 'JlW1',     # NexaiQ-Core: the web app, run against a box (BOX=india|us)
    'tests/c2c/': '60W5',    # Camera 2 Cloud: the cameras' own web UIs (tests/data/c2c_cameras.yaml)
}


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
    when the files sit directly in it ('c2c' for tests/c2c/test_x.py).
    None outside the product roots."""
    root = product_root(path)
    if root is None:
        return None
    rest = _posix(path)[len(root):].split('/')
    return rest[0] if len(rest) > 1 else root.strip('/').split('/')[-1]
