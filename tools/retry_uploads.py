"""Compatibility shim. The code moved to soterix-qa-shared.

Import this path as before; it resolves to soterix_qa_shared.qatouch.retry.
See that repo's docs/RULES.md for why the shim has this exact shape.
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    from soterix_qa_shared.qatouch import retry as _mod
except ModuleNotFoundError as exc:
    if (exc.name or "").split(".")[0] != "soterix_qa_shared":
        raise                    # a dependency of the package is missing
    raise ModuleNotFoundError(
        "soterix-qa-shared is not installed. "
        "Run: pip install -e ../soterix-qa-shared"
    ) from None

_ROOT = Path(__file__).resolve().parent.parent

# The package reads credentials from os.environ and never opens a repo's
# .env. A CLI has no conftest to load it, so the shim does.
load_dotenv(_ROOT / '.env')
_mod.configure(_ROOT)

if __name__ == "__main__":       # BEFORE the alias swap, or the CLI
    sys.exit(_mod.main())        # is a silent exit-0 no-op
sys.modules[__name__] = _mod
