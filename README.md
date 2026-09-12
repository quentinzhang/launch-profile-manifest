# Launch Operations Protocol

Launch Operations Protocol (LOP) is an open protocol set for launch workflow coordination across launch planning, distribution channels, and agent workflows. The protocol's core profile layer is the `Launch Profile Manifest` (LPM), paired with `Release Envelope` and `Browser Task` records.

This repository keeps the original `launch-profile-manifest` package path for backwards compatibility, while presenting an umbrella identity for all related launch-operational artifacts.

The project separates three kinds of records:

- **Launch Profile Manifest** (core profile layer) contains durable product identity, positioning, audience, offers, assets, claims, and provenance.
- **Release Envelope** describes one launch, relaunch, major release, integration, market entry, or distribution wave for a profile.
- **Browser Task** is a self-contained, transport-neutral instruction for storing, opening, and prefilling one batch of browser work. It never authorizes final submission.

Draft specification site: <https://quentinzhang.github.io/launch-profile-manifest/>

The specification is product-type neutral. A profile may represent an app, SaaS product, service, newsletter, podcast, open-source project, community, course, or another digital product.

## Naming and migration note

Current canonical repository and package path remains `launch-profile-manifest` to preserve existing schema `$id` and `$ref` links in v0.1:

- `spec/v0.1/launch-profile-manifest.schema.json`
- `spec/v0.1/release-envelope.schema.json`
- `openapi/launch-profile-registry.openapi.yaml`

If the name is changed in the future, the migration should happen only after a stable domain is prepared for protocol identifiers (for example `protocol.consolex.ai`) and a version-aware path strategy is in place (e.g., keep current v0.1 IDs and introduce v0.2 canonical IDs on the new domain).

## Status

This repository contains a **Draft v0.1 specification** and reference tooling. It is not yet an industry standard. Compatibility feedback and independent implementations are welcome.

## Repository layout

```text
spec/v0.1/                         JSON Schemas
spec/browser-task/v0.1/            Browser Task and Site Target Profile schemas
examples/                          Valid example documents
openapi/                           Registry API contract
skills/collect-launch-profile/    Agent Skill for product discovery
skills/launch-profile-manager/    Agent Skill for authenticated registry management
skills/directory-submission/       Agent Skill for directory task creation
mcp_server/                        stdio / Streamable HTTP MCP API client
```

## Design principles

1. Define stable product facts once; describe each release separately.
2. A website is an optional source, not a required starting point.
3. Preserve provenance and distinguish user-confirmed facts from inference.
4. Reuse existing standards through links and mappings rather than copying their complete documents.
5. Keep channel-specific fields in namespaced extensions or generated submission packs.
6. Keep publishing and external submissions human-controlled.
7. Keep tasks self-contained; profile references provide lineage, not a runtime dependency.

## Documents

- [Launch Profile Manifest schema](spec/v0.1/launch-profile-manifest.schema.json)
- [Release Envelope schema](spec/v0.1/release-envelope.schema.json)
- [Browser Task v0.1](spec/browser-task/v0.1/README.md)
- [Registry OpenAPI contract](openapi/launch-profile-registry.openapi.yaml)
- [Product discovery Agent Skill](skills/collect-launch-profile/SKILL.md)
- [Launch Profile Manager Agent Skill](skills/launch-profile-manager/SKILL.md)
- [Directory submission Agent Skill](skills/directory-submission/SKILL.md)
- [Streamable HTTP MCP server](mcp_server/README.md)

## Quick validation

```bash
python skills/collect-launch-profile/scripts/validate_documents.py \
  --profile examples/saas-profile.json \
  --release examples/saas-release.json \
  --browser-task examples/directory-submission-task.json
```

The validation helper requires Python 3.10+ and `jsonschema`.

Build a Browser Task from a confirmed profile and one or more current Site Target Profiles:

```bash
python skills/directory-submission/scripts/build_browser_task.py \
  --profile examples/saas-profile.json \
  --target examples/directory-target-profile.json \
  --source-agent codex \
  --output /tmp/browser-task.json
```

Launch Profile Manager is optional. An agent can extract a reviewed local Product Profile packet from a document or conversational description and build the same Browser Task:

```bash
python skills/directory-submission/scripts/build_browser_task.py \
  --product-profile /absolute/path/to/reviewed-product-profile.json \
  --target examples/directory-target-profile.json \
  --source-agent codex \
  --output /tmp/browser-task.json
```

See the Skill's [Product Profile extraction guide](skills/directory-submission/references/profile-extraction.md) for canonical fields, evidence statuses, and confirmation rules.

For local compatible-agent delivery, include route and delivery flags:

```bash
python skills/directory-submission/scripts/build_browser_task.py \
  --profile examples/saas-profile.json \
  --target examples/directory-target-profile.json \
  --source-agent codex \
  --route agent-inbox \
  --deliver \
  --addon-path /absolute/path/to/consolex_addon \
  --output /tmp/browser-task.json
```

The example target uses the reserved `.example` domain and must not be treated as a live submission destination.

## Install an Agent Skill

After cloning the repository, an agent can read the skills directly. Agents supported by the open `skills` CLI can install the needed workflow with:

```bash
npx skills add quentinzhang/launch-profile-manifest \
  --skill directory-submission

npx skills add quentinzhang/launch-profile-manifest \
  --skill launch-profile-manager
```

The directory Skill creates a human-reviewed Browser Task; delivering it still requires a compatible ConsoleX Web or local Agent Inbox adapter. The manager Skill and MCP client call the authenticated ConsoleX Launch Manifest API with a user-scoped `CONSOLEX_API_KEY`. Both accept `CONSOLEX_API_BASE_URL`; the MCP defaults it to `https://api.evalsone.com`. For the initial ConsoleX multi-user rollout, the MCP supports a per-user stdio process mode through `LAUNCH_PROFILE_MCP_TRANSPORT=stdio`; see its [ConsoleX preset instructions](mcp_server/README.md#consolex-per-user-process-mode).

## Versioning

Draft releases use semantic versions. Additive optional fields may land in a minor version. A breaking meaning, required-field, or structural change requires a major version.

## License

MIT. See [LICENSE](LICENSE).
