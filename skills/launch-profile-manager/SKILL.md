---
name: launch-profile-manager
description: Create, inspect, validate, update, and deliberately delete ConsoleX Launch product profiles through the Launch Manifest API. Use when managing a profile registry record or importing a product URL; authentication comes only from skill environment variables.
---

# Launch Profile Manager

Use the bundled client instead of composing `curl` commands. It reads authentication from the skill environment and never prints the API key.

## Configuration

- `CONSOLEX_API_BASE_URL`: ConsoleX API origin, such as `https://apidev.evalsone.com` or `https://api.evalsone.com`.
- `CONSOLEX_API_KEY`: the current user's ConsoleX API key, sent as `Authorization: Bearer <api-key>`.

Never ask the user to paste an API key into chat, pass it as a command argument, or save it in a file. If configuration is missing or authentication returns `401`, tell the user to create or rotate the key in ConsoleX Settings and update the Skill environment.

Run commands from this skill's root with `python3 scripts/launch_profile_api.py ...`. Keep analyzed drafts under `.work/`; the client restricts file access to the skill workspace.

## Create or update

Before creating a profile, list existing profiles. The client blocks duplicate canonical URLs unless `--allow-duplicate` is deliberately supplied. New profiles are private by default; publishing requires the user's explicit request and the matching confirmation flag.

```bash
python3 scripts/launch_profile_api.py config-check
python3 scripts/launch_profile_api.py list
python3 scripts/launch_profile_api.py analyze --url 'https://example.com' --output .work/profile.json
python3 scripts/launch_profile_api.py validate --input .work/profile.json
python3 scripts/launch_profile_api.py create --input .work/profile.json
python3 scripts/launch_profile_api.py get --profile-uuid PROFILE_UUID
python3 scripts/launch_profile_api.py update --profile-uuid PROFILE_UUID --input .work/profile.json
```

Use `--public --confirm-public` when explicitly creating a public profile. Use `--visibility public --confirm-public` or `--visibility private` when changing visibility; omitting `--visibility` preserves the current state.

## Delete

Deletion is a hard delete. It also deletes Release Envelopes attached to the Profile. Perform it only when the user explicitly asks to delete the identified Profile.

The client fetches the Profile first and refuses to delete unless at least one expected identity value matches. Prefer supplying both:

```bash
python3 scripts/launch_profile_api.py delete \
  --profile-uuid PROFILE_UUID \
  --expected-name 'Example Product' \
  --expected-canonical-url 'https://example.com/' \
  --confirm-delete
```

If the preflight finds Release Envelopes, reread their count to the user and add `--confirm-delete-releases` only when deletion of those records is also authorized. After deletion, the client verifies both that GET returns `404` and that the UUID is absent from the owned Profile list.

Report the affected `profile_uuid`, name, canonical URL, Release count, and deletion verification. Do not claim a mutation succeeded unless the API returns `succ: true` and the post-delete checks pass.

Read [references/launch-profile-api.md](references/launch-profile-api.md) for API paths, response semantics, and error handling.
