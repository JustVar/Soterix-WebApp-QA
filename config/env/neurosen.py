"""Neurosen: the private cloud build of the web app, deployed in the lab.

The Core UI tests (tests/ui) run against it as they do against a QA box,
and it reports to its own QA Touch project (P0BK, NexaiQ-Neurosen); the
mapping file carries a per-project key for each Core test that has a
Neurosen case (config/qatouch_case_mapping.json > case_keys). Tests that
exist only for Neurosen (backend, config, admin) get a product root of
their own when the first one lands (config/products.py).

Before the first run, in .env: NEUROSEN_BASE_URL (the deployment's
address), NEUROSEN_USER and NEUROSEN_PASSWORD (an account on it). Then
fill in `default_site_id` and the `test_data` block below from that
tenant, the way config/env/qa.py names Spartan0 for the US box.
Run with ENV=neurosen; the one box is `lab`.
"""
import os

_BASE_URL = os.environ.get("NEUROSEN_BASE_URL", "").strip().rstrip("/")

config = {
    # Empty until .env names the deployment; base_config refuses to load
    # an env with no base_url and says which variable to set.
    "base_url": _BASE_URL,
    "base_url_env": "NEUROSEN_BASE_URL",
    "api_base_url": f"{_BASE_URL}/v-apiserver" if _BASE_URL else "",

    # Safety flags. Writes yes: the deployment is a lab tenant. Deletes
    # stay off until the tenant is confirmed disposable (Justin decides).
    "allow_write": True,
    "allow_delete": False,

    # The QA Touch project the Core UI tests report to under this env.
    # plugins/products.py turns it into the path rule for tests/ui/, so
    # the archive names the product and the reporter picks the row's key
    # for this project.
    "qatouch_project": "P0BK",

    # What this deployment does not have, by pytest marker, with the
    # reason. Same shape and guard as a box's `without` (conftest.py
    # env_skip_reason): a Core test carrying one of these markers skips
    # here at collection with that reason, and runs on the QA boxes.
    # Empty until measured against the deployment; an entry reads
    #   "chats": "Neurosen has no messaging (measured 2026-xx-xx)",
    "without": {},

    "boxes": {
        "lab": {
            "email_env": "NEUROSEN_USER",
            "password_env": "NEUROSEN_PASSWORD",
            # The tenant's site id, for the api fixture; fill in from the
            # deployment (config/env/qa.py: 16 on india, 156 on us).
            "default_site_id": None,
            "test_data": {
                # The site and camera the UI tests open, and the chat
                # partner, on this tenant. None until known: a test that
                # needs one fails at that step naming the missing value.
                "test_site_name": None,
                "test_camera_name": None,
                "test_chat_user_search": None,
                "test_chat_user_name": None,
            },
        },
    },
    "default_box": "lab",
}


def get_box_config(box_name=None):
    box = box_name or os.environ.get("BOX", config["default_box"])
    if box not in config["boxes"]:
        raise KeyError(
            f"Unknown box '{box}' for this environment. "
            f"Valid boxes: {sorted(config['boxes'])}")
    return config["boxes"][box]


def get_credentials(box_name=None):
    """Credentials for a box, from the variables the box names."""
    box_config = get_box_config(box_name)
    return {
        "email": os.environ.get(box_config["email_env"], ""),
        "password": os.environ.get(box_config["password_env"], ""),
        "site_id": box_config["default_site_id"],
    }
