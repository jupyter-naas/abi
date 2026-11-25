"""Safety and attribution checks for the optional Settings measurement tool."""

import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path


def module(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(f"{name}.py")
    )
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


baseline = module("measure_settings")
fixture = module("settings_fixture")


class PrivacyTests(unittest.TestCase):
    def test_live_measurement_blocks_mutations_and_requires_sync_opt_in(self):
        allows = baseline.allows_live_request
        self.assertTrue(allows("GET", "/api/iam/admin/groups", False))
        self.assertTrue(allows("POST", "/api/auth/oidc/web-pass", False))
        self.assertFalse(allows("POST", "/api/agents/sync", False))
        self.assertTrue(allows("POST", "/api/agents/sync", True))
        for method, path in [
            ("DELETE", "/api/iam/admin/groups/g"),
            ("PATCH", "/api/auth/me"),
            ("POST", "/api/iam/admin/groups"),
            ("DELETE", "/api/web-pass"),
        ]:
            self.assertFalse(allows(method, path, True))

    def test_report_paths_never_include_origin_ids_or_query_values(self):
        url = "https://private.example/api/organizations/client-name/members/person@example.com?q=personal-text&scope=private-scope&token=secret"
        safe = baseline.endpoint(url)
        self.assertEqual(safe, "/api/organizations/{id}/members/{id}?q&scope&{param}")
        for private in [
            "private.example",
            "client-name",
            "person",
            "personal-text",
            "private-scope",
            "secret",
        ]:
            self.assertNotIn(private, safe)

    def test_request_signatures_distinguish_scopes_but_ignore_query_order(self):
        one = "/api/iam/admin/access?scope=first&limit=2"
        reordered = "/api/iam/admin/access?limit=2&scope=first"
        other = "/api/iam/admin/access?limit=2&scope=second"
        signature = baseline.request_signature
        self.assertEqual(
            signature("GET", one, b"run-one"), signature("GET", reordered, b"run-one")
        )
        self.assertNotEqual(
            signature("GET", one, b"run-one"), signature("GET", other, b"run-one")
        )
        self.assertNotEqual(
            signature("GET", one, b"run-one"), signature("GET", one, b"run-two")
        )

    def test_summary_does_not_treat_unavailable_runs_as_fast_successes(self):
        rows = [
            {
                "case": "test",
                "phase": "cold",
                "status": "ok",
                "useful_content_ms": 100,
                "api_calls": 4,
                "permission_calls": 2,
            },
            {"case": "test", "phase": "cold", "status": "unavailable"},
        ]
        summary = baseline.summary(rows)[0]
        self.assertEqual(summary["attempts"], 2)
        self.assertEqual(summary["successful"], 1)
        self.assertEqual(summary["median_useful_content_ms"], 100)

    def test_fixture_unknown_endpoints_fail_and_group_count_is_controlled(self):
        self.assertEqual(fixture.answer("/api/unknown", "GET", 5)[0], 501)
        status, body = fixture.answer("/api/iam/admin/groups", "GET", 30)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["items"]), 30)
        self.assertEqual(
            fixture.answer("/api/iam/admin/groups/missing", "GET", 30)[0], 404
        )


class RecorderTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_error_is_reported_without_private_exception_message(self):
        class Page:
            pass

        async def unavailable():
            raise baseline.BrowserError("secret in https://private.example/account")

        result = await baseline.sample(
            Page(),
            baseline.Recorder(),
            baseline.Case("test", "/account", "main"),
            "cold",
            unavailable,
            100,
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["useful_content_ms"])
        self.assertNotIn("secret", str(result))
        self.assertNotIn("private.example", str(result))

    async def test_response_after_navigation_belongs_to_its_original_sample(self):
        class Response:
            status = 200

        class Request:
            url = "http://localhost/api/iam/admin/access?scope=private"
            method = "GET"

            async def response(self):
                await asyncio.sleep(0)
                return Response()

            async def sizes(self):
                return {"responseBodySize": 42}

        recorder = baseline.Recorder()
        old, new = [], []
        recorder.active = old
        request = Request()
        recorder.started(request)
        recorder.active = new
        await recorder.finish(request)
        self.assertEqual(len(old), 1)
        self.assertEqual(new, [])
        self.assertEqual(old[0]["status"], 200)
        self.assertEqual(old[0]["body_bytes"], 42)
        self.assertNotIn("private", str(old))


if __name__ == "__main__":
    unittest.main()
