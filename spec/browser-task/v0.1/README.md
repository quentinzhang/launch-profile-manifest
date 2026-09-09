# Browser Task v0.1

Browser Task is an open, transport-neutral handoff from an AI agent to a browser runner. The producer decides what to submit and where; the runner stores the task, opens the selected target, and prefills supported fields.

**Status: Draft v0.1.** It is a compatibility target, not yet an industry standard.

## Relationship to Launch Profile

- A **Launch Profile Manifest** contains durable product facts.
- A **Release Envelope** describes one launch or distribution wave.
- A **Browser Task** copies the values needed for one run and may retain `profileRef` as lineage.

The task is self-contained. A browser runner must not need registry access or dereference `profileRef` in order to fill a form.

## Documents

- [browser-task.schema.json](browser-task.schema.json) — one task batch
- [site-target-profile.schema.json](site-target-profile.schema.json) — one reusable submission surface
- [directory-submission-task.json](../../../examples/directory-submission-task.json) — a complete example

## Conformance levels

| Level | Requirement | Runner behavior |
| --- | --- | --- |
| `invalid` | no usable HTTP(S) submission URL | reject this target |
| `navigable` | id, host and submission URL | open; generic field inference only |
| `mapped` | plus selectors or field hints | prefill using the mapping |
| `verified` | plus an honestly verified mapping status | prefill with higher confidence |

A producer should emit `mapped` or better. A consumer may accept `navigable`, but must report the degraded mapping.

## Safety boundary

A conforming runner may store, open, and prefill a task. It must not autonomously submit or publish, log in, solve a captcha, enter payment details, or complete checkout. `requiresConfirmation` is fixed to `true`; `manualFields` and `manualSteps` make human work explicit.

Target profiles are data, not executable programs. Selectors and text hints are allowed; JavaScript, remote code, and arbitrary action sequences are not.

## Transport bindings

The format does not require ConsoleX. Two bindings are verified by the reference implementation:

1. **Compatible local agent → Agent Inbox:** write the bare task JSON and enqueue it with the ConsoleX Add-on CLI.
2. **ConsoleX Web → Add-on:** wrap the same task in `sync_submission_task` and emit a `consolex-browser-task` action block.

Transport wrappers are not part of the Browser Task schema. See the [directory-submission delivery guide](../../../skills/directory-submission/references/delivery.md).

## Validation

```bash
python skills/collect-launch-profile/scripts/validate_documents.py \
  --browser-task examples/directory-submission-task.json
```

Validation checks the JSON Schema, URI formats, and the referenced Site Target Profile schema. Runtime compatibility should also be checked against the target browser runner before declaring a new adapter compatible.
