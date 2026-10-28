"""Apps, app projects and the marketplace of modules."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("app"), rtype("app_project"), rtype("module"))

ACTIONS = (
    # Listing and opening a module's app is its module scope
    # (``module:OpenApp``, ``services/apps/scopes.py``), not the "apps"
    # section: the section is the settings page and the app projects.
    action("ListApps", "list", "app"),
    action("GetApp", "read", "app"),
    # A link that is no module's app: a Pages portal's sign-in.
    action("UseApp", "read", "app"),
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
    # Every module's agents, apps, workflows, pipelines and declared actions:
    # what the policy builder grants.
    action("ListModuleScopes", "admin", "module"),
)
