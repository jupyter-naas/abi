"""Synthetic API for the Settings browser baseline; never installed in the app."""

from __future__ import annotations

import asyncio
import json
from urllib.parse import urlsplit

USER = {
    "id": "baseline-user",
    "name": "Baseline user",
    "email": "baseline@example.invalid",
}
ORG_ID = "baseline-org"
WORKSPACE_ID = "baseline-workspace"
FEATURES = [
    "chat",
    "files",
    "datasets",
    "search",
    "graph",
    "ontology",
    "agents",
    "apps",
    "maps",
    "skills",
    "settings",
    "settings.workspace",
    "settings.organization",
]
ORG = {
    "id": ORG_ID,
    "name": "Baseline organization",
    "slug": ORG_ID,
    "current_user_role": "owner",
    "timezone": "UTC",
    "primary_color": "#22c55e",
}
WORKSPACE = {
    "id": WORKSPACE_ID,
    "name": "Baseline workspace",
    "slug": WORKSPACE_ID,
    "organization_id": ORG_ID,
    "current_user_role": "owner",
    "feature_flags": dict.fromkeys(FEATURES, True),
    "owner_id": USER["id"],
}
AGENTS = [
    {
        "id": "baseline-agent",
        "name": "Baseline agent",
        "description": "Synthetic agent",
        "workspace_id": WORKSPACE_ID,
        "system_prompt": "Synthetic prompt",
        "enabled": True,
    }
]
ACTIONS = dict.fromkeys(
    [
        "nexus:ReadSystem",
        "nexus:ListUsers",
        "nexus:ListDrives",
        "nexus:InviteUser",
        "iam:ListPolicies",
        "iam:CreatePolicy",
        "iam:GetPolicy",
        "iam:UpdatePolicy",
        "iam:ListAttachments",
        "iam:AttachPolicy",
        "iam:DetachPolicy",
        "iam:ListGroups",
        "iam:GetGroup",
        "iam:CreateGroup",
        "iam:UpdateGroup",
        "iam:DeleteGroup",
        "iam:ListPrincipals",
        "iam:GetPrincipal",
        "iam:ListManifests",
        "iam:Explain",
    ],
    True,
)


def groups(count: int) -> list[dict]:
    return [
        {
            "id": f"baseline-group-{i}",
            "kind": "group",
            "name": f"Baseline group {i}",
            "status": "active",
            "owner_scope": "abi:",
        }
        for i in range(count)
    ]


def answer(path: str, method: str, group_count: int) -> tuple[int, object]:
    """Unknown routes fail visibly instead of silently making a broken view look fast."""
    if method == "OPTIONS":
        return 204, None
    if path == "/api/auth/oidc/session":
        return 200, {
            "user": USER,
            "view": None,
            "provider": "fixture",
            "csrf_token": "fixture-only",
        }
    if path == "/api/web-pass":
        return 200, {"active": True, "expires_in": 28800}
    if path == "/api/auth/me":
        return 200, USER
    if path == "/api/tenant":
        return 200, {"name": "Nexus", "tab_title": "Nexus baseline"}
    if path == "/api/organizations":
        return 200, [ORG]
    if path == f"/api/organizations/{ORG_ID}":
        return 200, ORG
    if path == f"/api/organizations/{ORG_ID}/workspaces" or path == "/api/workspaces":
        return 200, [WORKSPACE]
    if path == f"/api/workspaces/{WORKSPACE_ID}":
        return 200, WORKSPACE
    if path.endswith("/analytics/access"):
        return 200, {
            "can_read": True,
            "can_read_conversations": False,
            "timezone": "UTC",
        }
    if path == "/api/iam/admin/access":
        return 200, {"actions": ACTIONS}
    if path == "/api/iam/admin/groups":
        return 200, {"items": groups(group_count)}
    if path.startswith("/api/iam/admin/groups/"):
        group = next(
            (g for g in groups(group_count) if g["id"] == path.rsplit("/", 1)[1]), None
        )
        return (
            (200, {**group, "members": [USER], "idp_mappings": []})
            if group
            else (404, {})
        )
    if path == "/api/iam/admin/capabilities":
        return 200, {"capabilities": []}
    if path == "/api/iam/admin/policies":
        return 200, {"items": [], "next_after": None}
    if path == "/api/iam/admin/resources":
        return 200, {"items": [], "next_cursor": None, "listed": True}
    if path == "/api/iam/admin/attachments":
        return 200, {"items": []}
    if path == f"/api/organizations/{ORG_ID}/domains":
        return 200, []
    if path.rstrip("/") in {"/api/agents", "/api/agents/sync"}:
        return 200, AGENTS
    if path == "/api/providers/available" or path == "/api/providers/models":
        return 200, []
    if path == "/api/chat/conversations":
        return 200, []
    if (
        path == f"/api/workspaces/{WORKSPACE_ID}/servers"
        or path.rstrip("/") == "/api/skills"
    ):
        return 200, []
    if path == f"/api/workspaces/{WORKSPACE_ID}/resources":
        return 200, {
            "features": FEATURES,
            "modules": [],
            "totals": dict.fromkeys(["agents", "apps", "workflows", "pipelines"], 0),
            "organization_id": ORG_ID,
        }
    if path == "/api/admin/system/jobs/failures":
        return 200, {"count": 0, "more": False, "runs": []}
    if path == "/api/admin/me":
        return 200, {"is_superadmin": True}
    if path in {"/api/admin/ping", "/health"}:
        return 200, {"ok": True}
    if path.startswith("/api/analytics/"):
        return 204, None
    return 501, {"detail": "Not implemented by the Settings baseline fixture"}


async def install(context, base_url: str, *, delay_ms: int, group_count: int) -> None:
    """Intercept the isolated browser context only; no real API requests or writes."""
    await context.add_cookies(
        [
            {"name": "nexus-auth-flag", "value": "true", "url": base_url},
            {"name": "nexus-web-pass-until", "value": "4102444800", "url": base_url},
        ]
    )
    snapshot = json.dumps(
        {"state": {"user": USER, "isAuthenticated": True}, "version": 0}
    )
    await context.add_init_script(
        f"localStorage.setItem('nexus-auth', {json.dumps(snapshot)});"
    )

    async def route_request(route):
        path = urlsplit(route.request.url).path
        if path == "/runtime-config.js":
            await route.fulfill(
                content_type="application/javascript",
                body="window.__NEXUS_RUNTIME_CONFIG__={apiUrl:''};",
            )
        elif path.startswith("/api/") or path == "/health":
            await asyncio.sleep(delay_ms / 1000)
            status, body = answer(path, route.request.method, group_count)
            await route.fulfill(
                status=status,
                content_type="application/json",
                body="" if body is None else json.dumps(body),
            )
        elif urlsplit(route.request.url).netloc == urlsplit(base_url).netloc:
            await route.continue_()
        else:
            await route.abort()

    await context.route("**/*", route_request)
