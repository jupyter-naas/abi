"""Catalog accumulation event using the canonical event-service contract."""

from typing import ClassVar

from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess
from pydantic import Field


class DatasetCatalogPressure(LogProcess):
    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/dataset/DatasetCatalogPressure"
    )
    _property_uris: ClassVar[dict] = {
        **LogProcess._property_uris,
        "dataset_name": "http://ontology.naas.ai/abi/dataset/datasetName",
        "namespace": "http://ontology.naas.ai/abi/dataset/namespace",
        "inlined_records": "http://ontology.naas.ai/abi/dataset/inlinedRecords",
        "threshold_records": "http://ontology.naas.ai/abi/dataset/thresholdRecords",
    }

    dataset_name: str
    namespace: str
    inlined_records: int = Field(ge=0)
    threshold_records: int = Field(gt=0)
