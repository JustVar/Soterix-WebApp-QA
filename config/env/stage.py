import os

config = {
    "base_url": "https://staging.example.invalid",
    "api_base_url": "https://staging.example.invalid/v-apiserver",

    # Safety flags - staging allows writes but not deletes
    "allow_write": True,
    "allow_delete": False,

    # Box configurations
    "boxes": {
        "us": {
            "user_key": "TEST_AUTO_STAGE",
            "email": "test-auto-stage@soterixsystems.com",
            "password_env": "TEST_AUTO_STAGE_PASSWORD",
            "default_site_id": None,  # TBD - update when known
        },
    },

    # Default box if not specified
    "default_box": "us",
}

# Helper to get active box config
def get_box_config(box_name=None):
    box = box_name or os.environ.get("BOX", config["default_box"])
    return config["boxes"].get(box, config["boxes"][config["default_box"]])

# Helper to get credentials for active box
def get_credentials(box_name=None):
    box_config = get_box_config(box_name)
    password = os.environ.get(box_config["password_env"], "")
    return {
        "email": box_config["email"],
        "password": password,
        "site_id": box_config["default_site_id"],
    }

