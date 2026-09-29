"""The QA server. A new server edits this file and .env, nothing else.

Keys a new server needs: base_url and media_host. The site and the camera
are optional. Leave test_site_name and test_camera_name blank and the run
reads them from the server at session start: the first site by name that
has a camera, and the first camera of that site by name
(tests/shared/api/discovery.py). Name them to drive one site and one
camera on every run. default_site_id follows the site: leave it None when
the site is discovered. test_chat_user_search and test_chat_user_name name
a person on the server the chat tests can talk to.

Optional: camera_capabilities (a marker -> the camera it needs) and
without (a marker -> why this server cannot run it). Measure before you
fill either.

A second server is a copy of this file under config/env/<name>.py,
selected with ENV=<name> in .env.
"""
import os

from config.secret import Secret

config = {
    "base_url": "https://qa.example.invalid",          # the QA server
    # The media socket host the app's live player opens (wss://...). Read it
    # from the browser's network tab on a playing tile: the request whose
    # path is /v3/api/ws. The stream guard and tools/stream_probe.py open it.
    "media_host": "wss://media.example.invalid",
    # Tests marked admin_users, admin_rules, admin_sites, bookmark or
    # sequences create and delete data on the server. They run only when
    # this is True.
    "allow_write": True,
    # The site and the camera the tests drive. Blank means the run picks
    # them from the server at session start and says so on the [CAMERA]
    # line. A name here is checked at session start: a name the server
    # does not know stops the run with the names it does know.
    "test_site_name": "Example Corporate Office",
    "default_site_id": 17,      # siteId of test_site_name; None when the site is discovered
    # The camera a test drives when it does not care which. The stream guard
    # measures it. The rule wizard hides a camera that is at rule capacity:
    # if this camera is missing from the wizard's device list, delete the
    # leftover *_Auto_* rules on it (tools/tenant_cleanup.py).
    "test_camera_name": "Thermal-14",
    # The chat partner. Accounts differ per server, so a new server needs
    # a person of its own here.
    "test_chat_user_search": "QA Engineer B",
    "test_chat_user_name": "Chat Partner",
    # A test marked lpr, audio, thermal or ptz drives the camera named here for
    # that marker. Empty means the run's camera serves every marker.
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
