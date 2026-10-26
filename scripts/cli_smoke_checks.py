"""Readiness checks for scripts/cli_smoke.sh against a running `abi dev` stack.

Standard library only, so any python3 runs it. Each check is retried until it
passes or the shared deadline (--timeout seconds) runs out; the first one that
does not pass in time fails the run with what it saw last.

    python3 scripts/cli_smoke_checks.py --api http://localhost:10437 \
        --web http://localhost:12558 --mail-dir storage/email \
        --remote-module smoke.research:Research --agents Research,Analyst \
        --apps remote/smoke.research:board,legacy:reports
"""

from __future__ import annotations

import argparse
import email
import email.policy
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ADMIN_EMAIL = "admin@example.com"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class NotYet(Exception):
    """The check does not pass yet; the message says what it saw."""


class Session:
    """A browser-like session: cookies kept, redirects followed. Nexus has no
    password: the built-in identity provider mails a code, and the API sets its
    session cookie once the code is entered (`sign_in`)."""

    def __init__(self) -> None:
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        self.csrf = ""

    def open(
        self,
        url: str,
        *,
        method: str = "GET",
        body: Any = None,
        form: dict[str, str] | None = None,
    ) -> tuple[int, bytes, str]:
        data = None
        headers: dict[str, str] = {}
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if self.csrf and method.upper() not in SAFE_METHODS:
            headers[CSRF_HEADER] = self.csrf
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            # Redirects are followed: Nexus web sends / to its login page.
            with self.opener.open(req, timeout=60) as response:
                return response.status, response.read(), response.geturl()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), url
        except (urllib.error.URLError, OSError) as exc:
            raise NotYet(f"{url}: {exc}") from exc


def request(url: str, *, method: str = "GET", body: Any = None) -> tuple[int, bytes]:
    status, payload, _ = Session().open(url, method=method, body=body)
    return status, payload


def get_json(url: str, *, session: Session | None = None, **kwargs: Any) -> Any:
    status, payload, _ = (session or Session()).open(url, **kwargs)
    if status != 200:
        raise NotYet(f"{url}: HTTP {status} {payload[:300]!r}")
    return json.loads(payload)


class _Form(HTMLParser):
    """The first form of a page: its action and its fields."""

    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None
        self.fields: dict[str, str] = {}
        self._done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "form" and self.action is None:
            self.action = values.get("action", "")
        elif tag == "input" and self.action is not None and not self._done:
            if values.get("name"):
                self.fields[values["name"]] = values.get("value", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self.action is not None:
            self._done = True


def parse_form(html: bytes, page_url: str) -> tuple[str, dict[str, str]]:
    parser = _Form()
    parser.feed(html.decode("utf-8", "replace"))
    if parser.action is None:
        raise NotYet(f"{page_url}: no form to fill in")
    return urllib.parse.urljoin(page_url, parser.action), parser.fields


def code_mailed_to(mail_dir: Path, address: str, since: float) -> str | None:
    """The newest sign-in code mailed to `address` after `since` (epoch seconds).

    The dev email adapter keeps every mail as `<epoch ms>-<id>.eml`; `abi dev
    code` prints the same code."""
    if not mail_dir.is_dir():
        return None
    for path in sorted(mail_dir.glob("*.eml"), reverse=True):
        stamp = path.name.split("-", 1)[0]
        if not stamp.isdigit() or int(stamp) / 1000 < since - 1:
            break
        message = email.message_from_bytes(
            path.read_bytes(), policy=email.policy.default
        )
        if address.lower() not in str(message.get("To", "")).lower():
            continue
        body = message.get_body(preferencelist=("plain", "html"))
        found = re.search(
            r"sign-in code is:\s*(\d{4,10})", body.get_content() if body else ""
        )
        if found:
            return found.group(1)
    return None


def sign_in(
    api: str, mail_dir: Path, address: str, wait_seconds: float = 60.0
) -> Session:
    """Sign in as `address` the way the login page does: the API sends the
    browser to the built-in identity provider, which mails a code."""
    session = Session()
    since = time.time()
    query = urllib.parse.urlencode({"email": address})
    status, page, url = session.open(f"{api}/api/auth/oidc/login?{query}")
    if status != 200:
        raise NotYet(f"sign-in page: HTTP {status} {page[:200]!r}")
    action, fields = parse_form(page, url)
    if "code" not in fields:
        # The provider asked for the address again.
        fields["email"] = address
        status, page, url = session.open(action, method="POST", form=fields)
        if status != 200:
            raise NotYet(f"sign-in email step: HTTP {status} {page[:200]!r}")
        action, fields = parse_form(page, url)
    deadline = time.monotonic() + wait_seconds
    code = None
    while code is None:
        code = code_mailed_to(mail_dir, address, since)
        if code is None:
            if time.monotonic() >= deadline:
                raise NotYet(f"no sign-in code mailed to {address} in {mail_dir}")
            time.sleep(1)
    fields["code"] = code
    status, page, url = session.open(action, method="POST", form=fields)
    if status >= 400:
        raise NotYet(f"sign-in code step: HTTP {status} {page[:200]!r}")
    info = get_json(f"{api}/api/auth/oidc/session", session=session)
    session.csrf = str(info.get("csrf_token") or "")
    return session


def wait(name: str, deadline: float, check: Callable[[], str]) -> None:
    started = time.monotonic()
    last = "never ran"
    while True:
        try:
            detail = check()
        except NotYet as exc:
            last = str(exc)
        else:
            print(
                f"ok    {name} ({time.monotonic() - started:.0f}s): {detail}",
                flush=True,
            )
            return
        if time.monotonic() >= deadline:
            print(f"FAIL  {name}: {last}", flush=True)
            sys.exit(1)
        time.sleep(3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", required=True, help="API base URL")
    parser.add_argument("--web", required=True, help="Nexus web base URL")
    parser.add_argument(
        "--mail-dir",
        required=True,
        type=Path,
        help="where the dev email adapter writes mails (storage/email)",
    )
    parser.add_argument(
        "--remote-module",
        default="",
        help="<module_id>:<agent> that discovery must list READY",
    )
    parser.add_argument("--agents", default="", help="comma-separated agent names")
    parser.add_argument("--apps", default="", help="comma-separated app ids")
    parser.add_argument(
        "--no-sign-in",
        action="store_true",
        help="a project with no identity provider (legacy, --without-nats): check "
        "the API and the web app only",
    )
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()
    deadline = time.monotonic() + args.timeout
    api = args.api.rstrip("/")

    def docs() -> str:
        status, _ = request(f"{api}/docs")
        if status != 200:
            raise NotYet(f"/docs: HTTP {status}")
        return "HTTP 200"

    wait("API /docs", deadline, docs)

    def web() -> str:
        # The first request compiles the page (`next dev`): give it time.
        status, _ = request(f"{args.web.rstrip('/')}/")
        if status != 200:
            raise NotYet(f"Nexus web: HTTP {status}")
        return "HTTP 200"

    if args.no_sign_in:
        # The built-in identity provider is a module over NATS: a legacy project
        # has none, so nobody can sign in unless it names a provider of its own.
        wait("Nexus web", deadline, web)
        return

    state: dict[str, Any] = {}

    def login() -> str:
        session = sign_in(api, args.mail_dir, ADMIN_EMAIL)
        workspaces = get_json(f"{api}/api/workspaces", session=session)
        if not workspaces:
            raise NotYet("the admin has no workspace yet")
        state.update(session=session, workspace=workspaces[0]["id"])
        return f"{ADMIN_EMAIL}, workspace {state['workspace']}"

    wait("admin sign-in", deadline, login)
    session, workspace = state["session"], state["workspace"]

    if args.remote_module:
        module_id, _, agent = args.remote_module.partition(":")

        def discovered() -> str:
            modules = get_json(f"{api}/api/admin/system/modules", session=session)
            seen = {m["module_id"]: m for m in modules.get("remote", [])}
            module = seen.get(module_id)
            if module is None or module.get("status") != "READY":
                raise NotYet(f"discovery lists {seen or 'no remote module'}")
            if agent not in module.get("agents", []):
                raise NotYet(f"{module_id} serves {module.get('agents')}")
            return f"{module_id} READY, serving {agent}"

        wait("remote module in discovery", deadline, discovered)

    agents = [name for name in args.agents.split(",") if name]
    if agents:

        def listed() -> str:
            # What Nexus does before showing the roster: reconcile it with the
            # engine's agents and the ones remote modules publish.
            roster = get_json(
                f"{api}/api/agents/sync?workspace_id={workspace}",
                method="POST",
                session=session,
            )
            names = {agent["name"] for agent in roster}
            missing = [name for name in agents if name not in names]
            if missing:
                raise NotYet(f"missing {missing} among {sorted(names)}")
            return ", ".join(agents)

        wait("agents listed in Nexus", deadline, listed)

    apps = [app for app in args.apps.split(",") if app]
    if apps:

        def catalog() -> str:
            result = get_json(
                f"{api}/api/apps/?workspace_id={workspace}", session=session
            )
            ids = {app["app_id"] for app in result["apps"]}
            missing = [app for app in apps if app not in ids]
            if missing:
                raise NotYet(f"missing {missing} among {sorted(ids)}")
            return ", ".join(apps)

        wait("apps listed in Nexus", deadline, catalog)

    wait("Nexus web", deadline, web)


if __name__ == "__main__":
    main()
