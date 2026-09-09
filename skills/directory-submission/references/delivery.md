# Browser Task delivery

Choose one route supported by the current environment. Skill installation alone does not prove that a delivery adapter is installed.

## ConsoleX Web

Emit one complete block outside Markdown code fences. Replace the JSON with the validated connector envelope produced by `--transport consolex-web`.

```text
<consolex-browser-task identifier="kebab-case-task-id" type="application/vnd.consolex.browser-task+json" title="Brief task title">
{"action":"sync_submission_task","payload":{"task":{}}}
</consolex-browser-task>
```

The task is received only after ConsoleX renders the card and the user chooses to add it to the extension. Do not describe emitted text alone as delivered.

## Compatible local agent

Save the bare Browser Task JSON, then use the ConsoleX Add-on's Agent Inbox CLI:

```bash
npm --prefix /absolute/path/to/consolex_addon run agent-inbox -- \
  add /absolute/path/to/browser-task.json --source codex

npm --prefix /absolute/path/to/consolex_addon run agent-inbox -- list --all
```

Replace `codex` and the Add-on path with the actual producer and installation. Never write directly into the inbox directory.

A successful `add` means **queued for browser review**, not executed. `processed` means the extension imported the task; it still does not mean a form was submitted. Preserve the JSON and report the missing adapter if the CLI, Native Messaging host, or extension is unavailable.

## Compatibility invariant

Both routes carry the same Browser Task object. Transport adapters may add an envelope or provenance, but must not weaken `requiresConfirmation`, request autonomous final submission, or remove manual steps.
