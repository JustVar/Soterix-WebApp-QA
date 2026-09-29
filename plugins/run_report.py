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
        "Run: pip install -r requirements.txt"
    ) from None

# The tests red for an app defect somebody already knows about, from
# config/known_defects.yaml, so the run page can say which failures are
# news and which are being worked.
from tests.shared.helpers.known_defects import known_defect_for

_archive.configure_known_defects(known_defect_for)

if __name__ == "__main__":       # BEFORE the alias swap, or the CLI is a silent exit-0 no-op.
    # With the swap first, the rebuild command that docs/FAILURE_TRIAGE.md gives
    # printed nothing and wrote nothing, and no run page was rebuilt.
    _archive.configure(Path(__file__).resolve().parent.parent)
    sys.exit(_mod.main())

sys.modules[__name__] = _mod
