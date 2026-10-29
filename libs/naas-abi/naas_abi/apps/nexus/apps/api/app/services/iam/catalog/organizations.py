"""Organizations. An organization is a container at the platform,
``abi:nexus:organization/<org>``: its own actions are decided on that name, and
what it holds is ``abi:nexus:organization/<org>/nexus:...``.

The org directory (members, domains, their verification tokens) and billing are
the owners' and admins' to read (#1346), so their list and get actions are
``admin``, not ``list``.
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype
from naas_abi_core.services.iam.catalog import PlatformAccess

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
)

ACTIONS = (
    action("ListOrganizations", "list", "organization"),
    action("GetOrganization", "read", "organization"),
    # Checked on the new organization's name, ``abi:nexus:organization/<new id>``.
    action("CreateOrganization", "write", "organization", creates=True),
    action("UpdateOrganization", "admin", "organization"),
    action("DeleteOrganization", "admin", "organization", owner_only=True, deletes=True),
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

# Every user may create an organization (``builtin.self``).
PLATFORM_ACCESS = (PlatformAccess(("organization/*",), self_=("CreateOrganization",)),)
