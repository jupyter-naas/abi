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
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_below,
    org_container,
    workspace_container,
)
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
        {
            "effect": "Allow",
            "actions": ["iam:ListPolicies"],
            "resources": ["abi:iam:policy/*", "abi:*/iam:policy/*"],
        }
    ],
}
GRAPH_POLICY = {
    "version": "2026-10-13",
    "statements": [
        {
            "sid": "Read",
            "effect": "Allow",
            "actions": ["triple_store:Query", "triple_store:ListGraphs"],
            "resources": ["abi:triple_store:graph/*"],
        },
        {
            "sid": "NoSecret",
            "effect": "Deny",
            "actions": ["triple_store:Query"],
            "resources": ["abi:triple_store:graph/secret"],
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
    # A delegated IAM admin: Platform settings shows them Roles & permissions and nothing of
    # System or the tables, which need nexus:ReadSystem.
    assert root["nexus:ReadSystem"] and not lister["nexus:ReadSystem"]
    assert not any(get(world, "/access", "stranger").json()["actions"].values())


def test_access_at_a_scope_follows_the_attachment_rules(world):
    scope = org_container("org-1")
    admin = get(world, f"/access?scope={scope}", "admin").json()["actions"]
    assert admin["iam:ListAttachments"] and admin["iam:AttachPolicy"]
    other = get(world, f"/access?scope={org_container('org-2')}", "admin").json()["actions"]
    assert not other["iam:ListAttachments"] and not other["iam:AttachPolicy"]
    assert get(world, "/access?scope=nonsense", "admin").status_code == 422


PLATFORM_ONLY = (
    "iam:ListPrincipals",
    "iam:CreateServiceAccount",
    "iam:Explain",
    "iam:ListManifests",
    "iam:ApproveManifest",
    "iam:MapIdpGroup",
    "iam:UnmapIdpGroup",
    "iam:ListKeys",
    "iam:CreateKey",
    "nexus:ReadSystem",
)


def test_access_at_a_scope_answers_for_that_level_alone(world):
    """Service accounts, keys, approvals, the simulator, IdP mappings and the audit are the
    platform's: the Roles & permissions page of an org or a workspace never offers them,
    not even to the platform admin."""
    platform = get(world, "/access").json()["actions"]
    assert all(platform[action] for action in PLATFORM_ONLY)
    for scope in (org_container("org-1"), org_below("org-1"), workspace_container("org-1", "ws-1")):
        root = get(world, f"/access?scope={scope}").json()["actions"]
        assert not any(root[action] for action in PLATFORM_ONLY), scope
        assert root["iam:ListPolicies"] and root["iam:CreateGroup"] and root["iam:AttachPolicy"]


def test_access_reports_no_role_feature_defaults(world):
    """No role brings a feature: there are no defaults to read or edit anywhere."""
    for scope in (org_container("org-1"), workspace_container("org-1", "ws-1"), None):
        query = f"?scope={scope}" if scope else ""
        actions = get(world, f"/access{query}", "owner").json()["actions"]
        assert not any("RoleFeatures" in action for action in actions), scope


# -- policies --------------------------------------------------------------------------------


def test_a_policy_is_validated_created_edited_and_deleted(world):
    bad = post(
        world,
        "/policies/validate",
        document={
            "version": "2026-10-13",
            "statements": [
                {"effect": "Allow", "actions": ["nope:Nothing"], "resources": ["abi:nope:x/1"]},
                {"effect": "Maybe", "actions": [], "resources": []},
            ],
        },
    )
    assert bad.status_code == 200 and bad.json()["valid"] is False
    assert len(bad.json()["errors"]) >= 2

    text = "version: '2026-10-13'\nstatements:\n  - effect: Allow\n    actions: [triple_store:Query]\n    resources: ['abi:triple_store:graph/*']\n"
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
    scope = org_container("org-1")
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
        scope=org_container("org-2"),
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
        scope=workspace_container("org-1", "ws-1"),
    )
    assert response.status_code in (403, 404)
    # IAM administration is the admins' and owners': a member lists no attachment,
    # at its own scope or another's.
    assert get(world, f"/attachments?scope={org_container('org-1')}", "member").status_code == 403
    assert get(world, f"/attachments?scope={org_container('org-2')}", "member").status_code == 403


def test_attachable_policies_are_those_the_caller_may_attach_at_the_scope(world):
    scope = org_container("org-1")
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
                "abi:triple_store:graph/${module.id}-*",
                "abi:triple_store:graph/shared",
            ],
        },
        {
            "sid": "NoAdmin",
            "effect": "Deny",
            "actions": ["triple_store:DropGraph"],
            "resources": ["abi:triple_store:graph/*"],
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
                "resources": ["abi:triple_store:graph/${module.id}-*"],
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


CATALOG = {
    "version": 1,
    "resource_types": [{"name": "report", "id": "path"}],
    "actions": [{"name": "ExportReport", "level": "read", "resource_types": ["report"]}],
}


@pytest.fixture
def declaring(world):
    """A module whose manifest declares a catalog of its own."""
    from naas_abi_core.services.iam import module_scopes

    world.nexus.iam._register_catalog(module_scopes.CATALOG)
    with as_service_account("engine"):
        account = world.nexus.iam.create_service_account("module/acme/reports")
    context = CallContext(
        principal=Principal(id=account.id, kind="service_account", name=account.name)
    )
    with use_call_context(context):
        submitted = world.nexus.iam.submit_manifest(
            "reports", "acme", {**MANIFEST, "catalog": CATALOG}
        )
    return SimpleNamespace(account=account, sha=submitted.manifest.sha256)


def test_a_manifest_declaring_a_catalog_is_shown_split_and_narrowed(world, declaring):
    (listed,) = [
        m
        for m in get(world, "/manifests?status=pending").json()["items"]
        if m["module_id"] == "reports"
    ]
    assert "catalog" not in listed["document"]
    assert listed["catalog"]["service"] == "reports"
    assert listed["catalog"]["actions"][0]["name"] == "ExportReport"

    path = f"/manifests/{declaring.account.id}/{declaring.sha}/approve"
    # The UI may echo the catalog back; a changed one is refused.
    changed = {**MANIFEST, "catalog": {**CATALOG, "actions": []}}
    refused = post(world, path, document=changed)
    assert refused.status_code == 422
    assert "approved as submitted" in " ".join(refused.json()["detail"]["errors"])

    narrowed = {
        "version": MANIFEST["version"],
        "statements": [
            {**MANIFEST["statements"][0], "actions": MANIFEST["statements"][0]["actions"][:1]},
            MANIFEST["statements"][1],
        ],
    }
    ok = post(world, path, document={**narrowed, "catalog": listed["catalog"]})
    assert ok.status_code == 200, ok.text
    assert world.nexus.iam.catalogs.get("reports").module == "reports"


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
        resource="abi:triple_store:graph/sales",
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
        resource="abi:triple_store:graph/secret",
    ).json()
    assert not denied["allowed"] and denied["reason"] == "explicit_deny"
    assert denied["statement"]["sid"] == "NoSecret" and denied["statement"]["effect"] == "Deny"

    nothing = post(
        world,
        "/simulate",
        principal_id=user,
        action="triple_store:DropGraph",
        resource="abi:triple_store:graph/sales",
    ).json()
    assert not nothing["allowed"] and nothing["reason"] == "implicit_deny"
    assert nothing["statement"] is None and nothing["principal"]["id"] == user


def test_the_simulator_needs_iam_explain(world):
    user = _principal_id(world, "member")
    body = {
        "principal_id": user,
        "action": "triple_store:Query",
        "resource": "abi:triple_store:graph/a",
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
            "resources": ["${scope}/triple_store:graph/*"],
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
    ws1 = workspace_container("org-1", "ws-1")
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
    org_group = post(world, "/groups", "admin", name="org team", scope=org_container("org-1"))
    assert org_group.status_code == 201, org_group.text
    assert org_group.json()["owner_scope"] == org_container("org-1")
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
    ws1 = workspace_container("org-1", "ws-1")
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


def test_validating_at_a_scope_checks_what_creating_there_does(world, ws2):
    def statement(effect, resource):
        return {
            "version": "2026-10-13",
            "statements": [
                {"effect": effect, "actions": ["triple_store:Query"], "resources": [resource]}
            ],
        }

    at_ws2 = f"/policies/validate?scope={ws2}"
    for document in (statement("Deny", "*"), statement("Allow", f"{ws2}:triple_store:graph/*")):
        checked = post(world, at_ws2, "ws2admin", document=document).json()
        assert checked["valid"] is False and "${scope}" in checked["errors"][0], checked
        refused = post(world, "/policies", "ws2admin", name="x", document=document, scope=ws2)
        assert refused.status_code == 422, refused.text
    assert post(world, at_ws2, "ws2admin", document=SCOPED_READER).json()["valid"] is True
    # The platform's policies name what they like.
    assert post(world, "/policies/validate", document=statement("Deny", "*")).json()["valid"]


def test_an_org_wide_scope_lists_its_orgs_policies_and_groups(world, ws2):
    org = org_container("org-1")
    policy = post(world, "/policies", "admin", name="org", document=SCOPED_READER, scope=org)
    group = post(world, "/groups", "admin", name="org team", scope=org)
    assert policy.status_code == 201 and group.status_code == 201
    wide = org_below("org-1")
    policies = get(world, f"/policies?scope={wide}", "admin")
    groups = get(world, f"/groups?scope={wide}", "admin")
    assert policies.status_code == 200 and groups.status_code == 200, policies.text
    assert policy.json()["id"] in {p["id"] for p in policies.json()["items"]}
    assert group.json()["id"] in {g["id"] for g in groups.json()["items"]}
    # Answered as for the org: a workspace's admin holds nothing there.
    for path in ("/policies", "/groups"):
        assert get(world, f"{path}?scope={wide}", "ws2admin").status_code == 403
        assert get(world, f"{path}?scope={org}", "ws2admin").status_code == 403


def test_a_platform_deny_is_attached_at_a_scope_by_the_platform_admin_only(world):
    guard = post(
        world,
        "/policies",
        name="guardrail",
        document={
            "version": "2026-10-13",
            "statements": [
                {
                    "effect": "Allow",
                    "actions": ["triple_store:Query"],
                    "resources": ["${scope}/triple_store:graph/*"],
                },
                {"effect": "Deny", "actions": ["iam:*"], "resources": ["*"]},
            ],
        },
    ).json()
    shared = post(world, "/policies", name="shared", document=SCOPED_READER).json()
    scope = workspace_container("org-1", "ws-1")
    member = _principal_id(world, "member")
    # Attached nowhere, the shared policy is offered once attached at ws-1.
    attached = post(world, "/attachments", policy_id=shared["id"], principal_id=member, scope=scope)
    assert attached.status_code == 201, attached.text
    for user in ("admin", "owner"):
        offered = {
            p["id"] for p in get(world, f"/attachable-policies?scope={scope}", user).json()["items"]
        }
        assert guard["id"] not in offered and shared["id"] in offered, user
        refused = post(
            world, "/attachments", user, policy_id=guard["id"], principal_id=member, scope=scope
        )
        assert refused.status_code == 403, refused.text
    offered = {p["id"] for p in get(world, f"/attachable-policies?scope={scope}").json()["items"]}
    assert guard["id"] in offered
    attached = post(world, "/attachments", policy_id=guard["id"], principal_id=member, scope=scope)
    assert attached.status_code == 201, attached.text


def test_another_organisations_access_policy_is_not_listed(world, ws2):
    """A platform policy confined to a scope and attached in org-1 ("org-1 access",
    as the upgrade makes one per organisation): listed, offered as a parent and
    for attaching in org-1, never to org-9's admins."""
    other_org, other_ws = org_container("org-9"), workspace_container("org-9", "ws-9")
    world.nexus.grant("admin9", "admin", other_org)
    world.nexus.grant("wsadmin9", "admin", other_ws)
    access = post(world, "/policies", name="org-1 access", document=SCOPED_READER).json()
    attached = post(
        world,
        "/attachments",
        policy_id=access["id"],
        principal_id=_principal_id(world, "admin"),
        scope=org_below("org-1"),
    )
    assert attached.status_code == 201, attached.text

    def ids(path: str, user: str) -> set[str]:
        response = get(world, path, user)
        assert response.status_code == 200, response.text
        return {p["id"] for p in response.json()["items"]}

    # The policy list, which the parent picker offers from, and the attach list.
    for user, scopes in (("admin9", (other_org, other_ws)), ("wsadmin9", (other_ws,))):
        for scope in scopes:
            assert access["id"] not in ids(f"/policies?scope={scope}", user), (user, scope)
            assert access["id"] not in ids(f"/attachable-policies?scope={scope}", user)
            assert "builtin.member" in ids(f"/policies?scope={scope}", user)
        assert get(world, f"/policies/{access['id']}", user).status_code == 404
        # Nor named by deriving from it, at its own level.
        refused = post(
            world,
            "/policies",
            user,
            name="mine",
            document=SCOPED_READER,
            scope=other_ws,
            parent=access["id"],
        )
        assert refused.status_code == 403, refused.text
        assert "org-1 access" not in refused.text
    # Org-1's admins, at org-1 and in its workspaces; the platform admin everywhere.
    for scope in (org_container("org-1"), workspace_container("org-1", "ws-1"), ws2):
        assert access["id"] in ids(f"/policies?scope={scope}", "admin")
        assert access["id"] in ids(f"/attachable-policies?scope={scope}", "admin")
    assert access["id"] in ids(f"/policies?scope={ws2}", "ws2admin")
    for scope in (org_container("org-1"), other_org, other_ws):
        assert access["id"] in ids(f"/policies?scope={scope}", "root")
        assert access["id"] in ids(f"/attachable-policies?scope={scope}", "root")
    # Org-1's admin derives from it, as the scenario's "W analysts".
    derived = post(
        world,
        "/policies",
        "admin",
        name="ws-2 analysts",
        document=SCOPED_READER,
        scope=ws2,
        parent=access["id"],
    )
    assert derived.status_code == 201, derived.text


def _attachable(world, user: str, scope: str, principal_id: str | None = None) -> set[str]:
    query = f"?scope={scope}" + (f"&principal_id={principal_id}" if principal_id else "")
    response = get(world, f"/attachable-policies{query}", user)
    assert response.status_code == 200, response.text
    return {p["id"] for p in response.json()["items"]}


def test_the_attach_list_offers_what_may_be_attached_without_listing(world):
    """A right to attach at a level, without one to list its policies, still
    offers the level's own policies."""
    ws1 = workspace_container("org-1", "ws-1")
    own = post(world, "/policies", name="ws-1 readers", document=SCOPED_READER, scope=ws1)
    assert own.status_code == 201, own.text
    world.nexus.user("attacher")
    _holding(
        world,
        "attacher",
        {
            "effect": "Allow",
            "actions": ["iam:AttachPolicy"],
            "resources": [f"{ws1}/iam:attachment/pol_*/*"],
        },
    )
    listed = get(world, f"/policies?scope={ws1}", "attacher")
    assert own.json()["id"] not in {p["id"] for p in listed.json().get("items", [])}
    assert own.json()["id"] in _attachable(world, "attacher", ws1)
    assert own.json()["id"] in _attachable(world, "attacher", ws1, _principal_id(world, "member"))


def test_the_attach_list_offers_a_policy_for_the_one_principal_it_may_go_to(world):
    """A right to attach a policy from above to one principal offers it for that
    principal only."""
    ws1, org1 = workspace_container("org-1", "ws-1"), org_container("org-1")
    created = post(world, "/policies", name="org readers", document=SCOPED_READER, scope=org1)
    assert created.status_code == 201, created.text
    policy = created.json()["id"]
    known = post(
        world,
        "/attachments",
        policy_id=policy,
        principal_id=_principal_id(world, "admin"),
        scope=org1,
    )
    assert known.status_code == 201, known.text
    member, viewer = _principal_id(world, "member"), _principal_id(world, "viewer")
    world.nexus.user("narrow")
    _holding(
        world,
        "narrow",
        {
            "effect": "Allow",
            "actions": ["iam:AttachPolicy"],
            "resources": [f"{ws1}/iam:attachment/{policy}/{member}"],
        },
    )
    assert policy in _attachable(world, "narrow", ws1, member)
    assert policy not in _attachable(world, "narrow", ws1, viewer)
    assert policy not in _attachable(world, "narrow", ws1)


# -- grant only what you hold ------------------------------------------------------------------


def _holding(world, user: str, *statements: dict, scope: str | None = None) -> str:
    """``user`` holds one custom policy (at ``scope``, with a viewer's role there)."""
    principal = _principal_id(world, user)
    with as_service_account("engine"):
        policy = world.nexus.iam.create_policy(
            user, {"version": "2026-10-13", "statements": list(statements)}
        )
        world.nexus.iam.attach_policy(policy.id, principal, scope)
        if scope is not None:
            world.nexus.iam.attach_policy("builtin.viewer", principal, scope)
    return principal


def _refused(response, *named: str) -> None:
    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert "You cannot grant what you do not hold" in detail, detail
    for part in named:
        assert part in detail, detail


def test_an_admin_holding_a_narrower_role_writes_no_wider_policy(world):
    ws1 = workspace_container("org-1", "ws-1")
    _holding(
        world,
        "editor",
        {
            "effect": "Allow",
            "actions": ["iam:CreatePolicy", "iam:UpdatePolicy", "iam:GetPolicy"],
            "resources": ["${scope}/iam:policy/*"],
        },
        {
            "effect": "Allow",
            "actions": ["triple_store:Query"],
            "resources": ["${scope}/triple_store:graph/*"],
        },
        scope=ws1,
    )
    made = post(world, "/policies", "editor", name="readers", document=SCOPED_READER, scope=ws1)
    assert made.status_code == 201, made.text
    wider = {
        "version": "2026-10-13",
        "statements": [
            {
                **SCOPED_READER["statements"][0],
                "actions": ["triple_store:Query", "triple_store:Insert"],
            }
        ],
    }
    _refused(
        post(world, "/policies", "editor", name="writers", document=wider, scope=ws1),
        "triple_store:Insert",
        f"{ws1}/triple_store:graph/*",
    )
    edited = world.client.put(
        f"/api/iam/admin/policies/{made.json()['id']}",
        json={"expected_revision": 1, "document": wider},
        headers=as_("editor"),
    )
    _refused(edited, "triple_store:Insert")
    assert world.audit.phases("create_policy")[-1] == "failed"


def test_an_owner_grants_no_feature_it_does_not_hold(world):
    ws1 = workspace_container("org-1", "ws-1")
    every = {
        "version": "2026-10-13",
        "statements": [
            {
                "effect": "Allow",
                "actions": ["nexus:UseFeature"],
                "resources": ["${scope}/nexus:feature/*"],
            }
        ],
    }
    _refused(
        post(world, "/policies", "owner", name="every feature", document=every, scope=ws1),
        "nexus:UseFeature",
        f"{ws1}/nexus:feature/*",
    )
    # The owner holds chat through a policy (no role brings a feature): it gives that.
    one = "${scope}/nexus:feature/chat"
    some = {"version": "2026-10-13", "statements": [{**every["statements"][0], "resources": [one]}]}
    made = post(world, "/policies", "owner", name="one feature", document=some, scope=ws1)
    assert made.status_code == 201, made.text


def test_nobody_joins_a_group_that_holds_more_than_the_one_adding(world):
    ws1 = workspace_container("org-1", "ws-1")
    admin = _principal_id(world, "admin")
    with as_service_account("engine"):
        owners = world.nexus.iam.create_group("owners", scope=ws1)
        world.nexus.iam.attach_policy("builtin.owner", owners.id, ws1)
    _refused(put(world, f"/groups/{owners.id}/members/{admin}", "admin"), "builtin.owner")
    assert put(world, f"/groups/{owners.id}/members/{admin}", "owner").status_code == 200


def test_a_delegated_approver_approves_no_more_than_it_holds(world, pending):
    _holding(
        world,
        "approver",
        {
            "effect": "Allow",
            "actions": ["iam:ApproveManifest", "iam:GetManifest", "iam:ListManifests"],
            "resources": ["abi:iam:manifest/*"],
        },
        {
            "effect": "Allow",
            "actions": ["triple_store:Query", "triple_store:ListGraphs"],
            "resources": ["abi:triple_store:graph/*"],
        },
    )
    path = f"/manifests/{pending.account.id}/{pending.sha}/approve"
    _refused(post(world, path, "approver"), "triple_store:Insert")
    narrowed = {
        "version": "2026-10-13",
        "statements": [
            {**MANIFEST["statements"][0], "actions": ["triple_store:Query"]},
            MANIFEST["statements"][1],
        ],
    }
    approved = post(world, path, "approver", document=narrowed)
    assert approved.status_code == 200, approved.text


def _grantable(world, user: str, scope: str) -> dict[str, list[str]]:
    found = get(world, f"/grantable?scope={scope}", user)
    assert found.status_code == 200, found.text
    return {a["action"]: a["resources"] for c in found.json()["catalogs"] for a in c["actions"]}


def test_what_the_caller_may_grant(world):
    ws1 = workspace_container("org-1", "ws-1")
    root = _grantable(world, "root", ws1)
    assert root["triple_store:Insert"] == ["${scope}/*"]
    assert root["nexus:UseFeature"] == ["${scope}/*"]
    admin = _grantable(world, "admin", ws1)
    # An admin of the organization holds it below the organization: the graphs of
    # the workspace, and of every container inside it.
    assert admin["triple_store:Insert"] == [
        "${scope}/triple_store:graph/*",
        "${scope}/*/triple_store:graph/*",
    ]
    assert "${scope}/iam:attachment/builtin.owner/*" not in admin["iam:AttachPolicy"]
    assert "${scope}/nexus:feature/*" not in admin.get("nexus:UseFeature", [])
    # Written for every container: at the workspace, its policies and those of the
    # containers inside it.
    assert _grantable(world, "lister", ws1) == {
        "iam:ListPolicies": ["${scope}/iam:policy/*", "${scope}/*/iam:policy/*"]
    }
    assert _grantable(world, "stranger", ws1) == {}
    assert get(world, "/grantable?scope=nonsense", "admin").status_code == 422


# -- sub-policies ----------------------------------------------------------------------------


def test_a_sub_policy_names_its_parent_and_the_parent_its_sub_policies(world, ws2):
    parent = post(world, "/policies", name="graphs", document=SCOPED_READER).json()
    created = post(
        world,
        "/policies",
        name="ws-2 graphs",
        document=SCOPED_READER,
        scope=ws2,
        parent=parent["id"],
    )
    assert created.status_code == 201, created.text
    child = created.json()
    assert child["parent_id"] == parent["id"]
    read = get(world, f"/policies/{child['id']}").json()
    assert read["parent"] == {
        "id": parent["id"],
        "name": "graphs",
        "owner_scope": "abi:",
        "managed": False,
    }
    assert read["sub_policies"] == []
    assert [s["id"] for s in get(world, f"/policies/{parent['id']}").json()["sub_policies"]] == [
        child["id"]
    ]
    assert world.audit.records[-1].action.detail.endswith(f"sub-policy of {parent['id']}")

    # A parent with sub-policies is not deleted: the refusal names them.
    refused = world.client.delete(f"/api/iam/admin/policies/{parent['id']}", headers=as_("root"))
    assert refused.status_code == 409 and child["id"] in refused.json()["detail"]

    # Saving without the parent keeps it; null removes it.
    renamed = world.client.put(
        f"/api/iam/admin/policies/{child['id']}",
        json={"expected_revision": 1, "name": "renamed"},
        headers=as_("root"),
    )
    assert renamed.status_code == 200 and renamed.json()["parent_id"] == parent["id"]
    freed = world.client.put(
        f"/api/iam/admin/policies/{child['id']}",
        json={"expected_revision": 2, "parent": None},
        headers=as_("root"),
    )
    assert freed.status_code == 200 and freed.json()["parent_id"] is None
    assert world.audit.records[-1].action.detail.endswith("no parent")
    assert get(world, f"/policies/{child['id']}").json()["parent"] is None


def test_a_sub_policy_is_refused_as_iam_refuses_it(world, ws2):
    parent = post(world, "/policies", name="graphs", document=SCOPED_READER).json()
    # Ws-2's admin does not hold it: deriving is refused, naming it.
    refused = post(
        world,
        "/policies",
        "ws2admin",
        name="mine",
        document=SCOPED_READER,
        scope=ws2,
        parent=parent["id"],
    )
    assert refused.status_code == 403, refused.text
    assert parent["id"] in refused.json()["detail"]
    assert "derive only from a policy attached to you" in refused.json()["detail"]
    assert world.audit.phases("create_policy")[-1] == "failed"
    # A parent that does not exist, a cycle, an owner above the parent's.
    missing = post(world, "/policies", name="x", document=SCOPED_READER, parent="pol_" + "0" * 26)
    assert missing.status_code == 404
    cycle = world.client.put(
        f"/api/iam/admin/policies/{parent['id']}",
        json={"expected_revision": 1, "parent": parent["id"]},
        headers=as_("root"),
    )
    assert cycle.status_code == 422 and "cycle" in cycle.json()["detail"]
    ws_policy = post(world, "/policies", name="w", document=SCOPED_READER, scope=ws2).json()
    above = post(world, "/policies", name="x", document=SCOPED_READER, parent=ws_policy["id"])
    assert above.status_code == 422 and "or below it" in above.json()["detail"]


def test_a_sub_policy_is_offered_where_iam_lets_it_be_attached(world, ws2):
    """Its parent's Deny beyond ``${scope}`` is its own: offered at a scope to the
    platform admin only; its parent's ``${scope}`` keeps it from being offered
    unscoped."""
    parent = post(
        world,
        "/policies",
        name="no hr anywhere",
        document={
            "version": "2026-10-13",
            "statements": [
                *SCOPED_READER["statements"],
                {
                    "effect": "Deny",
                    "actions": ["triple_store:Query"],
                    "resources": ["abi:triple_store:graph/hr", "abi:*/triple_store:graph/hr"],
                },
            ],
        },
    ).json()
    child = post(
        world, "/policies", name="graphs", document=SCOPED_READER, parent=parent["id"]
    ).json()

    def offered(user: str, scope: str | None) -> set[str]:
        query = f"?scope={scope}" if scope else ""
        response = get(world, f"/attachable-policies{query}", user)
        return {p["id"] for p in response.json()["items"]}

    assert child["id"] not in offered("ws2admin", ws2)
    assert child["id"] in offered("root", ws2)
    assert child["id"] not in offered("root", None)
    refused = post(
        world,
        "/attachments",
        "ws2admin",
        policy_id=child["id"],
        principal_id=_principal_id(world, "colleague"),
        scope=ws2,
    )
    assert refused.status_code == 403 and "unscoped" in refused.json()["detail"]
