from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP


API_BASE_URL = os.environ.get("LAUNCH_PROFILE_API_BASE_URL", "http://127.0.0.1:8000/api/launch_manifest").rstrip("/")
API_TOKEN = os.environ.get("LAUNCH_PROFILE_API_TOKEN", "")
AUTH_HEADER = os.environ.get("LAUNCH_PROFILE_AUTH_HEADER", "Blade-auth")

mcp = FastMCP(
    "Launch Profile Registry",
    instructions="Manage portable product profiles and their separate release envelopes. Never publish or submit externally without explicit authorization.",
    host=os.environ.get("LAUNCH_PROFILE_MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("LAUNCH_PROFILE_MCP_PORT", "8765")),
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)


def _headers() -> dict[str, str]:
    if not API_TOKEN:
        raise ValueError("LAUNCH_PROFILE_API_TOKEN is required")
    return {AUTH_HEADER: API_TOKEN, "Accept": "application/json"}


async def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(method, f"{API_BASE_URL}{path}", headers=_headers(), json=payload)
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Registry returned HTTP {response.status_code} without JSON") from exc
    if response.is_error:
        message = body.get("error_msg") if isinstance(body, dict) else None
        raise RuntimeError(message or f"Registry request failed with HTTP {response.status_code}")
    return body


@mcp.tool(description="List the authenticated user's product profiles.")
async def list_profiles() -> dict[str, Any]:
    return await _request("GET", "/profiles")


@mcp.tool(description="Get one product profile by registry UUID.")
async def get_profile(profile_uuid: str) -> dict[str, Any]:
    return await _request("GET", f"/profiles/{profile_uuid}")


@mcp.tool(description="Validate and save a new Launch Profile Manifest.")
async def create_profile(manifest: dict[str, Any], is_public: bool = False) -> dict[str, Any]:
    return await _request("POST", "/profiles", {"manifest": manifest, "is_public": is_public})


@mcp.tool(description="Replace an existing product profile after validation.")
async def update_profile(profile_uuid: str, manifest: dict[str, Any], is_public: bool | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"manifest": manifest}
    if is_public is not None:
        payload["is_public"] = is_public
    return await _request("PUT", f"/profiles/{profile_uuid}", payload)


@mcp.tool(description="Delete an owned product profile and its release envelopes.")
async def delete_profile(profile_uuid: str) -> dict[str, Any]:
    return await _request("DELETE", f"/profiles/{profile_uuid}")


@mcp.tool(description="List all release envelopes attached to a product profile.")
async def list_releases(profile_uuid: str) -> dict[str, Any]:
    return await _request("GET", f"/profiles/{profile_uuid}/releases")


@mcp.tool(description="Attach a validated Release Envelope to a product profile.")
async def create_release(profile_uuid: str, release: dict[str, Any]) -> dict[str, Any]:
    return await _request("POST", f"/profiles/{profile_uuid}/releases", {"release": release})


@mcp.tool(description="Get one release envelope by UUID.")
async def get_release(profile_uuid: str, release_uuid: str) -> dict[str, Any]:
    return await _request("GET", f"/profiles/{profile_uuid}/releases/{release_uuid}")


@mcp.tool(description="Replace an existing release envelope after validation.")
async def update_release(profile_uuid: str, release_uuid: str, release: dict[str, Any]) -> dict[str, Any]:
    return await _request("PUT", f"/profiles/{profile_uuid}/releases/{release_uuid}", {"release": release})


@mcp.tool(description="Delete one release envelope from an owned profile.")
async def delete_release(profile_uuid: str, release_uuid: str) -> dict[str, Any]:
    return await _request("DELETE", f"/profiles/{profile_uuid}/releases/{release_uuid}")


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
