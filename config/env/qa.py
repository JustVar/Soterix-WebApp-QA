import os

config = {
    "base_url": "https://qa.example.invalid",
    "api_base_url": "https://qa.example.invalid/v-apiserver",
    
    # Safety flags
    "allow_write": True,
    "allow_delete": True,
    
    # Box configurations
    "boxes": {
        "us": {
            "user_key": "QA_LAB",
            "email": "qa@soterixsystems.com",
            "password_env": "QA_LAB_PASSWORD",
            "default_site_id": 110,
        },
        "india": {
            "user_key": "JUSTIN",
            "email": "qa@soterixsystems.com",
            "password_env": "JUSTIN_PASSWORD",
            "default_site_id": None,  # TBD
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
