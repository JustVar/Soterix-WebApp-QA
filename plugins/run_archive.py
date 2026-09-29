"""Compatibility shim. The code moved to soterix-qa-shared.

Import this path as before; it resolves to soterix_qa_shared.reporting.run_archive.
See that repo's docs/RULES.md for why the shim has this exact shape.
"""
import sys

try:
    from soterix_qa_shared.reporting import run_archive as _mod
except ModuleNotFoundError as exc:
    if (exc.name or "").split(".")[0] != "soterix_qa_shared":
        raise                    # a dependency of the package is missing
    raise ModuleNotFoundError(
        "soterix-qa-shared is not installed. "
        "Run: pip install -r requirements.txt"
    ) from None

# The tests red for an app defect somebody already knows about, from
# config/known_defects.yaml, so the run page can say which failures are
# news and which are being worked.
from tests.shared.helpers.known_defects import known_defect_for

_mod.configure_known_defects(known_defect_for)

sys.modules[__name__] = _mod
