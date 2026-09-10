from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import launch_profile_api as api  # noqa: E402


PROFILE_UUID = "a23ef15e-dd13-46f9-b870-be0bc8663839"
PROFILE_PATH = f"/api/launch_manifest/profiles/{PROFILE_UUID}"


def profile_response() -> dict[str, Any]:
    return {
        "succ": True,
        "profile": {
            "profile_uuid": PROFILE_UUID,
            "name": "huisheng.fm",
            "canonical_url": "https://huisheng.fm/",
            "revision": 1,
            "is_public": False,
            "checksum": "abc123",
            "manifest": {"product": {"canonicalUrl": "https://huisheng.fm/"}},
        },
    }


def delete_args(**overrides: Any) -> argparse.Namespace:
    values = {
        "command": "delete",
        "profile_uuid": PROFILE_UUID,
        "expected_name": "huisheng.fm",
        "expected_canonical_url": "https://huisheng.fm",
        "confirm_delete": True,
        "confirm_delete_releases": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class FakeClient:
    def __init__(self, responses: dict[tuple[str, str], list[Any]]):
        self.responses = responses
        self.calls: list[tuple[str, str, Any]] = []

    def call(self, method: str, path: str, payload: Any = None) -> dict[str, Any]:
        key = (method, path)
        self.calls.append((method, path, payload))
        if key not in self.responses or not self.responses[key]:
            raise AssertionError(f"Unexpected call: {key}")
        outcome = self.responses[key].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class DeleteProfileTests(unittest.TestCase):
    def test_requires_explicit_delete_confirmation_before_api_calls(self) -> None:
        client = FakeClient({})
        with self.assertRaises(api.ClientError) as raised:
            api.run(delete_args(confirm_delete=False), client)
        self.assertEqual(raised.exception.error_type, "DELETE_CONFIRMATION_REQUIRED")
        self.assertEqual(client.calls, [])

    def test_requires_expected_identity_before_api_calls(self) -> None:
        client = FakeClient({})
        with self.assertRaises(api.ClientError) as raised:
            api.run(delete_args(expected_name=None, expected_canonical_url=None), client)
        self.assertEqual(raised.exception.error_type, "DELETE_IDENTITY_REQUIRED")
        self.assertEqual(client.calls, [])

    def test_rejects_identity_mismatch_without_delete(self) -> None:
        client = FakeClient({("GET", PROFILE_PATH): [profile_response()]})
        with self.assertRaises(api.ClientError) as raised:
            api.run(delete_args(expected_name="Different Product"), client)
        self.assertEqual(raised.exception.error_type, "DELETE_IDENTITY_MISMATCH")
        self.assertEqual([call[0] for call in client.calls], ["GET"])

    def test_requires_separate_confirmation_when_releases_exist(self) -> None:
        client = FakeClient(
            {
                ("GET", PROFILE_PATH): [profile_response()],
                ("GET", f"{PROFILE_PATH}/releases"): [{"succ": True, "releases": [{"release_uuid": "r1"}]}],
            }
        )
        with self.assertRaises(api.ClientError) as raised:
            api.run(delete_args(), client)
        self.assertEqual(raised.exception.error_type, "DELETE_RELEASES_CONFIRMATION_REQUIRED")
        self.assertEqual(raised.exception.details["release_count"], 1)
        self.assertFalse(any(call[0] == "DELETE" for call in client.calls))

    def test_deletes_and_verifies_profile_with_no_releases(self) -> None:
        client = FakeClient(
            {
                ("GET", PROFILE_PATH): [
                    profile_response(),
                    api.ApiError(404, {"error_type": "NOT_FOUND", "error_msg": "Product profile not found"}),
                ],
                ("GET", f"{PROFILE_PATH}/releases"): [{"succ": True, "releases": []}],
                ("DELETE", PROFILE_PATH): [{"succ": True}],
                ("GET", "/api/launch_manifest/profiles"): [{"succ": True, "profiles": []}],
            }
        )

        result = api.run(delete_args(), client)

        self.assertTrue(result["succ"])
        self.assertTrue(result["verified_deleted"])
        self.assertEqual(result["deleted_release_count"], 0)
        self.assertEqual(result["deleted_profile"]["profile_uuid"], PROFILE_UUID)
        self.assertEqual(
            [(method, path) for method, path, _payload in client.calls],
            [
                ("GET", PROFILE_PATH),
                ("GET", f"{PROFILE_PATH}/releases"),
                ("DELETE", PROFILE_PATH),
                ("GET", PROFILE_PATH),
                ("GET", "/api/launch_manifest/profiles"),
            ],
        )

    def test_allows_confirmed_cascade_and_reports_release_count(self) -> None:
        client = FakeClient(
            {
                ("GET", PROFILE_PATH): [
                    profile_response(),
                    api.ApiError(404, {"error_type": "NOT_FOUND", "error_msg": "not found"}),
                ],
                ("GET", f"{PROFILE_PATH}/releases"): [
                    {"succ": True, "releases": [{"release_uuid": "r1"}, {"release_uuid": "r2"}]}
                ],
                ("DELETE", PROFILE_PATH): [{"succ": True}],
                ("GET", "/api/launch_manifest/profiles"): [{"succ": True, "profiles": []}],
            }
        )

        result = api.run(delete_args(confirm_delete_releases=True), client)

        self.assertEqual(result["deleted_release_count"], 2)

    def test_fails_when_deleted_profile_remains_readable(self) -> None:
        client = FakeClient(
            {
                ("GET", PROFILE_PATH): [profile_response(), profile_response()],
                ("GET", f"{PROFILE_PATH}/releases"): [{"succ": True, "releases": []}],
                ("DELETE", PROFILE_PATH): [{"succ": True}],
            }
        )
        with self.assertRaises(api.ClientError) as raised:
            api.run(delete_args(), client)
        self.assertEqual(raised.exception.error_type, "DELETE_VERIFICATION_FAILED")


if __name__ == "__main__":
    unittest.main()
