"""The IAM admin routes over a real IAM: reachable only with the matching ``iam:*``
permission, every change audited, a key's value shown once."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_scope, workspace_scope
from naas_abi.apps.nexus.apps.api.app.services.iam_admin import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.primary.iam_admin__primary_adapter__FastAPI import (  # noqa: E501
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.service import IamAdminService
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    use_call_context,
)
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER

READ_POLICIES = {
    "version": "2026-10-13",
    "statements": [
        {"effect": "Allow", "actions": ["iam:ListPolicies"], "resources": ["abi:*:*:iam:policy/*"]}
    ],
}
GRAPH_POLICY = {
    "version": "2026-10-13",
    "statements": [
        {
            "sid": "Read",
            "effect": "Allow",
            "actions": ["triple_store:Query", "triple_store:ListGraphs"],
            "resources": ["abi:-:-:triple_store:graph/*"],
        },
        {
            "sid": "NoSecret",
            "effect": "Deny",
            "actions": ["triple_store:Query"],
            "resources": ["abi:-:-:triple_store:graph/secret"],
        },
    ],
}


@pytest.fixture
def audit() -> MemoryAudit:
    return MemoryAudit()


@pytest.fixture
def world(team, audit):
    """``root`` (platform admin), an org admin and owner of ``org-1``, a user who may
    only list policies, and strangers: through the real routes."""
    team.platform_admin("root")
    team.user("lister")
    with as_service_account("engine"):
        policy = team.iam.create_policy("list-policies", READ_POLICIES)
        listing = team.iam.ensure_user(LEGACY_NEXUS_ISSUER, "lister")
        team.iam.attach_policy(policy.id, listing.id)
    previous = runtime.configure(lambda: IamAdminService(EngineIamGateway(), audit))
    app = FastAPI()
    app.include_router(router, prefix="/api/iam/admin")
    app.dependency_overrides[get_current_user_required] = _signed_in_user

    @app.get("/me")
    async def me(user=_signed_in_dependency):  # noqa: B008
        return {"id": user.id}

    yield SimpleNamespace(nexus=team, client=TestClient(app), audit=audit)
    runtime.configure(previous)


def _signed_in_user():  # replaced below: needs the request
    raise NotImplementedError


from fastapi import Depends, Request  # noqa: E402


def _by_header(request: Request) -> SimpleNamespace:
    user = request.headers.get("x-user")
    if not user:
        from fastapi import HTTPException

        raise HTTPException(401, "Not authenticated")
    return SimpleNamespace(id=user, email=f"{user}@example.com", name=user)


_signed_in_user = _by_header  # noqa: F811
_signed_in_dependency = Depends(_by_header)


def as_(user: str) -> dict[str, str]:
    return {"x-user": user}


def post(world, path, user="root", **body):
    return world.client.post(f"/api/iam/admin{path}", json=body, headers=as_(user))


def get(world, path, user="root"):
    return world.client.get(f"/api/iam/admin{path}", headers=as_(user))


# -- reachable only with the matching permission ---------------------------------------------


def test_a_platform_admin_reaches_every_page_and_a_stranger_none(world):
    pages = [
        "/policies",
        "/principals",
        "/groups",
        "/service-accounts",
        "/manifests",
        "/attachments",
        "/catalogs",
    ]
    for page in pages:
        assert get(world, page).status_code == 200, page
        denied = get(world, page, "stranger")
        assert denied.status_code == 403, (page, denied.text)


def test_a_user_with_one_permission_reaches_the_one_page(world):
    assert get(world, "/policies", "lister").status_code == 200
    assert get(world, "/catalogs", "lister").status_code == 200
    assert get(world, "/groups", "lister").status_code == 403
    assert get(world, "/principals", "lister").status_code == 403
    assert get(world, "/manifests", "lister").status_code == 403
    created = post(world, "/policies", "lister", name="x", document=GRAPH_POLICY)
    assert created.status_code in (403, 404)
    assert world.audit.phases("create_policy")[-1] == "failed"


def test_the_caller_is_the_session_never_a_request_field(world):
    anonymous = world.client.get("/api/iam/admin/policies")
    assert anonymous.status_code == 401


def test_access_says_what_the_caller_may_do(world):
    root = get(world, "/access").json()["actions"]
    assert root["iam:CreatePolicy"] and root["iam:ApproveManifest"] and root["iam:Explain"]
    lister = get(world, "/access", "lister").json()["actions"]
    assert lister["iam:ListPolicies"]
    assert not lister["iam:CreatePolicy"] and not lister["iam:ListGroups"]
    assert not any(get(world, "/access", "stranger").json()["actions"].values())


def test_access_at_a_scope_follows_the_attachment_rules(world):
    scope = org_scope("org-1")
    admin = get(world, f"/access?scope={scope}", "admin").json()["actions"]
    assert admin["iam:ListAttachments"] and admin["iam:AttachPolicy"]
    other = get(world, f"/access?scope={org_scope('org-2')}", "admin").json()["actions"]
    assert not other["iam:ListAttachments"] and not other["iam:AttachPolicy"]
    assert get(world, "/access?scope=nonsense", "admin").status_code == 422


# -- policies --------------------------------------------------------------------------------


def test_a_policy_is_validated_created_edited_and_deleted(world):
    bad = post(
        world,
        "/policies/validate",
        document={
            "version": "2026-10-13",
            "statements": [
                {"effect": "Allow", "actions": ["nope:Nothing"], "resources": ["abi:-:-:nope:x/1"]},
                {"effect": "Maybe", "actions": [], "resources": []},
            ],
        },
    )
    assert bad.status_code == 200 and bad.json()["valid"] is False
    assert len(bad.json()["errors"]) >= 2

    text = "version: '2026-10-13'\nstatements:\n  - effect: Allow\n    actions: [triple_store:Query]\n    resources: ['abi:-:-:triple_store:graph/*']\n"
    good = post(world, "/policies/validate", text=text).json()
    assert good["valid"] and good["document"]["statements"][0]["actions"] == ["triple_store:Query"]

    refused = post(
        world,
        "/policies",
        name="bad",
        document={
            "version": "2026-10-13",
            "statements": [{"effect": "Allow", "actions": ["nope:Nothing"], "resources": ["*"]}],
        },
    )
    assert refused.status_code == 422 and refused.json()["detail"]["errors"]

    created = post(
        world, "/policies", name="graphs", description="read graphs", document=GRAPH_POLICY
    )
    assert created.status_code == 201
    policy = created.json()
    assert policy["revision"] == 1 and not policy["managed"]
    assert get(world, f"/policies/{policy['id']}").json()["name"] == "graphs"

    updated = world.client.put(
        f"/api/iam/admin/policies/{policy['id']}",
        json={"expected_revision": 1, "name": "graphs v2"},
        headers=as_("root"),
    )
    assert updated.status_code == 200 and updated.json()["revision"] == 2
    stale = world.client.put(
        f"/api/iam/admin/policies/{policy['id']}",
        json={"expected_revision": 1, "name": "again"},
        headers=as_("root"),
    )
    assert stale.status_code == 409

    gone = world.client.delete(f"/api/iam/admin/policies/{policy['id']}", headers=as_("root"))
    assert gone.status_code == 204
    assert get(world, f"/policies/{policy['id']}").status_code == 404


def test_a_managed_policy_cannot_be_edited(world):
    response = world.client.put(
        "/api/iam/admin/policies/builtin.viewer",
        json={"expected_revision": 1, "name": "mine"},
        headers=as_("root"),
    )
    assert response.status_code == 409


def test_validation_is_for_those_who_may_write_policies(world):
    assert post(world, "/policies/validate", "lister", text="x").status_code == 403


# -- attachments -----------------------------------------------------------------------------


def _principal_id(world, user: str) -> str:
    with as_service_account("engine"):
        return world.nexus.iam.ensure_user(LEGACY_NEXUS_ISSUER, user).id


def test_an_org_admin_attaches_roles_in_their_org_only(world):
    member = _principal_id(world, "stranger")
    scope = org_scope("org-1")
    attached = post(
        world, "/attachments", "admin", policy_id="builtin.viewer", principal_id=member, scope=scope
    )
    assert attached.status_code == 201, attached.text
    assert attached.json()["principal"]["id"] == member

    listed = get(world, f"/attachments?scope={scope}", "admin").json()["items"]
    assert [(a["policy_id"], a["principal_id"]) for a in listed if a["principal_id"] == member] == [
        ("builtin.viewer", member)
    ]
    assert listed[0]["policy_name"]

    elsewhere = post(
        world,
        "/attachments",
        "admin",
        policy_id="builtin.viewer",
        principal_id=member,
        scope=org_scope("org-2"),
    )
    assert elsewhere.status_code in (403, 404)
    owner_role = post(
        world, "/attachments", "admin", policy_id="builtin.owner", principal_id=member, scope=scope
    )
    assert owner_role.status_code in (403, 404)
    platform = post(world, "/attachments", "admin", policy_id="builtin.viewer", principal_id=member)
    assert platform.status_code in (403, 404)

    removed = world.client.delete(
        "/api/iam/admin/attachments",
        params={"policy_id": "builtin.viewer", "principal_id": member, "scope": scope},
        headers=as_("admin"),
    )
    assert removed.status_code == 204
    again = world.client.delete(
        "/api/iam/admin/attachments",
        params={"policy_id": "builtin.viewer", "principal_id": member, "scope": scope},
        headers=as_("admin"),
    )
    assert again.status_code == 404


def test_a_member_attaches_nothing(world):
    victim = _principal_id(world, "stranger")
    response = post(
        world,
        "/attachments",
        "member",
        policy_id="builtin.viewer",
        principal_id=victim,
        scope=workspace_scope("org-1", "ws-1"),
    )
    assert response.status_code in (403, 404)
    # IAM administration is the admins' and owners': a member lists no attachment,
    # at its own scope or another's.
    assert get(world, f"/attachments?scope={org_scope('org-1')}", "member").status_code == 403
    assert get(world, f"/attachments?scope={org_scope('org-2')}", "member").status_code == 403


def test_attachable_policies_are_those_the_caller_may_attach_at_the_scope(world):
    scope = org_scope("org-1")
    seen = {
        p["id"] for p in get(world, f"/attachable-policies?scope={scope}", "admin").json()["items"]
    }
    assert {"builtin.admin", "builtin.member", "builtin.viewer"} <= seen
    assert "builtin.owner" not in seen
    owner = {
        p["id"] for p in get(world, f"/attachable-policies?scope={scope}", "owner").json()["items"]
    }
    assert "builtin.owner" in owner
    assert get(world, f"/attachable-policies?scope={scope}", "stranger").json()["items"] == []


def test_a_custom_policy_attaches_at_the_platform(world):
    created = post(world, "/policies", name="graphs", document=GRAPH_POLICY).json()
    group = post(world, "/groups", name="analysts").json()
    attached = post(world, "/attachments", policy_id=created["id"], principal_id=group["id"])
    assert attached.status_code == 201
    items = get(world, f"/attachments?policy_id={created['id']}").json()["items"]
    assert [a["principal"]["name"] for a in items] == ["analysts"]


# -- groups ----------------------------------------------------------------------------------


def test_a_group_has_members_and_an_idp_mapping(world):
    group = post(world, "/groups", name="data-team").json()
    assert group["kind"] == "group" and group["name"] == "data-team"
    member = _principal_id(world, "member")
    added = world.client.put(
        f"/api/iam/admin/groups/{group['id']}/members/{member}", headers=as_("root")
    )
    assert added.status_code == 200 and [m["id"] for m in added.json()["members"]] == [member]
    mapped = world.client.put(
        f"/api/iam/admin/groups/{group['id']}/idp-mappings",
        json={"provider": "zitadel", "claim_value": "data"},
        headers=as_("root"),
    )
    assert mapped.json()["idp_mappings"] == [{"provider": "zitadel", "claim_value": "data"}]
    detail = get(world, f"/groups/{group['id']}").json()
    assert len(detail["members"]) == 1 and len(detail["idp_mappings"]) == 1

    unmapped = world.client.delete(
        f"/api/iam/admin/groups/{group['id']}/idp-mappings",
        params={"provider": "zitadel", "claim_value": "data"},
        headers=as_("root"),
    )
    assert unmapped.json()["idp_mappings"] == []
    removed = world.client.delete(
        f"/api/iam/admin/groups/{group['id']}/members/{member}", headers=as_("root")
    )
    assert removed.json()["members"] == []
    assert (
        world.client.delete(f"/api/iam/admin/groups/{group['id']}", headers=as_("root")).status_code
        == 204
    )
    assert get(world, f"/groups/{group['id']}").json()["status"] == "deleted"
    assert group["id"] not in [g["id"] for g in get(world, "/groups").json()["items"]]


def test_group_changes_need_their_own_permission(world):
    group = post(world, "/groups", name="data-team").json()
    assert post(world, "/groups", "admin", name="mine").status_code in (403, 404)
    member = _principal_id(world, "member")
    denied = world.client.put(
        f"/api/iam/admin/groups/{group['id']}/members/{member}", headers=as_("admin")
    )
    assert denied.status_code in (403, 404)


# -- service accounts and keys -----------------------------------------------------------------


def test_a_service_accounts_keys_are_shown_once(world):
    account = post(world, "/service-accounts", name="ci/deploy").json()
    assert account["account_kind"] == "custom" and account["active_keys"] == 0

    created = post(world, f"/service-accounts/{account['id']}/keys", description="prod")
    assert created.status_code == 201
    assert created.headers["cache-control"] == "no-store"
    value = created.json()["value"]
    key = created.json()["key"]
    assert value.startswith("abi_sk_") and key["prefix"] == f"abi_sk_{key['id']}"

    listed = get(world, f"/service-accounts/{account['id']}/keys")
    assert value not in listed.text and "value" not in listed.json()["items"][0]
    assert get(world, "/service-accounts").json()["items"][-1]["active_keys"] == 1

    rotated = post(world, f"/service-accounts/{account['id']}/keys/{key['id']}/rotate")
    assert rotated.status_code == 200
    new_value = rotated.json()["value"]
    assert new_value != value and new_value.startswith("abi_sk_")
    statuses = {
        k["id"]: k["status"]
        for k in get(world, f"/service-accounts/{account['id']}/keys").json()["items"]
    }
    assert statuses[key["id"]] == "revoked" and statuses[rotated.json()["key"]["id"]] == "active"
    assert new_value not in get(world, f"/service-accounts/{account['id']}/keys").text

    revoked = world.client.delete(
        f"/api/iam/admin/service-accounts/{account['id']}/keys/{rotated.json()['key']['id']}",
        headers=as_("root"),
    )
    assert revoked.json()["status"] == "revoked"
    for record in world.audit.records:
        assert value not in repr(record) and new_value not in repr(record)

    assert (
        world.client.delete(
            f"/api/iam/admin/service-accounts/{account['id']}", headers=as_("root")
        ).status_code
        == 204
    )


def test_the_engines_own_accounts_cannot_be_deleted_and_keys_need_permission(world):
    with as_service_account("engine"):
        engine_id = world.nexus.iam.find_service_account("engine").id
    refused = world.client.delete(
        f"/api/iam/admin/service-accounts/{engine_id}", headers=as_("root")
    )
    assert refused.status_code == 409
    assert post(world, f"/service-accounts/{engine_id}/keys", "admin").status_code in (403, 404)
    assert get(world, "/service-accounts", "lister").status_code == 403


def test_a_key_that_lasts_too_long_is_refused(world):
    account = post(world, "/service-accounts", name="ci/long").json()
    refused = post(world, f"/service-accounts/{account['id']}/keys", expires_in_days=9999)
    assert refused.status_code == 422


# -- module permission approvals --------------------------------------------------------------

MANIFEST = {
    "version": "2026-10-13",
    "statements": [
        {
            "sid": "OwnGraphs",
            "effect": "Allow",
            "actions": ["triple_store:Query", "triple_store:ListGraphs", "triple_store:Insert"],
            "resources": [
                "abi:-:-:triple_store:graph/${module.id}-*",
                "abi:-:-:triple_store:graph/shared",
            ],
        },
        {
            "sid": "NoAdmin",
            "effect": "Deny",
            "actions": ["triple_store:DropGraph"],
            "resources": ["abi:-:-:triple_store:graph/*"],
        },
    ],
}


@pytest.fixture
def pending(world):
    with as_service_account("engine"):
        account = world.nexus.iam.create_service_account("module/acme/people")
    context = CallContext(
        principal=Principal(id=account.id, kind="service_account", name=account.name)
    )
    with use_call_context(context):
        submitted = world.nexus.iam.submit_manifest("people", "acme", MANIFEST)
    return SimpleNamespace(account=account, sha=submitted.manifest.sha256)


def test_a_pending_manifest_is_listed_and_approved_as_submitted(world, pending):
    listed = get(world, "/manifests?status=pending").json()["items"]
    assert [(m["account_name"], m["status"]) for m in listed] == [("module/acme/people", "pending")]
    approved = post(world, f"/manifests/{pending.account.id}/{pending.sha}/approve")
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert get(world, "/manifests?status=pending").json()["items"] == []
    assert world.audit.phases("approve_manifest") == ["requested", "succeeded"]


def test_a_manifest_can_be_narrowed_never_widened(world, pending):
    narrowed = {
        "version": "2026-10-13",
        "statements": [
            {
                "sid": "OwnGraphs",
                "effect": "Allow",
                "actions": ["triple_store:Query"],
                "resources": ["abi:-:-:triple_store:graph/${module.id}-*"],
            },
            MANIFEST["statements"][1],
        ],
    }
    ok = post(world, f"/manifests/{pending.account.id}/{pending.sha}/approve", document=narrowed)
    assert ok.status_code == 200
    with as_service_account("engine"):
        policy = world.nexus.iam.get_policy("module.acme.people")
    actions = [a for s in policy.document.statements if s.effect == "Allow" for a in s.actions]
    assert actions == ["triple_store:Query"]


def test_widening_or_dropping_a_deny_is_refused(world, pending):
    wider = {
        "version": "2026-10-13",
        "statements": [
            {
                **MANIFEST["statements"][0],
                "actions": ["triple_store:Query", "triple_store:DropGraph"],
            },
            MANIFEST["statements"][1],
        ],
    }
    refused = post(world, f"/manifests/{pending.account.id}/{pending.sha}/approve", document=wider)
    assert refused.status_code == 422
    assert "more than the module submitted" in " ".join(refused.json()["detail"]["errors"])

    no_deny = {"version": "2026-10-13", "statements": [MANIFEST["statements"][0]]}
    refused = post(
        world, f"/manifests/{pending.account.id}/{pending.sha}/approve", document=no_deny
    )
    assert refused.status_code == 422
    assert "Deny" in " ".join(refused.json()["detail"]["errors"])
    assert get(world, "/manifests?status=pending").json()["items"][0]["status"] == "pending"
    assert world.audit.phases("approve_manifest") == ["requested", "failed", "requested", "failed"]


def test_a_manifest_can_be_rejected_with_a_reason(world, pending):
    rejected = post(
        world, f"/manifests/{pending.account.id}/{pending.sha}/reject", reason="too broad"
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected" and rejected.json()["reason"] == "too broad"


def test_approving_needs_the_permission(world, pending):
    for user in ("admin", "lister", "stranger"):
        assert get(world, "/manifests", user).status_code == 403
        denied = post(world, f"/manifests/{pending.account.id}/{pending.sha}/approve", user)
        assert denied.status_code in (403, 404), user
    assert get(world, "/manifests?status=pending").json()["items"][0]["status"] == "pending"


# -- the simulator ----------------------------------------------------------------------------


def test_the_simulator_names_the_deciding_statement(world):
    policy = post(world, "/policies", name="graphs", document=GRAPH_POLICY).json()
    group = post(world, "/groups", name="analysts").json()
    post(world, "/attachments", policy_id=policy["id"], principal_id=group["id"])
    user = _principal_id(world, "member")
    world.client.put(f"/api/iam/admin/groups/{group['id']}/members/{user}", headers=as_("root"))

    allowed = post(
        world,
        "/simulate",
        principal_id=user,
        action="triple_store:Query",
        resource="abi:-:-:triple_store:graph/sales",
    ).json()
    assert allowed["allowed"] and allowed["reason"] == "allow"
    assert allowed["statement"]["policy_name"] == "graphs"
    assert (
        allowed["statement"]["sid"] == "Read" and allowed["statement"]["via_group"] == group["id"]
    )
    assert allowed["statement"]["statement"]["actions"] == [
        "triple_store:Query",
        "triple_store:ListGraphs",
    ]

    denied = post(
        world,
        "/simulate",
        principal_id=user,
        action="triple_store:Query",
        resource="abi:-:-:triple_store:graph/secret",
    ).json()
    assert not denied["allowed"] and denied["reason"] == "explicit_deny"
    assert denied["statement"]["sid"] == "NoSecret" and denied["statement"]["effect"] == "Deny"

    nothing = post(
        world,
        "/simulate",
        principal_id=user,
        action="triple_store:DropGraph",
        resource="abi:-:-:triple_store:graph/sales",
    ).json()
    assert not nothing["allowed"] and nothing["reason"] == "implicit_deny"
    assert nothing["statement"] is None and nothing["principal"]["id"] == user


def test_the_simulator_needs_iam_explain(world):
    user = _principal_id(world, "member")
    body = {
        "principal_id": user,
        "action": "triple_store:Query",
        "resource": "abi:-:-:triple_store:graph/a",
    }
    for caller in ("admin", "lister", "stranger"):
        assert post(world, "/simulate", caller, **body).status_code in (403, 404), caller
    group = post(world, "/groups", name="g").json()
    refused = post(world, "/simulate", **{**body, "principal_id": group["id"]})
    assert refused.status_code == 422
    assert post(world, "/simulate", **{**body, "resource": "not a name"}).status_code == 422


# -- audit ------------------------------------------------------------------------------------


def test_every_change_is_audited_before_it_happens_and_after(world):
    post(world, "/policies", name="graphs", document=GRAPH_POLICY)
    assert world.audit.phases("create_policy") == ["requested", "succeeded"]
    first = world.audit.records[0].action
    assert (first.actor_id, first.service, first.operation) == ("root", "iam", "create_policy")


def test_a_change_that_cannot_be_audited_is_not_made(world):
    world.audit.broken = True
    refused = post(world, "/policies", name="graphs", document=GRAPH_POLICY)
    assert refused.status_code == 503 and "No change made" in refused.text
    world.audit.broken = False
    assert "graphs" not in [p["name"] for p in get(world, "/policies").json()["items"]]


def test_a_failed_change_is_audited_as_failed_with_its_error_type(world):
    refused = post(
        world,
        "/policies",
        name="bad",
        document={
            "version": "2026-10-13",
            "statements": [{"effect": "Allow", "actions": ["nope:Nothing"], "resources": ["*"]}],
        },
    )
    assert refused.status_code == 422
    record = world.audit.records[-1]
    assert record.phase == "failed" and record.error == "PolicyValidationError"


def test_every_change_route_writes_an_audit_record(world):
    policy = post(world, "/policies", name="graphs", document=GRAPH_POLICY).json()
    group = post(world, "/groups", name="g").json()
    member = _principal_id(world, "member")
    account = post(world, "/service-accounts", name="ci/x").json()
    key = post(world, f"/service-accounts/{account['id']}/keys").json()["key"]
    calls = [
        lambda: world.client.put(
            f"/api/iam/admin/policies/{policy['id']}",
            json={"expected_revision": 1, "name": "n"},
            headers=as_("root"),
        ),
        lambda: post(world, "/attachments", policy_id=policy["id"], principal_id=group["id"]),
        lambda: world.client.delete(
            "/api/iam/admin/attachments",
            params={"policy_id": policy["id"], "principal_id": group["id"]},
            headers=as_("root"),
        ),
        lambda: world.client.put(
            f"/api/iam/admin/groups/{group['id']}/members/{member}", headers=as_("root")
        ),
        lambda: world.client.delete(
            f"/api/iam/admin/groups/{group['id']}/members/{member}", headers=as_("root")
        ),
        lambda: world.client.put(
            f"/api/iam/admin/groups/{group['id']}/idp-mappings",
            json={"provider": "p", "claim_value": "v"},
            headers=as_("root"),
        ),
        lambda: world.client.delete(
            f"/api/iam/admin/groups/{group['id']}/idp-mappings",
            params={"provider": "p", "claim_value": "v"},
            headers=as_("root"),
        ),
        lambda: post(world, f"/principals/{member}/suspend"),
        lambda: post(world, f"/principals/{member}/resume"),
        lambda: post(world, f"/service-accounts/{account['id']}/keys/{key['id']}/rotate"),
        lambda: world.client.delete(f"/api/iam/admin/groups/{group['id']}", headers=as_("root")),
        lambda: world.client.delete(f"/api/iam/admin/policies/{policy['id']}", headers=as_("root")),
        lambda: world.client.delete(
            f"/api/iam/admin/service-accounts/{account['id']}", headers=as_("root")
        ),
    ]
    for call in calls:
        before = len(world.audit.records)
        response = call()
        assert response.status_code < 300, response.text
        assert len(world.audit.records) - before == 2
    operations = {r.action.operation for r in world.audit.records}
    assert {
        "create_policy",
        "update_policy",
        "delete_policy",
        "attach_policy",
        "detach_policy",
        "create_group",
        "delete_group",
        "add_group_member",
        "remove_group_member",
        "map_idp_group",
        "unmap_idp_group",
        "suspend_principal",
        "resume_principal",
        "create_service_account",
        "create_key",
        "rotate_key",
        "delete_principal",
    } <= operations


def test_the_history_is_for_platform_admins(world):
    post(world, "/policies", name="graphs", document=GRAPH_POLICY)
    history = get(world, "/audit").json()["items"]
    assert [(e["operation"], e["phase"]) for e in history][:2] == [
        ("create_policy", "succeeded"),
        ("create_policy", "requested"),
    ]
    assert get(world, "/audit?operation=nothing").json()["items"] == []
    for user in ("admin", "lister", "stranger"):
        assert get(world, "/audit", user).status_code == 403


# -- policies and groups of an org or a workspace ---------------------------------------------

SCOPED_READER = {
    "version": "2026-10-13",
    "statements": [
        {
            "effect": "Allow",
            "actions": ["triple_store:Query"],
            "resources": ["${scope}:triple_store:graph/*"],
        }
    ],
}


def put(world, path, user="root"):
    return world.client.put(f"/api/iam/admin{path}", headers=as_(user))


@pytest.fixture
def ws2(world):
    """``ws-2`` of ``org-1`` with its own admin and a member (``colleague``), and a
    member of another org (``outsider``)."""
    scope = world.nexus.workspace("org-1", "ws-2")
    world.nexus.grant("ws2admin", "admin", scope)
    world.nexus.grant("colleague", "member", scope)
    world.nexus.grant("outsider", "member", world.nexus.workspace("org-9", "ws-9"))
    return scope


def test_a_workspace_admin_manages_its_own_policies_and_groups(world, ws2):
    ws1 = workspace_scope("org-1", "ws-1")
    created = post(
        world, "/policies", "ws2admin", name="readers", document=SCOPED_READER, scope=ws2
    )
    assert created.status_code == 201, created.text
    policy = created.json()
    assert policy["owner_scope"] == ws2
    group = post(world, "/groups", "ws2admin", name="analysts", scope=ws2).json()
    assert group["owner_scope"] == ws2 and group["org"] == "org-1"
    attached = post(
        world,
        "/attachments",
        "ws2admin",
        policy_id=policy["id"],
        principal_id=group["id"],
        scope=ws2,
    )
    assert attached.status_code < 300, attached.text
    colleague = _principal_id(world, "colleague")
    added = put(world, f"/groups/{group['id']}/members/{colleague}", "ws2admin")
    assert added.status_code == 200, added.text
    assert [m["id"] for m in added.json()["members"]] == [colleague]

    # Users of another org and service accounts never join.
    outsider = _principal_id(world, "outsider")
    assert put(world, f"/groups/{group['id']}/members/{outsider}", "ws2admin").status_code == 422
    with as_service_account("engine"):
        account = world.nexus.iam.create_service_account("ci/nightly")
    assert put(world, f"/groups/{group['id']}/members/{account.id}", "ws2admin").status_code == 422

    # Its lists: its own, plus what it may attach from above (the roles below owner).
    listed = {p["id"] for p in get(world, f"/policies?scope={ws2}", "ws2admin").json()["items"]}
    assert policy["id"] in listed and "builtin.member" in listed
    assert "builtin.owner" not in listed
    groups = get(world, f"/groups?scope={ws2}", "ws2admin").json()["items"]
    assert [g["id"] for g in groups] == [group["id"]]
    assert get(world, f"/access?scope={ws2}", "ws2admin").json()["actions"]["iam:CreatePolicy"]

    # Nothing of ws-1's.
    assert get(world, f"/policies?scope={ws1}", "ws2admin").status_code == 403
    assert get(world, f"/groups?scope={ws1}", "ws2admin").status_code == 403
    ws1_policy = post(world, "/policies", "admin", name="ws-1", document=SCOPED_READER, scope=ws1)
    assert ws1_policy.status_code == 201, ws1_policy.text
    assert get(world, f"/policies/{ws1_policy.json()['id']}", "ws2admin").status_code == 404
    refused = post(world, "/policies", "ws2admin", name="x", document=SCOPED_READER, scope=ws1)
    assert refused.status_code in (403, 404)
    # A ws-2 policy goes at ws-2 only.
    member = _principal_id(world, "member")
    elsewhere = post(
        world, "/attachments", "ws2admin", policy_id=policy["id"], principal_id=member, scope=ws1
    )
    assert elsewhere.status_code in (403, 404)
    assert world.audit.phases("create_policy")[-1] == "failed"


def test_an_org_admin_manages_its_workspaces_policies_and_groups(world, ws2):
    policy = post(
        world, "/policies", "ws2admin", name="readers", document=SCOPED_READER, scope=ws2
    ).json()
    # ``admin`` is an admin of org-1, mirrored org-wide.
    seen = {p["id"] for p in get(world, f"/policies?scope={ws2}", "admin").json()["items"]}
    assert policy["id"] in seen
    org_group = post(world, "/groups", "admin", name="org team", scope=org_scope("org-1"))
    assert org_group.status_code == 201, org_group.text
    assert org_group.json()["owner_scope"] == org_scope("org-1")
    attached = post(
        world,
        "/attachments",
        "admin",
        policy_id=policy["id"],
        principal_id=org_group.json()["id"],
        scope=ws2,
    )
    assert attached.status_code < 300, attached.text
    # The org's groups are offered at its workspaces, to whoever attaches there.
    groups = {g["id"] for g in get(world, f"/groups?scope={ws2}", "ws2admin").json()["items"]}
    assert org_group.json()["id"] in groups
    deleted = world.client.delete(f"/api/iam/admin/policies/{policy['id']}", headers=as_("admin"))
    assert deleted.status_code == 409  # still attached: IAM's rule


def test_members_and_viewers_see_nothing_of_iam_administration(world):
    ws1 = workspace_scope("org-1", "ws-1")
    for user in ("member", "viewer"):
        for page in (
            f"/policies?scope={ws1}",
            f"/groups?scope={ws1}",
            f"/attachments?scope={ws1}",
            f"/catalogs?scope={ws1}",
            "/policies",
            "/groups",
        ):
            assert get(world, page, user).status_code == 403, (user, page)
        assert post(
            world, "/policies", user, name="x", document=SCOPED_READER, scope=ws1
        ).status_code in (403, 404)
        assert post(world, "/groups", user, name="x", scope=ws1).status_code in (403, 404)
        assert not any(get(world, f"/access?scope={ws1}", user).json()["actions"].values())
