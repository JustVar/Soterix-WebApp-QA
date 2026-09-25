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
        "Run: pip install -e ../soterix-qa-shared"
    ) from None

# This repo's names for the map of a run page. The package knows a lab camera only as a
# parameter text; config/run_axis.py reads its model and its address from the registry.
from soterix_qa_shared.reporting import run_page as _page

from config.run_axis import camera_columns

_page.configure_axis(camera_columns)
# The tests red for an app defect somebody already knows about, from
# config/known_defects.yaml, so the run page can say which failures are
# news and which are being worked.
from tests.shared.helpers.known_defects import known_defect_for  # noqa: E402

_mod.configure_known_defects(known_defect_for)

sys.modules[__name__] = _mod
