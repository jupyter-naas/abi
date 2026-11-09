"""Slides, documents and sheets: ``project/<kind>/<slug>``.

The feature is the project's kind (``slides``, ``documents``, ``sheets``), so
callers pass it to ``authz`` (or ``project_guard``) themselves. Reading a
project is everything that leaves it as it is: its content, history, a diff, an
export, an asset. Every other call changes a repository, or provisions the
runtime that does, and needs ``write``.
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("project", id="path"),)

ACTIONS = (
    action("ListProjects", "list", "project"),
    action("ListProjectTemplates", "list", "project"),
    action("GetProject", "read", "project"),
    action("CreateProject", "write", "project"),
    # Rename, archive.
    action("UpdateProject", "write", "project"),
    # Replace the content (PUT).
    action("SaveProject", "write", "project"),
    action("ApplyProjectTemplate", "write", "project"),
    # Slides, sections, tabs and document commands: inserted, deleted,
    # duplicated, reordered, edited.
    action("EditProject", "write", "project"),
    action("EnsureProjectRuntime", "write", "project"),
    # A workbook draft calculated on the server, never saved.
    action("EvaluateProject", "write", "project"),
)
