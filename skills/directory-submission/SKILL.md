---
name: directory-submission
description: Turn a Launch Profile, structured product facts, or an unstructured product document into a reviewed directory-listing Browser Task, then deliver it to ConsoleX Web or a compatible local agent for browser prefill; never autonomously submit the final form.
---

# Directory Submission

Turn confirmed product facts into one self-contained Browser Task that a compatible browser runner can review and prefill. Launch Profile Manager is an optional persistence source, not a prerequisite.

## Choose the input path

- For a confirmed Launch Profile Manifest, use `--profile`.
- For already structured canonical fields, create a reviewed Product Profile packet and use `--product-profile`.
- For a document, pasted prose, transcript, or conversational description, read [references/profile-extraction.md](references/profile-extraction.md). Use the language model to extract a Product Profile packet, show uncertain or generated values to the user, and use `--product-profile` only after confirmation.

Do not require installation of Launch Profile Manager when the user has supplied enough product information locally. A local Product Profile is a task input snapshot; it does not create or update a ConsoleX Launch Profile unless the user separately asks for that.

## Boundary

- Accept product facts from either a confirmed Launch Profile Manifest or a confirmed local Product Profile packet.
- Select only target sites the user requested or that were checked recently enough for the current run. Do not present the example target as live.
- Target profiles contain data only: URLs, allowed hosts, selectors, field hints, and manual steps. Never include JavaScript, remote code, credentials, or arbitrary browser actions.
- The runner may store, open, and prefill. Login, captcha, uploads marked manual, payment, checkout, publish, and final submit stay with the user.

## Workflow

1. Resolve the product input. Confirm a Launch Profile through `provenance.confirmedByUser: true`, or confirm a local Product Profile through `confirmedByUser: true`. Never invent prices, contact details, claims, assets, URLs, or launch dates.
2. Inspect each requested target's current submission path, eligibility, login/payment requirements, and visible fields. Treat old mappings as hints until rechecked.
3. Create a Site Target Profile for every target. Include `id`, `hosts`, an HTTP(S) `submissionUrl`, honest `fieldMappingStatus`, selectors or field hints, and `requiredAutofillFields` for fields the current form requires.
4. Build exactly one `directory_submission` task for the requested batch. Copy the required field values into `productProfile`; keep `profileRef` only as lineage.
5. Validate the task against Browser Task v0.1 before delivery.
6. Read [references/delivery.md](references/delivery.md), choose the route available in the current runtime, and execute that route (`--route` + `--deliver`). Verify either that ConsoleX rendered the action card or that Agent Inbox queued the task.
7. Report queued/prefilled status separately from final submission. Stop at every manual or irreversible step.

## Build and validate

The reference builder maps a confirmed Launch Profile and one or more Site Target Profiles into a portable task:

```bash
python skills/directory-submission/scripts/build_browser_task.py \
  --profile /absolute/path/to/launch-profile.json \
  --target /absolute/path/to/site-target-profile.json \
  --source-agent codex \
  --output /absolute/path/to/browser-task.json

# Or build without Launch Profile Manager from a reviewed local Product Profile packet
python skills/directory-submission/scripts/build_browser_task.py \
  --product-profile /absolute/path/to/reviewed-product-profile.json \
  --target /absolute/path/to/site-target-profile.json \
  --source-agent codex \
  --output /absolute/path/to/browser-task.json

# Submit immediately to a selected route (recommended for local compatible agent runtime)
python skills/directory-submission/scripts/build_browser_task.py \
  --profile /absolute/path/to/launch-profile.json \
  --target /absolute/path/to/site-target-profile.json \
  --source-agent codex \
  --route agent-inbox \
  --deliver \
  --addon-path /absolute/path/to/consolex_addon \
  --output /absolute/path/to/browser-task.json

python skills/collect-launch-profile/scripts/validate_documents.py \
  --browser-task /absolute/path/to/browser-task.json
```

`--profile` and `--product-profile` are mutually exclusive. When `--target` points to a catalogue object with a `profiles` array, the builder includes only entries explicitly marked `defaultSelected: true`; it never turns the whole catalogue into a batch implicitly.

Use `--release` when the task belongs to a specific Release Envelope. Use `--transport consolex-web` only when a JSON connector envelope is needed; the underlying Browser Task remains identical.

## Output quality

- Use Browser Task v0.1 at `mapped` or better for autofill delivery.
- Keep all targets in one `targets` array unless the user requested separate batches.
- `requiresConfirmation` must be `true`, and `requestedCapabilities` must include `store_task`.
- Keep the task self-contained. A runner must not need registry or network access to resolve `profileRef`.
- Preserve extraction evidence under `extensions.ai.consolex.fieldEvidence` when the input came from unstructured text so the mapping remains auditable.
- Do not claim completion when a task is merely generated, rendered, queued, opened, or prefilled.
