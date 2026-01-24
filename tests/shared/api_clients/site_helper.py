"""Helper utilities for discovering sites available to a user."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_available_sites(user_api) -> List[Dict[str, Any]]:
    """Return a list of site objects available to the logged-in user.

    Strategy:
    - Call `/REST/central/user/session` via the provided `user_api` and
      inspect the response for site/assignedSites information.
    - If the session response does not include site info, attempt
      `/REST/site/user/{userid}` as used by the UI client.
    - If both fail, return an empty list.
    """
    try:
        sess = user_api.get_user_session()
    except Exception:
        sess = None

    # Try session result first
    if isinstance(sess, dict):
        res = sess.get("result") or []
        if res and isinstance(res, list):
            # Some deployments embed assignedSites inside session result
            first = res[0]
            if isinstance(first, dict):
                # common key used by UI: assignedSites stored in localStorage
                assigned = first.get("assignedSites") or first.get("sites")
                if isinstance(assigned, list) and assigned:
                    return assigned

    # Fallback: try calling site/user/{userid}
    try:
        # derive username/userId from session if possible
        user_id = None
        if isinstance(sess, dict):
            res = sess.get("result") or []
            if res and isinstance(res, list) and isinstance(res[0], dict):
                user_id = res[0].get("userId") or res[0].get("userid") or res[0].get("user", {}).get("userId")
        if user_id:
            path = f"/REST/site/user/{user_id}"
            try:
                r = user_api.get(path)
                if r.status_code == 200:
                    body = r.json()
                    # body may contain a result list
                    if isinstance(body, dict):
                        for key in ("result", "sites", "assignedSites", "data"):
                            v = body.get(key)
                            if isinstance(v, list) and v:
                                return v
                    if isinstance(body, list) and body:
                        return body
            except Exception:
                pass
    except Exception:
        pass

    return []
