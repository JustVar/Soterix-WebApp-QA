"""Compatibility shim. The code moved to soterix-qa-shared.

Import this path as before; it resolves to
soterix_qa_shared.reporting.health. As a CLI it writes reports/runs/health.html
for THIS repo. See that repo's docs/RULES.md for the shim's shape.
"""
import sys
from pathlib import Path

try:
    from soterix_qa_shared.reporting import health as _mod, run_archive as _archive
except ModuleNotFoundError as exc:
    if (exc.name or "").split(".")[0] != "soterix_qa_shared":
        raise                    # a dependency of the package is missing
    raise ModuleNotFoundError(
        "soterix-qa-shared is not installed. "
        "Run: pip install -r requirements.txt"
    ) from None

_ROOT = Path(__file__).resolve().parent.parent

# Root the archive paths at THIS repo so an import (or a test) reads
# run_archive.RUNS_DIR/MAPPING_FILE for this tree, not the package's cwd.
_archive.configure(_ROOT)

if __name__ == "__main__":       # BEFORE the alias swap, or the CLI
    sys.exit(_mod.main(root=_ROOT))  # is a silent exit-0 no-op
sys.modules[__name__] = _mod
