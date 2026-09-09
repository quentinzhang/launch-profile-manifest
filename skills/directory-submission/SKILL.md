---
name: directory-submission
description: Prepare a directory-listing Browser Task from a Launch Profile Manifest and hand it to ConsoleX Web or a compatible local AI agent; use for reviewed browser prefills, never autonomous final submission.
---

# Directory Submission

Turn confirmed product facts into one self-contained Browser Task that a compatible browser runner can review and prefill.

## Boundary

- Read product facts from a Launch Profile Manifest. If none exists, use `collect-launch-profile` first or create and validate one before continuing.
- Select only target sites the user requested or that were checked recently enough for the current run. Do not present the example target as live.
- Target profiles contain data only: URLs, allowed hosts, selectors, field hints, and manual steps. Never include JavaScript, remote code, credentials, or arbitrary browser actions.
- The runner may store, open, and prefill. Login, captcha, uploads marked manual, payment, checkout, publish, and final submit stay with the user.

## Workflow

1. Confirm the Launch Profile has `provenance.confirmedByUser: true`. Do not invent missing prices, contact details, claims, assets, or launch dates.
2. Inspect each requested target's current submission path, eligibility, login/payment requirements, and visible fields. Treat old mappings as hints until rechecked.
3. Create a Site Target Profile for every target. Include `id`, `hosts`, an HTTP(S) `submissionUrl`, honest `fieldMappingStatus`, and selectors or field hints for a `mapped` task.
4. Build exactly one `directory_submission` task for the requested batch. Copy the required field values into `productProfile`; keep `profileRef` only as lineage.
5. Validate the task against Browser Task v0.1 before delivery.
6. Read [references/delivery.md](references/delivery.md), choose the route available in the current runtime, and verify either that ConsoleX rendered the action card or that Agent Inbox queued the task.
7. Report queued/prefilled status separately from final submission. Stop at every manual or irreversible step.

## Build and validate

The reference builder maps a confirmed Launch Profile and one or more Site Target Profiles into a portable task:

```bash
python skills/directory-submission/scripts/build_browser_task.py \
  --profile /absolute/path/to/launch-profile.json \
  --target /absolute/path/to/site-target-profile.json \
  --source-agent codex \
  --output /absolute/path/to/browser-task.json

python skills/collect-launch-profile/scripts/validate_documents.py \
  --browser-task /absolute/path/to/browser-task.json
```

When `--target` points to a catalogue object with a `profiles` array, the builder includes only entries explicitly marked `defaultSelected: true`; it never turns the whole catalogue into a batch implicitly.

Use `--release` when the task belongs to a specific Release Envelope. Use `--transport consolex-web` only when a JSON connector envelope is needed; the underlying Browser Task remains identical.

## Output quality

- Use Browser Task v0.1 at `mapped` or better for autofill delivery.
- Keep all targets in one `targets` array unless the user requested separate batches.
- `requiresConfirmation` must be `true`, and `requestedCapabilities` must include `store_task`.
- Keep the task self-contained. A runner must not need registry or network access to resolve `profileRef`.
- Do not claim completion when a task is merely generated, rendered, queued, opened, or prefilled.
