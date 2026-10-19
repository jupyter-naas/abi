"""Apps, app projects and the marketplace of modules."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("app"), rtype("app_project"), rtype("module"))

ACTIONS = (
    action("ListApps", "list", "app", feature="apps"),
    action("GetApp", "read", "app", feature="apps"),
    # Open, link or grant: the sandboxed iframe of an app.
    action("UseApp", "read", "app", feature="apps"),
    # Turning an app on, off or back to its default in the workspace.
    action("InstallApp", "admin", "app", feature="apps"),
    action("UpdateApp", "admin", "app", feature="apps"),
    action("UninstallApp", "admin", "app", feature="apps"),
    action("ListAppProjects", "list", "app_project", feature="apps"),
    action("GetAppProject", "read", "app_project", feature="apps"),
    action("CreateAppProject", "write", "app_project", feature="apps"),
    # Files, saves, discards and archiving of a project.
    action("UpdateAppProject", "write", "app_project", feature="apps"),
    action("DeleteAppProject", "write", "app_project", feature="apps"),
    # The link that serves a project's draft in a sandbox: viewing, not editing.
    action("PreviewAppProject", "read", "app_project", feature="apps"),
    action("SubmitAppProject", "write", "app_project", feature="apps"),
    # The marketplace of modules and its pricing.
    action("ListModules", "list", "module", feature="marketplace"),
    action("GetMarketplaceConfig", "read", "module", feature="marketplace"),
)
