"""CLI: diagnose X API account access, usage, and credit-related failures.

Reproduces the 402 "credits depleted" error on paid endpoints and reports
which calls still succeed. Run from the repo root:

    uv run python \\
      .abi/libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/scripts/XIntegration_diagnose_account.py

Requires ``X_BEARER_TOKEN`` in the environment or the X module enabled in
``config.yaml``. Each run is saved to object storage as both
``x/diagnostic/<timestamp>_diagnostic.md`` and
``x/diagnostic/<timestamp>_diagnostic.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import requests

from naas_abi_marketplace.applications.x.scripts._common import (
    DEFAULT_BASE_URL,
    get_bearer_token,
    save_diagnostic_report,
    token_fingerprint,
)

_RATE_LIMIT_HEADERS = (
    "x-rate-limit-limit",
    "x-rate-limit-remaining",
    "x-rate-limit-reset",
    "x-app-limit-24hour-limit",
    "x-app-limit-24hour-remaining",
    "x-app-limit-24hour-reset",
    "x-user-limit-24hour-limit",
    "x-user-limit-24hour-remaining",
    "x-user-limit-24hour-reset",
)


@dataclass
class ProbeResult:
    name: str
    method: str
    path: str
    status_code: int | None
    ok: bool
    rate_limits: dict[str, str] = field(default_factory=dict)
    body: Any = None
    error: str | None = None
    diagnosis: str | None = None


def _parse_body(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        text = response.text.strip()
        return text[:500] if text else None


def _extract_rate_limits(response: requests.Response) -> dict[str, str]:
    limits: dict[str, str] = {}
    for header in _RATE_LIMIT_HEADERS:
        value = response.headers.get(header)
        if value is not None:
            limits[header] = value
    return limits


def _probe(
    *,
    name: str,
    bearer_token: str,
    base_url: str,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
) -> ProbeResult:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Accept": "application/json",
    }
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params or {},
            timeout=30,
        )
    except requests.RequestException as exc:
        return ProbeResult(
            name=name,
            method=method,
            path=path,
            status_code=None,
            ok=False,
            error=str(exc),
            diagnosis="Network or TLS failure before X responded.",
        )

    body = _parse_body(response)
    result = ProbeResult(
        name=name,
        method=method,
        path=path,
        status_code=response.status_code,
        ok=response.ok,
        rate_limits=_extract_rate_limits(response),
        body=body,
    )
    result.diagnosis = _diagnose_probe(result)
    return result


def _diagnose_probe(result: ProbeResult) -> str:
    if result.error:
        return result.error

    status = result.status_code
    body = result.body if isinstance(result.body, dict) else {}

    if status == 402:
        detail = body.get("detail") if isinstance(body, dict) else None
        problem_type = body.get("type") if isinstance(body, dict) else None
        if detail == "credits depleted" or (
            isinstance(problem_type, str) and "credits-depleted" in problem_type
        ):
            return (
                "Account prepaid credits are exhausted. X blocks paid read/write "
                "endpoints until credits are purchased in the Developer Console."
            )
        return "Payment required — billing or credit issue on the developer account."

    if status == 401:
        return "Bearer token rejected — regenerate the App token in console.x.com."

    if status == 403:
        return "Forbidden — the app may lack product access for this endpoint."

    if status == 429:
        return "Rate limited — wait for the reset window and retry."

    if result.ok:
        return "OK"

    title = body.get("title") if isinstance(body, dict) else None
    detail = body.get("detail") if isinstance(body, dict) else None
    if title or detail:
        return " — ".join(part for part in (title, detail) if part)
    return f"Unexpected HTTP {status}."


def _sum_daily_usage(usage_payload: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    data = usage_payload.get("data") or {}
    daily = data.get("daily_project_usage") or {}
    entries = daily.get("usage") or []
    total = 0
    rows: list[dict[str, Any]] = []
    for entry in entries:
        raw = entry.get("usage")
        count = int(raw) if raw is not None else 0
        total += count
        rows.append({"date": entry.get("date"), "posts_consumed": count})
    rows.sort(key=lambda row: row.get("date") or "")
    return total, rows


def _build_summary(probes: list[ProbeResult], usage_probe: ProbeResult | None) -> dict[str, Any]:
    search = next((p for p in probes if p.name == "search_recent_tweets"), None)
    usage = usage_probe

    credits_depleted = any(
        p.status_code == 402
        and isinstance(p.body, dict)
        and (
            p.body.get("detail") == "credits depleted"
            or "credits-depleted" in str(p.body.get("type", ""))
        )
        for p in probes
    )

    if credits_depleted:
        headline = (
            "X API credits are depleted — paid endpoints (including "
            "tweets/search/recent) are blocked until you add credits."
        )
        remediation = [
            "Open https://console.x.com and sign in with the developer account that owns this app.",
            "Check Billing / Credits and purchase additional prepaid credits (pay-per-use model).",
            "Review Usage on the app to see monthly post consumption vs project_cap.",
            "Enable auto-recharge if you want uninterrupted access.",
            "Regenerating the bearer token will NOT fix this — the block is account-level.",
        ]
    elif search is not None and search.ok:
        headline = "X API search access looks healthy for this bearer token."
        remediation = []
    elif search is not None and search.status_code == 401:
        headline = "Bearer token is invalid or expired."
        remediation = [
            "In console.x.com → Projects & Apps → your app → Keys and tokens, regenerate the Bearer Token.",
            "Update X_BEARER_TOKEN in .env / secrets and restart services.",
        ]
    else:
        headline = "X API access is partially or fully blocked — see probe details below."
        remediation = [
            "Review each probe's status and diagnosis.",
            "Confirm the app has the required products enabled in console.x.com.",
        ]

    usage_summary: dict[str, Any] | None = None
    if usage is not None and usage.ok and isinstance(usage.body, dict):
        data = usage.body.get("data") or {}
        total, rows = _sum_daily_usage(usage.body)
        usage_summary = {
            "project_id": data.get("project_id"),
            "project_cap": data.get("project_cap"),
            "project_usage": data.get("project_usage"),
            "cap_reset_day": data.get("cap_reset_day"),
            "posts_consumed_in_window": total,
            "daily_project_usage": rows[-14:],
        }

    return {
        "headline": headline,
        "credits_depleted": credits_depleted,
        "remediation": remediation,
        "usage": usage_summary,
        "docs": {
            "pricing": "https://docs.x.com/x-api/getting-started/pricing",
            "usage_api": "https://docs.x.com/x-api/usage/introduction",
            "developer_console": "https://console.x.com",
        },
    }


def run_diagnosis(*, base_url: str = DEFAULT_BASE_URL, usage_days: int = 30) -> dict[str, Any]:
    bearer_token = get_bearer_token()
    probes: list[ProbeResult] = []

    usage_probe = _probe(
        name="usage_tweets",
        bearer_token=bearer_token,
        base_url=base_url,
        method="GET",
        path="usage/tweets",
        params={
            "days": usage_days,
            "usage.fields": ",".join(
                [
                    "cap_reset_day",
                    "daily_project_usage",
                    "project_cap",
                    "project_id",
                    "project_usage",
                ]
            ),
        },
    )
    probes.append(usage_probe)

    probes.extend(
        [
            _probe(
                name="get_user_by_username",
                bearer_token=bearer_token,
                base_url=base_url,
                method="GET",
                path="users/by/username/NASA",
                params={"user.fields": "id,name,username,public_metrics"},
            ),
            _probe(
                name="count_recent_tweets",
                bearer_token=bearer_token,
                base_url=base_url,
                method="GET",
                path="tweets/counts/recent",
                params={
                    "query": "python lang:en -is:retweet",
                    "granularity": "day",
                },
            ),
            _probe(
                name="search_recent_tweets",
                bearer_token=bearer_token,
                base_url=base_url,
                method="GET",
                path="tweets/search/recent",
                params={
                    "query": "python lang:en -is:retweet",
                    "max_results": 10,
                    "tweet.fields": "id,text,created_at",
                },
            ),
        ]
    )

    summary = _build_summary(probes, usage_probe)
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "token": token_fingerprint(bearer_token),
        "summary": summary,
        "probes": [asdict(probe) for probe in probes],
    }


def _format_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# X API account diagnosis",
        "",
        f"- **Checked at:** {report['checked_at']}",
        f"- **Base URL:** {report['base_url']}",
        f"- **Token:** {report['token']}",
        "",
        "## Summary",
        "",
        summary["headline"],
        "",
    ]

    usage = summary.get("usage")
    if usage:
        lines.extend(
            [
                "## Usage (GET /2/usage/tweets)",
                "",
                f"- **project_id:** {usage.get('project_id')}",
                f"- **project_cap:** {usage.get('project_cap')}",
                f"- **project_usage:** {usage.get('project_usage')}",
                f"- **cap_reset_day:** {usage.get('cap_reset_day')}",
                f"- **posts (window):** {usage.get('posts_consumed_in_window')}",
                "",
            ]
        )
        daily = usage.get("daily_project_usage") or []
        if daily:
            lines.append("### Recent daily usage")
            lines.append("")
            lines.append("| Date | Posts consumed |")
            lines.append("| --- | ---: |")
            for row in daily:
                date = (row.get("date") or "?")[:10]
                lines.append(f"| {date} | {row.get('posts_consumed', 0)} |")
            lines.append("")

    lines.extend(["## Endpoint probes", ""])
    for probe in report["probes"]:
        status = probe["status_code"] if probe["status_code"] is not None else "ERR"
        mark = "OK" if probe["ok"] else "FAIL"
        lines.append(
            f"### [{mark}] {probe['name']} — `{probe['method']} /2/{probe['path']}` → HTTP {status}"
        )
        lines.append("")
        if probe.get("diagnosis"):
            lines.append(probe["diagnosis"])
            lines.append("")
        if probe.get("rate_limits"):
            lines.append("Rate limits:")
            lines.append("")
            for key, value in probe["rate_limits"].items():
                lines.append(f"- `{key}`: {value}")
            lines.append("")
        if not probe["ok"] and probe.get("body"):
            body_text = json.dumps(probe["body"], ensure_ascii=False, indent=2)
            lines.extend(["Response body:", "", "```json", body_text, "```", ""])

    remediation = summary.get("remediation") or []
    if remediation:
        lines.extend(["## Suggested next steps", ""])
        for index, step in enumerate(remediation, start=1):
            lines.append(f"{index}. {step}")
        lines.append("")

    docs = summary.get("docs") or {}
    if docs:
        lines.extend(["## References", ""])
        for label, url in docs.items():
            lines.append(f"- **{label}:** {url}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _print_human_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("X API account diagnosis")
    print("=" * 72)
    print(f"Checked at : {report['checked_at']}")
    print(f"Base URL   : {report['base_url']}")
    print(f"Token      : {report['token']}")
    print()
    print(summary["headline"])
    print()

    usage = summary.get("usage")
    if usage:
        print("Usage (from GET /2/usage/tweets)")
        print("-" * 72)
        print(f"  project_id     : {usage.get('project_id')}")
        print(f"  project_cap    : {usage.get('project_cap')}")
        print(f"  project_usage  : {usage.get('project_usage')}")
        print(f"  cap_reset_day  : {usage.get('cap_reset_day')}")
        print(f"  posts (window) : {usage.get('posts_consumed_in_window')}")
        daily = usage.get("daily_project_usage") or []
        if daily:
            print("  recent daily usage:")
            for row in daily:
                print(f"    {row.get('date', '?')[:10]}  {row.get('posts_consumed', 0)} posts")
        print()

    print("Endpoint probes")
    print("-" * 72)
    for probe in report["probes"]:
        status = probe["status_code"] if probe["status_code"] is not None else "ERR"
        mark = "OK" if probe["ok"] else "FAIL"
        print(f"[{mark}] {probe['name']} — {probe['method']} /2/{probe['path']} → HTTP {status}")
        if probe.get("diagnosis"):
            print(f"       {probe['diagnosis']}")
        if probe.get("rate_limits"):
            for key, value in probe["rate_limits"].items():
                print(f"       {key}: {value}")
        if not probe["ok"] and probe.get("body"):
            body_text = json.dumps(probe["body"], ensure_ascii=False)
            if len(body_text) > 240:
                body_text = body_text[:240] + "…"
            print(f"       body: {body_text}")
        print()

    remediation = summary.get("remediation") or []
    if remediation:
        print("Suggested next steps")
        print("-" * 72)
        for index, step in enumerate(remediation, start=1):
            print(f"  {index}. {step}")
        print()

    docs = summary.get("docs") or {}
    if docs:
        print("References")
        print("-" * 72)
        for label, url in docs.items():
            print(f"  {label}: {url}")

    file_paths = report.get("file_paths")
    if file_paths:
        print()
        print("Saved to object storage:")
        print(f"  markdown: {file_paths['markdown']}")
        print(f"  json:     {file_paths['json']}")


def _persist_report(report: dict[str, Any]) -> dict[str, str]:
    markdown = _format_markdown_report(report)
    # JSON is saved from the report dict before file_paths are attached.
    payload = dict(report)
    payload.pop("file_paths", None)
    return save_diagnostic_report(markdown=markdown, report=payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose X API account access, usage, and credit errors."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full report as JSON instead of a human-readable summary.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"X v2 API base URL (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--usage-days",
        type=int,
        default=30,
        choices=range(1, 91),
        metavar="[1-90]",
        help="Days of usage history to request from GET /2/usage/tweets (default: 30).",
    )
    args = parser.parse_args(argv)

    try:
        report = run_diagnosis(base_url=args.base_url, usage_days=args.usage_days)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    try:
        report["file_paths"] = _persist_report(report)
    except Exception as exc:
        print(
            f"Warning: could not save diagnostic to object storage: {exc}",
            file=sys.stderr,
        )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_human_report(report)

    credits_depleted = report["summary"].get("credits_depleted")
    any_ok = any(probe["ok"] for probe in report["probes"])
    if credits_depleted:
        return 1
    if not any_ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
