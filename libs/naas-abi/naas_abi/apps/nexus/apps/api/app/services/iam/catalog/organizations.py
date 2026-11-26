"""Organizations. An organization is a container at the platform,
``abi:nexus:organization/<org>``: its own actions are decided on that name, and
what it holds is ``abi:nexus:organization/<org>/nexus:...``.

The org directory (members, domains, their verification tokens) and billing are
the owners' and admins' to read (#1346), so their list and get actions are
``admin``, not ``list``.
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    # An organization sits at the platform.
    rtype("organization", container=True, parents=("-",)),
    # Members of an org (in its container) and of a workspace (in the workspace's).
    rtype("member"),
    rtype("domain"),
    rtype("billing", id="singleton"),
    # Deprecated, no route: the organization's role feature defaults, gone with
    # the role features. Kept declared so a policy that still names the actions
    # never blocks the catalog's registration (IAM refuses dropping an action a
    # policy names); they authorize nothing.
    rtype("role_features", id="singleton"),
    # An organization as the platform keeps it (``abi:nexus:organization_record/<org>``):
    # platform-level, no role reaches it, so deleting one is the platform admin's (#1585).
    rtype(
        "organization_record",
        platform=True,
        description="An organization as the platform keeps it: deleting one.",
    ),
)

ACTIONS = (
    action("ListOrganizations", "list", "organization"),
    action("GetOrganization", "read", "organization"),
    # Checked on the new organization's name, ``abi:nexus:organization/<new id>``.
    action("CreateOrganization", "write", "organization", creates=True),
    action("UpdateOrganization", "admin", "organization"),
    # Deprecated (#1585): no route asks for it; it stays the action IAM's
    # ``delete_container`` checks (Nexus calls it as ``api``).
    action(
        "DeleteOrganization",
        "admin",
        "organization",
        owner_only=True,
        deletes=True,
        description="Deprecated: deleting an organization is DeletePlatformOrganization.",
    ),
    # Deleting an organization is the platform admin's: no role reaches the type.
    action(
        "DeletePlatformOrganization",
        "admin",
        "organization_record",
        description="Delete an organization (the platform admin's).",
    ),
    # Deleting one of its workspaces is the organization's admins' (on the organization).
    action(
        "DeleteOrganizationWorkspace",
        "admin",
        "organization",
        description="Delete a workspace of the organization (its admins).",
    ),
    # The org's full workspace catalog, every workspace and its memberships.
    action("ListOrganizationCatalog", "admin", "organization"),
    action("ListOrganizationMembers", "admin", "member"),
    action("InviteOrganizationMember", "admin", "member"),
    action("UpdateOrganizationMember", "admin", "member"),
    action("RemoveOrganizationMember", "admin", "member"),
    action("ListOrganizationDomains", "admin", "domain"),
    action("AddOrganizationDomain", "admin", "domain"),
    action("VerifyOrganizationDomain", "admin", "domain"),
    action("UpdateOrganizationDomain", "admin", "domain"),
    action("RemoveOrganizationDomain", "admin", "domain"),
    action("GetBilling", "admin", "billing"),
    action("UpdateBilling", "admin", "billing"),
    action("GetRoleFeatures", "admin", "role_features"),
    action("UpdateRoleFeatures", "admin", "role_features"),
)

# Creating an organization is the platform admins' (``builtin.platform_admin``): no
# user holds it from ``builtin.self`` (catalog 16).
