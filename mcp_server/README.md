# Launch Operations Protocol MCP

Version 0.4.0 exposes the Launch registry API over **Streamable HTTP only** at `/mcp`. One hosted process serves multiple users. Each HTTP request must carry that user's ConsoleX API key in `Authorization: Bearer <user-api-key>`.

The MCP is a ConsoleX registry adapter. It accepts ConsoleX user API keys issued for the configured registry and forwards them only to that server-configured API origin. It is not a general OAuth authorization server and does not forward arbitrary third-party OAuth tokens.

## Server configuration

```bash
# Optional: this is already the default registry origin.
export CONSOLEX_API_BASE_URL="https://api.evalsone.com"
export LAUNCH_PROFILE_MCP_HOST="127.0.0.1"
export LAUNCH_PROFILE_MCP_PORT="8765"

python -m pip install -e mcp_server
launch-profile-mcp
```

Do not configure a shared `CONSOLEX_API_KEY` on this service: it is ignored. Only the authenticated HTTP request supplies the registry credential. The API origin must be HTTPS without a path, query, fragment, or embedded credentials; the service appends `/api/launch_manifest`. Restart after changing server configuration. Pin the package/repository revision in production.

Expose `/mcp` through the hosting platform's HTTPS endpoint and preserve the incoming Authorization header on every request, including initialize, tool discovery, notifications, and tool calls. If forwarding to the loopback listener, use the upstream Host with its port (for example `127.0.0.1:8765`) to match the SDK's default allowed hosts. Container deployments can set `LAUNCH_PROFILE_MCP_HOST=0.0.0.0` and restrict accepted public hosts at the ingress.

## Request authentication

- Missing, malformed, duplicate, or unresolved placeholder Authorization headers receive HTTP 401 before MCP dispatch.
- Each well-formed key is verified through authenticated `GET /api/launch_manifest/profiles`. The registry's 401/403 is returned as HTTP 401/403; verification outages or unexpected responses return HTTP 503. A key's format alone never proves its validity.
- Successful verification stores the key only in the current request scope. Tool handlers obtain it through the SDK's request context. Requests neither modify environment variables nor cache another user's identity.
- Each tool operation then calls the registry using the same key. The registry enforces ownership of Profiles and Releases. An operation-specific ownership denial is reported as an MCP tool error.
- Verification is intentionally uncached, so revocation takes effect on the next request. This currently adds one registry read per HTTP request, in addition to the tool's business operation.
- The transport is stateless. An old session ID, `X-User-Id`, or a server environment key cannot replace request credentials.
- Keys are redacted from registry results and errors. Configure hosting logs to exclude Authorization headers.

## ConsoleX hosted multi-tenant preset

Use [the preset template](examples/consolex-streamable-http-preset.json). ConsoleX uses `trans_type: "http"` for Streamable HTTP and a flat definition:

```json
{
  "http_url": "https://replace-with-hosted-launch-mcp.example/mcp",
  "Authorization": "Bearer {{CONSOLEX_API_KEY}}"
}
```

1. Deploy version 0.4.0 or later, then replace the reserved `.example` URL with its actual HTTPS MCP endpoint. The endpoint is distinct from the registry API origin; it does not point to the old MCP Bridge.
2. Register a **system-owned public preset** (`user_id: 0` in ConsoleX's stored MCP record) with `force_key: true` and the template's required `CONSOLEX_API_KEY` configuration field. Do not distribute it as an owner's private MCP attached to a shared Agent: that path can select the Agent owner's configuration.
3. Each user creates or retrieves their own key in ConsoleX Settings → API Access, then saves it in this MCP's user configuration. ConsoleX substitutes the placeholder and sends the resulting Authorization header. Never place a real key in the shared definition, tool arguments, or Agent prompt.
4. Attach the preset to the Launch Agent. A user without a configured key must be asked to configure it; do not fall back to the author. A Skill's environment does not automatically populate MCP user configuration.
5. Use initialize, tools/list, and a read-only list_profiles call to verify deployment. Test with two users to confirm each sees only their records and a missing/revoked key is rejected.

## Migration from 0.3.x

The fixed environment-key HTTP server and local stdio MCP mode have been removed. Remove old `command`, `args`, `env`, and `bridge_url` definitions and replace them with the HTTP preset above. Remove `LAUNCH_PROFILE_MCP_TRANSPORT`; a legacy non-HTTP value fails startup explicitly. Legacy SSE is also unsupported.

Local coding agents can use this HTTP endpoint or the independent [launch-profile-manager Skill](../skills/launch-profile-manager/SKILL.md), which retains its own environment-key configuration. Browser Task delivery through Agent Inbox is a separate feature and is unaffected.

## Verification

```bash
python -m unittest discover -s mcp_server/tests
```

Tests exercise the real ASGI/MCP request handling with a mocked registry: handshake, discovery, concurrent users, missing/invalid/revoked credentials, denial of cross-user records, unavailable verification, redaction, and rejection of environment fallback. They do not prove that a hosted deployment or its ConsoleX preset has been updated.

## Launch Agent integration

Use the [Launch Agent setup and prompt templates](../agents/consolex-launch-agent/README.md). The registry MCP manages Profiles and Releases; it does not detect Sidekick or deliver Browser Tasks. ConsoleX Web supplies current-profile connection context and renders task cards. Missing registry credentials need not block task preparation from confirmed product facts.
