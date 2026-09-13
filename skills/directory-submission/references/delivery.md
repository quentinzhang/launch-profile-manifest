# Browser Task delivery

Choose one route supported by the current environment. Skill installation alone does not prove that a delivery adapter is installed.

## ConsoleX Web

Read the current request's `Client Runtime Capabilities` context, supplied from `clientCapabilities.sidekick`. `connected` with `connected=true` means the current browser profile was reachable at detection time. `checking` is pending; `unknown` or missing context means unconfirmed; `unavailable` means currently unreachable, not necessarily uninstalled. This client-reported context is ephemeral and is not authentication or authorization. Do not invent a status MCP tool or claim a fresh check when the runtime provides no callable one.

For connection help, direct the user to Settings → Browser Sidekick → Check again, then check installation and enablement in the current Chrome profile and refresh the ConsoleX page after extension changes if needed. Use the platform's official Chrome Web Store link. Chrome is the supported distribution; do not introduce Edge setup or multi-profile selection. Web delivery does not use the local Agent Inbox CLI or require a Native Host.

Connection problems do not prevent product extraction or task generation. Preserve prepared tasks and explain that sending requires a working connection. The card checks connectivity again when the user sends it.

Emit one complete block outside Markdown code fences. Replace the JSON with the validated connector envelope produced by `--transport consolex-web`.

```text
<consolex-browser-task identifier="kebab-case-task-id" type="application/vnd.consolex.browser-task+json" title="Brief task title">
{"action":"sync_submission_task","payload":{"task":{}}}
</consolex-browser-task>
```

The task is received only after ConsoleX renders the card and the user chooses to add it to the extension. Do not describe emitted text alone as rendered or delivered. If rendering or sending feedback is not exposed to the agent, say the task has been generated and instruct the user to add it through the card; do not claim a successful queue operation.

## Compatible local agent

Save the bare Browser Task JSON, then use the ConsoleX Add-on's Agent Inbox CLI:

```bash
npm --prefix /absolute/path/to/consolex_addon run agent-inbox -- \
  status --require-connected

npm --prefix /absolute/path/to/consolex_addon run agent-inbox -- \
  add /absolute/path/to/browser-task.json --source codex

npm --prefix /absolute/path/to/consolex_addon run agent-inbox -- list --all
```

Replace `codex` and the Add-on path with the actual producer and installation. Never write directly into the inbox directory.

The status check is a freshness check for the one supported local Chrome Native Messaging transport. It does not enumerate browser profiles or ask the agent to choose between multiple Connectors. If it reports `waiting_for_sidekick` or `stale`, preserve the Browser Task JSON, show the CLI guidance, and stop before enqueueing by default. Open Browser Runner or reload Sidekick, then retry. A previously installed Native Host may need to be reinstalled once to gain heartbeat support.

A successful `add` means **queued for browser review**, not executed. `processed` means the extension imported the task; it still does not mean a form was submitted. Preserve the JSON and report the missing adapter if the CLI, Native Messaging host, or extension is unavailable.

## End-to-end route execution

If you want the skill to choose and execute a route in one step, use:

```bash
python skills/directory-submission/scripts/build_browser_task.py \
  --profile /absolute/path/to/launch-profile.json \
  --target /absolute/path/to/site-target-profile.json \
  --source-agent codex \
  --route auto \
  --deliver \
  --addon-path /absolute/path/to/consolex_addon \
  --output /absolute/path/to/browser-task.json
```

Use `--product-profile /absolute/path/to/reviewed-product-profile.json` instead of `--profile` when the product facts were extracted and confirmed locally. Delivery behavior is identical and no Launch Profile API is required.

`--route auto` prefers `agent-inbox` when `--addon-path` exists and points to a local ConsoleX Add-on checkout; otherwise it emits ConsoleX Web card output. When `--deliver` resolves to `agent-inbox`, the builder runs `status --require-connected` before `add` and leaves the generated task file intact if the preflight fails.

## Compatibility invariant

Both routes carry the same Browser Task object. Transport adapters may add an envelope or provenance, but must not weaken `requiresConfirmation`, request autonomous final submission, or remove manual steps.
