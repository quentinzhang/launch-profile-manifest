# Product discovery guide

Ask progressively. A user should be able to start with a sentence, a document, or a URL.

## Minimum viable profile

Resolve these before producing a useful draft:

- Product name
- Product type
- Lifecycle stage
- What it does or is intended to do
- Primary intended audience
- At least one provenance source

Only `name`, `type`, and `stage` are schema-required product fields. The remaining questions improve usefulness and may remain unresolved for an early concept.

## High-impact optional information

Prioritize in this order:

1. Problem, outcome, positioning, and differentiation
2. Primary audience and use cases
3. Short and long descriptions in the user's working languages
4. Core features or contents
5. Availability, pricing, trial, and purchase links
6. Logo, screenshots, demo, social preview, and press kit
7. Support and social links
8. Verifiable claims and supporting evidence
9. Existing Schema.org, Web App Manifest, RSS, OpenAPI, llms.txt, or merchant feeds

## Source handling

- Conversation or form answers: `user_input`
- Product and marketing documents: `document`
- Public product pages: `website`
- App Store or Play Store: `app_store`
- Source repository: `github`
- Anything else: `other`

When sources disagree, expose the conflict and ask the user. Do not silently choose the more promotional version.

## Product type guidance

- Native, mobile, desktop, web apps, and SaaS: `SoftwareApplication`
- Paid downloadable or physical product: `Product`
- Consulting or managed operation: `Service`
- Newsletter or serial publication: `Periodical`
- Podcast: `PodcastSeries`
- Course: `Course`
- Community or membership organization: `Organization`
- Early concepts that do not fit cleanly: `Other`

Use `CreativeWork` for a bounded authored work that is not better represented by a more specific supported type.
