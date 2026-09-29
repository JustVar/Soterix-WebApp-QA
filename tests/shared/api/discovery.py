"""Which site and camera a run drives when config/env/ names none.

A server has whatever sites and cameras its people added in the app, and
the tests do not care which camera they drive as long as the account can
see it. So config/env/ may leave `test_site_name` and `test_camera_name`
blank, and the run reads them from the server at session start:

- the site is the first site by name that the account can see, registered,
  with at least one camera;
- the camera is the first camera of that site by name.

By name, not by the order the server returns them: that order changes when
a camera is added, which would silently re-point every run. Every process
of an xdist run reads the same list and sorts it the same way, so the
workers and the controller reach one camera without talking to each other.

A camera can be listed and dark. The stream guard measures the chosen
camera at session start and skips the livestream tests with the frame
count when it streams nothing (the [STREAM] line). Then name a camera in
config/env/ (`test_camera_name`) or for one run (`TEST_CAMERA`).

Channel records carry the camera's own credentials (`username`,
`password`). Only names and ids leave this module.
"""
from __future__ import annotations

import requests

from tests.shared.api.client import ApiError, InternalApi

# The location that holds every camera of a site (GET /REST/site/{id}/location/tree).
ALL_CAMERAS_LOCATION = 1
REGISTERED = "REGISTERED"
# The reasons a configured name gets, so a caller can tell a checked name
# from a choice the server made.
CONFIGURED_SITE_REASON = "test_site_name in config/env/"
CONFIGURED_CAMERA_REASON = "the configured camera (test_camera_name in config/env/)"


class DiscoveryError(Exception):
    """The server could not be asked, or it has nothing to drive."""


# --------------------------------------------------------------- the server

def sites(api: InternalApi) -> list[dict]:
    """The sites the account can see: [{site_id, name, status}], sorted by name."""
    rows = []
    for site in api.get("/REST/site"):
        name = str(site.get("name") or "").strip()
        if not name or site.get("siteId") is None:
            continue
        rows.append({"site_id": int(site["siteId"]), "name": name,
                     "status": str(site.get("status") or "")})
    return sorted(rows, key=lambda row: row["name"].lower())


def camera_names(api: InternalApi, site_id: int) -> list[str]:
    """The site's camera names, sorted, deleted cameras left out.

    Read from the All Cameras location of location/tree, which holds every
    camera of the site; a site without that location gives the union of
    its locations.
    """
    tree = api.get(f"/REST/site/{int(site_id)}/location/tree")
    nodes = [node for node in tree
             if int((node.get("location") or {}).get("id") or 0) == ALL_CAMERAS_LOCATION] or tree
    names = set()
    for node in nodes:
        for channel in node.get("channel") or []:
            if channel.get("isChannelDeleted"):
                continue
            name = str(channel.get("name") or "").strip()
            if name:
                names.add(name)
    return sorted(names, key=str.lower)


# ------------------------------------------------------------- the choices

def choose_site(rows: list[dict], cameras_of, configured: str | None = None) -> dict:
    """The site a run drives: {site_id, name, reason}.

    `rows` is what sites() answered, `cameras_of(site_id)` the names of a
    site's cameras. A configured name must be one of the rows, or the error
    lists the names the account sees, so a rename is fixed in one edit.
    """
    configured = (configured or "").strip()
    if configured:
        for row in rows:
            if row["name"] == configured:
                return {"site_id": row["site_id"], "name": row["name"],
                        "reason": CONFIGURED_SITE_REASON}
        raise DiscoveryError(
            f"no site named '{configured}' for this account. Sites: "
            f"{[row['name'] for row in rows]}. Fix test_site_name in config/env/, "
            f"or leave it blank to drive the first site with a camera.")
    for row in rows:
        if row["status"] and row["status"] != REGISTERED:
            continue
        if cameras_of(row["site_id"]):
            return {"site_id": row["site_id"], "name": row["name"],
                    "reason": "the first site by name with a camera (test_site_name is blank in config/env/)"}
    raise DiscoveryError(
        f"none of the account's sites has a camera. Sites: {[row['name'] for row in rows]}.")


def choose_camera(names: list[str], site_name: str, configured: str | None = None) -> dict:
    """The camera a run drives: {camera, reason}.

    `names` is what camera_names() answered for the chosen site. A configured
    name must be in the list, or the error lists the names, for the same
    one-edit fix as the site.
    """
    configured = (configured or "").strip()
    if configured:
        if configured in names:
            return {"camera": configured, "reason": CONFIGURED_CAMERA_REASON}
        raise DiscoveryError(
            f"no camera named '{configured}' on site '{site_name}'. Cameras: {names}. "
            f"Fix test_camera_name in config/env/, or leave it blank to drive the first camera by name.")
    if not names:
        raise DiscoveryError(f"site '{site_name}' has no camera.")
    return {"camera": names[0],
            "reason": f"the first camera by name of site '{site_name}' (test_camera_name is blank in config/env/)"}


# --------------------------------------------------------------- the entry

def needs_discovery(config: dict) -> bool:
    """Whether config/env/ leaves the site or the camera to the server."""
    return not (str(config.get("test_site_name") or "").strip()
                and str(config.get("test_camera_name") or "").strip()
                and config.get("default_site_id"))


def discover(config: dict, creds: dict) -> dict:
    """Ask the server for what config/env/ leaves blank.

    Answers {site_id, site_name, site_reason, camera, camera_reason,
    cameras (how many the site has)}. Raises DiscoveryError with a message
    that names the fix and carries no credential.
    """
    email, password = creds.get("email"), creds.get("password")
    if not email or not password:
        raise DiscoveryError("QA_USER and QA_PASSWORD (.env) are needed to read the server's sites and cameras.")
    api = InternalApi(str(config.get("base_url") or ""), 0)
    try:
        api.login(email, password)
        rows = sites(api)
        site = choose_site(rows, lambda site_id: camera_names(api, site_id),
                           config.get("test_site_name"))
        names = camera_names(api, site["site_id"])
    except (ApiError, requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        raise DiscoveryError(f"the server could not be read: {type(exc).__name__}: {exc}") from None
    camera = choose_camera(names, site["name"], config.get("test_camera_name"))
    return {"site_id": site["site_id"], "site_name": site["name"], "site_reason": site["reason"],
            "camera": camera["camera"], "camera_reason": camera["reason"], "cameras": len(names)}


def fill_config(config: dict, creds: dict) -> dict | None:
    """Write the discovered site and camera into `config` where it is blank.

    Answers the discovery record, or None when config/env/ names everything
    (then the server is not asked). A configured value is never replaced,
    only checked: a stale name raises with the names the account sees.
    """
    if not needs_discovery(config):
        return None
    record = discover(config, creds)
    config["test_site_name"] = record["site_name"]
    config["default_site_id"] = record["site_id"]
    config["test_camera_name"] = record["camera"]
    return record
