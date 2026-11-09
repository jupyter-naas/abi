"""Datasets: ``dataset/<namespace>/<name>`` (the engine's dataset service holds them).

The dataset service is global: a namespace belongs to no workspace, so the type is
platform-level (``abi:-:-:nexus:dataset/...``). The workspace a request names only
carries the ``datasets`` feature and the caller's membership; the roles reach the
namespaces through a deployment grant (``bootstrap.dataset_grants``), and a policy
that denies ``dataset/<namespace>`` hides it from every workspace.
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("dataset", id="path", platform=True),)

ACTIONS = (
    action("ListDatasets", "list", "dataset", feature="datasets"),
    action("GetDataset", "read", "dataset", feature="datasets"),
    action("PreviewDataset", "read", "dataset", feature="datasets"),
    # Read-only SQL over a namespace: ``dataset/<namespace>``.
    action("QueryDataset", "read", "dataset", feature="datasets"),
)
