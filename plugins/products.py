"""QA Touch project keys and the product each one stands for.

The table copies the "QA Touch projects" table of
docs/QA_TOUCH_INTEGRATION.md. Change the doc first, then this table.

A test belongs to one product. `product_for` names its project key, in
this order, first hit wins:
  1. An explicit `qatouch_project` marker on the test.
  2. A path rule: tests under tests/ui/c2c/ belong to Camera 2 Cloud.
  3. The mapping file's top-level project_key (the caller reads it).
  4. The QATOUCH_PROJECT_ID environment variable.
  5. NexaiQ-Core (JlW1), the project every other tool defaults to.

`target_product` names a run's product from its invocation targets alone
(steps 2 to 5, there is no marker to read), for archives that recorded no
per-test product: a folder target under tests/ui/c2c is Camera 2 Cloud,
anything else is the default.

The archive records the product name per test and once per run, and the
run, health, and index pages show it. Stdlib only.
"""
from __future__ import annotations

# Duplicated in soterix-qa-shared (soterix_qa_shared/reporting/products.py).
# At migration step 6 this file becomes a shim and the duplication ends.
#
# Until then: change BOTH, or neither. One difference is deliberate and must
# stay - the package ships PATH_RULES empty and this repo injects the c2c
# rule through configure_path_rules(), because a rule about tests/ui/c2c/ is
# meaningless in the API repo.
import os
from collections.abc import Iterable

PRODUCTS = {
    'JlW1': 'NexaiQ-Core',
    'P0BK': 'NexaiQ-Neurosen',
    '60w8': 'NexaiQ-Technician App',
    '70l1': 'NexaiQ-Partner Admin Tool',
    'K5kB': 'NexiaQ-Mobile',
    '60W5': 'NexaiQ-Camera 2 Cloud',
}

DEFAULT_KEY = 'JlW1'
ENV_VAR = 'QATOUCH_PROJECT_ID'

# (path prefix under the repo, project key). The prefix matches the node
# id's file part with forward slashes. First match wins.
PATH_RULES = (
    ('tests/ui/c2c/', '60W5'),
)

MIXED_PREFIX = 'Mixed: '


def product_name(key: str | None) -> str:
    """The product a project key stands for.

    An unknown key comes back as itself, so a page never hides a key it
    cannot name. None or an empty key is ''.
    """
    if not key:
        return ''
    return PRODUCTS.get(str(key), str(key))


def product_for(nodeid: str, marker_project: str | None = None,
                default_key: str | None = None) -> str:
    """The project key of a test, by the precedence in the module docstring.

    `marker_project` is the qatouch_project marker's value when the test
    carries one. `default_key` is the mapping file's top-level
    project_key when the caller could read it.
    """
    if marker_project:
        return str(marker_project)
    path = str(nodeid or '').split('::', 1)[0].replace('\\', '/').lstrip('/')
    # The rule's prefix ends in '/'. The folder itself ('tests/ui/c2c', a
    # run target) must match too, so the path is compared as a folder.
    for prefix, key in PATH_RULES:
        if f"{path.rstrip('/')}/".startswith(prefix):
            return key
    if default_key:
        return str(default_key)
    return os.environ.get(ENV_VAR, '').strip() or DEFAULT_KEY


def target_product(targets: Iterable[str], default_key: str | None = None) -> str:
    """The product a run's invocation targets name, as `run_product` labels
    it: one name, or "Mixed: A, B" when the targets differ. No target
    (the whole suite) is the default. Never '': a page that shows this
    has no blank to fall back to."""
    names = [product_name(product_for(t, None, default_key))
             for t in targets if str(t or '').strip()]
    return run_product(names) or product_name(product_for('', None, default_key))


def run_product(names: Iterable[str]) -> str:
    """One label for a run from its tests' product names.

    The single name when every test agrees, else "Mixed: A, B" with the
    names sorted, so two runs of one mix read the same. '' for no names.
    """
    distinct = sorted({str(n) for n in names if n})
    if not distinct:
        return ''
    if len(distinct) == 1:
        return distinct[0]
    return MIXED_PREFIX + ', '.join(distinct)


def is_mixed(product: str | None) -> bool:
    return str(product or '').startswith(MIXED_PREFIX)
