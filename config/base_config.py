# config/base_config.py
import importlib
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present: ENV, QA_USER, QA_PASSWORD and the run switches.
load_dotenv()

# The env log. conftest.py installs the one rotating handler for it; a
# basicConfig here would win the race (this module imports first) and the
# file would grow for good, which it once did (1.4 MB).
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "env_config.log"

# Map aliases to real environment modules. Every file under config/env/
# has the same flat shape (see config/env/qa.py); a team with a second
# server copies qa.py to config/env/<name>.py, adds the alias here and
# runs with ENV=<name>.
ENV_ALIAS = {
    "qa":    "config.env.qa",
    "neurosen": "config.env.neurosen",   # the private cloud build of the web app
    "stage": "config.env.stage",
    "staging": "config.env.stage",
    "prod":  "config.env.prod",
    "production": "config.env.prod",
}


def _env_name() -> str:
    return (os.environ.get("ENV") or "qa").strip().lower()


def _module_path(env: str) -> str:
    module_path = ENV_ALIAS.get(env)
    if not module_path:
        raise RuntimeError(f"Unknown ENV '{env}'. Valid: {', '.join(sorted(ENV_ALIAS))}")
    return module_path


def load_config():
    env = _env_name()
    module_path = _module_path(env)
    try:
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        raise RuntimeError(f"Config module not found for ENV='{env}': {module_path}") from e

    cfg = getattr(mod, "config", None)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"{module_path} must define a dict named 'config'")
    # An env whose address comes from .env (neurosen) must not run
    # against '' and fail at the first goto with a bare Playwright
    # error: refuse here and name the variable.
    if not (cfg.get("base_url") or "").strip():
        var = cfg.get("base_url_env")
        raise RuntimeError(
            f"ENV='{env}' has no base_url: "
            + (f"set {var} in .env" if var else f"add base_url to {module_path}"))

    logging.getLogger(__name__).info(
        f"[ENV RESOLVED] ENV='{env}' -> {module_path} | base_url={cfg.get('base_url')}")
    return cfg


def get_credentials():
    """The account and site for the active environment: {email, password, site_id}.

    The env module reads the account from QA_USER and QA_PASSWORD in .env
    and the site from its own default_site_id (config/env/qa.py).
    """
    return _get_env_module().get_credentials()


def is_write_allowed():
    """Whether the tests that create and delete data may run here (allow_write)."""
    return config.get("allow_write", False)


def _get_env_module():
    """Get the loaded environment module."""
    return importlib.import_module(_module_path(_env_name()))


# Exposed to the rest of the test suite:
config = load_config()
