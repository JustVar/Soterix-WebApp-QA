"""Report an absent artifact only after proving the surface that holds it.

House rule (docs/CONVENTIONS.md > Missing artifacts and skips): "No maps
found" and "the panel never loaded" read the same in a report, and a
skip gets scrolled past. So a test may only report absence once it has
seen the surface itself.

`require_items` is that check in one call. It waits for the items; if
none arrive it looks for the container. A container that is there with
nothing in it is a data fact and skips, naming what IS on screen. A
container that is not there is a broken page and fails.

Register item 25 audited every skip in the UI suite against this rule.
Use this helper rather than a bare `if locator.count() == 0: skip`,
which cannot tell the two apart.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import Error as PlaywrightError, Locator


def _first_visible(locator: Locator, timeout_ms: int) -> bool:
    """True when the locator's first match becomes visible in time."""
    # typed: a locator that never resolves times out, and that is the
    # question being asked - it must not read as a page fault here
    try:
        locator.first.wait_for(state="visible", timeout=timeout_ms)
        return True
    # a timeout is the answer False. require_items turns that answer into
    # a skip or a fail that names the surface
    except PlaywrightError:
        return False


def require_items(
    items: Locator,
    *,
    container: Locator,
    surface: str,
    artifact: str,
    empty_means: str,
    timeout_ms: int = 10000,
    container_timeout_ms: int = 5000,
) -> int:
    """Return how many `items` the surface holds, or skip/fail saying why.

    items      the rows, cards or thumbnails under test
    container  something that proves the surface itself rendered. It
               must be page FURNITURE - a tab, a search box, a panel
               header - never a row or a row-level icon. A container
               that disappears along with the rows cannot tell an empty
               surface from a broken one, which is the whole point of
               this call. Measured 09/04/2026: the rules TABLE looked
               like a fair container until a tenant with no rule
               rendered an empty state and no table, and an honest data
               skip failed instead.
    surface    its name for the report ("Views > Maps panel")
    artifact   what is being counted ("map thumbnail")
    empty_means what an empty surface tells the reader ("no map is
               published under this site")

    Skips only when the container rendered and stayed empty. Raises
    when the container never rendered: that is a page fault wearing an
    absence, and it must not report as Blocked.
    """
    if _first_visible(items, timeout_ms):
        return items.count()

    if not _first_visible(container, container_timeout_ms):
        raise AssertionError(
            f"{surface} never rendered, so the absence of any {artifact} "
            f"proves nothing. Waited {timeout_ms} ms for a {artifact} and "
            f"{container_timeout_ms} ms for the surface itself."
        )

    pytest.skip(
        f"{surface} rendered with no {artifact}: {empty_means}. "
        f"(The surface was proved up first, so this is the tenant's "
        f"data, not a broken page.)"
    )
    return 0  # unreachable: pytest.skip raises
