"""Organizations (RFC §6.5). Org-level resources: ``abi:<org>:-:nexus:...``.

The org directory (members, domains, their verification tokens) and billing are
the owners' and admins' to read (#1346), so their list and get actions are
``admin``, not ``list``.
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    rtype("organization", id="singleton"),
    # Members of an org (``abi:<org>:-``) and of a workspace (``abi:<org>:<ws>``).
    rtype("member"),
    rtype("domain"),
    rtype("billing", id="singleton"),
    rtype("role_features", id="singleton"),
)

ACTIONS = (
    action("ListOrganizations", "list", "organization"),
    action("GetOrganization", "read", "organization"),
    action("CreateOrganization", "write", "organization"),
    action("UpdateOrganization", "admin", "organization"),
    action("DeleteOrganization", "admin", "organization"),
    # The org's full workspace catalog, every workspace and its memberships.
    action("ListOrganizationCatalog", "admin", "organization"),
    # Only the organization's owners and admins add a workspace to it.
    action("CreateWorkspace", "admin", "organization"),
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
