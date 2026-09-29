"""The staging server. Same shape as config/env/qa.py. Run with ENV=stage.

Writes are allowed, deletes are not. The test data keys are None until
somebody measures them on that tenant.
"""
import os

from config.secret import Secret

config = {
    "base_url": "https://staging.example.invalid",
    "api_base_url": "https://staging.example.invalid/v-apiserver",
    "allow_write": True,
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
