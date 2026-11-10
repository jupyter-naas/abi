"""Workspaces. A workspace is a container in its organization,
``abi:nexus:organization/<org>/nexus:workspace/<ws>``, or at the platform,
``abi:nexus:workspace/<ws>``, when it belongs to none: its own actions are decided
on that name, and what it holds is ``<workspace>/nexus:...``. A role attached at
one brings the platform companions (an organization's own level does not)."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype
from naas_abi_core.services.iam.catalog import PlatformAccess

TYPES = (
    # A workspace sits in its organization, or at the platform in none.
    rtype(
        "workspace",
        container=True,
        platform_companions=True,
        parents=("nexus:organization", "-"),
    ),
    rtype("server"),
    rtype("resource_access"),
)

ACTIONS = (
    action("ListWorkspaces", "list", "workspace"),
    # Checked on the new workspace's name as placed: only the organization's owners
    # and admins add a workspace to it; a personal one (in none) is every user's.
    action("CreateWorkspace", "admin", "workspace", creates=True),
    action("GetWorkspace", "read", "workspace"),
    action("GetWorkspaceStats", "read", "workspace"),
    action("GetWorkspaceConfiguration", "admin", "workspace"),
    action("UpdateWorkspace", "admin", "workspace"),
    action("UpdateWorkspaceTheme", "admin", "workspace"),
    action("DeleteWorkspace", "admin", "workspace", owner_only=True, deletes=True),
    # ``member`` is declared with the organizations: one type, named at the
    # org's or the workspace's level.
    action("ListWorkspaceMembers", "list", "member"),
    action("InviteWorkspaceMember", "admin", "member"),
    action("UpdateWorkspaceMember", "admin", "member"),
    action("RemoveWorkspaceMember", "admin", "member"),
    action("ListServers", "list", "server", feature="settings"),
    action("CreateServer", "admin", "server", feature="settings"),
    action("UpdateServer", "admin", "server", feature="settings"),
    action("DeleteServer", "admin", "server", feature="settings"),
    action("GetResourceAccess", "admin", "resource_access"),
    action("UpdateResourceAccess", "admin", "resource_access"),
)

# Every user may create a personal workspace, at the platform (``builtin.self``).
PLATFORM_ACCESS = (PlatformAccess(("workspace/*",), self_=("CreateWorkspace",)),)
