"""Thin authenticated client for Nexus HTTP admin APIs.

Auth resolution order:
1. Explicit access token (`--token` / `NEXUS_ACCESS_TOKEN`)
2. Email + password login (`--email`/`--password` or `NEXUS_EMAIL`/`NEXUS_PASSWORD`)

Base URL: `--api-url` / `NEXUS_API_URL` (default `http://localhost:9879`).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_NEXUS_API_URL = "http://localhost:9879"


class NexusApiError(RuntimeError):
    def __init__(self, status: int, detail: str, path: str) -> None:
        self.status = status
        self.detail = detail
        self.path = path
        super().__init__(f"Nexus API {status} on {path}: {detail}")


@dataclass
class NexusClient:
    api_url: str
    access_token: str
    timeout_s: float = 30.0

    @classmethod
    def from_env(
        cls,
        *,
        api_url: str | None = None,
        token: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ) -> NexusClient:
        base = (api_url or os.getenv("NEXUS_API_URL") or DEFAULT_NEXUS_API_URL).rstrip(
            "/"
        )
        access = token or os.getenv("NEXUS_ACCESS_TOKEN")
        if not access:
            login_email = email or os.getenv("NEXUS_EMAIL")
            login_password = password or os.getenv("NEXUS_PASSWORD")
            if not login_email or not login_password:
                raise click_auth_error()
            access = cls._login(base, login_email, login_password)
        return cls(api_url=base, access_token=access)

    @staticmethod
    def _login(api_url: str, email: str, password: str) -> str:
        body = json.dumps({"email": email, "password": password}).encode("utf-8")
        req = urllib.request.Request(
            f"{api_url}/api/auth/login",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            # http(s) Nexus API only; Request URL is built from api_url.
            with urllib.request.urlopen(req, timeout=30.0) as resp:  # nosec B310
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = _read_error_detail(exc)
            raise NexusApiError(exc.code, detail, "/api/auth/login") from exc
        token = payload.get("access_token")
        if not token:
            raise NexusApiError(500, "login response missing access_token", "/api/auth/login")
        return str(token)

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        form_body: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.api_url}{path}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }
        data: bytes | None = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif form_body is not None:
            data = urllib.parse.urlencode(form_body).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
        try:
            # http(s) Nexus API only; Request URL is built from api_url + path.
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # nosec B310
                raw = resp.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise NexusApiError(exc.code, _read_error_detail(exc), path) from exc

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, json_body: dict[str, Any] | None = None) -> Any:
        return self.request("POST", path, json_body=json_body or {})

    def patch(self, path: str, json_body: dict[str, Any]) -> Any:
        return self.request("PATCH", path, json_body=json_body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)


def click_auth_error() -> RuntimeError:
    return RuntimeError(
        "Nexus auth required. Set NEXUS_ACCESS_TOKEN, or NEXUS_EMAIL + NEXUS_PASSWORD "
        "(or pass --token / --email --password). Base URL via NEXUS_API_URL "
        f"(default {DEFAULT_NEXUS_API_URL})."
    )


def _read_error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return exc.reason or str(exc)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw or (exc.reason or str(exc))
    detail = payload.get("detail", payload)
    if isinstance(detail, (dict, list)):
        return json.dumps(detail)
    return str(detail)


def common_api_options(fn):  # type: ignore[no-untyped-def]
    """Decorator stacking shared Nexus API connection options onto a click command."""
    import click

    opts = [
        click.option(
            "--api-url",
            envvar="NEXUS_API_URL",
            default=DEFAULT_NEXUS_API_URL,
            show_default=True,
            help="Nexus API base URL (no trailing slash).",
        ),
        click.option(
            "--token",
            envvar="NEXUS_ACCESS_TOKEN",
            default=None,
            help="Bearer access token (preferred over email/password).",
        ),
        click.option(
            "--auth-email",
            "email",
            envvar="NEXUS_EMAIL",
            default=None,
            help="Login email when no token is set (env: NEXUS_EMAIL).",
        ),
        click.option(
            "--auth-password",
            "password",
            envvar="NEXUS_PASSWORD",
            default=None,
            help="Login password when no token is set (env: NEXUS_PASSWORD).",
        ),
        click.option(
            "--dry-run",
            is_flag=True,
            default=False,
            help="Print the intended API call without executing it.",
        ),
    ]
    for opt in reversed(opts):
        fn = opt(fn)
    return fn


def build_client(
    *,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
) -> NexusClient:
    return NexusClient.from_env(
        api_url=api_url, token=token, email=email, password=password
    )


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, default=str, sort_keys=True))


def print_table(rows: list[dict[str, Any]], columns: list[str], title: str) -> None:
    from rich.console import Console
    from rich.table import Table

    table = Table(title=title, show_header=True, header_style="bold magenta")
    for col in columns:
        table.add_column(col, overflow="fold")
    for row in rows:
        table.add_row(*[str(row.get(col, "") or "") for col in columns])
    Console().print(table)
