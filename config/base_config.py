# config/base_config.py
import os
import importlib
import logging
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
    # keep room for future aliases if needed:
    "uat":   "config.env.stage",   # until a dedicated UAT file exists
    "demo":  "config.env.prod",
    "user":  "config.env.prod",
}

def load_config():
    env = (os.environ.get("ENV") or "stage").strip().lower()
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

    logging.info(f"[ENV RESOLVED] ENV='{env}' APP_TYPE='{app_type}' -> {module_path} | base_url={cfg.get('base_url')}")
    return cfg

# Exposed to the rest of the test suite:
config = load_config()
