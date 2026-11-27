#!/usr/bin/env python3
"""Measure Settings browser navigation without exporting page data or credentials."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import secrets
import statistics
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from importlib.metadata import version
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

try:
    from playwright.async_api import Error as BrowserError
except ImportError:

    class BrowserError(Exception):
        """Optional browser dependency is absent."""


@dataclass(frozen=True)
class Case:
    name: str
    path: str
    ready: str
    probe: str | None = None


def cases(org: str, workspace: str) -> list[Case]:
    org, workspace = quote(org, safe=""), quote(workspace, safe="")
    return [
        Case(
            "platform_groups",
            "/settings/access/groups",
            'table[aria-label="Groups"]',
            'input[aria-label="Search groups"]',
        ),
        Case(
            "organization_general",
            f"/organizations/{org}/settings/general",
            "#org-name",
            "#org-name",
        ),
        Case("workspace_agents", f"/workspace/{workspace}/settings/agents", "table"),
        Case(
            "account_profile",
            "/account/profile",
            ".account-profile-form-grid",
            ".account-profile-form-grid input",
        ),
        Case(
            "account_appearance",
            "/account/appearance",
            ".account-appearance-theme-grid",
        ),
    ]


SAFE_SEGMENTS = frozenset(
    [
        "api",
        "auth",
        "oidc",
        "session",
        "me",
        "web-pass",
        "tenant",
        "organizations",
        "workspaces",
        "analytics",
        "access",
        "iam",
        "admin",
        "groups",
        "policies",
        "capabilities",
        "resources",
        "attachments",
        "members",
        "domains",
        "agents",
        "sync",
        "providers",
        "available",
        "models",
        "servers",
        "skills",
        "configuration",
        "offer",
        "feature-access",
        "jobs",
        "failures",
        "system",
        "health",
        "events",
        "collect",
        "tracking",
        "pageview",
        "page-view",
        "presence",
        "status",
        "branding",
        "background-image",
        "chat",
        "conversations",
    ]
)


def endpoint(url: str) -> str:
    """Allowlist static route words: ids, emails, search text and query values never leave."""
    parsed = urlsplit(url)
    path = "/".join(
        p if p in SAFE_SEGMENTS else "{id}" for p in parsed.path.split("/") if p
    )
    keys = sorted(
        {
            k if k in {"scope", "workspace_id", "limit", "after", "q"} else "{param}"
            for k, _ in parse_qsl(parsed.query)
        }
    )
    return f"/{path}" + ("?" + "&".join(keys) if keys else "")


def request_signature(method: str, url: str, salt: bytes) -> str:
    parsed = urlsplit(url)
    canonical = parsed.path + "?" + urlencode(sorted(parse_qsl(parsed.query)))
    return hmac.new(
        salt, f"{method} {parsed.netloc}{canonical}".encode(), hashlib.sha256
    ).hexdigest()[:16]


class Recorder:
    def __init__(self):
        self.active: list[dict] | None = None
        self.pending: dict[object, tuple[list[dict], dict, float]] = {}
        self.tasks: set[asyncio.Task] = set()
        self.salt = secrets.token_bytes(32)
        self.last_started = 0.0

    def started(self, request) -> None:
        if self.active is None or not urlsplit(request.url).path.startswith("/api/"):
            return
        row = {
            "endpoint": endpoint(request.url),
            "method": request.method,
            "signature": request_signature(request.method, request.url, self.salt),
            "permission": urlsplit(request.url).path.endswith(
                ("/access", "/admin/me", "/admin/ping")
            ),
            "status": None,
            "duration_ms": None,
            "body_bytes": None,
        }
        self.active.append(row)
        self.last_started = time.perf_counter()
        self.pending[request] = (self.active, row, self.last_started)

    def finished(self, request) -> None:
        task = asyncio.create_task(self.finish(request))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def finish(self, request) -> None:
        found = self.pending.pop(request, None)
        if found is None:
            return
        _, row, started = found
        row["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        response = await request.response()
        row["status"] = response.status if response else None
        try:
            size = (await request.sizes())["responseBodySize"]
            row["body_bytes"] = size if size >= 0 else None
        except BrowserError:
            row["body_bytes"] = None  # Failed/intercepted requests may have no sizes.

    async def settle(self, max_ms: int = 3000) -> None:
        deadline = time.perf_counter() + max_ms / 1000
        while time.perf_counter() < deadline:
            if not self.pending and time.perf_counter() - self.last_started > 0.25:
                break
            await asyncio.sleep(0.05)
        if self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)


async def link(page, path: str, timeout: int) -> None:
    await page.locator(f'a[href="{path}"]:visible').first.click(timeout=timeout)


async def sample(
    page, recorder: Recorder, case: Case, phase: str, action, timeout: int
) -> dict:
    requests: list[dict] = []
    recorder.active = requests
    started = time.perf_counter()
    result = {
        "case": case.name,
        "phase": phase,
        "status": "ok",
        "useful_content_ms": None,
        "requests": requests,
        "heap_bytes": None,
    }
    try:
        await action()
        await page.wait_for_url(
            lambda url: urlsplit(url).path == case.path, timeout=timeout
        )
        await page.locator(case.ready).first.wait_for(state="visible", timeout=timeout)
        await page.evaluate(
            "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        result["useful_content_ms"] = round((time.perf_counter() - started) * 1000, 2)
        await recorder.settle()
        result["heap_bytes"] = await page.evaluate(
            "() => performance.memory?.usedJSHeapSize ?? null"
        )
    except BrowserError as exc:
        result["status"] = "unavailable"
        result["reason"] = type(
            exc
        ).__name__  # Exception messages can contain private URLs/DOM.
    finally:
        recorder.active = None
    result["api_calls"] = len(requests)
    result["permission_calls"] = sum(row["permission"] for row in requests)
    counts = Counter(row["signature"] for row in requests)
    result["repeated_requests"] = sum(count - 1 for count in counts.values())
    result["incomplete_requests"] = sum(row["duration_ms"] is None for row in requests)
    if result["status"] == "ok" and any(
        row["status"] is not None and row["status"] >= 500 for row in requests
    ):
        result["status"] = "partial"
        result["reason"] = "api_server_error_or_missing_fixture"
    return result


SCROLL = """() => {
  const nodes = [...document.querySelectorAll('.org-settings-layout-main, .org-settings-layout-content')];
  const node = nodes.find(n => n.scrollHeight > n.clientHeight + 20);
  return node ? {node, max: node.scrollHeight - node.clientHeight} : null;
}"""


async def prepare_state(page, case: Case) -> dict:
    probe = page.locator(case.probe).first if case.probe else None
    typed = probe is not None and await probe.count() > 0 and await probe.is_editable()
    if typed:
        await probe.fill("settings-baseline-probe")
    offset = await page.evaluate(
        f"() => {{ const s = ({SCROLL})(); if (!s) return null; s.node.scrollTop = Math.min(100, s.max); return s.node.scrollTop; }}"
    )
    return {"typed": typed, "scroll": offset}


async def check_state(page, case: Case, before: dict) -> dict:
    draft = None
    if before["typed"]:
        probe = page.locator(case.probe).first
        draft = (
            await probe.input_value() == "settings-baseline-probe"
            if await probe.count()
            else False
        )
    offset = await page.evaluate(
        f"() => {{ const s = ({SCROLL})(); return s?.node.scrollTop ?? null; }}"
    )
    return {
        "input_preserved": draft,
        "scroll_preserved": None
        if before["scroll"] is None
        else offset is not None and abs(offset - before["scroll"]) < 2,
    }


def summary(samples: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in samples:
        grouped[(row["case"], row["phase"])].append(row)
    output = []
    for (case, phase), rows in grouped.items():
        good = [r for r in rows if r["status"] == "ok"]
        output.append(
            {
                "case": case,
                "phase": phase,
                "attempts": len(rows),
                "successful": len(good),
                "median_useful_content_ms": statistics.median(
                    r["useful_content_ms"] for r in good
                )
                if good
                else None,
                "median_api_calls": statistics.median(r["api_calls"] for r in good)
                if good
                else None,
                "median_permission_calls": statistics.median(
                    r["permission_calls"] for r in good
                )
                if good
                else None,
            }
        )
    return output


def source_revision() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def working_tree_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout)


def allows_live_request(method: str, path: str, allow_agent_sync: bool) -> bool:
    if method in {"GET", "HEAD", "OPTIONS"}:
        return True
    handshake = path in {"/api/web-pass", "/api/auth/oidc/web-pass"}
    sync = allow_agent_sync and path == "/api/agents/sync"
    return method == "POST" and (handshake or sync)


async def run(args) -> dict:
    report = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "source_revision": source_revision(),
        "working_tree_dirty": await asyncio.to_thread(working_tree_dirty),
        "environment": args.environment,
        "viewport": {"width": 1440, "height": 900},
        "mode": "fixture" if args.fixture else "authenticated",
        "samples_per_case": args.runs,
        "browser": None,
        "samples": [],
        "summary": [],
        "conditions": {
            "browser_http_cache": "disabled by Playwright request interception; router/module state remains on revisit",
            "cold": "fresh browser context; server/build caches are not cleared",
            "revisit": "real Settings link after a cross-level/sibling detour",
            "fixture_delay_ms": args.fixture_delay_ms if args.fixture else None,
            "fixture_groups": args.fixture_groups if args.fixture else None,
            "heap": "Chromium reported JS heap, not total tab/process memory",
            "api_window": "navigation until content ready plus API quiet (250 ms), capped at 3 s",
        },
    }
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        report.update(status="unavailable", reason="playwright_not_installed")
        return report
    from settings_fixture import ORG_ID, WORKSPACE_ID, install

    selected = cases(
        ORG_ID if args.fixture else args.organization_id,
        WORKSPACE_ID if args.fixture else args.workspace_id,
    )
    if args.case:
        selected = [case for case in selected if case.name in args.case]
    stage = "browser_launch"
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                executable_path=args.browser_executable,
            )
            report["browser"] = browser.version
            report["playwright_version"] = version("playwright")
            stage = "navigation"
            for case in selected:
                for iteration in range(args.runs):
                    context = await browser.new_context(
                        viewport={"width": 1440, "height": 900},
                        storage_state=args.storage_state,
                    )
                    if args.fixture:
                        await install(
                            context,
                            args.base_url,
                            delay_ms=args.fixture_delay_ms,
                            group_count=args.fixture_groups,
                        )
                    else:

                        async def safe_reads(route):
                            request = route.request
                            path = urlsplit(request.url).path
                            if not allows_live_request(
                                request.method, path, args.allow_agent_sync
                            ):
                                await route.abort()
                            else:
                                await route.continue_()

                        await context.route("**/api/**", safe_reads)
                    page = await context.new_page()
                    recorder = Recorder()
                    page.on("request", recorder.started)
                    page.on("requestfinished", recorder.finished)
                    page.on("requestfailed", recorder.finished)
                    cold = await sample(
                        page,
                        recorder,
                        case,
                        "cold",
                        partial(
                            page.goto,
                            args.base_url + case.path,
                            timeout=args.timeout_ms,
                        ),
                        args.timeout_ms,
                    )
                    cold["iteration"] = iteration + 1
                    report["samples"].append(cold)
                    if cold["status"] == "ok":
                        before = await prepare_state(page, case)
                        detour = (
                            cases("", "")[-1]
                            if case.name == "account_profile"
                            else cases("", "")[-2]
                        )
                        try:
                            await link(page, detour.path, args.timeout_ms)
                            await page.locator(detour.ready).first.wait_for(
                                timeout=args.timeout_ms
                            )
                            await recorder.settle()
                            warm = await sample(
                                page,
                                recorder,
                                case,
                                "revisit",
                                partial(link, page, case.path, args.timeout_ms),
                                args.timeout_ms,
                            )
                            if warm["status"] == "ok":
                                warm["state"] = await check_state(page, case, before)
                        except BrowserError as exc:
                            warm = {
                                "case": case.name,
                                "phase": "revisit",
                                "status": "unavailable",
                                "reason": type(exc).__name__,
                                "api_calls": 0,
                                "permission_calls": 0,
                            }
                        warm["iteration"] = iteration + 1
                        report["samples"].append(warm)
                    await context.close()
            await browser.close()
    except (BrowserError, OSError) as exc:
        report.update(status="unavailable", reason=type(exc).__name__, stage=stage)
        return report
    report["summary"] = summary(report["samples"])
    report["status"] = (
        "ok"
        if report["samples"] and all(r["status"] == "ok" for r in report["samples"])
        else "partial"
    )
    return report


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--environment", required=True, choices=["development", "production"]
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Use synthetic API in the browser only (loopback origin required)",
    )
    parser.add_argument("--fixture-delay-ms", type=int, default=80)
    parser.add_argument("--fixture-groups", type=int, default=5)
    parser.add_argument(
        "--browser-executable", help="Optional already-installed Chromium executable"
    )
    parser.add_argument("--organization-id")
    parser.add_argument("--workspace-id")
    parser.add_argument(
        "--storage-state",
        help="Private existing Playwright session; never copied into the report",
    )
    parser.add_argument(
        "--allow-agent-sync",
        action="store_true",
        help="Allow the app's navigation-triggered reconciliation on an isolated test deployment",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument(
        "--case", action="append", choices=[c.name for c in cases("", "")]
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        parser.error(
            "base-url must be an HTTP(S) origin without credentials, path, query or fragment"
        )
    args.base_url = args.base_url.rstrip("/")
    if args.fixture and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("fixture mode requires a loopback origin")
    if args.fixture and args.storage_state:
        parser.error(
            "fixture mode uses a synthetic identity, not an authenticated storage-state"
        )
    if not args.fixture and not (
        args.organization_id and args.workspace_id and args.storage_state
    ):
        parser.error(
            "authenticated mode requires organization-id, workspace-id and storage-state"
        )
    if (
        args.runs < 1
        or args.timeout_ms < 1
        or args.fixture_delay_ms < 0
        or args.fixture_groups < 0
    ):
        parser.error(
            "runs/timeout must be positive; fixture delay/group count must be non-negative"
        )
    return args


def main() -> int:
    args = arguments()
    report = asyncio.run(run(args))
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps({"status": report["status"], "summary": report["summary"]}, indent=2)
    )
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
