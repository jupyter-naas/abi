# onto2py-source-sha256: e80076363117c3fb35700114adb7e664606bb04595182ca77895da3dcaeeed69
from __future__ import annotations

import contextlib
import datetime
import os
import uuid
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Iterable,
    List,
    Optional,
    Union,
    get_args,
    get_origin,
)

from naas_abi.ontologies.modules.ABIOntology import (
    Disposition,
    GenericallyDependentContinuant,
    MaterialEntity,
    Process,
    Quality,
    Role,
    TemporalRegion,
)
from naas_abi.ontologies.modules.GeospatialRegionOntology import (
    GeospatialRegion,
)
from naas_abi.ontologies.modules.OrganizationOntology import Organization
from naas_abi.ontologies.modules.PersonOntology import Person
from pydantic import BaseModel, Field, ValidationError
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

BFO = Namespace("http://purl.obolibrary.org/obo/")
ABI = Namespace("http://ontology.naas.ai/abi/")
CCO = Namespace("https://www.commoncoreontologies.org/")


# Base class for all RDF entities
class RDFEntity(BaseModel):
    """Base class for all RDF entities with URI and namespace management"""

    _namespace: ClassVar[str] = "http://ontology.naas.ai/abi/"
    _uri: str = ""
    _object_properties: ClassVar[set[str]] = set()
    _query_executor: ClassVar[Callable[[str], Iterable[object]] | None] = None

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}

    def __init__(self, **kwargs):
        uri = kwargs.pop("_uri", None)
        super().__init__(**kwargs)
        if uri is not None:
            self._uri = uri
        elif not self._uri:
            self._uri = f"{self._namespace}{uuid.uuid4()}"

    @classmethod
    def set_namespace(cls, namespace: str):
        """Set the namespace for generating URIs"""
        cls._namespace = namespace

    @classmethod
    def set_query_executor(
        cls, query_executor: Callable[[str], Iterable[object]] | None
    ):
        """Set the SPARQL query executor used by from_iri()."""
        cls._query_executor = query_executor

    @staticmethod
    def _extract_result_value(row: object, key: str) -> object | None:
        """Extract a SPARQL binding value from a ResultRow-like object."""
        if hasattr(row, key):
            return getattr(row, key)
        with contextlib.suppress(LookupError, TypeError):
            return row[key]  # type: ignore[index]

        labels = getattr(row, "labels", None)
        if labels and key in labels:
            with contextlib.suppress(LookupError, TypeError):
                return row[key]  # type: ignore[index]

        if isinstance(row, (list, tuple)):
            idx = 0 if key == "p" else 1
            if len(row) > idx:
                return row[idx]

        return None

    @staticmethod
    def _coerce_rdf_value(value: object, is_object_property: bool) -> object:
        """Convert RDFLib values to python values used by generated models."""
        if value is None:
            return None
        if is_object_property:
            return str(value)
        if isinstance(value, Literal):
            return value.toPython()
        return str(value)

    @staticmethod
    def _field_expects_list(field_annotation: object) -> bool:
        """Return True when a field annotation contains a list type."""
        origin = get_origin(field_annotation)
        if origin in (list, List):
            return True
        if origin is Annotated:
            args = get_args(field_annotation)
            if args:
                return RDFEntity._field_expects_list(args[0])
            return False
        if origin is Union:
            return any(
                RDFEntity._field_expects_list(arg)
                for arg in get_args(field_annotation)
                if arg is not type(None)
            )
        return False

    @staticmethod
    def _fallback_label_from_iri(iri: str) -> str:
        """Build a best-effort label from an IRI."""
        trimmed = iri.rstrip("/")
        if "#" in trimmed:
            return trimmed.split("#")[-1] or trimmed
        return trimmed.split("/")[-1] or trimmed

    @classmethod
    def from_iri(
        cls,
        iri: str,
        query_executor: Callable[[str], Iterable[object]] | None = None,
        graph_name: str | None = None,
    ):
        """Load a class instance from an IRI using SPARQL query results."""
        iri = str(iri).strip()
        if not iri:
            raise ValueError("iri must be a non-empty string")
        if "<" in iri or ">" in iri:
            raise ValueError("iri must not contain angle brackets")
        if graph_name is not None:
            graph_name = str(graph_name).strip()
            if not graph_name:
                graph_name = None
            elif "<" in graph_name or ">" in graph_name:
                raise ValueError("graph_name must not contain angle brackets")

        executor = query_executor or cls._query_executor
        if executor is None:
            raise ValueError(
                "No query executor configured. Pass query_executor to from_iri() "
                "or set it with set_query_executor()."
            )

        if graph_name:
            sparql_query = f"""
                SELECT ?p ?o
                WHERE {{
                    GRAPH <{graph_name}> {{
                        <{iri}> ?p ?o .
                        FILTER(?p != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)
                    }}
                }}
            """
        else:
            sparql_query = f"""
                SELECT ?p ?o
                WHERE {{
                    <{iri}> ?p ?o .
                    FILTER(?p != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)
                }}
            """

        results = executor(sparql_query)
        reverse_property_uris = {
            prop_uri: prop_name
            for prop_name, prop_uri in getattr(cls, "_property_uris", {}).items()
        }
        object_props: set[str] = getattr(cls, "_object_properties", set())
        model_fields = getattr(cls, "model_fields", {})
        values: dict[str, Any] = {}

        for row in results:  # type: ignore[assignment]
            predicate = cls._extract_result_value(row, "p")
            obj = cls._extract_result_value(row, "o")
            if predicate is None:
                continue
            prop_name = reverse_property_uris.get(str(predicate))
            if not prop_name:
                continue

            coerced = cls._coerce_rdf_value(
                obj,
                is_object_property=prop_name in object_props,
            )
            field_info = model_fields.get(prop_name)
            expects_list = False
            if field_info is not None:
                expects_list = cls._field_expects_list(field_info.annotation)

            if prop_name not in values:
                if expects_list:
                    values[prop_name] = [coerced]
                else:
                    values[prop_name] = coerced
            else:
                existing = values[prop_name]
                if isinstance(existing, list):
                    existing.append(coerced)
                elif expects_list:
                    values[prop_name] = [existing, coerced]
                else:
                    values[prop_name] = existing

        if "label" in model_fields and "label" not in values:
            values["label"] = cls._fallback_label_from_iri(iri)

        for field_name, field_info in model_fields.items():
            if field_name in values:
                continue
            if field_info.is_required():
                if cls._field_expects_list(field_info.annotation):
                    values[field_name] = []
                else:
                    values[field_name] = None

        try:
            return cls(_uri=iri, **values)
        except ValidationError:
            # Keep loading permissive for partially populated RDF resources.
            return cls.model_construct(
                _fields_set=set(values.keys()), _uri=iri, **values
            )

    def rdf(
        self, subject_uri: str | None = None, visited: set[str] | None = None
    ) -> Graph:
        """Generate RDF triples for this instance

        Args:
            subject_uri: Optional URI to use as subject (defaults to self._uri)
            visited: Set of URIs that have already been processed (for cycle detection)
        """
        # Initialize visited set if not provided
        if visited is None:
            visited = set()

        g = Graph()
        g.bind("cco", CCO)
        g.bind("bfo", BFO)
        g.bind("abi", ABI)
        g.bind("rdfs", RDFS)
        g.bind("rdf", RDF)
        g.bind("owl", OWL)
        g.bind("xsd", XSD)

        # Use stored URI or provided subject_uri
        if subject_uri is None:
            subject_uri = self._uri
        subject = URIRef(subject_uri)

        # Check if we've already processed this entity (cycle detection)
        if subject_uri in visited:
            # Already processed, just return empty graph to avoid infinite recursion
            # The relationship triple will be added by the caller
            return g

        # Mark this entity as visited before processing
        visited.add(subject_uri)

        # Add class type
        if hasattr(self, "_class_uri"):
            g.add((subject, RDF.type, URIRef(self._class_uri)))

        # Add owl:NamedIndividual type
        g.add((subject, RDF.type, OWL.NamedIndividual))

        # Add label if it exists
        if hasattr(self, "label"):
            g.add((subject, RDFS.label, Literal(self.label)))

        object_props: set[str] = getattr(self, "_object_properties", set())

        # Add properties
        if hasattr(self, "_property_uris"):
            for prop_name, prop_uri in self._property_uris.items():
                is_object_prop = prop_name in object_props
                prop_value = getattr(self, prop_name, None)
                if prop_value is not None:
                    if isinstance(prop_value, list):
                        for item in prop_value:
                            if hasattr(item, "rdf") and hasattr(item, "_uri"):
                                # Check if this entity was already visited to prevent cycles
                                if item._uri not in visited:
                                    # Add triples from related object
                                    g += item.rdf(visited=visited)
                                # Always add the triple, even if already visited
                                g.add((subject, URIRef(prop_uri), URIRef(item._uri)))
                            elif is_object_prop and isinstance(item, (str, URIRef)):
                                g.add((subject, URIRef(prop_uri), URIRef(str(item))))
                            else:
                                g.add((subject, URIRef(prop_uri), Literal(item)))
                    elif hasattr(prop_value, "rdf") and hasattr(prop_value, "_uri"):
                        # Check if this entity was already visited to prevent cycles
                        if prop_value._uri not in visited:
                            # Add triples from related object
                            g += prop_value.rdf(visited=visited)
                        # Always add the triple, even if already visited
                        g.add((subject, URIRef(prop_uri), URIRef(prop_value._uri)))
                    elif is_object_prop and isinstance(prop_value, (str, URIRef)):
                        g.add((subject, URIRef(prop_uri), URIRef(str(prop_value))))
                    else:
                        g.add((subject, URIRef(prop_uri), Literal(prop_value)))

        return g


class ActOfWorking(RDFEntity):
    """
    Act of Working
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/ActOfWorking"
    _name: ClassVar[str] = "Act of Working"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "developsLanguageCapability": "http://ontology.naas.ai/people/developsLanguageCapability",
        "developsSkill": "http://ontology.naas.ai/people/developsSkill",
        "employment_type": "http://ontology.naas.ai/people/employment_type",
        "for_client": "http://ontology.naas.ai/people/forClient",
        "for_organization": "http://ontology.naas.ai/people/forOrganization",
        "hasParticipant": "http://ontology.naas.ai/abi/hasParticipant",
        "hasSourceDocument": "http://ontology.naas.ai/people/hasSourceDocument",
        "is_act_of_working_of": "http://ontology.naas.ai/people/isActOfWorkingOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupiesTemporalRegion": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occursIn": "http://ontology.naas.ai/abi/occursIn",
        "realizes": "http://ontology.naas.ai/abi/realizes",
    }
    _object_properties: ClassVar[set[str]] = {
        "developsLanguageCapability",
        "developsSkill",
        "for_client",
        "for_organization",
        "hasParticipant",
        "hasSourceDocument",
        "is_act_of_working_of",
        "occupiesTemporalRegion",
        "occursIn",
        "realizes",
    }

    # Data properties
    employment_type: Optional[
        Annotated[
            str,
            Field(
                description="Engagement type a source states for an act of working, e.g. 'Full-time', 'Freelance', 'Self-employed', 'Internship'. What was published, not the terms of a contract: a contract is an internal record of the employing organization, outside this vocabulary."
            ),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now(datetime.timezone.utc)
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    developsLanguageCapability: Optional[Annotated[Union[URIRef, str], Field()]] = None
    developsSkill: Optional[Annotated[Union[URIRef, str], Field()]] = None
    for_client: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="Relates an act of working to the client organization the work was performed for, when the worker was staffed there by their employer (forOrganization) rather than working for the client directly."
            ),
        ]
    ] = None
    for_organization: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="Relates an act of working to the organization that participates as employer."
            ),
        ]
    ] = None
    hasParticipant: Optional[Annotated[List[Union[Person, URIRef, str]], Field()]] = (
        None
    )
    hasSourceDocument: Optional[Annotated[Union[URIRef, str], Field()]] = None
    is_act_of_working_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates an act of working to the person performing the work."
            ),
        ]
    ] = None
    occupiesTemporalRegion: Optional[
        Annotated[List[Union[TemporalRegion, URIRef, str]], Field()]
    ] = None
    occursIn: Optional[
        Annotated[List[Union[GeospatialRegion, URIRef, str]], Field()]
    ] = None
    realizes: Optional[Annotated[Union[URIRef, str], Field()]] = None


class Mission(GenericallyDependentContinuant, RDFEntity):
    """
    Deliberately a GDC and NOT a BFO function. A mission is stated, copied between systems and survives the person leaving the post, which a disposition inhering in the person could not. The WHY that inheres in the person is people:OccupationRole; the mission is what that role concretizes. rdfs:label carries the opening sentence; people:mission_content carries the full text.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/Mission"
    _name: ClassVar[str] = "Mission"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "genericallyDependsOn": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "isConcretizedBy": "http://ontology.naas.ai/abi/isConcretizedBy",
        "isSourcedFrom": "http://ontology.naas.ai/people/isSourcedFrom",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_mission_carried_by": "http://ontology.naas.ai/people/isMissionCarriedBy",
        "is_mission_of": "http://ontology.naas.ai/people/isMissionOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "mission_content": "http://ontology.naas.ai/people/mission_content",
        "mission_context": "http://ontology.naas.ai/people/mission_context",
    }
    _object_properties: ClassVar[set[str]] = {
        "genericallyDependsOn",
        "generically_depends_on",
        "isConcretizedBy",
        "isSourcedFrom",
        "is_concretized_by",
        "is_mission_carried_by",
        "is_mission_of",
    }

    # Data properties
    mission_context: Optional[
        Annotated[
            str,
            Field(
                description="The situation a mission was undertaken in: what the organization needed and why, stated as prose before the mission's own objectives and activities. Optional: a source that states only what was done, not the situation it responded to, leaves this unset."
            ),
        ]
    ] = None
    mission_content: Optional[
        Annotated[
            str,
            Field(
                description="Full stated text of a mission: the objectives and activities listed under its opening sentence, one per line when the source enumerates them as discrete tasks. The opening sentence alone is carried by rdfs:label; the situation the mission responded to is carried by people:mission_context, not here."
            ),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[
            datetime.datetime,
            Field(description="Date of creation of the resource."),
        ]
    ] = None
    creator: Optional[
        Annotated[
            Any,
            Field(description="An entity responsible for making the resource."),
        ]
    ] = None

    # Object properties
    genericallyDependsOn: Optional[
        Annotated[List[Union[Person, URIRef, str]], Field()]
    ] = None
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    isConcretizedBy: Optional[Annotated[Union[URIRef, str], Field()]] = None
    isSourcedFrom: Optional[Annotated[Union[URIRef, str], Field()]] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_mission_carried_by: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a mission to the person on which it generically depends."
            ),
        ]
    ] = None
    is_mission_of: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="Relates a mission to the occupation role that concretizes it while the person works in that capacity."
            ),
        ]
    ] = None


# Rebuild models to resolve forward references
ActOfWorking.model_rebuild()
Mission.model_rebuild()
