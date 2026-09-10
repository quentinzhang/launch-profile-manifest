#!/usr/bin/env python3
"""Safe CLI for the authenticated ConsoleX Launch Profile API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request


BASE_URL_ENV = "CONSOLEX_API_BASE_URL"
API_KEY_ENV = "CONSOLEX_API_KEY"
DEFAULT_TIMEOUT_SECONDS = 45


class ClientError(Exception):
    def __init__(self, message: str, *, error_type: str = "CLIENT_ERROR", details: Any = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details


class ApiError(ClientError):
    def __init__(self, status: int, payload: Any):
        message = "ConsoleX Launch API request failed"
        error_type = "API_ERROR"
        if isinstance(payload, dict):
            message = str(payload.get("error_msg") or message)
            error_type = str(payload.get("error_type") or error_type)
        super().__init__(message, error_type=error_type, details=payload)
        self.status = status


@dataclass(frozen=True)
class Config:
    base_url: str
    api_key: str

    @classmethod
    def from_environment(cls) -> "Config":
        base_url = str(os.environ.get(BASE_URL_ENV) or "").strip().rstrip("/")
        api_key = str(os.environ.get(API_KEY_ENV) or "").strip()
        missing = [name for name, value in ((BASE_URL_ENV, base_url), (API_KEY_ENV, api_key)) if not value]
        if missing:
            raise ClientError(
                f"Missing required skill environment variable(s): {', '.join(missing)}",
                error_type="CONFIG_ERROR",
            )

        parsed = parse.urlsplit(base_url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ClientError(
                f"{BASE_URL_ENV} must be an HTTPS origin without a path, query, credentials, or fragment",
                error_type="CONFIG_ERROR",
            )
        return cls(base_url=f"https://{parsed.netloc}", api_key=api_key)


def _sanitize(value: Any, token: str) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize(item, token) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item, token) for item in value]
    if isinstance(value, str) and token:
        return value.replace(token, "[REDACTED]")
    return value


class LaunchProfileClient:
    def __init__(self, config: Config):
        self.config = config

    def call(self, method: str, path: str, payload: Any = None) -> dict[str, Any]:
        if not path.startswith("/api/launch_manifest/"):
            raise ClientError("Refusing to call a non-Launch API path")

        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
            "User-Agent": "consolex-launch-profile-manager/1.1",
        }
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(
            f"{self.config.base_url}{path}",
            data=body,
            headers=headers,
            method=method.upper(),
        )
        try:
            with request.urlopen(req, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8", errors="replace")
                status = int(getattr(response, "status", 200))
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            payload_out = self._decode_body(raw)
            raise ApiError(int(exc.code), _sanitize(payload_out, self.config.api_key)) from None
        except error.URLError as exc:
            raise ClientError(
                f"Unable to reach the configured ConsoleX API: {exc.reason}",
                error_type="NETWORK_ERROR",
            ) from None

        payload_out = self._decode_body(raw)
        if status >= 400:
            raise ApiError(status, _sanitize(payload_out, self.config.api_key))
        if not isinstance(payload_out, dict):
            raise ClientError("Launch API returned a non-object JSON response", error_type="INVALID_RESPONSE")
        return _sanitize(payload_out, self.config.api_key)

    @staticmethod
    def _decode_body(raw: str) -> Any:
        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"error_msg": "Launch API returned a non-JSON response"}


def _workspace_path(raw_path: str, *, must_exist: bool) -> Path:
    root = Path.cwd().resolve()
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ClientError("File path must stay inside the skill workspace", error_type="INVALID_PATH") from None
    if must_exist and (not candidate.is_file() or candidate.is_symlink()):
        raise ClientError(f"Input file not found: {raw_path}", error_type="INVALID_PATH")
    return candidate


def _load_manifest(raw_path: str) -> dict[str, Any]:
    path = _workspace_path(raw_path, must_exist=True)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClientError(f"Unable to read manifest JSON: {exc}", error_type="INVALID_INPUT") from None
    if not isinstance(payload, dict):
        raise ClientError("Manifest input must be a JSON object", error_type="INVALID_INPUT")
    manifest = payload.get("manifest", payload)
    if not isinstance(manifest, dict):
        raise ClientError("Top-level manifest must be a JSON object", error_type="INVALID_INPUT")
    return manifest


def _save_manifest(raw_path: str, manifest: dict[str, Any]) -> str:
    path = _workspace_path(raw_path, must_exist=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise ClientError("Refusing to overwrite a symbolic link", error_type="INVALID_PATH")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return str(path.relative_to(Path.cwd().resolve()))


def _normalize_canonical_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = parse.urlsplit(raw)
    path = parsed.path.rstrip("/") or "/"
    return parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def _canonical_url(manifest: dict[str, Any]) -> str:
    product = manifest.get("product")
    if not isinstance(product, dict):
        return ""
    return _normalize_canonical_url(product.get("canonicalUrl"))


def _profile_canonical_url(profile: dict[str, Any]) -> str:
    stored = _normalize_canonical_url(profile.get("canonical_url"))
    if stored:
        return stored
    manifest = profile.get("manifest")
    return _canonical_url(manifest) if isinstance(manifest, dict) else ""


def _emit(payload: Any, *, stream=None) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False), file=stream or sys.stdout)


def _validate(client: LaunchProfileClient, manifest: dict[str, Any]) -> dict[str, Any]:
    result = client.call("POST", "/api/launch_manifest/validate", {"manifest": manifest})
    if result.get("succ") is not True or not isinstance(result.get("manifest"), dict):
        raise ClientError("Launch API did not return a validated manifest", error_type="INVALID_RESPONSE")
    return result


def _find_duplicate(client: LaunchProfileClient, manifest: dict[str, Any]) -> dict[str, Any] | None:
    target = _canonical_url(manifest)
    if not target:
        return None
    result = client.call("GET", "/api/launch_manifest/profiles")
    profiles = result.get("profiles") if isinstance(result, dict) else None
    if not isinstance(profiles, list):
        return None
    for profile in profiles:
        if isinstance(profile, dict) and _profile_canonical_url(profile) == target:
            return profile
    return None


def _owned_profile(client: LaunchProfileClient, profile_uuid: str) -> dict[str, Any]:
    result = client.call("GET", f"/api/launch_manifest/profiles/{profile_uuid}")
    profile = result.get("profile") if isinstance(result, dict) else None
    if result.get("succ") is not True or not isinstance(profile, dict):
        raise ClientError("Launch API did not return the owned Profile", error_type="INVALID_RESPONSE")
    return profile


def _assert_delete_identity(args: argparse.Namespace, profile: dict[str, Any]) -> None:
    if not args.expected_name and not args.expected_canonical_url:
        raise ClientError(
            "Deletion requires --expected-name or --expected-canonical-url",
            error_type="DELETE_IDENTITY_REQUIRED",
        )

    mismatches: dict[str, dict[str, str]] = {}
    if args.expected_name:
        expected_name = str(args.expected_name).strip()
        actual_name = str(profile.get("name") or "").strip()
        if expected_name != actual_name:
            mismatches["name"] = {"expected": expected_name, "actual": actual_name}
    if args.expected_canonical_url:
        expected_url = _normalize_canonical_url(args.expected_canonical_url)
        actual_url = _profile_canonical_url(profile)
        if expected_url != actual_url:
            mismatches["canonical_url"] = {"expected": expected_url, "actual": actual_url}
    if mismatches:
        raise ClientError(
            "The stored Profile does not match the expected identity",
            error_type="DELETE_IDENTITY_MISMATCH",
            details={"mismatches": mismatches},
        )


def _delete_profile(args: argparse.Namespace, client: LaunchProfileClient) -> dict[str, Any]:
    if not args.confirm_delete:
        raise ClientError(
            "Hard deletion requires --confirm-delete after explicit user authorization",
            error_type="DELETE_CONFIRMATION_REQUIRED",
        )
    if not args.expected_name and not args.expected_canonical_url:
        raise ClientError(
            "Deletion requires --expected-name or --expected-canonical-url",
            error_type="DELETE_IDENTITY_REQUIRED",
        )

    profile_uuid = parse.quote(str(args.profile_uuid), safe="")
    profile_path = f"/api/launch_manifest/profiles/{profile_uuid}"
    profile = _owned_profile(client, profile_uuid)
    _assert_delete_identity(args, profile)

    releases_result = client.call("GET", f"{profile_path}/releases")
    releases = releases_result.get("releases") if isinstance(releases_result, dict) else None
    if releases_result.get("succ") is not True or not isinstance(releases, list):
        raise ClientError("Launch API did not return the Profile releases", error_type="INVALID_RESPONSE")
    if releases and not args.confirm_delete_releases:
        raise ClientError(
            "Profile has Release Envelopes; add --confirm-delete-releases only after their deletion is authorized",
            error_type="DELETE_RELEASES_CONFIRMATION_REQUIRED",
            details={"profile_uuid": str(args.profile_uuid), "release_count": len(releases)},
        )

    result = client.call("DELETE", profile_path)
    if result.get("succ") is not True:
        raise ClientError("Launch API did not confirm Profile deletion", error_type="DELETE_FAILED", details=result)

    try:
        client.call("GET", profile_path)
    except ApiError as exc:
        if exc.status != 404:
            raise
    else:
        raise ClientError(
            "Deleted Profile is still readable",
            error_type="DELETE_VERIFICATION_FAILED",
            details={"profile_uuid": str(args.profile_uuid)},
        )

    list_result = client.call("GET", "/api/launch_manifest/profiles")
    profiles = list_result.get("profiles") if isinstance(list_result, dict) else None
    if list_result.get("succ") is not True or not isinstance(profiles, list):
        raise ClientError("Launch API did not return the Profile list", error_type="INVALID_RESPONSE")
    if any(isinstance(item, dict) and str(item.get("profile_uuid")) == str(args.profile_uuid) for item in profiles):
        raise ClientError(
            "Deleted Profile remains present in the Profile list",
            error_type="DELETE_VERIFICATION_FAILED",
            details={"profile_uuid": str(args.profile_uuid)},
        )

    return {
        "succ": True,
        "deleted_profile": {
            key: profile.get(key)
            for key in ("profile_uuid", "name", "canonical_url", "revision", "is_public", "checksum")
        },
        "deleted_release_count": len(releases),
        "verified_deleted": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage ConsoleX Launch product profiles")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("config-check", help="Verify required environment variables without printing values")
    subparsers.add_parser("schema", help="Fetch the current Launch Manifest schema")
    subparsers.add_parser("list", help="List profiles owned by the authenticated user")

    analyze = subparsers.add_parser("analyze", help="Analyze a public product URL into a Launch Manifest")
    analyze.add_argument("--url", required=True)
    analyze.add_argument("--output", help="Save only the returned manifest to a workspace-relative JSON file")

    validate = subparsers.add_parser("validate", help="Validate and normalize a manifest JSON file")
    validate.add_argument("--input", required=True)

    create = subparsers.add_parser("create", help="Validate and create a Launch product profile")
    create.add_argument("--input", required=True)
    create.add_argument("--allow-duplicate", action="store_true")
    create.add_argument("--public", action="store_true")
    create.add_argument("--confirm-public", action="store_true")

    get = subparsers.add_parser("get", help="Fetch one owned Launch product profile")
    get.add_argument("--profile-uuid", required=True)

    update = subparsers.add_parser("update", help="Validate and update one owned Launch product profile")
    update.add_argument("--profile-uuid", required=True)
    update.add_argument("--input", required=True)
    update.add_argument("--visibility", choices=("public", "private"))
    update.add_argument("--confirm-public", action="store_true")

    delete = subparsers.add_parser("delete", help="Hard-delete one owned Profile after identity and Release checks")
    delete.add_argument("--profile-uuid", required=True)
    delete.add_argument("--expected-name")
    delete.add_argument("--expected-canonical-url")
    delete.add_argument("--confirm-delete", action="store_true")
    delete.add_argument("--confirm-delete-releases", action="store_true")

    return parser


def run(args: argparse.Namespace, client: LaunchProfileClient) -> dict[str, Any]:
    if args.command == "config-check":
        return {
            "succ": True,
            "configured": True,
            "base_url": client.config.base_url,
            "auth": "configured",
        }
    if args.command == "schema":
        return client.call("GET", "/api/launch_manifest/schema")
    if args.command == "list":
        return client.call("GET", "/api/launch_manifest/profiles")
    if args.command == "analyze":
        result = client.call("POST", "/api/launch_manifest/analyze", {"url": args.url})
        manifest = result.get("manifest")
        if args.output:
            if not isinstance(manifest, dict):
                raise ClientError("Analyze response did not contain a manifest", error_type="INVALID_RESPONSE")
            result["saved_manifest"] = _save_manifest(args.output, manifest)
        return result
    if args.command == "validate":
        return _validate(client, _load_manifest(args.input))
    if args.command == "create":
        if args.public and not args.confirm_public:
            raise ClientError(
                "Public creation requires both --public and --confirm-public",
                error_type="PUBLIC_CONFIRMATION_REQUIRED",
            )
        validated = _validate(client, _load_manifest(args.input))
        manifest = validated["manifest"]
        if not args.allow_duplicate:
            duplicate = _find_duplicate(client, manifest)
            if duplicate:
                raise ClientError(
                    "A Launch profile already exists for this canonical URL",
                    error_type="DUPLICATE_PROFILE",
                    details={"existing_profile": duplicate},
                )
        return client.call(
            "POST",
            "/api/launch_manifest/profiles",
            {"manifest": manifest, "is_public": bool(args.public)},
        )
    if args.command == "get":
        profile_uuid = parse.quote(str(args.profile_uuid), safe="")
        return client.call("GET", f"/api/launch_manifest/profiles/{profile_uuid}")
    if args.command == "update":
        if args.visibility == "public" and not args.confirm_public:
            raise ClientError(
                "Publishing requires --visibility public and --confirm-public",
                error_type="PUBLIC_CONFIRMATION_REQUIRED",
            )
        validated = _validate(client, _load_manifest(args.input))
        payload: dict[str, Any] = {"manifest": validated["manifest"]}
        if args.visibility:
            payload["is_public"] = args.visibility == "public"
        profile_uuid = parse.quote(str(args.profile_uuid), safe="")
        return client.call("PUT", f"/api/launch_manifest/profiles/{profile_uuid}", payload)
    if args.command == "delete":
        return _delete_profile(args, client)
    raise ClientError("Unsupported command")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = Config.from_environment()
        result = run(args, LaunchProfileClient(config))
        _emit(result)
        return 0
    except ApiError as exc:
        payload = {
            "succ": False,
            "error_type": exc.error_type,
            "error_msg": str(exc),
            "status": exc.status,
        }
        if exc.details is not None:
            payload["details"] = exc.details
        _emit(payload, stream=sys.stderr)
        return 2
    except ClientError as exc:
        payload = {"succ": False, "error_type": exc.error_type, "error_msg": str(exc)}
        if exc.details is not None:
            payload["details"] = exc.details
        _emit(payload, stream=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
