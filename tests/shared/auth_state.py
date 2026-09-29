"""Where a cached browser session is stored, and why the name matters.

One place decides the filename so the test fixture and the probe tools
cannot disagree about it. A session is only valid for the server it was
made against, so the name carries a slug of the base_url: two envs on one
machine never share a file, and on shared cookie domains (staging and prod
under one parent domain) a stage session cannot pass validation against
prod.
"""
import re


def auth_state_filename(base_url: str, worker: str = "") -> str:
    """Name the session cache after the server it belongs to.

    Under pytest-xdist the worker name is appended, so parallel workers do
    not fight over one file.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", (base_url or "").lower()).strip("-") or "default"
    suffix = f".{worker}" if worker else ""
    return f".auth_state.{slug}{suffix}.json"
