"""Workspaces (RFC §6.5). Resources: ``abi:<org>:<ws>:nexus:...``."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    rtype("workspace", id="singleton"),
    rtype("server"),
    rtype("resource_access"),
)

ACTIONS = (
    action("ListWorkspaces", "list", "workspace"),
    action("GetWorkspace", "read", "workspace"),
    action("GetWorkspaceStats", "read", "workspace"),
    action("GetWorkspaceConfiguration", "admin", "workspace"),
    action("UpdateWorkspace", "admin", "workspace"),
    action("UpdateWorkspaceTheme", "admin", "workspace"),
    action("DeleteWorkspace", "admin", "workspace"),
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
