"""Compatibility shim. The code moved to soterix-qa-shared.

Import this path as before; it resolves to soterix_qa_shared.reporting.products.
See that repo's docs/RULES.md for why the shim has this exact shape.
"""
import sys

try:
    from soterix_qa_shared.reporting import products as _mod
except ModuleNotFoundError as exc:
    if (exc.name or "").split(".")[0] != "soterix_qa_shared":
        raise                    # a dependency of the package is missing
    raise ModuleNotFoundError(
        "soterix-qa-shared is not installed. "
        "Run: pip install -e ../soterix-qa-shared"
    ) from None

# This repo's folders, not the package's. A rule about tests/c2c/ is
# meaningless in the API repo, so the package ships none. The roots and
# their projects live in config/products.py, one place for every tool.
from config.products import PRODUCT_ROOTS

_mod.configure_path_rules(list(PRODUCT_ROOTS.items()))

sys.modules[__name__] = _mod
