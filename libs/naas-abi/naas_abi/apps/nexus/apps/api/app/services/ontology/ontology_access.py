"""Which ontology files a caller may assign to a workspace, and read in it.

An ontology file is a ``nexus:ontology``, named by its path, and IAM decides each:

* **Reading** (``GetOntology``) is decided in the workspace, on
  ``<workspace>/nexus:ontology/<path>``: every ontology route reads only the
  workspace's enabled ontologies the caller may get (``readable_paths``), so a
  Deny on one takes it out of every list, dictionary and overview.
* **Assigning** (``AssignOntology``) is decided in the workspace's organization,
  on ``<organization>/nexus:ontology/<path>`` (the platform's for a workspace in
  none): a policy at the organization or at the platform grants it, one at the
  workspace cannot. An organization's admins hold it there by their role; a
  workspace's admins only through such a policy.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource
from naas_abi_core.services.iam.names import parent_of

FEATURE = "ontology"


async def assignable_paths(user: Any, workspace_id: str, paths: Iterable[str]) -> set[str]:
    """The ``paths`` the user may assign to ``workspace_id`` (``AssignOntology`` in
    its organization); none when the deployment does not enable the feature or IAM
    does not know the workspace."""
    wanted = list(dict.fromkeys(paths))
    if not wanted or not authz.feature_exists(FEATURE):
        return set()
    container = await authz.AUTHZ.container_of(workspace_id)
    if container is None:
        return set()
    where = parent_of(container)
    found = await authz.filter_allowed(
        "AssignOntology",
        wanted,
        user=user,
        resource_of=lambda path: nexus_resource("ontology", container=where, id=path),
    )
    return set(found)


async def readable_paths(user: Any, workspace_id: str, paths: Iterable[str]) -> set[str]:
    """The ``paths`` the user may read in ``workspace_id`` (``GetOntology`` there,
    and the ontology feature)."""
    return await authz.allowed_ids("GetOntology", user=user, workspace=workspace_id, ids=paths)
