import os

config = {
    "base_url": "https://qa.example.invalid",
    "api_base_url": "https://qa.example.invalid/v-apiserver",

    # Safety flags
    "allow_write": True,
    "allow_delete": True,

    # Test Data Configuration
    "test_site_name": "Newtown Action Area",
    # NOTE: the rule wizard hides cameras that are at rule capacity.
    # If this camera is missing from the wizard device list, check for
    # leftover *_Auto_* rules on it and delete them (verified 08/2026)
    "test_camera_name": "main gate",
    # Chat panel: the user the messaging tests chat with. The search
    # term must match them in the chat user search; the name is the
    # full display name shown on their conversation row.
    "test_chat_user_search": "QA Engineer B",
    "test_chat_user_name": "Chat Partner",

    # Box configurations. Each box names the environment variables that hold
    # the account to use, so every tester signs in as themselves.
    "boxes": {
        # Per-box test_data overrides the top-level test_* keys when that
        # box is active (BOX env var; overlay happens in
        # config/base_config.py load_config), so config.get("test_site_name")
        # is always the ACTIVE box's site and no test needs box logic.
        "india": {
            "email_env": "QA_INDIA_USER",
            "password_env": "QA_INDIA_PASSWORD",
            # siteId of test_site_name below; the api fixture builds its
            # data here, so it must be the site the UI tests open
            "default_site_id": 16,
            "test_data": {
                "test_site_name": "Newtown Action Area",
                "test_camera_name": "main gate",
                # Chat partners differ per tenant: the accounts on one
                # box do not exist on the other, so a shared name fails
                # the chats tests everywhere but home (register item 29)
                "test_chat_user_search": "QA Engineer B",
                "test_chat_user_name": "Chat Partner",
            },
        },
        # The US QA box signs in with the automation account
        # (test-auto-qa@soterixsystems.com, enterprise 132, site "Spartan0").
        # Set QA_US_USER / QA_US_PASSWORD in .env to those credentials.
        "us": {
            "email_env": "QA_US_USER",
            "password_env": "QA_US_PASSWORD",
            # siteId of Spartan0, this box's only site
            "default_site_id": 156,
            "test_data": {
                # Spartan0 is the box's only site (site id 156); the camera
                # is a live streaming one (probe 09/01/2026, 22 cameras)
                "test_site_name": "Spartan0",
                "test_camera_name": "Soterix Multicam 1.15",
                # 'Dallas QA Lab' is the one real chat account on this
                # tenant; 'qa' matches it alone (probed 09/04/2026).
                # The only other searchable names are our own leaked
                # AutoTest users (register item 11), which are not a
                # person to message.
                "test_chat_user_search": "Dallas",
                "test_chat_user_name": "Dallas QA Lab",
            },
        },
    },

    # Default box if not specified
    "default_box": "india",
}

# Helper to get active box config
def get_box_config(box_name=None):
    box = box_name or os.environ.get("BOX", config["default_box"])
    if box not in config["boxes"]:
        raise KeyError(
            f"Unknown box '{box}' for this environment. "
            f"Valid boxes: {sorted(config['boxes'])}")
    return config["boxes"][box]

# Helper to get credentials for active box
def get_credentials(box_name=None):
    """Credentials for a box.

    A box gives either a literal `email` (shared accounts) or an `email_env`
    naming the variable that holds it (per-tester accounts).
    """
    box_config = get_box_config(box_name)
    email = box_config.get("email") or os.environ.get(
        box_config.get("email_env", ""), "")
    password = os.environ.get(box_config["password_env"], "")
    return {
        "email": email,
        "password": password,
        "site_id": box_config["default_site_id"],
    }
