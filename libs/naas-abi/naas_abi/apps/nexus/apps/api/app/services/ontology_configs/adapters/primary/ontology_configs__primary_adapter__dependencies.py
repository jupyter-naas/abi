from __future__ import annotations

from fastapi import Depends
from naas_abi.apps.nexus.apps.api.app.services.ontology_configs.service import (
    OntologyConfigsService,
)
from naas_abi.apps.nexus.apps.api.app.services.registry import (
    ServiceRegistry,
    get_service_registry,
)


def get_ontology_configs_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> OntologyConfigsService:
    return registry.ontology_configs
