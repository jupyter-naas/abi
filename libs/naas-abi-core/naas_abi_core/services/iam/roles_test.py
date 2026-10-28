import inspect

import pytest

from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ActionSpec,
    CatalogError,
    CatalogRegistry,
    PlatformAccess,
    ResourceType,
)
from naas_abi_core.services.iam.iam_catalog import CATALOG as IAM

# What naas_abi declares: the flags say what the roles leave out.
NEXUS = ActionCatalog(
    service="nexus",
    version=1,
    resource_types=(
        ResourceType("workspace", id="singleton"),
        ResourceType("feature", policy_only=True),
        ResourceType("conversation", id="path", personal=True),
        ResourceType("organization", id="singleton"),
        ResourceType("provider_model", placement="platform"),
    ),
    actions=(
        ActionSpec("GetWorkspace", "read", ("workspace",)),
        ActionSpec("UpdateWorkspace", "admin", ("workspace",)),
        ActionSpec("DeleteWorkspace", "admin", ("workspace",), owner_only=True),
        ActionSpec("UseFeature", "read", ("feature",)),
        ActionSpec("GetConversation", "read", ("conversation",)),
        ActionSpec("CreateOrganization", "write", ("organization",)),
        ActionSpec("ListProviderModels", "list", ("provider_model",)),
    ),
    platform_access=(
        PlatformAccess(("organization/-",), self_=("CreateOrganization",)),
        PlatformAccess(("provider_model/*",), viewer=("ListProviderModels",)),
    ),
)


def registry() -> CatalogRegistry:
    found = CatalogRegistry()
    found.register(IAM)
    found.register(NEXUS)
    return found


def actions_of(policy) -> set[str]:
    return {a for s in policy.document.statements for a in s.actions}


def resources_of(policy) -> set[str]:
    return {r for s in policy.document.statements for r in s.resources}


def test_roles_are_cumulative_by_level():
    found = registry()
    viewer, member, admin, owner = (roles.role_policy(r, found) for r in roles.ROLES)
    assert (
        actions_of(viewer)
        <= actions_of(member)
        <= actions_of(admin)
        <= actions_of(owner)
    )
    assert "nexus:GetWorkspace" in actions_of(viewer)
    assert "nexus:UpdateWorkspace" in actions_of(admin)
    assert "nexus:UpdateWorkspace" not in actions_of(member)


def test_no_role_reaches_a_policy_only_type_and_owner_only_actions_are_the_owners():
    found = registry()
    for role in roles.ROLES:
        policy = roles.role_policy(role, found)
        assert "nexus:UseFeature" not in actions_of(policy)
        assert not any("feature" in r for r in resources_of(policy))
    assert "nexus:DeleteWorkspace" not in actions_of(
        roles.role_policy(roles.ADMIN, found)
    )
    assert "nexus:DeleteWorkspace" in actions_of(roles.role_policy(roles.OWNER, found))


def test_personal_types_are_reached_through_their_owner():
    viewer = roles.role_policy(roles.VIEWER, registry())
    assert "${scope}:nexus:conversation/${principal.id}" in resources_of(viewer)
    assert "${scope}:nexus:conversation/${principal.id}/*" in resources_of(viewer)
    assert "${scope}:nexus:conversation/*" not in resources_of(viewer)


def test_admins_grant_roles_below_owner_only():
    admin = roles.role_policy(roles.ADMIN, registry())
    sids = ("AdminGrantsRolesBelowOwner", "AdminAttachesCustomerPolicies")
    grants = {s.sid: s for s in admin.document.statements if s.sid in sids}
    assert set(grants[sids[0]].resources) == {
        "${scope}:iam:attachment/builtin.admin/*",
        "${scope}:iam:attachment/builtin.member/*",
        "${scope}:iam:attachment/builtin.viewer/*",
    }
    # Customer policies (pol_…), never another managed one (owner, features).
    assert grants[sids[1]].resources == ("${scope}:iam:attachment/pol_*/*",)
    # Nothing else of admin's names the attachment type with an admin action.
    others = [s for s in admin.document.statements if s.sid not in sids]
    assert not any(
        "iam:AttachPolicy" in s.actions or "iam:DetachPolicy" in s.actions
        for s in others
    )
    owner = roles.role_policy(roles.OWNER, registry())
    assert {"iam:AttachPolicy", "iam:DetachPolicy"} <= actions_of(owner)


def test_statements_carry_valid_sids_and_stay_within_limits():
    import re

    for policy in roles.builtin_policies(registry()):
        assert len(policy.document.statements) <= 100
        sids = [s.sid for s in policy.document.statements]
        assert len(set(sids)) == len(sids), policy.id
        for statement in policy.document.statements:
            assert statement.sid and re.match(r"^[A-Za-z0-9]{1,64}$", statement.sid)
            assert len(statement.actions) <= 100


def test_platform_and_self_policies_name_registered_actions_only():
    found = registry()
    self_policy = next(p for p in roles.builtin_policies(found) if p.id == roles.SELF)
    assert actions_of(self_policy) == {
        "iam:GetPrincipal",
        "iam:RevokeTokens",
        "iam:ListKeys",
        "iam:CreateKey",
        "iam:RevokeKey",
        "nexus:CreateOrganization",
    }


def test_engine_and_api_hold_enumerated_statements_only():
    by_id = {p.id: p for p in roles.builtin_policies(registry())}
    for policy_id in (roles.ENGINE, roles.API):
        statements = by_id[policy_id].document.statements
        assert statements
        for statement in statements:
            assert statement.sid, policy_id
            assert statement.actions != ("*",), (policy_id, statement.sid)
            assert "*" not in statement.actions
        assert not any("TRANSITIONAL" in s.description for s in [by_id[policy_id]])
    api_services = {
        a.split(":")[0] for s in by_id[roles.API].document.statements for a in s.actions
    }
    assert "identity" in api_services and "nexus" in api_services
    # Nexus does not administer IAM: only the memberships, scopes and placements.
    assert not any(
        a == "iam:*" for s in by_id[roles.API].document.statements for a in s.actions
    )
    assert any(
        a == "iam:*" for s in by_id[roles.ENGINE].document.statements for a in s.actions
    )


def _platform(policy_id: str, found: CatalogRegistry):
    return next(p for p in roles.builtin_policies(found) if p.id == policy_id)


def test_a_catalogs_platform_access_joins_the_platform_policies():
    found = registry()
    self_policy = _platform(roles.SELF, found)
    viewer = _platform(roles.PLATFORM_VIEWER, found)
    member = _platform(roles.PLATFORM_MEMBER, found)
    assert "nexus:CreateOrganization" in actions_of(self_policy)
    assert "abi:-:-:nexus:organization/-" in resources_of(self_policy)
    for policy in (viewer, member):
        assert "nexus:ListProviderModels" in actions_of(policy)
        assert "abi:-:-:nexus:provider_model/*" in resources_of(policy)
    assert "nexus:ListProviderModels" not in actions_of(self_policy)


def test_a_modules_catalog_declares_no_platform_access():
    with pytest.raises(CatalogError, match="platform access"):
        ActionCatalog(
            service="acme",
            version=1,
            resource_types=(ResourceType("deal"),),
            actions=(ActionSpec("GetDeal", "read", ("deal",)),),
            module="acme",
            platform_access=(PlatformAccess(("deal/*",), viewer=("GetDeal",)),),
        )


@pytest.mark.parametrize(
    "access, error",
    [
        (PlatformAccess(("ghost/*",), viewer=("GetWorkspace",)), "not <type>/<id>"),
        (PlatformAccess(("workspace",), viewer=("GetWorkspace",)), "not <type>/<id>"),
        (PlatformAccess(("workspace/*",), viewer=("Nope",)), "unknown action"),
    ],
)
def test_platform_access_names_this_catalogs_types_and_actions(access, error):
    with pytest.raises(CatalogError, match=error):
        ActionCatalog(
            service="acme",
            version=1,
            resource_types=(ResourceType("workspace"),),
            actions=(ActionSpec("GetWorkspace", "read", ("workspace",)),),
            platform_access=(access,),
        )


def test_only_an_admin_action_is_owner_only():
    with pytest.raises(CatalogError, match="owner-only"):
        ActionCatalog(
            service="acme",
            version=1,
            resource_types=(ResourceType("workspace"),),
            actions=(
                ActionSpec("GetWorkspace", "read", ("workspace",), owner_only=True),
            ),
        )


def test_the_flags_survive_the_catalog_format_and_the_wire():
    from naas_abi_core.services.iam.adapters import iam_nats_codec as codec

    assert ActionCatalog.from_dict(NEXUS.to_dict(stored=True)) == NEXUS
    # The stored form has the format; read back from a store without one, it
    # is an older writer's.
    assert "format" not in NEXUS.to_dict()
    assert ActionCatalog.from_dict(NEXUS.to_dict(), stored=True).format == 1
    assert codec.catalog_from_pb(codec.catalog_to_pb(NEXUS)) == NEXUS


def test_core_roles_name_no_nexus_action_or_type():
    """naas_abi is a module: its catalog's flags say what the roles leave out
    (``builtin.api``, Nexus's own account, aside)."""
    assert not any(row.service == "nexus" for row in roles.PLATFORM_TYPES)
    source = inspect.getsource(roles).replace(
        '_everything_of("NexusOwnActions", "nexus")', ""
    )
    assert "nexus:" not in source
    assert '"nexus"' not in source
    assert "feature" not in source.replace("builtin.features.", "")
