# Launch Profile API reference

## Authentication

Authenticated endpoints receive the current user's ConsoleX API key as:

```text
Authorization: Bearer API_KEY_VALUE
```

The bundled client obtains the value from `CONSOLEX_API_KEY`. Never pass it as a command argument or print it. `CONSOLEX_API_BASE_URL` must be an HTTPS origin without a path, query, fragment, or embedded credentials.

## Endpoints used

| Operation | Method and path | Notes |
| --- | --- | --- |
| Schema | `GET /api/launch_manifest/schema` | Returns the current JSON schema. |
| Validate | `POST /api/launch_manifest/validate` | Normalizes and validates a manifest. |
| Analyze URL | `POST /api/launch_manifest/analyze` | Requires authentication. |
| List Profiles | `GET /api/launch_manifest/profiles` | Returns summaries owned by the authenticated user. |
| Create Profile | `POST /api/launch_manifest/profiles` | `is_public` defaults to `false`. |
| Get Profile | `GET /api/launch_manifest/profiles/{uuid}` | Requires ownership. |
| Update Profile | `PUT /api/launch_manifest/profiles/{uuid}` | Requires ownership. |
| Delete Profile | `DELETE /api/launch_manifest/profiles/{uuid}` | Hard-deletes the owned Profile and cascades to its Release Envelopes. |
| List Releases | `GET /api/launch_manifest/profiles/{uuid}/releases` | Used as the delete preflight. |

## Manifest input

`create`, `validate`, and `update` accept either a raw Launch Manifest or a response wrapper containing a top-level `manifest` object. The client validates through the API before every create or update.

An analyzed draft can be saved directly:

```bash
python3 scripts/launch_profile_api.py analyze --url 'https://example.com' --output .work/profile.json
```

## Visibility and duplication

- Creation is private unless both `--public` and `--confirm-public` are supplied.
- Updating without `--visibility` preserves the stored visibility.
- Publishing on update requires both `--visibility public` and `--confirm-public`.
- Creation checks the canonical URL against the current user's Profile list. Use `--allow-duplicate` only for an intentional duplicate.

## Delete safeguards

`delete` requires all of the following:

- `--profile-uuid`;
- `--confirm-delete` following an explicit user request;
- at least one identity assertion: `--expected-name` or `--expected-canonical-url`.

Both identity assertions are checked when both are supplied. The command refuses to mutate if either value differs from the Profile returned by the API.

The client lists Release Envelopes before deletion. A non-empty list requires the additional `--confirm-delete-releases` flag. A successful DELETE is followed by two checks: GET must return `404`, and the UUID must be absent from the Profile list.

## Errors

- `CONFIG_ERROR`: a required environment variable is missing or malformed.
- `401`: the API key is missing, inactive, invalid, or belongs to another environment.
- `404`: the route is disabled, the Profile does not belong to the authenticated user, or a deletion verification succeeded.
- `VALIDATION_ERROR` or `INVALID_MANIFEST`: correct the listed manifest fields.
- `DUPLICATE_PROFILE`: use the existing Profile or explicitly confirm duplication.
- `DELETE_CONFIRMATION_REQUIRED`: `--confirm-delete` was omitted.
- `DELETE_IDENTITY_REQUIRED`: neither expected name nor canonical URL was supplied.
- `DELETE_IDENTITY_MISMATCH`: an expected identity value differs from the stored Profile.
- `DELETE_RELEASES_CONFIRMATION_REQUIRED`: Release Envelopes exist and their deletion was not explicitly confirmed.
- `DELETE_FAILED`: the registry did not return `succ: true` for DELETE.
- `DELETE_VERIFICATION_FAILED`: the Profile remained readable or present in the list after DELETE.

The client emits JSON on stdout and structured errors on stderr. A nonzero exit code means the requested operation did not succeed.
