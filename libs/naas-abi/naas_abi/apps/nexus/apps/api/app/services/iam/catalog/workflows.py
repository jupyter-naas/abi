"""The workflows and pipelines of a workspace's set, on or off there.

Using one is its module scope (``module:RunWorkflow`` / ``RunPipeline``,
``services/workflows/scopes.py``); these are the settings page that turns each
on or off for everyone in the workspace."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("workflow"),)

ACTIONS = (
    action("ListWorkflowSettings", "admin", "workflow", feature="settings"),
    action("UpdateWorkflow", "admin", "workflow", feature="settings"),
)
