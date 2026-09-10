from __future__ import annotations

import json
from pathlib import Path

import naas_abi
from naas_abi.apps.nexus.apps.api.app.services.identity_events.events import (
    EVENT_CLASSES,
    NexusIdentityEvent,
)
from naas_abi_core.services.event import EventCodec
from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess
from rdflib import OWL, RDF, Graph, URIRef

_TTL = Path(naas_abi.__file__).parent / "ontologies" / "modules" / "NexusPlatformOntology.ttl"


def _ontology() -> Graph:
    graph = Graph()
    graph.parse(_TTL)
    return graph


def test_event_classes_are_the_ontology_process_classes() -> None:
    """Runtime events and the boot-time graph use the same IRIs."""
    graph = _ontology()
    for name, cls in EVENT_CLASSES.items():
        assert issubclass(cls, LogProcess)
        assert (URIRef(cls._class_uri), RDF.type, OWL.Class) in graph, name
        assert cls._class_uri.endswith(f"/{name}")


def test_event_properties_are_declared_in_the_ontology() -> None:
    graph = _ontology()
    declared = set(graph.subjects(RDF.type, OWL.ObjectProperty)) | set(
        graph.subjects(RDF.type, OWL.DatatypeProperty)
    )
    abi_occurs_in = URIRef("http://ontology.naas.ai/abi/occursIn")
    for field, iri in NexusIdentityEvent._property_uris.items():
        assert URIRef(iri) in declared or URIRef(iri) == abi_occurs_in, field


def test_every_identity_process_of_the_ontology_has_an_event_class() -> None:
    graph = _ontology()
    base = URIRef("http://ontology.naas.ai/nexus/IdentityAndAccessProcess")
    in_ontology = {
        str(c).rsplit("/", 1)[-1]
        for c in graph.transitive_subjects(
            URIRef("http://www.w3.org/2000/01/rdf-schema#subClassOf"), base
        )
        if c != base
    }
    # Applying the configuration happens at boot, into the graph only.
    assert in_ontology - {"ApplyPlatformConfiguration"} == set(EVENT_CLASSES)


def test_event_round_trips_through_the_codec_with_its_iris() -> None:
    cls = EVENT_CLASSES["ChangeWorkspaceMemberRole"]
    event = cls(
        target_user_id="usr-2",
        target_workspace_id="ws-1",
        membership_role="admin",
        previous_membership_role="member",
        updates=["http://ontology.naas.ai/nexus/workspace-membership/ws-1/usr-2"],
        changed_fields=["role"],
    )

    payload = json.loads(EventCodec.serialize(event))
    decoded = EventCodec.deserialize(EventCodec.serialize(event))

    assert payload["_class_uri"] == "http://ontology.naas.ai/nexus/ChangeWorkspaceMemberRole"
    assert payload["_property_uris"]["updates"] == "http://ontology.naas.ai/nexus/updates"
    assert payload["_property_uris"]["actor_user_id"] == "http://ontology.naas.ai/abi/actorUserId"
    assert type(decoded) is cls
    assert (decoded.previous_membership_role, decoded.membership_role) == ("member", "admin")
