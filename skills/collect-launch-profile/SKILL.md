---
name: collect-launch-profile
description: Collect product information from a founder, URLs, documents, or existing metadata and produce a validated Launch Profile Manifest; use for idea-stage through live products, not for publishing or submitting to external channels.
---

# Collect Launch Profile

Create a truthful, reusable Launch Profile Manifest without requiring a public website.

## Workflow

1. Establish the product stage and available sources. Accept conversation, pasted notes, uploaded documents, websites, app-store pages, repositories, feeds, and existing manifests.
2. Extract source-backed facts before asking questions. Record every material source in `provenance.sources`.
3. Read [references/discovery.md](references/discovery.md) and ask only for high-impact gaps. Do not force users to complete optional fields.
4. Separate facts, user claims, and inference:
   - Put factual product information in `product` only when sourced or confirmed.
   - Put measurable marketing statements in `claims` with evidence URLs when available.
   - Never invent prices, customers, traction, testimonials, availability, or launch dates.
5. Use a stable absolute URL as `id` when the user controls one. Otherwise generate a UUID URN. A canonical website is optional.
6. Set `provenance.confirmedByUser` to `false` until the user has reviewed the resulting profile.
7. Validate against `../../../spec/v0.1/launch-profile-manifest.schema.json` with `scripts/validate_documents.py` before presenting or saving it.
8. Present a compact review containing confirmed facts, unresolved gaps, and the manifest. Ask for confirmation before marking it confirmed or invoking a registry mutation.

Creating a Profile does not authorize publishing it, submitting it to a channel, or creating a Release Envelope.

## Release handoff

When the user requests a launch or release record, preserve the stable Profile and create a separate Release Envelope. Read the Release Envelope schema and validate both documents. Use the Profile's exact `id` as `profileId`.
