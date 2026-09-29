"""The production server. Same shape as config/env/qa.py. Run with ENV=prod.

Production is read-only: allow_write stays False, so the tests marked
with a write marker skip here at collection (conftest.py
env_skip_reason). The site and the camera are None, so a run reads them
from the server (config/env/qa.py explains the keys). The account comes
from QA_USER and QA_PASSWORD in .env, never from this file.
"""
import os

from config.secret import Secret

config = {
    "base_url": "https://app.example.invalid",
    "media_host": None,
    "allow_write": False,
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
