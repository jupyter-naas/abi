"""Boot hook for the Nexus catalog graph.

When enabled, seeds agent/graph metadata via NexusPlatformPipeline.
When disabled, drops the leftover named graph so a reload does not leave
stale catalog triples behind.
"""

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import URIRef

NEXUS_PLATFORM_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/nexus")


def apply_nexus_platform_pipeline(
    *,
    enabled: bool,
    triple_store: TripleStoreService,
    object_storage: ObjectStorageService,
) -> None:
    if enabled:
        from naas_abi.pipelines.NexusPlatformPipeline import (
            NexusPlatformPipeline,
            NexusPlatformPipelineConfiguration,
            NexusPlatformPipelineParameters,
        )

        pipeline = NexusPlatformPipeline(
            NexusPlatformPipelineConfiguration(
                triple_store=triple_store,
                object_storage=object_storage,
            )
        )
        pipeline.run(NexusPlatformPipelineParameters())
        return

    logger.info(
        "NexusPlatformPipeline disabled; dropping leftover graph {}",
        NEXUS_PLATFORM_GRAPH_URI,
    )
    # DROP SILENT avoids list_graphs() (which can NPE on a dangling TDB2 node)
    # and is a no-op if the named graph is already gone.
    triple_store.query(f"DROP SILENT GRAPH <{NEXUS_PLATFORM_GRAPH_URI}>")
