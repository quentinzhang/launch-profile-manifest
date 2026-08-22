#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, RefResolver


SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_DIR.parents[1]
SPEC_DIR = REPO_ROOT / "spec" / "v0.1"
PROFILE_SCHEMA_PATH = SPEC_DIR / "launch-profile-manifest.schema.json"
RELEASE_SCHEMA_PATH = SPEC_DIR / "release-envelope.schema.json"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validator(schema_path: Path) -> Draft202012Validator:
    profile_schema = load_json(PROFILE_SCHEMA_PATH)
    release_schema = load_json(RELEASE_SCHEMA_PATH)
    schema = load_json(schema_path)
    store = {
        profile_schema["$id"]: profile_schema,
        release_schema["$id"]: release_schema,
    }
    return Draft202012Validator(
        schema,
        resolver=RefResolver.from_schema(schema, store=store),
        format_checker=FormatChecker(),
    )


def validate(path: Path, schema_path: Path) -> list[str]:
    errors = sorted(validator(schema_path).iter_errors(load_json(path)), key=lambda item: list(item.path))
    return [f"{'.'.join(str(part) for part in error.path) or '$'}: {error.message}" for error in errors]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Launch Profile Manifest documents")
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--release", type=Path)
    args = parser.parse_args()
    if not args.profile and not args.release:
        parser.error("provide --profile and/or --release")

    failed = False
    for label, path, schema in (
        ("profile", args.profile, PROFILE_SCHEMA_PATH),
        ("release", args.release, RELEASE_SCHEMA_PATH),
    ):
        if not path:
            continue
        errors = validate(path, schema)
        if errors:
            failed = True
            print(f"{label}: invalid")
            for error in errors:
                print(f"- {error}")
        else:
            print(f"{label}: valid")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
