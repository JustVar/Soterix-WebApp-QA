"""Compatibility shim. The code moved to soterix-qa-shared.

Import this path as before; it resolves to soterix_qa_shared.qatouch.reporter.
See that repo's docs/RULES.md for why the shim has this exact shape.
"""
import sys

from tools.qatouch_mapping import reviewed_lookup as _policy

try:
    from soterix_qa_shared.qatouch import reporter as _mod
except ModuleNotFoundError as exc:
    if (exc.name or "").split(".")[0] != "soterix_qa_shared":
        raise                    # a dependency of the package is missing
    raise ModuleNotFoundError(
        "soterix-qa-shared is not installed. "
        "Run: pip install -e ../soterix-qa-shared"
    ) from None

# Which mapping rows may upload is THIS repo's decision. Of its 378 rows
# only 121 are reviewed; the rest were auto-matched by word overlap, and
# uploading through one writes a real status onto a case no test verifies.
# Injected BEFORE the alias swap.
_mod.MAPPING_POLICY = _policy

sys.modules[__name__] = _mod
