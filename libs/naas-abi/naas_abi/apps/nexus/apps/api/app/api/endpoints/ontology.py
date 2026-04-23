"""Compatibility layer for ontology exports.

Deprecated: import ontology router and schemas from
`naas_abi.apps.nexus.apps.api.app.services.ontology.adapters.primary`.
"""

from naas_abi.apps.nexus.apps.api.app.services.ontology.adapters.primary import (
    EntityCreate,
    ImportRequest,
    OntologyFileItem,
    OntologyItem,
    OntologyOverviewAggregateStats,
    OntologyOverviewGraph,
    OntologyOverviewGraphEdge,
    OntologyOverviewGraphNode,
    OntologyOverviewStats,
    OntologyTypeCounts,
    ReferenceClass,
    ReferenceOntology,
    ReferenceProperty,
    RelationshipCreate,
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.service import OntologyService

# Deprecated aliases kept for migration clarity.
DeprecatedEntityCreate = EntityCreate
DeprecatedImportRequest = ImportRequest
DeprecatedOntologyFileItem = OntologyFileItem
DeprecatedOntologyItem = OntologyItem
DeprecatedOntologyOverviewAggregateStats = OntologyOverviewAggregateStats
DeprecatedOntologyOverviewGraph = OntologyOverviewGraph
DeprecatedOntologyOverviewGraphEdge = OntologyOverviewGraphEdge
DeprecatedOntologyOverviewGraphNode = OntologyOverviewGraphNode
DeprecatedOntologyOverviewStats = OntologyOverviewStats
DeprecatedOntologyTypeCounts = OntologyTypeCounts
DeprecatedReferenceClass = ReferenceClass
DeprecatedReferenceOntology = ReferenceOntology
DeprecatedReferenceProperty = ReferenceProperty
DeprecatedRelationshipCreate = RelationshipCreate
DeprecatedOntologyRouter = router
DeprecatedOntologyService = OntologyService

__all__ = [
    "DeprecatedEntityCreate",
    "DeprecatedImportRequest",
    "DeprecatedOntologyFileItem",
    "DeprecatedOntologyItem",
    "DeprecatedOntologyOverviewAggregateStats",
    "DeprecatedOntologyOverviewGraph",
    "DeprecatedOntologyOverviewGraphEdge",
    "DeprecatedOntologyOverviewGraphNode",
    "DeprecatedOntologyOverviewStats",
    "DeprecatedOntologyRouter",
    "DeprecatedOntologyService",
    "DeprecatedOntologyTypeCounts",
    "DeprecatedReferenceClass",
    "DeprecatedReferenceOntology",
    "DeprecatedReferenceProperty",
    "DeprecatedRelationshipCreate",
    "EntityCreate",
    "ImportRequest",
    "OntologyFileItem",
    "OntologyItem",
    "OntologyOverviewAggregateStats",
    "OntologyOverviewGraph",
    "OntologyOverviewGraphEdge",
    "OntologyOverviewGraphNode",
    "OntologyOverviewStats",
    "OntologyService",
    "OntologyTypeCounts",
    "ReferenceClass",
    "ReferenceOntology",
    "ReferenceProperty",
    "RelationshipCreate",
    "router",
]
