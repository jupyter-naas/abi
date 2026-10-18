"""Readiness checks for scripts/cli_smoke.sh against a running `abi dev` stack.

Standard library only, so any python3 runs it. Each check is retried until it
passes or the shared deadline (--timeout seconds) runs out; the first one that
does not pass in time fails the run with what it saw last.

    python3 scripts/cli_smoke_checks.py --api http://localhost:10437 \
        --web http://localhost:12558 --env-file .env \
        --remote-module smoke.research:Research --agents Research,Analyst \
        --apps remote/smoke.research:board,legacy:reports
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD_KEY = "NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD"


class NotYet(Exception):
    """The check does not pass yet; the message says what it saw."""


def request(
    url: str, *, method: str = "GET", token: str = "", body: Any = None
) -> tuple[int, bytes]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        # Redirects are followed: Nexus web sends / to its login page.
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError) as exc:
        raise NotYet(f"{url}: {exc}") from exc


def get_json(url: str, **kwargs: Any) -> Any:
    status, payload = request(url, **kwargs)
    if status != 200:
        raise NotYet(f"{url}: HTTP {status} {payload[:300]!r}")
    return json.loads(payload)


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


def admin_password(env_file: Path) -> str:
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == ADMIN_PASSWORD_KEY:
            return value.strip().strip("'\"")
    sys.exit(f"FAIL  no {ADMIN_PASSWORD_KEY} in {env_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", required=True, help="API base URL")
    parser.add_argument("--web", required=True, help="Nexus web base URL")
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument(
        "--remote-module",
        default="",
        help="<module_id>:<agent> that discovery must list READY",
    )
    parser.add_argument("--agents", default="", help="comma-separated agent names")
    parser.add_argument("--apps", default="", help="comma-separated app ids")
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

    session: dict[str, str] = {}

    def login() -> str:
        result = get_json(
            f"{api}/api/auth/login",
            method="POST",
            body={"email": ADMIN_EMAIL, "password": admin_password(args.env_file)},
        )
        session["token"] = result["access_token"]
        workspaces = get_json(f"{api}/api/workspaces", token=session["token"])
        if not workspaces:
            raise NotYet("the admin has no workspace yet")
        session["workspace"] = workspaces[0]["id"]
        return f"{ADMIN_EMAIL}, workspace {session['workspace']}"

    wait("admin login", deadline, login)
    token, workspace = session["token"], session["workspace"]

    if args.remote_module:
        module_id, _, agent = args.remote_module.partition(":")

        def discovered() -> str:
            modules = get_json(f"{api}/api/admin/system/modules", token=token)
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
                token=token,
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
            result = get_json(f"{api}/api/apps/?workspace_id={workspace}", token=token)
            ids = {app["app_id"] for app in result["apps"]}
            missing = [app for app in apps if app not in ids]
            if missing:
                raise NotYet(f"missing {missing} among {sorted(ids)}")
            return ", ".join(apps)

        wait("apps listed in Nexus", deadline, catalog)

    def web() -> str:
        # The first request compiles the page (`next dev`): give it time.
        status, _ = request(f"{args.web.rstrip('/')}/")
        if status != 200:
            raise NotYet(f"Nexus web: HTTP {status}")
        return "HTTP 200"

    wait("Nexus web", deadline, web)


if __name__ == "__main__":
    main()
