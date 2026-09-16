"""Match a name the app may show cut short.

Several panels cut a long name in the DOM itself and append an ellipsis:
the Maps site dropdown reads 'Example Corporat...', the Event Wall
form's Available Cameras panel 'Example Corporate Off...', with no
title attribute carrying the full name (measured 09/15 and 09/16/2026).
An exact match can never reach such a row, and a substring match cannot
either: the shown text is shorter than the name. These helpers accept the
name, or any head of it (at least MIN_HEAD characters) followed by an
ellipsis, and nothing else, so a name that merely shares a prefix with
another cannot be picked by mistake.
"""
from __future__ import annotations

import re

ELLIPSIS_RE = re.compile(r"\s*(?:\.\.\.|…)$")
MIN_HEAD = 6


def is_shown_as(text: str, name: str) -> bool:
    """True when `text` is `name`, or a cut of `name` ending in an ellipsis."""
    shown = " ".join(text.split())
    if shown == name:
        return True
    if not ELLIPSIS_RE.search(shown):
        return False
    head = ELLIPSIS_RE.sub("", shown).rstrip()
    return len(head) >= MIN_HEAD and name.startswith(head)


def shown_as(name: str) -> re.Pattern:
    """A pattern for get_by_text: the full name, or a cut of it with an ellipsis."""
    heads = [re.escape(name[:k].rstrip()) for k in range(MIN_HEAD, len(name))]
    alternatives = "|".join(dict.fromkeys(heads))  # unique, in order
    return re.compile(rf"^(?:{re.escape(name)}|(?:{alternatives})\s*(?:\.\.\.|…))$")
