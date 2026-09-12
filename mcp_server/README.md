# Launch Operations Protocol MCP

This server exposes the Launch Operations Protocol registry API as MCP tools over Streamable HTTP or stdio. It is an API client and does not access the registry database directly.

## Configuration

```bash
export CONSOLEX_API_KEY="your-user-api-key"

# Optional; this is already the default.
export CONSOLEX_API_BASE_URL="https://api.evalsone.com"
export LAUNCH_PROFILE_MCP_HOST="127.0.0.1"
export LAUNCH_PROFILE_MCP_PORT="8765"
export LAUNCH_PROFILE_MCP_TRANSPORT="streamable-http"
```

Create or rotate the user-scoped key in ConsoleX Settings. The MCP sends it as `Authorization: Bearer <api-key>` and never uses the browser-only `Blade-auth` JWT header. Do not pass the key as a tool argument, save it in MCP configuration committed to source control, or expose it to MCP clients.

`CONSOLEX_API_BASE_URL` must be an HTTPS origin without a path. The MCP appends `/api/launch_manifest` itself. Override the default only for another compatible deployment.

## Run

```bash
python -m pip install -e mcp_server
launch-profile-mcp
```

The default transport is Streamable HTTP and its endpoint is `/mcp`. Set `LAUNCH_PROFILE_MCP_TRANSPORT=stdio` when a local MCP client or the ConsoleX MCP bridge launches one isolated process for the current user. `sse` is also accepted for compatibility. External mutations remain subject to the registry's authentication and authorization policy. Restart the MCP process after changing environment variables.

## ConsoleX per-user process mode

For the first multi-user rollout, run one stdio MCP process per ConsoleX user instead of sharing one HTTP process and one credential. ConsoleX already supports encrypted user-level MCP configuration and substitutes `{{CONSOLEX_API_KEY}}` in the MCP definition at invocation time.

Use [the preset template](examples/consolex-per-user-preset.json) as the admin-side starting point:

1. Replace the reserved `.example` `bridge_url` with the deployment's real ConsoleX MCP bridge URL.
2. Ensure `launch-profile-mcp` version `0.3.0` or newer is installed at the command path used by the bridge definition. The example uses `/home/azureuser/.local/bin/launch-profile-mcp`; replace it if the bridge image installs the entry point elsewhere. Pin the installed package or repository revision in production.
3. Register the MCP as a public preset with `force_key: true`. Do not put an author's API key in the definition.
4. Each user creates or reveals their own key in ConsoleX Settings and saves it in the MCP's `CONSOLEX_API_KEY` field. ConsoleX stores this configuration encrypted.
5. Attach the preset MCP to the Launch Agent. A user without a configured key must remain blocked from tool execution rather than falling back to the author or another user.

Process isolation is part of the security boundary. Do not reuse one spawned process across users, and do not put the API key in tool arguments, prompts, logs, or shared Agent data.
