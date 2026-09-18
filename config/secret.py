"""A credential that never prints itself.

pytest prints a failing frame's arguments, and a dict's repr prints its
values: on 09/14/2026 a fresh-login failure wrote the account password
into a test log that the nightly then published to the team archive
(found 09/18/2026, register row 92). Every password the suite reads is
wrapped in Secret at the point it leaves the environment. repr() is the
path tracebacks, dict reprs, pytest-html and %r logging all take, and it
answers '***'; str(), fill() and HTTP calls still get the real value,
because a Secret is a str.
"""
from __future__ import annotations


class Secret(str):
    """A str whose repr is masked. Compare, format and send it as any str."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "'***'"
