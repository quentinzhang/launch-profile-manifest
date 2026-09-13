# ConsoleX Launch Agent

Reference configuration for a ConsoleX agent that manages Launch Profiles and prepares human-reviewed AI directory submissions.

## Configure the agent

1. Copy [system-prompt.zh-CN.md](system-prompt.zh-CN.md) into the agent's system-instruction field. It contains standing operating rules, not a per-run user request.
2. Load [collect-launch-profile](../../skills/collect-launch-profile/SKILL.md) for product discovery and [directory-submission](../../skills/directory-submission/SKILL.md) for task building, validation, and delivery.
3. Attach the [hosted Streamable HTTP MCP preset](../../mcp_server/README.md#consolex-hosted-multi-tenant-preset) for registry access. Each user supplies their own API key through MCP user configuration; ConsoleX sends it in the request's Authorization header. Register a system-owned public preset with `force_key: true` so a shared Launch Agent uses its caller's configuration. The default registry API origin is `https://api.evalsone.com`.
4. Use [launch-profile-manager](../../skills/launch-profile-manager/SKILL.md) as an alternative registry client in environments that execute Skills with configured credentials. It is optional when MCP already supplies registry operations, and is not required for directory tasks from confirmed product facts.
5. Provide browsing tools for current directory checks and a compatible Python runtime with `jsonschema` for the reference validators. Attaching a Skill alone does not prove its scripts or delivery adapter are available.

Avoid mixing unrelated directory-submission Skills in the initial preset; these project Skills share the Browser Task contract and human-confirmation boundary.

ConsoleX Web must supply `Client Runtime Capabilities` from `clientCapabilities.sidekick` and support the `consolex-browser-task` card. The registry MCP does not supply browser connectivity. Missing capability context means unknown, and emitted card markup is not proof of rendering or delivery. Local Agent Inbox status is a separate route used by local coding agents only.

## User prompt examples

Use a concrete request as the user prompt; do not repeat the system instructions:

```text
根据这个产品网址创建一个私有 Launch Profile：[产品网址]。
优先读取已有资料，只询问必要的缺失信息；保存前让我确认新整理的文案。
```

```text
使用我已有的 [产品名称] Launch Profile，选择几个适合它的高优先级 AI 目录，
检查当前提交要求，并生成一批 Directory Submission Browser Task，交给 Sidekick。
```

```text
根据下面的产品说明创建目录提交任务，这次不用创建云端 Launch Profile：
[产品说明]
先整理并确认资料，再生成可通过 Sidekick 检查和预填的任务。
```

## Behavioral review before rollout

- Given a confirmed product document and no registry credentials, the agent can prepare a self-contained task without requiring a cloud Profile.
- Given `checking`, the agent does not announce a failed connection; given `unavailable`, it gives current-profile troubleshooting without claiming the extension is uninstalled.
- Given no card feedback, the agent reports generation and asks the user to add the task through the card rather than claiming queue success.
- Given a local CLI preflight failure, the builder keeps the task file and does not enqueue it.
- A delete request identifies the Profile and associated Releases before executing the explicitly authorized deletion.
- Final submission, payment, login, and CAPTCHA remain user steps.

These are review scenarios, not a statement that a deployed ConsoleX agent has passed them. Updating this repository does not update an existing agent's saved prompts, deployed frontend/backend, installed CLI, Native Host, or Chrome extension.
