# MCP maintenance

- This package serves Streamable HTTP only. Authentication is per request; never use process-level `CONSOLEX_API_KEY` as a fallback or identity cache.
- Preserve stateless transport, request-scoped credentials, registry ownership checks, and redaction. Only the server config chooses the registry origin.
- ConsoleX presets use `trans_type: "http"`, flat `http_url`/`Authorization` definition fields, system ownership, and required user configuration with `force_key: true`.
- Run `python -m unittest discover -s mcp_server/tests` in an environment with this package installed. HTTP tests must cover interleaved users through the actual MCP transport, mocking only downstream registry I/O.
- Update README, preset examples, and Agent configuration guidance when changing authentication or startup. Repository tests are not hosted-deployment proof.
