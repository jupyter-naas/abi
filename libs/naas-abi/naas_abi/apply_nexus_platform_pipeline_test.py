from unittest.mock import MagicMock, patch

from naas_abi.apply_nexus_platform_pipeline import (
    NEXUS_PLATFORM_GRAPH_URI,
    apply_nexus_platform_pipeline,
)
from naas_abi_core.services.triple_store.TripleStorePorts import Exceptions


def test_disabled_pipeline_drops_nexus_graph_without_running():
    triple_store = MagicMock()
    object_storage = MagicMock()

    with patch(
        "naas_abi.pipelines.NexusPlatformPipeline.NexusPlatformPipeline"
    ) as pipeline_cls:
        apply_nexus_platform_pipeline(
            enabled=False,
            triple_store=triple_store,
            object_storage=object_storage,
        )

    pipeline_cls.assert_not_called()
    triple_store.query.assert_called_once()
    sparql = triple_store.query.call_args.args[0]
    assert sparql == f"DROP SILENT GRAPH <{NEXUS_PLATFORM_GRAPH_URI}>"


def test_disabled_pipeline_continues_when_fuseki_write_lock_is_busy():
    triple_store = MagicMock()
    triple_store.query.side_effect = Exceptions.RequestError(
        operation="acquire_write_lock",
        message="Could not acquire distributed write lock",
        endpoint="http://fuseki:3030/ds",
        attempts=4,
    )
    object_storage = MagicMock()

    apply_nexus_platform_pipeline(
        enabled=False,
        triple_store=triple_store,
        object_storage=object_storage,
    )

    triple_store.query.assert_called_once()


def test_enabled_pipeline_runs_and_does_not_drop_graph():
    triple_store = MagicMock()
    object_storage = MagicMock()

    with patch(
        "naas_abi.pipelines.NexusPlatformPipeline.NexusPlatformPipeline"
    ) as pipeline_cls:
        apply_nexus_platform_pipeline(
            enabled=True,
            triple_store=triple_store,
            object_storage=object_storage,
        )

    pipeline_cls.assert_called_once()
    pipeline_cls.return_value.run.assert_called_once()
    triple_store.query.assert_not_called()
