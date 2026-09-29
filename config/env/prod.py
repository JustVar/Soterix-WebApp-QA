"""The production server. Same shape as config/env/qa.py. Run with ENV=prod.

Production is read-only: allow_write and allow_delete stay False, so the
tests marked with a write or delete marker skip here at collection
(conftest.py env_skip_reason). The account comes from QA_USER and
QA_PASSWORD in .env, never from this file.
"""
import os

from config.secret import Secret

config = {
    "base_url": "https://app.example.invalid",
    "api_base_url": "https://app.example.invalid/v-apiserver",
    "allow_write": False,
    "allow_delete": False,
    "default_site_id": None,
    "test_site_name": None,
    "test_camera_name": None,
    "test_chat_user_search": None,
    "test_chat_user_name": None,
    "camera_capabilities": {},
    "without": {},
}


def get_credentials():
    """The account the tests sign in as, from .env, and the site its data goes to."""
    return {"email": os.environ.get("QA_USER", ""),
            "password": Secret(os.environ.get("QA_PASSWORD", "")),
            "site_id": config["default_site_id"]}
