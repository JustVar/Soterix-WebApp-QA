"""Compatibility shim. The code moved to soterix-qa-shared.

Import this path as before; it resolves to soterix_qa_shared.reporting.run_report.
As a CLI (`python -m plugins.run_report <run-dir|latest|--all>`) it rebuilds run.html
for THIS repo's archive. See that repo's docs/RULES.md for why the shim has this shape.
"""
import sys
from pathlib import Path

try:
    from soterix_qa_shared.reporting import run_archive as _archive, run_report as _mod
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

_archive.configure_known_defects(known_defect_for)

if __name__ == "__main__":       # BEFORE the alias swap, or the CLI is a silent exit-0 no-op.
    # It was one until 09/21/2026: the command that docs/FAILURE_TRIAGE.md gives
    # printed nothing and wrote nothing (found when 44 run pages did not rebuild).
    _archive.configure(Path(__file__).resolve().parent.parent)
    sys.exit(_mod.main())

sys.modules[__name__] = _mod
