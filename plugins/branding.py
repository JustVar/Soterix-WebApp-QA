"""Compatibility shim. The code moved to soterix-qa-shared.

Import this path as before; it resolves to soterix_qa_shared.reporting.branding.
See that repo's docs/RULES.md for why the shim has this exact shape.
"""
import sys
from pathlib import Path

try:
    from soterix_qa_shared.reporting import branding as _mod
except ModuleNotFoundError as exc:
    if (exc.name or "").split(".")[0] != "soterix_qa_shared":
        raise                    # a dependency of the package is missing
    raise ModuleNotFoundError(
        "soterix-qa-shared is not installed. "
        "Run: pip install -e ../soterix-qa-shared"
    ) from None

_ROOT = Path(__file__).resolve().parent.parent

# The logos live in THIS repo. The package resolves nothing from __file__,
# which after installation points into site-packages.
_mod.configure(_ROOT)

sys.modules[__name__] = _mod
