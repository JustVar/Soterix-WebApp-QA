"""Compatibility shim - the Graph email client moved to the shared package.

Import this path as before; it resolves to soterix_qa_shared.reporting.email.
The consumer loads its own .env (conftest / the CLI); the package reads the
environment and never loads a repo's .env itself.
"""
import sys

from soterix_qa_shared.reporting import email as _mod

sys.modules[__name__] = _mod
