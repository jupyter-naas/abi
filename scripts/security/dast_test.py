import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from xml.etree import ElementTree  # nosec B405

import pytest
from dast import (
    PLACEHOLDER_ID,
    classify_status,
    fill_path_params,
    get_routes,
    junit_to_sarif,
    unauth_sweep,
    zap_to_sarif,
)

_STATUS_BY_PATH = {
    "/health": 200,
    "/api/me": 401,
    "/api/leaky": 200,
    f"/api/items/{PLACEHOLDER_ID}": 500,
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(_STATUS_BY_PATH.get(self.path, 404))
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def _spec(*paths: str, method: str = "get") -> dict:
    return {"paths": {path: {method: {}} for path in paths}}


def test_fill_path_params():
    assert (
        fill_path_params("/a/{id}/b/{x}") == f"/a/{PLACEHOLDER_ID}/b/{PLACEHOLDER_ID}"
    )


def test_get_routes_only_returns_get_operations():
    spec = {"paths": {"/a": {"get": {}}, "/b": {"post": {}}}}
    assert get_routes(spec) == ["/a"]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (200, ("unauthenticated-access", "error")),
        (204, ("unauthenticated-access", "error")),
        (401, None),
        (403, None),
        (404, None),
        (500, ("unauthenticated-server-error", "warning")),
    ],
)
def test_classify_status(status, expected):
    assert classify_status(status) == expected


def test_unauth_sweep_flags_anonymous_2xx_and_5xx(server):
    spec = _spec("/health", "/api/me", "/api/leaky", "/api/items/{item_id}")
    results = unauth_sweep(server, spec)["runs"][0]["results"]
    found = {
        (r["ruleId"], r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"])
        for r in results
    }
    assert found == {
        ("unauthenticated-access", "health"),
        ("unauthenticated-access", "api/leaky"),
        ("unauthenticated-server-error", "api/items/{item_id}"),
    }


def test_unauth_sweep_skips_unreachable_host():
    spec = _spec("/x")
    assert (
        unauth_sweep("http://127.0.0.1:9", spec, timeout=1)["runs"][0]["results"] == []
    )


def test_zap_to_sarif_maps_risk_and_drops_false_positives():
    report = {
        "site": [
            {
                "alerts": [
                    {
                        "pluginid": "40018",
                        "alert": "SQL Injection",
                        "riskcode": "3",
                        "confidence": "2",
                        "instances": [
                            {"uri": "http://127.0.0.1:1/api/q?x=1", "method": "GET"}
                        ],
                    },
                    {
                        "pluginid": "1",
                        "alert": "FP",
                        "riskcode": "3",
                        "confidence": "0",
                    },
                ]
            }
        ]
    }
    results = zap_to_sarif(report)["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "zap-40018"
    assert results[0]["level"] == "error"
    assert (
        results[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        == "api/q"
    )


def test_junit_to_sarif_marks_auth_failures_as_errors():
    # Literal fixture, not untrusted input.
    root = ElementTree.fromstring(  # nosec B314
        """<testsuites><testsuite>
        <testcase name="GET /api/a"><failure message="Server error">x</failure></testcase>
        <testcase name="GET /api/b"><failure message="API accepts requests without authentication"/></testcase>
        <testcase name="GET /api/c"/>
        </testsuite></testsuites>"""
    )
    results = junit_to_sarif(root, "schemathesis")["runs"][0]["results"]
    levels = {r["message"]["text"].split(":")[0]: r["level"] for r in results}
    assert levels == {"GET /api/a": "warning", "GET /api/b": "error"}
