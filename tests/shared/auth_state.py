"""Where a cached browser session is stored, and why the name matters.

One place decides the filename so the test fixture and the probe tools
cannot disagree about it. They did once: the tools kept every session
in a single .auth_state.json, so a probe asked for the US box quietly
reused the India session and reported India's screen (09/03/2026).
"""
import re


def auth_state_filename(base_url: str, box: str = "", worker: str = "") -> str:
    """Name the session cache after the tenant it belongs to.

    A session is only valid for the account that made it, and on ENV=qa
    India and US share one base_url and differ only by the account BOX
    selects. So the name carries BOTH, and under pytest-xdist the worker
    as well, so parallel workers do not fight over one file.
    """
    parts = "-".join(p for p in (base_url or "", box or "") if p)
    slug = re.sub(r"[^a-z0-9]+", "-", parts.lower()).strip("-") or "default"
    suffix = f".{worker}" if worker else ""
    return f".auth_state.{slug}{suffix}.json"
