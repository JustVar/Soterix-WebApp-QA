"""Neurosen: the private cloud build of the web app, deployed in the lab.

The Core UI tests (tests/ui) run against it as they do against the QA
server, and it reports to its own QA Touch project (P0BK). The mapping
file carries a per-project key for each Core test that has a Neurosen
case (config/qatouch_case_mapping.json > case_keys).

Before the first run, in .env: NEUROSEN_BASE_URL (the deployment's
address) and the QA_USER / QA_PASSWORD pair of an account on it. Then
fill in default_site_id and the test data below from that tenant, the
way config/env/qa.py names them for the QA server. Run with ENV=neurosen.
"""
import os

from config.secret import Secret

_BASE_URL = os.environ.get("NEUROSEN_BASE_URL", "").strip().rstrip("/")

config = {
    # Empty until .env names the deployment; base_config refuses to load
    # an env with no base_url and says which variable to set.
    "base_url": _BASE_URL,
    "base_url_env": "NEUROSEN_BASE_URL",
    "api_base_url": f"{_BASE_URL}/v-apiserver" if _BASE_URL else "",

    # Writes yes: the deployment is a lab tenant. Deletes stay off until
    # the tenant is confirmed disposable.
    "allow_write": True,
    "allow_delete": False,

    # The QA Touch project the Core UI tests report to under this env.
    # plugins/products.py turns it into the path rule for tests/ui/, so
    # the archive names the product and the reporter picks the row's key
    # for this project.
    "qatouch_project": "P0BK",

    # The tenant's site id, for the api fixture. None until known: the
    # fixture fails and names this key.
    "default_site_id": None,
    # The site and camera the UI tests open, and the chat partner, on this
    # tenant. None until known: a test that needs one fails at that step
    # naming the missing value.
    "test_site_name": None,
    "test_camera_name": None,
    "test_chat_user_search": None,
    "test_chat_user_name": None,
    # A test marked lpr, audio, thermal or ptz drives the camera named here
    # for that marker. Empty means test_camera_name serves every marker.
    "camera_capabilities": {},
    # marker -> reason, for what this deployment lacks (conftest.py
    # env_skip_reason). A Core test carrying the marker skips here at
    # collection with that reason. Empty until measured. An entry reads
    #   "chats": "Neurosen has no messaging (measured 2026-xx-xx)",
    "without": {},
}


def get_credentials():
    """The account the tests sign in as, from .env, and the site its data goes to."""
    return {"email": os.environ.get("QA_USER", ""),
            "password": Secret(os.environ.get("QA_PASSWORD", "")),
            "site_id": config["default_site_id"]}
