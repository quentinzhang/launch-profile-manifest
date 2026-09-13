import asyncio
import json
import os
import unittest
from unittest.mock import patch

import httpx

from launch_profile_mcp import server


class HttpAuthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Exercise the actual ASGI/MCP transport and request context, mocking only
        # the downstream registry. Each test gets a fresh SDK session manager.
        self.mcp = server.LaunchProfileMCP(
            "test", host="127.0.0.1", stateless_http=True, json_response=True,
        )
        self.mcp.tool()(server.list_profiles)
        self.mcp.tool()(server.get_profile)
        self.mcp_patch = patch.object(server, "mcp", self.mcp)
        self.mcp_patch.start()
        self.env_patch = patch.dict(os.environ, {"CONSOLEX_API_KEY": "eo-owner-must-not-be-used"}, clear=True)
        self.env_patch.start()
        self.app = self.mcp.streamable_http_app()
        self.started = asyncio.Event()
        self.stopped = asyncio.Event()

        async def lifespan():
            async with self.app.router.lifespan_context(self.app):
                self.started.set()
                await self.stopped.wait()

        self.lifespan_task = asyncio.create_task(lifespan())
        await self.started.wait()
        self.calls = []
        self.revoked = set()
        self.fail_registry = False
        real_client = httpx.AsyncClient
        self.client = real_client(
            transport=httpx.ASGITransport(app=self.app), base_url="http://127.0.0.1:8765",
            headers={"Accept": "application/json, text/event-stream"},
        )
        self.client_patch = patch.object(
            server.httpx, "AsyncClient",
            side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(self.registry), **kwargs),
        )
        self.client_patch.start()

    async def asyncTearDown(self):
        self.client_patch.stop()
        await self.client.aclose()
        self.stopped.set()
        await self.lifespan_task
        self.env_patch.stop()
        self.mcp_patch.stop()

    async def registry(self, request):
        key = request.headers.get("Authorization")
        self.calls.append((key, request.url.path))
        await asyncio.sleep(0.005 if key == "Bearer eo-user-a" else 0)
        if self.fail_registry:
            raise httpx.ConnectError("connection error with credential " + str(key))
        if key not in {"Bearer eo-user-a", "Bearer eo-user-b"} or key in self.revoked:
            return httpx.Response(401, json={"error_msg": "invalid " + str(key)})
        if request.url.path.endswith("/profiles"):
            return httpx.Response(200, json={"succ": True, "profiles": [{"name": key[-1]}]})
        if request.url.path.endswith("/private-a") and key == "Bearer eo-user-b":
            return httpx.Response(403, json={"error_msg": "not owned: eo-user-b"})
        return httpx.Response(200, json={"succ": True, "echo": key})

    async def rpc(self, method, key=None, params=None, headers=None):
        request_headers = headers if headers is not None else ({"Authorization": "Bearer " + key} if key else {})
        return await self.client.post("/mcp", headers=request_headers, json={
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params or {},
        })

    async def test_missing_and_malformed_keys_fail_before_mcp_or_registry(self):
        for headers in ({}, {"Authorization": "Basic bad"}, {"Authorization": "Bearer {{CONSOLEX_API_KEY}}"},
                        {"Authorization": "Bearer "}, [("Authorization", "Bearer eo-user-a"), ("Authorization", "Bearer eo-user-b")],
                        {"X-User-Id": "83"}):
            with self.subTest(headers=headers):
                response = await self.rpc("tools/list", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertIn("www-authenticate", response.headers)
        self.assertEqual(self.calls, [])

    async def test_valid_key_handshake_and_tool_discovery(self):
        initialized = await self.rpc("initialize", "eo-user-a", {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        })
        self.assertEqual(initialized.status_code, 200)
        listed = await self.rpc("tools/list", "eo-user-a")
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn("eo-user-a", listed.text)
        tools = listed.json()["result"]["tools"]
        self.assertEqual({tool["name"] for tool in tools}, {"list_profiles", "get_profile"})
        self.assertNotIn("api_key", json.dumps(tools))

    async def test_every_http_method_requires_credentials(self):
        for method in ("GET", "DELETE"):
            response = await self.client.request(method, "/mcp", headers={"Mcp-Session-Id": "previous-session"})
            self.assertEqual(response.status_code, 401)
        self.assertEqual(self.calls, [])

    async def test_stdio_cannot_be_started_directly(self):
        with self.assertRaisesRegex(ValueError, "Only Streamable HTTP"):
            await self.mcp.run_stdio_async()

    async def test_interleaved_users_keep_their_own_credentials(self):
        keys = ["eo-user-a", "eo-user-b"] * 5
        responses = await asyncio.gather(*[
            self.rpc("tools/call", key, {"name": "list_profiles", "arguments": {}})
            for key in keys
        ])
        for key, response in zip(keys, responses):
            self.assertEqual(response.status_code, 200)
            result = response.json()["result"]
            self.assertFalse(result.get("isError", False), result)
            body = json.loads(result["content"][0]["text"])
            self.assertEqual(body["profiles"], [{"name": key[-1]}])
        self.assertEqual(len(self.calls), 20)  # admission check + actual tool request
        self.assertNotIn("eo-owner", str(self.calls))
        self.assertEqual(os.environ["CONSOLEX_API_KEY"], "eo-owner-must-not-be-used")
        self.assertEqual((await self.rpc("tools/list")).status_code, 401)

    async def test_invalid_and_revoked_keys_are_rejected_on_each_request(self):
        self.assertEqual((await self.rpc("tools/list", "eo-invalid")).status_code, 401)
        self.assertEqual((await self.rpc("tools/list", "eo-user-a")).status_code, 200)
        self.revoked.add("Bearer eo-user-a")
        rejected = await self.rpc("tools/call", "eo-user-a", {"name": "list_profiles", "arguments": {}})
        self.assertEqual(rejected.status_code, 401)
        self.assertNotIn("eo-user-a", rejected.text)

    async def test_registry_unavailable_fails_closed_without_secrets(self):
        self.fail_registry = True
        response = await self.rpc("tools/list", "eo-user-a")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("eo-user-a", response.text)

    async def test_ownership_denial_and_key_redaction(self):
        denied = await self.rpc("tools/call", "eo-user-b", {"name": "get_profile", "arguments": {"profile_uuid": "private-a"}})
        result = denied.json()["result"]
        self.assertTrue(result["isError"])
        self.assertNotIn("eo-user-b", denied.text)
        self.assertIn("[REDACTED]", denied.text)
        allowed = await self.rpc("tools/call", "eo-user-a", {"name": "get_profile", "arguments": {"profile_uuid": "private-a"}})
        self.assertFalse(allowed.json()["result"].get("isError", False))
        self.assertNotIn("eo-user-a", allowed.text)
