# Launch Profile MCP

This server exposes a Launch Profile Registry API as MCP tools over Streamable HTTP. It is an API client and does not access the registry database directly.

## Configuration

```bash
export LAUNCH_PROFILE_API_BASE_URL="https://consolex.example/api/launch_manifest"
export LAUNCH_PROFILE_API_TOKEN="your-consolex-jwt"
export LAUNCH_PROFILE_MCP_HOST="127.0.0.1"
export LAUNCH_PROFILE_MCP_PORT="8765"
```

The token is sent through ConsoleX's `Blade-auth` header by default. Override `LAUNCH_PROFILE_AUTH_HEADER` for another compatible registry.

## Run

```bash
python -m pip install -e mcp_server
launch-profile-mcp
```

The Streamable HTTP endpoint is `/mcp`. External mutations remain subject to the registry's authentication and authorization policy.
