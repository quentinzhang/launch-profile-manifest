import os
import re
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


DEFAULT_API_BASE_URL = "https://api.evalsone.com"
API_BASE_URL_ENV = "CONSOLEX_API_BASE_URL"
LAUNCH_API_PREFIX = "/api/launch_manifest"


class RequestAuthMiddleware:
    """Authenticate each HTTP request; keep credentials only in its ASGI scope."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        values = [v.decode("latin-1") for k, v in scope.get("headers", []) if k.lower() == b"authorization"]
        match = re.fullmatch(r"Bearer ([A-Za-z0-9._~+/-]+=*)", values[0], re.IGNORECASE) if len(values) == 1 else None
        if not match:
            await JSONResponse(
                {"error": "unauthorized", "message": "A user API key in Authorization: Bearer is required."},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="launch-profile-mcp"'},
            )(scope, receive, send)
            return

        api_key = match.group(1)
        try:
            # No credential cache: revoked keys must fail on the next request.
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                response = await client.get(_api_url("/profiles"), headers=_headers(api_key))
            if response.status_code in (401, 403):
                status = response.status_code
            elif response.status_code != 200 or response.json().get("succ") is not True:
                status = 503
            else:
                status = 200
        except (httpx.RequestError, ValueError, AttributeError):
            status = 503
        if status != 200:
            headers = {"WWW-Authenticate": 'Bearer realm="launch-profile-mcp"'} if status == 401 else {}
            await JSONResponse(
                {"error": "unauthorized" if status == 401 else "forbidden" if status == 403 else "authentication_unavailable"},
                status_code=status,
                headers=headers,
            )(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        state["launch_api_key"] = api_key
        try:
            await self.app(scope, receive, send)
        finally:
            state.pop("launch_api_key", None)


class LaunchProfileMCP(FastMCP):
    def streamable_http_app(self) -> Starlette:
        app = super().streamable_http_app()
        app.add_middleware(RequestAuthMiddleware)
        return app

    def sse_app(self, mount_path: str | None = None) -> Starlette:
        raise ValueError("Only Streamable HTTP is supported.")

    async def run_stdio_async(self) -> None:
        raise ValueError("Only Streamable HTTP is supported.")


mcp = LaunchProfileMCP(
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


def _api_key() -> str:
    try:
        request = mcp.get_context().request_context.request
    except ValueError:
        request = None
    if request is not None:
        api_key = request.scope.get("state", {}).get("launch_api_key")
        if not api_key:
            raise ValueError("Authenticated HTTP request credentials are required")
        return api_key
    raise ValueError("Authenticated HTTP request credentials are required")


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "launch-operations-protocol-mcp/0.4",
    }


def _api_url(path: str) -> str:
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("Launch API path must start with one slash")
    return f"{_api_base_url()}{LAUNCH_API_PREFIX}{path}"


def _redact(value: Any, api_key: str) -> Any:
    if isinstance(value, dict):
        return {key: _redact(item, api_key) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, api_key) for item in value]
    if isinstance(value, str) and api_key:
        return value.replace(api_key, "[REDACTED]")
    return value


def _path_segment(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{label} is required")
    return quote(normalized, safe="")


async def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    api_key = _api_key()
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            response = await client.request(method, _api_url(path), headers=_headers(api_key), json=payload)
    except httpx.RequestError:
        raise RuntimeError("Registry connection failed") from None
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Registry returned HTTP {response.status_code} without JSON") from exc
    body = _redact(body, api_key)
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
    legacy_transport = os.environ.get("LAUNCH_PROFILE_MCP_TRANSPORT", "streamable-http")
    if legacy_transport.strip().lower().replace("_", "-") != "streamable-http":
        raise ValueError("Only Streamable HTTP is supported; remove LAUNCH_PROFILE_MCP_TRANSPORT.")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
