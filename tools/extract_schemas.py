#!/usr/bin/env python3
"""Extract component schemas and response schemas from OpenAPI spec.

Saves component schemas to `tests/shared/schemas/responses/{SchemaName}.json`.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "tests" / "shared" / "schemas" / "openapi_spec_qa.json"
OUT_DIR = ROOT / "tests" / "shared" / "schemas" / "responses"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_spec():
    if not SPEC_PATH.exists():
        print(f"Spec not found: {SPEC_PATH}. Run download_openapi_spec.py first.")
        sys.exit(2)
    with open(SPEC_PATH, encoding="utf-8") as f:
        return json.load(f)


def extract_components(spec: dict) -> int:
    comps = spec.get("components", {}).get("schemas", {})
    count = 0
    for name, schema in comps.items():
        out = OUT_DIR / f"{name}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)
        count += 1
    return count


def extract_response_schemas(spec: dict) -> int:
    paths = spec.get("paths", {})
    count = 0
    for path, ops in paths.items():
        for method, op in ops.items():
            opid = op.get('operationId') or f"{method}_{path.replace('/','_').strip('_')}"
            responses = op.get('responses', {})
            for code, resp in responses.items():
                content = resp.get('content', {})
                app_json = content.get('application/json') or content.get('application/vnd.api+json')
                if app_json:
                    schema = app_json.get('schema')
                    if schema:
                        out_name = f"resp_{opid}_{code}.json".replace(' ', '_').replace('/', '_')
                        out_path = OUT_DIR / out_name
                        with open(out_path, 'w', encoding='utf-8') as f:
                            json.dump(schema, f, indent=2)
                        count += 1
    return count


def main():
    spec = load_spec()
    ccount = extract_components(spec)
    rcount = extract_response_schemas(spec)
    print(f"Extracted {ccount} component schemas and {rcount} response schemas to {OUT_DIR}")


if __name__ == '__main__':
    main()
