# config/base_config.py
import importlib
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present (lets you set AUTO_USER/AUTO_PASSWORD, etc.)
load_dotenv()

# Logging setup
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "env_config.log"
logging.basicConfig(filename=str(LOG_FILE), level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# Map aliases to real environment modules
ENV_ALIAS = {
    "qa":    "config.env.qa",
    "stage": "config.env.stage",
    "staging": "config.env.stage",
    "prod":  "config.env.prod",
    "production": "config.env.prod",
    "uat":   "config.env.stage",   # until a dedicated UAT file exists
    "demo":  "config.env.prod",
    "user":  "config.env.prod",
}

def load_config():
    env = (os.environ.get("ENV") or "qa").strip().lower()
    app_type = (os.environ.get("APP_TYPE") or "customer").strip().lower()

    module_path = ENV_ALIAS.get(env)
    if not module_path:
        raise RuntimeError(f"Unknown ENV '{env}'. Valid: {', '.join(sorted(ENV_ALIAS))}")

    # If partner app_type requested, load partner-specific config module
    if app_type == "partner":
        # e.g. config.env.stage -> config.env.stage_pat
        module_path = module_path + "_pat"

    try:
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        raise RuntimeError(f"Config module not found for ENV='{env}', APP_TYPE='{app_type}': {module_path}") from e

    cfg = getattr(mod, "config", None)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"{module_path} must define a dict named 'config'")

    # Overlay the active box's test data onto the top-level keys, so
    # config.get("test_site_name") etc. always name the ACTIVE box's
    # tenant (BOX=us -> Spartan0) and tests stay box-agnostic. The env
    # module's top-level test_* keys remain the default-box values.
    box = os.environ.get("BOX", cfg.get("default_box", "")).strip().lower()
    box_cfg = (cfg.get("boxes") or {}).get(box) or {}
    overrides = box_cfg.get("test_data") or {}
    if overrides:
        cfg = {**cfg, **overrides}

    logging.info(f"[ENV RESOLVED] ENV='{env}' APP_TYPE='{app_type}' -> {module_path} | base_url={cfg.get('base_url')} | box='{box}' overlay={sorted(overrides)}")
    return cfg

# Helpers to expose box/credential and safety checks
def get_active_box():
    """Get the active box name from environment or default.

    The default matches config['default_box'] for the active env, so an
    unset BOX resolves the same way here and in get_box_config.
    """
    default = config.get("default_box", "us")
    return os.environ.get("BOX", default).strip().lower()


def get_credentials():
    """Get credentials for the active environment and box."""
    env_module = _get_env_module()
    if hasattr(env_module, 'get_credentials'):
        return env_module.get_credentials(get_active_box())
    # Fallback for old-style configs
    return {
        "email": config.get("default_user", ""),
        "password": config.get("default_password", ""),
        "site_id": None,
    }


def is_write_allowed():
    """Check if write operations (POST/PUT) are allowed in current environment."""
    return config.get("allow_write", False)


def is_delete_allowed():
    """Check if delete operations are allowed in current environment."""
    return config.get("allow_delete", False)


def _get_env_module():
    """Get the loaded environment module."""
    env = (os.environ.get("ENV") or "qa").strip().lower()
    app_type = (os.environ.get("APP_TYPE") or "customer").strip().lower()
    module_path = ENV_ALIAS.get(env)
    if app_type == "partner":
        module_path = module_path + "_pat"
    return importlib.import_module(module_path)

# Exposed to the rest of the test suite:
config = load_config()
