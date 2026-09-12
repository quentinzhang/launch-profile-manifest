import os
from typing import Any, Literal, cast
from urllib.parse import quote, urlsplit

import httpx
from mcp.server.fastmcp import FastMCP


DEFAULT_API_BASE_URL = "https://api.evalsone.com"
API_BASE_URL_ENV = "CONSOLEX_API_BASE_URL"
API_KEY_ENV = "CONSOLEX_API_KEY"
LAUNCH_API_PREFIX = "/api/launch_manifest"
MCP_TRANSPORT_ENV = "LAUNCH_PROFILE_MCP_TRANSPORT"
DEFAULT_MCP_TRANSPORT = "streamable-http"
SUPPORTED_MCP_TRANSPORTS = {"stdio", "sse", "streamable-http"}

mcp = FastMCP(
    "Launch Operations Protocol",
    instructions="Manage portable product profiles and their separate release envelopes. Never publish or submit externally without explicit authorization.",
    host=os.environ.get("LAUNCH_PROFILE_MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("LAUNCH_PROFILE_MCP_PORT", "8765")),
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)


def _api_base_url() -> str:
    raw = str(os.environ.get(API_BASE_URL_ENV) or DEFAULT_API_BASE_URL).strip().rstrip("/")
    parsed = urlsplit(raw)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            f"{API_BASE_URL_ENV} must be an HTTPS origin without a path, query, credentials, or fragment"
        )
    return f"https://{parsed.netloc}"


def _headers() -> dict[str, str]:
    api_key = str(os.environ.get(API_KEY_ENV) or "").strip()
    if not api_key:
        raise ValueError(f"{API_KEY_ENV} is required")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "launch-operations-protocol-mcp/0.3",
    }


def _mcp_transport() -> Literal["stdio", "sse", "streamable-http"]:
    raw = str(os.environ.get(MCP_TRANSPORT_ENV) or DEFAULT_MCP_TRANSPORT).strip().lower()
    normalized = raw.replace("_", "-")
    if normalized not in SUPPORTED_MCP_TRANSPORTS:
        supported = ", ".join(sorted(SUPPORTED_MCP_TRANSPORTS))
        raise ValueError(f"{MCP_TRANSPORT_ENV} must be one of: {supported}")
    return cast(Literal["stdio", "sse", "streamable-http"], normalized)


def _api_url(path: str) -> str:
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("Launch API path must start with one slash")
    return f"{_api_base_url()}{LAUNCH_API_PREFIX}{path}"


def _redact(value: Any) -> Any:
    api_key = str(os.environ.get(API_KEY_ENV) or "").strip()
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and api_key:
        return value.replace(api_key, "[REDACTED]")
    return value


def _path_segment(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{label} is required")
    return quote(normalized, safe="")


async def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(method, _api_url(path), headers=_headers(), json=payload)
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Registry returned HTTP {response.status_code} without JSON") from exc
    body = _redact(body)
    if response.is_error:
        message = body.get("error_msg") if isinstance(body, dict) else None
        raise RuntimeError(message or f"Registry request failed with HTTP {response.status_code}")
    if not isinstance(body, dict):
        raise RuntimeError("Registry returned a non-object JSON response")
    return body


@mcp.tool(description="List the authenticated user's product profiles.")
async def list_profiles() -> dict[str, Any]:
    return await _request("GET", "/profiles")


@mcp.tool(description="Get one product profile by registry UUID.")
async def get_profile(profile_uuid: str) -> dict[str, Any]:
    return await _request("GET", f"/profiles/{_path_segment(profile_uuid, 'profile_uuid')}")


@mcp.tool(description="Validate and save a new Launch Profile Manifest.")
async def create_profile(manifest: dict[str, Any], is_public: bool = False) -> dict[str, Any]:
    return await _request("POST", "/profiles", {"manifest": manifest, "is_public": is_public})


@mcp.tool(description="Replace an existing product profile after validation.")
async def update_profile(profile_uuid: str, manifest: dict[str, Any], is_public: bool | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"manifest": manifest}
    if is_public is not None:
        payload["is_public"] = is_public
    return await _request("PUT", f"/profiles/{_path_segment(profile_uuid, 'profile_uuid')}", payload)


@mcp.tool(description="Delete an owned product profile and its release envelopes.")
async def delete_profile(profile_uuid: str) -> dict[str, Any]:
    return await _request("DELETE", f"/profiles/{_path_segment(profile_uuid, 'profile_uuid')}")


@mcp.tool(description="List all release envelopes attached to a product profile.")
async def list_releases(profile_uuid: str) -> dict[str, Any]:
    return await _request("GET", f"/profiles/{_path_segment(profile_uuid, 'profile_uuid')}/releases")


@mcp.tool(description="Attach a validated Release Envelope to a product profile.")
async def create_release(profile_uuid: str, release: dict[str, Any]) -> dict[str, Any]:
    return await _request(
        "POST",
        f"/profiles/{_path_segment(profile_uuid, 'profile_uuid')}/releases",
        {"release": release},
    )


@mcp.tool(description="Get one release envelope by UUID.")
async def get_release(profile_uuid: str, release_uuid: str) -> dict[str, Any]:
    return await _request(
        "GET",
        f"/profiles/{_path_segment(profile_uuid, 'profile_uuid')}/releases/"
        f"{_path_segment(release_uuid, 'release_uuid')}",
    )


@mcp.tool(description="Replace an existing release envelope after validation.")
async def update_release(profile_uuid: str, release_uuid: str, release: dict[str, Any]) -> dict[str, Any]:
    return await _request(
        "PUT",
        f"/profiles/{_path_segment(profile_uuid, 'profile_uuid')}/releases/"
        f"{_path_segment(release_uuid, 'release_uuid')}",
        {"release": release},
    )


@mcp.tool(description="Delete one release envelope from an owned profile.")
async def delete_release(profile_uuid: str, release_uuid: str) -> dict[str, Any]:
    return await _request(
        "DELETE",
        f"/profiles/{_path_segment(profile_uuid, 'profile_uuid')}/releases/"
        f"{_path_segment(release_uuid, 'release_uuid')}",
    )


def main() -> None:
    mcp.run(transport=_mcp_transport())


if __name__ == "__main__":
    main()
