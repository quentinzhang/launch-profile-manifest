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
        with patch.dict(os.environ, {"CONSOLEX_API_KEY": "eo-test-key"}, clear=True):
            headers = server._headers()
        self.assertEqual(headers["Authorization"], "Bearer eo-test-key")
        self.assertNotIn("Blade-auth", headers)

    def test_api_key_is_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "CONSOLEX_API_KEY is required"):
                server._headers()

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

    def test_transport_defaults_to_streamable_http(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(server._mcp_transport(), "streamable-http")

    def test_consolex_bridge_can_select_stdio_transport(self) -> None:
        with patch.dict(os.environ, {"LAUNCH_PROFILE_MCP_TRANSPORT": "stdio"}, clear=True):
            self.assertEqual(server._mcp_transport(), "stdio")

    def test_invalid_transport_is_rejected(self) -> None:
        with patch.dict(os.environ, {"LAUNCH_PROFILE_MCP_TRANSPORT": "websocket"}, clear=True):
            with self.assertRaisesRegex(ValueError, "must be one of"):
                server._mcp_transport()

    def test_consolex_preset_requires_a_per_user_api_key(self) -> None:
        preset_path = Path(__file__).parents[1] / "examples" / "consolex-per-user-preset.json"
        preset = json.loads(preset_path.read_text(encoding="utf-8"))
        definition = preset["definition"]

        self.assertTrue(preset["force_key"])
        self.assertEqual(definition["env"]["CONSOLEX_API_KEY"], "{{CONSOLEX_API_KEY}}")
        self.assertEqual(definition["env"]["LAUNCH_PROFILE_MCP_TRANSPORT"], "stdio")
        self.assertEqual(definition["env"]["CONSOLEX_API_BASE_URL"], "https://api.evalsone.com")
        fields = preset["config_schema"]["fields"]
        self.assertEqual([field["key"] for field in fields], ["CONSOLEX_API_KEY"])
        self.assertTrue(fields[0]["required"])


class RequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_uses_default_url_and_api_key(self) -> None:
        FakeAsyncClient.response = FakeResponse(200, {"succ": True, "profiles": []})
        with (
            patch.dict(os.environ, {"CONSOLEX_API_KEY": "eo-test-key"}, clear=True),
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
            patch.dict(os.environ, {"CONSOLEX_API_KEY": "eo-secret-key"}, clear=True),
            patch.object(server.httpx, "AsyncClient", FakeAsyncClient),
        ):
            with self.assertRaisesRegex(RuntimeError, r"invalid credential \[REDACTED\]"):
                await server._request("GET", "/profiles")


if __name__ == "__main__":
    unittest.main()
