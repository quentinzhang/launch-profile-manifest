# Launch Operations Protocol MCP

This server exposes the Launch Operations Protocol registry API as MCP tools over Streamable HTTP. It is an API client and does not access the registry database directly.

## Configuration

```bash
export CONSOLEX_API_KEY="your-user-api-key"

# Optional; this is already the default.
export CONSOLEX_API_BASE_URL="https://api.evalsone.com"
export LAUNCH_PROFILE_MCP_HOST="127.0.0.1"
export LAUNCH_PROFILE_MCP_PORT="8765"
```

Create or rotate the user-scoped key in ConsoleX Settings. The MCP sends it as `Authorization: Bearer <api-key>` and never uses the browser-only `Blade-auth` JWT header. Do not pass the key as a tool argument, save it in MCP configuration committed to source control, or expose it to MCP clients.

`CONSOLEX_API_BASE_URL` must be an HTTPS origin without a path. The MCP appends `/api/launch_manifest` itself. Override the default only for another compatible deployment.

## Run

```bash
python -m pip install -e mcp_server
launch-profile-mcp
```

The Streamable HTTP endpoint is `/mcp`. External mutations remain subject to the registry's authentication and authorization policy. Restart the MCP process after changing environment variables.
