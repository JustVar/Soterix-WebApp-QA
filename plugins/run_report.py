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

if __name__ == "__main__":       # BEFORE the alias swap, or the CLI is a silent exit-0 no-op.
    # It was one until 09/21/2026: the command that docs/FAILURE_TRIAGE.md gives
    # printed nothing and wrote nothing (found when 44 run pages did not rebuild).
    _archive.configure(Path(__file__).resolve().parent.parent)
    sys.exit(_mod.main())

sys.modules[__name__] = _mod
