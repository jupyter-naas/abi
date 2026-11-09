"""Datasets: ``dataset/<namespace>/<name>`` (the engine's dataset service holds them)."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("dataset", id="path"),)

ACTIONS = (
    action("ListDatasets", "list", "dataset", feature="datasets"),
    action("GetDataset", "read", "dataset", feature="datasets"),
    action("PreviewDataset", "read", "dataset", feature="datasets"),
    # Read-only SQL over a namespace: ``dataset/<namespace>``.
    action("QueryDataset", "read", "dataset", feature="datasets"),
)
