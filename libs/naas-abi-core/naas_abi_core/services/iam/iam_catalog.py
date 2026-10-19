"""IAM's own catalog (RFC §6.4, "iam") and the seals of RFC §11.3.

IAM authorizes its own operations with these actions, like any other service.
Every resource type is platform-level except ``attachment``, which is named at
its attachment's scope, so a workspace admin can manage that workspace's roles.
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
    version=4,
    resource_types=(
        ResourceType("principal", id="opaque", placement="platform"),
        ResourceType("group", id="opaque", placement="platform"),
        ResourceType("policy", id="opaque", placement="platform"),
        ResourceType(
            "attachment",
            id="path",
            placement="placed",
            description="attachment/<policy id>/<principal id>, at its scope.",
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
    ),
)

# Sealed in code (RFC §11.3), each next to its service: no policy, no API and
# no OBO user opens them.
SEALS: tuple[Seal, ...] = (*DOCUMENT_SEALS, *SECRET_SEALS)
