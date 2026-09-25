"""Dynamic security checks against a running ABI API, reported as SARIF.

Subcommands:

  unauth-sweep   Call every GET route in the OpenAPI spec without credentials.
                 A 2xx answer means the route is reachable anonymously; each
                 one is either an intended public route (baseline it) or a
                 hole. A 5xx means anyone can make the server error.
  zap            Convert a ZAP JSON report (`-J`) to SARIF.
  junit          Convert a Schemathesis JUnit report to SARIF.

Output feeds `sarif_gate.py` like every other scanner. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree  # nosec B405

PLACEHOLDER_ID = "00000000-0000-0000-0000-000000000000"

_ZAP_RISK_TO_LEVEL = {"3": "error", "2": "warning", "1": "note", "0": "none"}


def sarif(tool: str, rules: dict[str, str], results: list[dict]) -> dict:
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": tool,
                        "rules": [
                            {"id": rule_id, "shortDescription": {"text": text}}
                            for rule_id, text in sorted(rules.items())
                        ],
                    }
                },
                "results": results,
            }
        ],
    }


def result(rule_id: str, level: str, message: str, uri: str) -> dict:
    return {
        "ruleId": rule_id,
        "level": level,
        "message": {"text": message},
        # Code scanning needs a file location; the route is the "file".
        "locations": [
            {"physicalLocation": {"artifactLocation": {"uri": uri.lstrip("/") or "/"}}}
        ],
    }


def fill_path_params(path: str) -> str:
    return re.sub(r"\{[^}]+\}", PLACEHOLDER_ID, path)


def get_routes(spec: dict) -> list[str]:
    return sorted(
        path
        for path, operations in spec.get("paths", {}).items()
        if "get" in operations
    )


def classify_status(status: int) -> tuple[str, str] | None:
    """Map an anonymous response status to (rule_id, level), or None if fine."""
    if 200 <= status < 300:
        return "unauthenticated-access", "error"
    if status >= 500:
        return "unauthenticated-server-error", "warning"
    return None


def _status(url: str, timeout: float) -> int | None:
    request = urllib.request.Request(url, method="GET")
    try:
        # Only the status line is read: streaming routes must not hang the sweep.
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None


def unauth_sweep(base_url: str, spec: dict, timeout: float = 10.0) -> dict:
    base = base_url.rstrip("/")
    results = []
    for path in get_routes(spec):
        status = _status(base + fill_path_params(path), timeout)
        verdict = classify_status(status) if status is not None else None
        if verdict is None:
            continue
        rule_id, level = verdict
        results.append(result(rule_id, level, f"GET {path} -> anonymous", path))
    rules = {
        "unauthenticated-access": "Route answers 2xx without credentials",
        "unauthenticated-server-error": "Route errors (5xx) for anonymous callers",
    }
    return sarif("abi-unauth-sweep", rules, results)


def zap_to_sarif(report: dict) -> dict:
    results, rules = [], {}
    for site in report.get("site", []) or []:
        for alert in site.get("alerts", []) or []:
            if str(alert.get("confidence")) == "0":  # ZAP: false positive
                continue
            rule_id = f"zap-{alert.get('pluginid', 'unknown')}"
            name = alert.get("alert") or alert.get("name") or rule_id
            rules[rule_id] = name
            level = _ZAP_RISK_TO_LEVEL.get(str(alert.get("riskcode")), "warning")
            for instance in alert.get("instances", []) or [{"uri": ""}]:
                path = urlparse(instance.get("uri", "")).path
                method = instance.get("method", "")
                results.append(
                    result(rule_id, level, f"{name} ({method} {path})", path)
                )
    return sarif("zap", rules, results)


def junit_to_sarif(tree: ElementTree.Element, tool: str) -> dict:
    results, rules = [], {}
    for case in tree.iter("testcase"):
        for failure in list(case.iter("failure")) + list(case.iter("error")):
            text = (failure.get("message") or failure.text or "").strip()
            operation = case.get("name", "unknown")
            first_line = text.splitlines()[0] if text else "failure"
            auth = "authentication" in text.lower() or "auth" in first_line.lower()
            rule_id = (
                f"{tool}-"
                + re.sub(r"[^a-z0-9]+", "-", first_line.lower()).strip("-")[:60]
            )
            rules[rule_id] = first_line
            level = "error" if auth else "warning"
            path = operation.split(" ", 1)[-1]
            results.append(result(rule_id, level, f"{operation}: {first_line}", path))
    return sarif(tool, rules, results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sweep = sub.add_parser("unauth-sweep")
    sweep.add_argument("--base-url", required=True)
    sweep.add_argument("--openapi", type=Path, required=True)
    sweep.add_argument("--output", type=Path, required=True)

    zap = sub.add_parser("zap")
    zap.add_argument("report", type=Path)
    zap.add_argument("--output", type=Path, required=True)

    junit = sub.add_parser("junit")
    junit.add_argument("report", type=Path)
    junit.add_argument("--tool", default="schemathesis")
    junit.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "unauth-sweep":
        document = unauth_sweep(args.base_url, json.loads(args.openapi.read_text()))
    elif args.command == "zap":
        document = zap_to_sarif(json.loads(args.report.read_text()))
    else:
        # The report is written by Schemathesis on this runner, not user input.
        tree = ElementTree.parse(args.report)  # nosec B314
        document = junit_to_sarif(tree.getroot(), args.tool)

    args.output.write_text(json.dumps(document, indent=2))
    print(
        f"{args.command}: {len(document['runs'][0]['results'])} result(s) -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
