import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from launch_profile_mcp import server


class FakeResponse:
    def __init__(self, status_code: int, body: object):
        self.status_code = status_code
        self._body = body
        self.is_error = status_code >= 400

    def json(self) -> object:
        return self._body


class FakeAsyncClient:
    response = FakeResponse(200, {"succ": True})
    request_args: tuple | None = None
    request_kwargs: dict | None = None

    def __init__(self, **kwargs):
        self.options = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def request(self, *args, **kwargs):
        type(self).request_args = args
        type(self).request_kwargs = kwargs
        return type(self).response


class ConfigurationTests(unittest.TestCase):
    def test_default_api_base_url_is_production_consolex_origin(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(server._api_base_url(), "https://api.evalsone.com")
            self.assertEqual(
                server._api_url("/profiles"),
                "https://api.evalsone.com/api/launch_manifest/profiles",
            )

    def test_api_key_uses_authorization_bearer_header(self) -> None:
        headers = server._headers("eo-test-key")
        self.assertEqual(headers["Authorization"], "Bearer eo-test-key")
        self.assertNotIn("Blade-auth", headers)

    def test_http_never_falls_back_to_environment_key(self) -> None:
        with patch.dict(os.environ, {"CONSOLEX_API_KEY": "eo-server-owner"}, clear=True):
            with self.assertRaisesRegex(ValueError, "Authenticated HTTP request credentials"):
                server._api_key()

    def test_legacy_sse_cannot_bypass_request_authentication(self) -> None:
        with self.assertRaisesRegex(ValueError, "Only Streamable HTTP"):
            server.mcp.sse_app()

    def test_custom_base_url_must_be_an_https_origin(self) -> None:
        invalid_values = (
            "http://api.evalsone.com",
            "https://api.evalsone.com/api",
            "https://user:pass@api.evalsone.com",
            "https://api.evalsone.com?environment=test",
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with patch.dict(os.environ, {"CONSOLEX_API_BASE_URL": value}, clear=True):
                    with self.assertRaisesRegex(ValueError, "must be an HTTPS origin"):
                        server._api_base_url()

    def test_entrypoint_runs_only_streamable_http(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch.object(server.mcp, "run") as run:
            server.main()
        run.assert_called_once_with(transport="streamable-http")

    def test_old_stdio_configuration_is_rejected(self) -> None:
        with patch.dict(os.environ, {"LAUNCH_PROFILE_MCP_TRANSPORT": "stdio"}, clear=True):
            with self.assertRaisesRegex(ValueError, "Only Streamable HTTP"):
                server.main()

    def test_consolex_preset_requires_a_per_user_api_key(self) -> None:
        preset_path = Path(__file__).parents[1] / "examples" / "consolex-streamable-http-preset.json"
        preset = json.loads(preset_path.read_text(encoding="utf-8"))
        definition = preset["definition"]

        self.assertTrue(preset["force_key"])
        self.assertEqual(preset["trans_type"], "http")
        self.assertEqual(definition["Authorization"], "Bearer {{CONSOLEX_API_KEY}}")
        self.assertTrue(definition["http_url"].endswith("/mcp"))
        self.assertNotIn("env", definition)
        fields = preset["config_schema"]["fields"]
        self.assertEqual([field["key"] for field in fields], ["CONSOLEX_API_KEY"])
        self.assertTrue(fields[0]["required"])


class RequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_uses_default_url_and_api_key(self) -> None:
        FakeAsyncClient.response = FakeResponse(200, {"succ": True, "profiles": []})
        with (
            patch.object(server, "_api_key", return_value="eo-test-key"),
            patch.object(server.httpx, "AsyncClient", FakeAsyncClient),
        ):
            result = await server._request("GET", "/profiles")

        self.assertEqual(result, {"succ": True, "profiles": []})
        self.assertEqual(
            FakeAsyncClient.request_args,
            ("GET", "https://api.evalsone.com/api/launch_manifest/profiles"),
        )
        assert FakeAsyncClient.request_kwargs is not None
        self.assertEqual(
            FakeAsyncClient.request_kwargs["headers"]["Authorization"],
            "Bearer eo-test-key",
        )

    async def test_api_error_redacts_the_key(self) -> None:
        FakeAsyncClient.response = FakeResponse(
            401,
            {"error_msg": "invalid credential eo-secret-key"},
        )
        with (
            patch.object(server, "_api_key", return_value="eo-secret-key"),
            patch.object(server.httpx, "AsyncClient", FakeAsyncClient),
        ):
            with self.assertRaisesRegex(RuntimeError, r"invalid credential \[REDACTED\]"):
                await server._request("GET", "/profiles")


if __name__ == "__main__":
    unittest.main()
