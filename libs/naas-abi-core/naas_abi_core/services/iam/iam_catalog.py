"""IAM's own catalog and the seals.

IAM authorizes its own operations with these actions, like any other service.
Four resource types are named in an org or a workspace: ``attachment``, at its
attachment's scope, ``policy`` and ``group``, at the scope that owns them, so
the admins of a workspace or an org manage that level's roles, policies and
groups, and ``set``, read at its own scope and written at the level above
(``sets.py``). Every other type is platform-level.
"""

from __future__ import annotations

from naas_abi_core.services.document.iam_catalog import SEALS as DOCUMENT_SEALS
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.IAMPorts import Seal
from naas_abi_core.services.secret.iam_catalog import SEALS as SECRET_SEALS

SERVICE = "iam"
SUBJECT_PREFIX = "abi.iam.v1"


def _action(
    name: str,
    level: str,
    types: tuple[str, ...],
    *operations: str,
    creates: bool = False,
) -> ActionSpec:
    subjects = tuple(f"{SUBJECT_PREFIX}.{operation}" for operation in operations)
    return ActionSpec(
        name=name,
        level=level,  # type: ignore[arg-type]
        resource_types=types,
        creates=creates,
        subjects=subjects,
    )


CATALOG = ActionCatalog(
    service=SERVICE,
    # 2: SubmitManifest, and the subjects of keys and manifests.
    # 3: RevokeTokens, and the exchange of tokens.
    # 4: ClaimPendingGrants, and the subjects of pending grants and IdP group
    # bindings.
    # 5: policies and groups are placed at the scope that owns them.
    # 6: organisation and workspace sets (GetSet, PutSet).
    version=6,
    resource_types=(
        ResourceType("principal", id="opaque", placement="platform"),
        ResourceType(
            "group",
            id="opaque",
            placement="placed",
            description="group/<group id>, at the scope that owns it.",
        ),
        ResourceType(
            "policy",
            id="opaque",
            placement="placed",
            description="policy/<policy id>, at the scope that owns it.",
        ),
        ResourceType(
            "attachment",
            id="path",
            placement="placed",
            description="attachment/<policy id>/<principal id>, at its scope.",
        ),
        ResourceType(
            "set",
            id="opaque",
            placement="placed",
            description=(
                "set/<org or workspace id>: what an org or a workspace may use, "
                "read at its own scope, written at the level above "
                "(abi:%2A:%2A:iam:set/<org>, abi:<org>:%2A:iam:set/<ws>)."
            ),
        ),
        ResourceType("key", id="path", placement="platform", personal=True),
        ResourceType("manifest", id="opaque", placement="platform"),
        ResourceType("placement", id="path", placement="platform"),
        ResourceType("scope", id="path", placement="platform"),
        ResourceType("catalog", id="opaque", placement="platform"),
        ResourceType("audience", id="opaque", placement="platform"),
    ),
    actions=(
        _action("ListPrincipals", "list", ("principal",), "list_principals"),
        _action("ListGroups", "list", ("group",), "list_groups"),
        _action("ListPolicies", "list", ("policy",), "list_policies"),
        _action(
            "ListAttachments",
            "list",
            ("attachment",),
            "list_attachments",
            "list_pending_grants",
            "list_idp_bindings",
        ),
        _action("ListKeys", "list", ("key",), "list_keys"),
        _action("ListManifests", "list", ("manifest",), "list_manifests"),
        _action("ListPlacements", "list", ("placement",), "list_placements"),
        _action("GetPrincipal", "read", ("principal",), "get_principal"),
        _action("GetGroup", "read", ("group",), "get_group"),
        _action("GetPolicy", "read", ("policy",), "get_policy"),
        _action("GetManifest", "read", ("manifest",), "get_manifest"),
        _action("Explain", "read", ("principal",), "explain"),
        _action("Simulate", "read", ("principal",)),
        _action("ExchangeToken", "write", ("audience",), "exchange_token"),
        _action("RevokeTokens", "admin", ("principal",), "revoke_tokens"),
        _action("CreateUser", "admin", ("principal",), "ensure_user", creates=True),
        _action(
            "CreateServiceAccount",
            "admin",
            ("principal",),
            "create_service_account",
            creates=True,
        ),
        _action("DeletePrincipal", "admin", ("principal",), "delete_principal"),
        _action("SuspendPrincipal", "admin", ("principal",), "suspend_principal"),
        _action("ResumePrincipal", "admin", ("principal",), "resume_principal"),
        _action("LinkUser", "admin", ("principal",)),
        _action("CreateGroup", "admin", ("group",), "create_group", creates=True),
        _action("DeleteGroup", "admin", ("group",), "delete_group"),
        _action("AddGroupMember", "admin", ("group",), "add_group_member"),
        _action("RemoveGroupMember", "admin", ("group",), "remove_group_member"),
        _action("MapIdpGroup", "admin", ("group",), "map_idp_group"),
        _action("UnmapIdpGroup", "admin", ("group",), "unmap_idp_group"),
        _action("CreatePolicy", "admin", ("policy",), "create_policy", creates=True),
        _action("UpdatePolicy", "admin", ("policy",), "update_policy"),
        _action("DeletePolicy", "admin", ("policy",), "delete_policy"),
        # An invitation is an attachment to someone who has not signed in yet,
        # and a bound IdP group holds one through an ABI group: both need the
        # right to attach (or detach) that policy at that scope, no more.
        _action(
            "AttachPolicy",
            "admin",
            ("attachment",),
            "attach_policy",
            "create_pending_grant",
            "bind_idp_group",
        ),
        _action(
            "DetachPolicy",
            "admin",
            ("attachment",),
            "detach_policy",
            "revoke_pending_grant",
            "unbind_idp_group",
        ),
        # The identity service, at a user's sign-in: grants an invitation named.
        _action(
            "ClaimPendingGrants",
            "admin",
            ("principal",),
            "claim_pending_grants",
        ),
        _action("CreateKey", "admin", ("key",), "create_key", creates=True),
        _action("RevokeKey", "admin", ("key",), "revoke_key"),
        # A module submits its own manifest (builtin.module_bootstrap).
        _action("SubmitManifest", "write", ("manifest",), "submit_manifest"),
        _action("ApproveManifest", "admin", ("manifest",), "approve_manifest"),
        _action("RejectManifest", "admin", ("manifest",), "reject_manifest"),
        _action("PutPlacement", "admin", ("placement",), "put_placement"),
        _action("DeletePlacement", "admin", ("placement",), "delete_placement"),
        _action("PutScope", "admin", ("scope",), "put_scope"),
        _action("DeleteScope", "admin", ("scope",), "delete_scope"),
        _action("RegisterCatalog", "admin", ("catalog",), "register_catalog"),
        _action("GetSet", "read", ("set",), "get_set", "effective_set", "list_sets"),
        _action("PutSet", "admin", ("set",), "put_set"),
    ),
)

# Sealed in code, each next to its service: no policy, no API and
# no OBO user opens them.
SEALS: tuple[Seal, ...] = (*DOCUMENT_SEALS, *SECRET_SEALS)
