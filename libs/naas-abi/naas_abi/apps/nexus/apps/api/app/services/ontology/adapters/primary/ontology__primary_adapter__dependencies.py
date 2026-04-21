from __future__ import annotations

from fastapi import Depends
from naas_abi.apps.nexus.apps.api.app.services.ontology.service import OntologyService
from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry, get_service_registry


def get_ontology_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> OntologyService:
    return registry.ontology
