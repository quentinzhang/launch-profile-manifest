# Launch Profile Manifest

Launch Profile Manifest (LPM) is an open, portable format for describing a product once and reusing that information across launch, listing, distribution, and agent workflows. The repository also defines a draft Browser Task handoff and installable Agent Skills that turn confirmed profile facts into human-reviewed browser work.

The project separates three kinds of records:

- **Launch Profile Manifest** contains durable product identity, positioning, audience, offers, assets, claims, and provenance.
- **Release Envelope** describes one launch, relaunch, major release, integration, market entry, or distribution wave for a profile.
- **Browser Task** is a self-contained, transport-neutral instruction for storing, opening, and prefilling one batch of browser work. It never authorizes final submission.

Draft specification site: <https://quentinzhang.github.io/launch-profile-manifest/>

The specification is product-type neutral. A profile may represent an app, SaaS product, service, newsletter, podcast, open-source project, community, course, or another digital product.

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
mcp_server/                        Streamable HTTP MCP API client
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

The example target uses the reserved `.example` domain and must not be treated as a live submission destination.

## Install an Agent Skill

After cloning the repository, an agent can read the skills directly. Agents supported by the open `skills` CLI can install the needed workflow with:

```bash
npx skills add quentinzhang/launch-profile-manifest \
  --skill directory-submission

npx skills add quentinzhang/launch-profile-manifest \
  --skill launch-profile-manager
```

The directory Skill creates a human-reviewed Browser Task; delivering it still requires a compatible ConsoleX Web or local Agent Inbox adapter. The manager Skill calls an authenticated ConsoleX Launch Manifest API and requires `CONSOLEX_API_BASE_URL` plus a user-scoped `CONSOLEX_API_KEY` in the Skill environment.

## Versioning

Draft releases use semantic versions. Additive optional fields may land in a minor version. A breaking meaning, required-field, or structural change requires a major version.

## License

MIT. See [LICENSE](LICENSE).
