# Launch Profile Manifest

Launch Profile Manifest (LPM) is an open, portable format for describing a product once and reusing that information across launch, listing, distribution, and agent workflows.

LPM separates two kinds of records:

- **Launch Profile Manifest** contains durable product identity, positioning, audience, offers, assets, claims, and provenance.
- **Release Envelope** describes one launch, relaunch, major release, integration, market entry, or distribution wave for a profile.

The specification is product-type neutral. A profile may represent an app, SaaS product, service, newsletter, podcast, open-source project, community, course, or another digital product.

## Status

This repository contains a **Draft v0.1 specification** and reference tooling. It is not yet an industry standard. Compatibility feedback and independent implementations are welcome.

## Repository layout

```text
spec/v0.1/                         JSON Schemas
examples/                          Valid example documents
openapi/                           Registry API contract
skills/collect-launch-profile/    Agent Skill for product discovery
mcp_server/                        Streamable HTTP MCP API client
```

## Design principles

1. Define stable product facts once; describe each release separately.
2. A website is an optional source, not a required starting point.
3. Preserve provenance and distinguish user-confirmed facts from inference.
4. Reuse existing standards through links and mappings rather than copying their complete documents.
5. Keep channel-specific fields in namespaced extensions or generated submission packs.
6. Keep publishing and external submissions human-controlled.

## Documents

- [Launch Profile Manifest schema](spec/v0.1/launch-profile-manifest.schema.json)
- [Release Envelope schema](spec/v0.1/release-envelope.schema.json)
- [Registry OpenAPI contract](openapi/launch-profile-registry.openapi.yaml)
- [Product discovery Agent Skill](skills/collect-launch-profile/SKILL.md)
- [Streamable HTTP MCP server](mcp_server/README.md)

## Quick validation

```bash
python skills/collect-launch-profile/scripts/validate_documents.py \
  --profile examples/saas-profile.json \
  --release examples/saas-release.json
```

The validation helper requires Python 3.10+ and `jsonschema`.

## Versioning

Draft releases use semantic versions. Additive optional fields may land in a minor version. A breaking meaning, required-field, or structural change requires a major version.

## License

MIT. See [LICENSE](LICENSE).
