#!/usr/bin/env python
"""Headless workspace provisioning demo for the Coder embedding prototype.

Drives abi's `coding_environment` core service entirely via Coder's REST API
(the CoderAdapter). With --in-memory it runs the identical flow against the
fake adapter, so the orchestration logic is demonstrable without Docker/Coder.

  uv run --no-sync python coder_prototype/scripts/provision.py --in-memory
  CODER_SESSION_TOKEN=$(cat coder_prototype/.coder-token) \
    uv run --no-sync python coder_prototype/scripts/provision.py
"""
from __future__ import annotations

import argparse
import os
import sys

from naas_abi_core.services.coding_environment.CodingEnvironmentFactory import (
    CodingEnvironmentFactory,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    CodingEnvironmentError,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--in-memory", action="store_true", help="use the fake adapter")
    p.add_argument(
        "--access-url",
        default=os.environ.get("CODER_ACCESS_URL", "http://localhost:7080"),
    )
    p.add_argument("--token", default=os.environ.get("CODER_SESSION_TOKEN", ""))
    p.add_argument(
        "--wildcard",
        default=os.environ.get("CODER_WILDCARD_ACCESS_URL", "*.coder.lvh.me"),
    )
    p.add_argument("--template-id", default=os.environ.get("CODER_TEMPLATE_ID", ""))
    p.add_argument("--username", default="alice")
    p.add_argument("--email", default="alice@example.com")
    p.add_argument("--workspace", default="dev")
    p.add_argument("--app-slug", default="code-server")
    return p


def main() -> int:
    args = build_parser().parse_args()

    if args.in_memory:
        print("[mode] in-memory fake adapter")
        svc = CodingEnvironmentFactory.CodingEnvironmentServiceInMemory(
            polls_until_ready=2
        )
    else:
        if not args.token:
            print(
                "ERROR: set CODER_SESSION_TOKEN (run scripts/bootstrap.sh first)",
                file=sys.stderr,
            )
            return 2
        print(f"[mode] coder @ {args.access_url}")
        svc = CodingEnvironmentFactory.CodingEnvironmentServiceCoder(
            access_url=args.access_url,
            wildcard_access_url=args.wildcard,
            admin_token=args.token,
            workspace_autostop_ms=1_800_000,
        )

    try:
        user_id = svc.ensure_user(
            external_id=f"ext-{args.username}",
            email=args.email,
            username=args.username,
        )
        print(f"[ensure_user] {args.username} -> {user_id}")

        templates = svc.list_templates()
        print(f"[list_templates] -> {[t.name for t in templates] or 'none'}")

        template_id = args.template_id or (templates[0].id if templates else "")
        if not template_id:
            print(
                "[provision] skipped: no template available.\n"
                "            Push one with `make template` (see README), then re-run."
            )
            return 0

        status = svc.provision(
            user_id=user_id, template_id=template_id, name=args.workspace
        )
        print(f"[provision] id={status.id} phase={status.phase}")

        status = svc.wait_until_ready(
            workspace_id=status.id, timeout_seconds=240, poll_interval_seconds=3
        )
        print(f"[ready] phase={status.phase} agent_ready={status.agent_ready}")

        access = svc.get_access(
            workspace_id=status.id, user_id=user_id, app_slug=args.app_slug
        )
        print("[get_access] embeddable URL:")
        print(f"  {access.url}")
        return 0
    except CodingEnvironmentError as exc:
        print(f"ERROR ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
