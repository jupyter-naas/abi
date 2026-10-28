"""Feature policies: ``nexus:UseFeature`` comes only from them."""

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.IAMPorts import ResourceNotFoundError

NEXUS = ActionCatalog(
    service="nexus",
    version=1,
    resource_types=(
        ResourceType("workspace", id="singleton"),
        ResourceType("feature"),
    ),
    actions=(
        ActionSpec("GetWorkspace", "read", ("workspace",)),
        ActionSpec("UseFeature", "read", ("feature",)),
    ),
)
WS = "abi:org-1:ws-1"


def feature(name: str, org: str = "org-1", workspace: str = "ws-1") -> str:
    return f"abi:{org}:{workspace}:nexus:feature/{name}"


@pytest.fixture
def nexus(iam):
    iam._register_catalog(NEXUS)
    return iam


def attached(iam, principal_id: str) -> set[tuple[str, str | None]]:
    return {
        (a.policy_id, a.scope)
        for a in iam.store.list_attachments(principal_id=principal_id)
    }


def put(iam, grants):
    with as_service_account("engine"):
        iam.put_feature_policies(grants)


def test_a_role_has_no_feature_without_a_feature_policy(h, nexus):
    bob = h.user()
    h.attach(roles.OWNER, bob.id, WS)
    assert h.allowed("nexus:GetWorkspace", "abi:org-1:ws-1:nexus:workspace/-", bob)
    assert not h.allowed("nexus:UseFeature", feature("chat"), bob)


def test_the_most_specific_feature_policy_rides_with_the_role(h, nexus):
    bob = h.user()
    h.attach(roles.MEMBER, bob.id, WS)
    put(
        nexus,
        {
            "member": ["chat", "files"],
            "org-1.member": ["chat"],
            "org-1.ws-2.member": ["maps"],
        },
    )
    assert attached(nexus, bob.id) >= {("builtin.features.org-1.member", WS)}
    assert not any(
        p in {"builtin.features.member", "builtin.features.org-1.ws-2.member"}
        for p, _ in attached(nexus, bob.id)
    )
    assert h.allowed("nexus:UseFeature", feature("chat"), bob)
    assert not h.allowed("nexus:UseFeature", feature("files"), bob)
    # Another workspace of the org follows the org's overlay, ws-2 its own override.
    h.attach(roles.MEMBER, bob.id, "abi:org-1:ws-2")
    assert h.allowed("nexus:UseFeature", feature("maps", workspace="ws-2"), bob)
    assert not h.allowed("nexus:UseFeature", feature("chat", workspace="ws-2"), bob)
    # An org without an overlay follows the deployment's.
    h.attach(roles.MEMBER, bob.id, "abi:org-2:ws-9")
    assert h.allowed("nexus:UseFeature", feature("files", "org-2", "ws-9"), bob)


def test_feature_policies_follow_attach_detach_and_changes(h, nexus):
    put(nexus, {"viewer": ["chat"], "member": ["chat", "files"]})
    bob = h.user()
    h.attach(roles.VIEWER, bob.id, WS)
    assert h.allowed("nexus:UseFeature", feature("chat"), bob)
    assert not h.allowed("nexus:UseFeature", feature("files"), bob)
    # A promotion swaps the role and its features.
    h.attach(roles.MEMBER, bob.id, WS)
    with as_service_account("engine"):
        nexus.detach_policy(roles.VIEWER, bob.id, WS)
    assert h.allowed("nexus:UseFeature", feature("files"), bob)
    assert attached(nexus, bob.id) >= {("builtin.features.member", WS)}
    assert ("builtin.features.viewer", WS) not in attached(nexus, bob.id)
    # Removing the role removes its features.
    with as_service_account("engine"):
        nexus.detach_policy(roles.MEMBER, bob.id, WS)
    assert not any(
        p.startswith(roles.FEATURES_PREFIX) for p, _ in attached(nexus, bob.id)
    )
    # Replacing the set drops what is not named, attachments included.
    h.attach(roles.MEMBER, bob.id, WS)
    put(nexus, {"member": ["maps"]})
    assert attached(nexus, bob.id) >= {("builtin.features.member", WS)}
    assert "viewer" not in nexus.feature_policy_keys()
    assert h.allowed("nexus:UseFeature", feature("maps"), bob)
    assert not h.allowed("nexus:UseFeature", feature("files"), bob)


def test_org_level_roles_bring_no_features_and_org_wide_ones_do(h, nexus):
    put(nexus, {"owner": ["chat"], "org-1.owner": ["files"]})
    bob = h.user()
    h.attach(roles.OWNER, bob.id, "abi:org-1:-")
    assert not any(
        p.startswith(roles.FEATURES_PREFIX) for p, _ in attached(nexus, bob.id)
    )
    h.attach(roles.OWNER, bob.id, "abi:org-1:*")
    assert ("builtin.features.org-1.owner", "abi:org-1:*") in attached(nexus, bob.id)
    assert h.allowed("nexus:UseFeature", feature("files", workspace="ws-7"), bob)


def test_a_role_scope_pattern_never_reaches_a_feature(h, nexus):
    bob = h.user()
    h.attach(roles.OWNER, bob.id, WS)
    put(nexus, {"owner": ["chat"]})
    assert h.allowed("nexus:UseFeature", feature("chat"), bob)
    assert not h.allowed("nexus:UseFeature", feature("code"), bob)


def test_platform_admin_reaches_every_feature(h, nexus):
    root = h.user("root")
    h.attach(roles.PLATFORM_ADMIN, root.id)
    assert h.allowed("nexus:UseFeature", feature("code"), root)


def test_feature_policies_are_validated_and_authorized(h, nexus):
    with as_service_account("engine"):
        with pytest.raises(ValueError):
            nexus.put_feature_policies({"boss": ["chat"]})
        with pytest.raises(ValueError):
            nexus.put_feature_policies({"member": ["Chat Room"]})
        with pytest.raises(ValueError):
            nexus.put_feature_policies({"a.b.c.member": ["chat"]})
    bob = h.user()
    with h.as_(bob), pytest.raises(ResourceNotFoundError):
        nexus.put_feature_policies({"member": ["chat"]})


def test_platform_grants_reach_members_by_level(h, iam):
    from naas_abi_core.services.iam.kernel_catalogs import kernel_catalogs

    for catalog in kernel_catalogs():
        iam._register_catalog(catalog)
    repo = "abi:-:-:source_control:repo/abi%2Fmonorepo"
    branch = "abi:-:-:source_control:branch/abi%2Fmonorepo/slides%2Fws-1%2Fa"
    viewer, member = h.user("viewer"), h.user("member")
    h.attach(roles.VIEWER, viewer.id, WS)
    h.attach(roles.MEMBER, member.id, WS)
    assert not h.allowed("source_control:GetFile", repo, viewer)
    with as_service_account("engine"):
        iam.set_platform_grants(
            [
                roles.PlatformGrant(
                    "source_control", (repo, branch.rsplit("/", 1)[0] + "/*")
                )
            ]
        )
    assert h.allowed("source_control:GetFile", repo, viewer)
    assert not h.allowed("source_control:UpsertFile", repo, viewer)
    assert h.allowed("source_control:CreateBranch", branch, member)
    assert not h.allowed("source_control:CreateBranch", branch, viewer)
    assert not h.allowed("source_control:AddCollaborator", repo, member)
    # A regeneration (a catalog change) keeps the grants.
    iam._register_catalog(NEXUS)
    assert h.allowed("source_control:GetFile", repo, viewer)
