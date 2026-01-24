#!/usr/bin/env python
"""
Discover cameras for any environment.

Usage:
    python tools/discover_cameras.py              # Uses ENV variable
    python tools/discover_cameras.py --env qa
    python tools/discover_cameras.py --env staging --site 120
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.shared.api_clients.auth_helper import AuthHelper
from tests.shared.api_clients.base_api_client import BaseAPIClient
from tests.shared.api_clients.discovery_helper import DiscoveryHelper


def main():
    parser = argparse.ArgumentParser(description="Discover cameras in environment")
    parser.add_argument("--env", default=os.getenv("ENV", "qa"), help="Environment (qa/staging/prod)")
    parser.add_argument("--site", type=int, help="Specific site ID (optional)")
    args = parser.parse_args()

    os.environ["ENV"] = args.env

    # Load config and authenticate
    from tests.shared.config.env_config import get_env_config
    config = get_env_config(args.env)

    auth = AuthHelper(config["base_url"])
    token = auth.get_token(config.get("username"), config.get("password"))

    client = BaseAPIClient(config["base_url"], token)
    discovery = DiscoveryHelper(client)

    # If site specified, just show that site
    if args.site:
        info = discovery.discover_all(args.site)
        print_site_info(info)
    else:
        site_id = 110 if args.env == "qa" else 1
        info = discovery.discover_all(site_id)
        print_site_info(info)


def print_site_info(info):
    print(f"\n=== Site {info['site_id']} ===")
    print(f"Total channels: {info['total_channels']}")
    print(f"\n{'ID':<6} {'Name':<40} {'Model':<15} {'Snapshot'}")
    print("-" * 70)
    for ch in info["channels"]:
        snap = "YES" if ch["has_snapshot"] else "NO"
        print(f"{ch['id']:<6} {str(ch.get('name') or '')[:40]:<40} {str(ch.get('model') or ''):<15} {snap}")


if __name__ == "__main__":
    main()
