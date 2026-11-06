"""Workspace settings › Workflows.

Using a workflow or pipeline is its module scope (``module:RunWorkflow`` /
``RunPipeline``, ``services/workflows/scopes.py``), IAM's alone; the settings
page lists those the caller may run."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("workflow"),)

ACTIONS = (
    action("ListWorkflowSettings", "admin", "workflow", feature="settings"),
    # Deprecated, no route: the workspace's workflow on/off switch, gone. Kept
    # declared so a policy that still names it never blocks the catalog's
    # registration (IAM refuses dropping an action a policy names); it
    # authorizes nothing.
    action("UpdateWorkflow", "admin", "workflow", feature="settings"),
)
