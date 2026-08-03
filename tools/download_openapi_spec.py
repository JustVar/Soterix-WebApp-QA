#!/usr/bin/env python3
"""Download OpenAPI specs (QA and Prod), validate, and summarize.

Saves to:
 - tests/shared/schemas/openapi_spec_qa.json
 - tests/shared/schemas/openapi_spec_prod.json

Requires: requests, openapi-spec-validator
"""
import json
import os
import sys
from pathlib import Path

QA_URL = "https://qa.example.invalid/v-apiserver/v3/api-docs"
PROD_URL = "https://app.example.invalid/v-apiserver/v3/api-docs"

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tests" / "shared" / "schemas"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def install_deps():
    try:
        import requests  # noqa: F401
        from openapi_spec_validator import validate_spec  # noqa: F401
    except Exception:
        print("Installing required packages: requests openapi-spec-validator jsonschema")
        os.system(f"{sys.executable} -m pip install requests openapi-spec-validator jsonschema")


def download(url: str, out_path: Path) -> bool:
    import requests

    print(f"Downloading {url} -> {out_path}")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        # Try insecure (no cert verify) as a fallback for internal/self-signed certs
        print(f"Primary download failed ({e}), retrying with certificate verification disabled...")
        try:
            r = requests.get(url, timeout=30, verify=False)
            r.raise_for_status()
            data = r.json()
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print("Downloaded with verify=False (insecure).")
            return True
        except Exception as e2:
            print(f"Failed to download {url} even with verify=False: {e2}")
            return False


def summarize(spec: dict) -> dict:
    paths = spec.get("paths", {})
    total_endpoints = sum(len(v.keys()) for v in paths.values())
    components = spec.get("components", {})
    schemas = components.get("schemas", {})
    security_schemes = components.get("securitySchemes", {})
    tags = spec.get("tags", [])
    tag_names = [t.get("name") for t in tags]
    return {
        "total_endpoints": total_endpoints,
        "total_schemas": len(schemas),
        "auth_methods": list(security_schemes.keys()),
        "tags": tag_names,
    }


def validate_spec_file(path: Path) -> bool:
    try:
        from openapi_spec_validator import validate_spec
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
        validate_spec(spec)
        return True
    except Exception as e:
        print(f"Spec validation failed for {path}: {e}")
        return False


def main():
    install_deps()
    qa_path = OUT_DIR / "openapi_spec_qa.json"
    prod_path = OUT_DIR / "openapi_spec_prod.json"

    qa_ok = download(QA_URL, qa_path)
    prod_ok = download(PROD_URL, prod_path)

    results = {}
    if qa_ok:
        try:
            spec = json.loads(qa_path.read_text(encoding="utf-8"))
            valid = validate_spec_file(qa_path)
            results['qa'] = summarize(spec)
            results['qa']['valid'] = valid
        except Exception as e:
            print(f"Error processing QA spec: {e}")
    if prod_ok:
        try:
            spec = json.loads(prod_path.read_text(encoding="utf-8"))
            valid = validate_spec_file(prod_path)
            results['prod'] = summarize(spec)
            results['prod']['valid'] = valid
        except Exception as e:
            print(f"Error processing Prod spec: {e}")

    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
