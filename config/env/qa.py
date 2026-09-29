"""The QA server. A new server edits this file and .env, nothing else.

Keys a new server needs: base_url, api_base_url, default_site_id,
test_site_name, test_camera_name, test_chat_user_search, test_chat_user_name.
Optional: camera_capabilities (a marker -> the camera it needs), without
(a marker -> why this server cannot run it). Measure before you fill either.
"""
import os

from config.secret import Secret

config = {
    "base_url": "https://qa.example.invalid",          # the QA server
    "api_base_url": "https://qa.example.invalid/v-apiserver",
    "allow_write": True,        # tests marked admin_users, admin_rules, admin_sites, bookmark, sequences run only when True
    "allow_delete": True,       # tests marked destructive, mutating run only when True
    "default_site_id": 17,      # siteId of test_site_name; the api fixture builds its data there and refuses when the two disagree
    "test_site_name": "Example Corporate Office",
    # The camera a test drives when it does not care which. The stream guard
    # measures it. The rule wizard hides a camera that is at rule capacity:
    # if this camera is missing from the wizard's device list, delete the
    # leftover *_Auto_* rules on it (tools/tenant_cleanup.py).
    "test_camera_name": "Thermal-14",
    # The chat partner. Accounts differ per tenant, so a new server needs
    # a person of its own here.
    "test_chat_user_search": "QA Engineer B",
    "test_chat_user_name": "Chat Partner",
    # A test marked lpr, audio, thermal or ptz drives the camera named here for
    # that marker. Empty means test_camera_name serves every marker.
    "camera_capabilities": {},
    # marker -> reason, for what this server lacks. A test carrying the marker
    # skips at collection with this reason. Example: "lpr": "no plate camera".
    "without": {},
}


def get_credentials():
    """The account the tests sign in as, from .env, and the site its data goes to."""
    return {"email": os.environ.get("QA_USER", ""),
            "password": Secret(os.environ.get("QA_PASSWORD", "")),
            "site_id": config["default_site_id"]}
