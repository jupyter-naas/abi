# onto2py-source-sha256: 88be8fbae4abb7c5726759103b0dd160632584ab7383b61505d631bd8568e1e2
from __future__ import annotations

import contextlib
import datetime
import os
import uuid
from collections.abc import Callable, Iterable
from typing import (
    Annotated,
    Any,
    ClassVar,
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
from naas_abi.ontologies.modules.DocumentContentEntityOntology import (
    DocumentContentEntity,
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
        if origin in (list, list):
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


class ActOfCertification(RDFEntity):
    """
    No CCO act of certification; the process is a direct subclass of CCO Planned Act. The act is not the certificate: it ends when the certification is awarded, whereas the Certification persists and may later expire.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ActOfCertification"
    _name: ClassVar[str] = "Act of Certification"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "demonstrates_skill": "http://ontology.naas.ai/abi/demonstratesSkill",
        "develops_language_capability": "http://ontology.naas.ai/abi/developsLanguageCapability",
        "for_certifying_organization": "http://ontology.naas.ai/abi/forCertifyingOrganization",
        "hasParticipant": "http://ontology.naas.ai/abi/hasParticipant",
        "has_awarded_certification": "http://ontology.naas.ai/abi/hasAwardedCertification",
        "has_source_document": "http://ontology.naas.ai/abi/hasSourceDocument",
        "is_act_of_certification_of": "http://ontology.naas.ai/abi/isActOfCertificationOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupiesTemporalRegion": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occursIn": "http://ontology.naas.ai/abi/occursIn",
        "realizes": "http://ontology.naas.ai/abi/realizes",
    }
    _object_properties: ClassVar[set[str]] = {
        "demonstrates_skill",
        "develops_language_capability",
        "for_certifying_organization",
        "hasParticipant",
        "has_awarded_certification",
        "has_source_document",
        "is_act_of_certification_of",
        "occupiesTemporalRegion",
        "occursIn",
        "realizes",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now(datetime.UTC)
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    demonstrates_skill: (
        Annotated[
            list[Skill | URIRef | str],
            Field(
                description="Relates an act of certification to a skill the person demonstrates in the course of it."
            ),
        ]
        | None
    ) = None
    develops_language_capability: (
        Annotated[
            list[LanguageCapability | URIRef | str],
            Field(
                description="Relates a planned act (an act of working, of studying or of certification) to a language capability exercised and developed in the course of it."
            ),
        ]
        | None
    ) = None
    for_certifying_organization: (
        Annotated[
            list[Organization | URIRef | str],
            Field(
                description="Relates an act of certification to the organization that participates as the certifying body."
            ),
        ]
        | None
    ) = None
    hasParticipant: Annotated[list[Person | URIRef | str], Field()] | None = None
    has_awarded_certification: (
        Annotated[
            list[Certification | URIRef | str],
            Field(
                description="Relates an act of certification to the certification it concretizes."
            ),
        ]
        | None
    ) = None
    has_source_document: (
        Annotated[
            list[ProfileDocument | URIRef | str],
            Field(
                description="Relates a planned act to the profile document it was read from and registered against."
            ),
        ]
        | None
    ) = None
    is_act_of_certification_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates an act of certification to the person being certified."
            ),
        ]
        | None
    ) = None
    occupiesTemporalRegion: (
        Annotated[list[TemporalRegion | URIRef | str], Field()] | None
    ) = None
    occursIn: Annotated[list[GeospatialRegion | URIRef | str], Field()] | None = None
    realizes: (
        Annotated[list[CertificationCandidateRole | URIRef | str], Field()] | None
    ) = None


class ActOfProfiling(RDFEntity):
    """
    Orchestration only. Episode triples are written by the working and studying pipelines; summary, certifications and social proof by the person profile pipeline.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ActOfProfiling"
    _name: ClassVar[str] = "Act of Profiling"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "from_profile_document": "http://ontology.naas.ai/abi/fromProfileDocument",
        "hasParticipant": "http://ontology.naas.ai/abi/hasParticipant",
        "is_act_of_profiling_of": "http://ontology.naas.ai/abi/isActOfProfilingOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "from_profile_document",
        "hasParticipant",
        "is_act_of_profiling_of",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now(datetime.UTC)
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    from_profile_document: (
        Annotated[
            list[ProfileDocument | URIRef | str],
            Field(
                description="Relates an act of profiling to the profile document that was read as its source."
            ),
        ]
        | None
    ) = None
    hasParticipant: Annotated[list[Person | URIRef | str], Field()] | None = None
    is_act_of_profiling_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates an act of profiling to the person who is its subject."
            ),
        ]
        | None
    ) = None


class ActOfStudying(RDFEntity):
    """
    Act of Studying
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ActOfStudying"
    _name: ClassVar[str] = "Act of Studying"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "develops_language_capability": "http://ontology.naas.ai/abi/developsLanguageCapability",
        "develops_skill": "http://ontology.naas.ai/abi/developsSkill",
        "for_educational_organization": "http://ontology.naas.ai/abi/forEducationalOrganization",
        "hasParticipant": "http://ontology.naas.ai/abi/hasParticipant",
        "has_degree": "http://ontology.naas.ai/abi/hasDegree",
        "has_enrollment": "http://ontology.naas.ai/abi/hasEnrollment",
        "has_source_document": "http://ontology.naas.ai/abi/hasSourceDocument",
        "is_act_of_studying_of": "http://ontology.naas.ai/abi/isActOfStudyingOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupiesTemporalRegion": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occursIn": "http://ontology.naas.ai/abi/occursIn",
        "realizes": "http://ontology.naas.ai/abi/realizes",
    }
    _object_properties: ClassVar[set[str]] = {
        "develops_language_capability",
        "develops_skill",
        "for_educational_organization",
        "hasParticipant",
        "has_degree",
        "has_enrollment",
        "has_source_document",
        "is_act_of_studying_of",
        "occupiesTemporalRegion",
        "occursIn",
        "realizes",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now(datetime.UTC)
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    develops_language_capability: (
        Annotated[
            list[LanguageCapability | URIRef | str],
            Field(
                description="Relates a planned act (an act of working, of studying or of certification) to a language capability exercised and developed in the course of it."
            ),
        ]
        | None
    ) = None
    develops_skill: (
        Annotated[
            list[Skill | URIRef | str],
            Field(
                description="Relates a planned act (an act of working or of studying, for one) to a skill exercised and developed in the course of it."
            ),
        ]
        | None
    ) = None
    for_educational_organization: (
        Annotated[
            list[Organization | URIRef | str],
            Field(
                description="Relates an act of studying to the educational organization that participates as the training provider."
            ),
        ]
        | None
    ) = None
    hasParticipant: Annotated[list[Person | URIRef | str], Field()] | None = None
    has_degree: (
        Annotated[
            list[AcademicDegree | URIRef | str],
            Field(
                description="Relates an act of studying to the academic degree it concretizes."
            ),
        ]
        | None
    ) = None
    has_enrollment: (
        Annotated[
            list[EnrollmentRecord | URIRef | str],
            Field(
                description="Relates an act of studying to the enrollment record it concretizes."
            ),
        ]
        | None
    ) = None
    has_source_document: (
        Annotated[
            list[ProfileDocument | URIRef | str],
            Field(
                description="Relates a planned act to the profile document it was read from and registered against."
            ),
        ]
        | None
    ) = None
    is_act_of_studying_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates an act of studying to the person acquiring the curriculum."
            ),
        ]
        | None
    ) = None
    occupiesTemporalRegion: (
        Annotated[list[TemporalRegion | URIRef | str], Field()] | None
    ) = None
    occursIn: Annotated[list[GeospatialRegion | URIRef | str], Field()] | None = None
    realizes: Annotated[list[StudentRole | URIRef | str], Field()] | None = None


class ActOfWorking(RDFEntity):
    """
    Act of Working
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ActOfWorking"
    _name: ClassVar[str] = "Act of Working"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "develops_language_capability": "http://ontology.naas.ai/abi/developsLanguageCapability",
        "develops_skill": "http://ontology.naas.ai/abi/developsSkill",
        "employment_type": "http://ontology.naas.ai/abi/employment_type",
        "for_client": "http://ontology.naas.ai/abi/forClient",
        "for_organization": "http://ontology.naas.ai/abi/forOrganization",
        "hasParticipant": "http://ontology.naas.ai/abi/hasParticipant",
        "has_source_document": "http://ontology.naas.ai/abi/hasSourceDocument",
        "is_act_of_working_of": "http://ontology.naas.ai/abi/isActOfWorkingOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupiesTemporalRegion": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occursIn": "http://ontology.naas.ai/abi/occursIn",
        "realizes": "http://ontology.naas.ai/abi/realizes",
    }
    _object_properties: ClassVar[set[str]] = {
        "develops_language_capability",
        "develops_skill",
        "for_client",
        "for_organization",
        "hasParticipant",
        "has_source_document",
        "is_act_of_working_of",
        "occupiesTemporalRegion",
        "occursIn",
        "realizes",
    }

    # Data properties
    employment_type: (
        Annotated[
            str,
            Field(
                description="Engagement type a source states for an act of working, e.g. 'Full-time', 'Freelance', 'Self-employed', 'Internship'. What was published, not the terms of a contract: a contract is an internal record of the employing organization, outside this vocabulary."
            ),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now(datetime.UTC)
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    develops_language_capability: (
        Annotated[
            list[LanguageCapability | URIRef | str],
            Field(
                description="Relates a planned act (an act of working, of studying or of certification) to a language capability exercised and developed in the course of it."
            ),
        ]
        | None
    ) = None
    develops_skill: (
        Annotated[
            list[Skill | URIRef | str],
            Field(
                description="Relates a planned act (an act of working or of studying, for one) to a skill exercised and developed in the course of it."
            ),
        ]
        | None
    ) = None
    for_client: (
        Annotated[
            list[Organization | URIRef | str],
            Field(
                description="Relates an act of working to the client organization the work was performed for, when the worker was staffed there by their employer (forOrganization) rather than working for the client directly."
            ),
        ]
        | None
    ) = None
    for_organization: (
        Annotated[
            list[Organization | URIRef | str],
            Field(
                description="Relates an act of working to the organization that participates as employer."
            ),
        ]
        | None
    ) = None
    hasParticipant: Annotated[list[Person | URIRef | str], Field()] | None = None
    has_source_document: (
        Annotated[
            list[ProfileDocument | URIRef | str],
            Field(
                description="Relates a planned act to the profile document it was read from and registered against."
            ),
        ]
        | None
    ) = None
    is_act_of_working_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates an act of working to the person performing the work."
            ),
        ]
        | None
    ) = None
    occupiesTemporalRegion: (
        Annotated[list[TemporalRegion | URIRef | str], Field()] | None
    ) = None
    occursIn: Annotated[list[GeospatialRegion | URIRef | str], Field()] | None = None
    realizes: Annotated[list[OccupationRole | URIRef | str], Field()] | None = None


class EnrollmentRecord(GenericallyDependentContinuant, RDFEntity):
    """
    Enrollment Record
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/EnrollmentRecord"
    _name: ClassVar[str] = "Enrollment Record"
    _property_uris: ClassVar[dict] = {
        "activities_content": "http://ontology.naas.ai/abi/activities_content",
        "completion_date": "http://ontology.naas.ai/abi/completion_date",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "enrollment_date": "http://ontology.naas.ai/abi/enrollment_date",
        "genericallyDependsOn": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "isConcretizedBy": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_enrollment_of": "http://ontology.naas.ai/abi/isEnrollmentOf",
        "is_enrollment_record_of": "http://ontology.naas.ai/abi/isEnrollmentRecordOf",
        "is_sourced_from": "http://ontology.naas.ai/abi/isSourcedFrom",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "program_name": "http://ontology.naas.ai/abi/program_name",
    }
    _object_properties: ClassVar[set[str]] = {
        "genericallyDependsOn",
        "generically_depends_on",
        "isConcretizedBy",
        "is_concretized_by",
        "is_enrollment_of",
        "is_enrollment_record_of",
        "is_sourced_from",
    }

    # Data properties
    program_name: (
        Annotated[
            str,
            Field(
                description="Name of the curriculum or programme the enrollment is for."
            ),
        ]
        | None
    ) = None
    enrollment_date: (
        Annotated[
            datetime.date,
            Field(
                description="Date on which the course of study documented by this record began."
            ),
        ]
        | None
    ) = None
    completion_date: (
        Annotated[
            datetime.date,
            Field(
                description="Date on which the course of study documented by this record ended. Absent while the person is still enrolled."
            ),
        ]
        | None
    ) = None
    activities_content: (
        Annotated[
            str,
            Field(
                description="Extracurricular activities and societies listed under an enrollment on the source profile."
            ),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    genericallyDependsOn: Annotated[URIRef | str, Field()] | None = None
    generically_depends_on: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
        | None
    ) = None
    isConcretizedBy: Annotated[list[ActOfStudying | URIRef | str], Field()] | None = (
        None
    )
    is_concretized_by: (
        Annotated[
            list[Disposition | Process | Quality | Role | URIRef | str],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
        | None
    ) = None
    is_enrollment_of: (
        Annotated[
            list[ActOfStudying | URIRef | str],
            Field(
                description="Relates an enrollment record to the act of studying that concretizes it."
            ),
        ]
        | None
    ) = None
    is_enrollment_record_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates an enrollment record to the person on which it generically depends."
            ),
        ]
        | None
    ) = None
    is_sourced_from: (
        Annotated[
            list[ProfileDocument | URIRef | str],
            Field(
                description="Relates an information content entity to the profile document it was read from."
            ),
        ]
        | None
    ) = None


class AcademicDegree(GenericallyDependentContinuant, RDFEntity):
    """
    Academic Degree
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AcademicDegree"
    _name: ClassVar[str] = "Academic Degree"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "genericallyDependsOn": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_degree_of": "http://ontology.naas.ai/abi/isDegreeOf",
        "is_sourced_from": "http://ontology.naas.ai/abi/isSourcedFrom",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "genericallyDependsOn",
        "generically_depends_on",
        "is_concretized_by",
        "is_degree_of",
        "is_sourced_from",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    genericallyDependsOn: Annotated[list[Person | URIRef | str], Field()] | None = None
    generically_depends_on: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
        | None
    ) = None
    is_concretized_by: (
        Annotated[
            list[Disposition | Process | Quality | Role | URIRef | str],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
        | None
    ) = None
    is_degree_of: (
        Annotated[
            list[ActOfStudying | URIRef | str],
            Field(
                description="Relates an academic degree to the act of studying that concretizes it."
            ),
        ]
        | None
    ) = None
    is_sourced_from: (
        Annotated[
            list[ProfileDocument | URIRef | str],
            Field(
                description="Relates an information content entity to the profile document it was read from."
            ),
        ]
        | None
    ) = None


class Certification(GenericallyDependentContinuant, RDFEntity):
    """
    Covers both certifications and licences: the difference is who may withhold it and what it permits, not what kind of entity it is. Where that distinction matters, state it with abi:certification_status and the issuing organization.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/Certification"
    _name: ClassVar[str] = "Certification"
    _property_uris: ClassVar[dict] = {
        "certification_name": "http://ontology.naas.ai/abi/certification_name",
        "certification_status": "http://ontology.naas.ai/abi/certification_status",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "credential_id": "http://ontology.naas.ai/abi/credential_id",
        "credential_url": "http://ontology.naas.ai/abi/credential_url",
        "expiry_date": "http://ontology.naas.ai/abi/expiry_date",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "isConcretizedBy": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_awarded_certification_of": "http://ontology.naas.ai/abi/isAwardedCertificationOf",
        "is_certification_of": "http://ontology.naas.ai/abi/isCertificationOf",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_sourced_from": "http://ontology.naas.ai/abi/isSourcedFrom",
        "issue_date": "http://ontology.naas.ai/abi/issue_date",
        "issued_by_organization": "http://ontology.naas.ai/abi/issuedByOrganization",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "isConcretizedBy",
        "is_awarded_certification_of",
        "is_certification_of",
        "is_concretized_by",
        "is_sourced_from",
        "issued_by_organization",
    }

    # Data properties
    certification_name: (
        Annotated[
            str,
            Field(
                description="Name of the certification as published by the issuing organization."
            ),
        ]
        | None
    ) = None
    issue_date: (
        Annotated[
            datetime.date,
            Field(description="Date on which the certification was issued."),
        ]
        | None
    ) = None
    expiry_date: (
        Annotated[
            datetime.date,
            Field(
                description="Date on which the certification ceases to be valid. Absent when the certification does not expire."
            ),
        ]
        | None
    ) = None
    credential_id: (
        Annotated[
            str,
            Field(
                description="Identifier the issuing organization assigned to this certification, by which it can be verified."
            ),
        ]
        | None
    ) = None
    credential_url: (
        Annotated[
            Any,
            Field(
                description="Address at which the issuing organization publishes verification of this certification."
            ),
        ]
        | None
    ) = None
    certification_status: (
        Annotated[
            str,
            Field(
                description="State of a certification at a point in time, e.g. 'active', 'expired', 'in-progress'."
            ),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    generically_depends_on: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
        | None
    ) = None
    isConcretizedBy: (
        Annotated[list[ActOfCertification | URIRef | str], Field()] | None
    ) = None
    is_awarded_certification_of: (
        Annotated[
            list[ActOfCertification | URIRef | str],
            Field(
                description="Relates a certification to the act of certification that concretizes it."
            ),
        ]
        | None
    ) = None
    is_certification_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates a certification to the person on which it generically depends."
            ),
        ]
        | None
    ) = None
    is_concretized_by: (
        Annotated[
            list[Disposition | Process | Quality | Role | URIRef | str],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
        | None
    ) = None
    is_sourced_from: (
        Annotated[
            list[ProfileDocument | URIRef | str],
            Field(
                description="Relates an information content entity to the profile document it was read from."
            ),
        ]
        | None
    ) = None
    issued_by_organization: (
        Annotated[
            list[Organization | URIRef | str],
            Field(
                description="Relates a certification to the organization that issued it and stands behind what it attests."
            ),
        ]
        | None
    ) = None


class Recommendation(DocumentContentEntity, RDFEntity):
    """
    Two people, and both are required: the subject it generically depends on, and the author who wrote it. An anonymous testimonial is not a recommendation in this sense and must not be minted as one.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/Recommendation"
    _name: ClassVar[str] = "Recommendation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_recommendation_author": "http://ontology.naas.ai/abi/hasRecommendationAuthor",
        "is_recommendation_of": "http://ontology.naas.ai/abi/isRecommendationOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "participatesIn": "http://ontology.naas.ai/abi/participatesIn",
        "recommendation_content": "http://ontology.naas.ai/abi/recommendation_content",
        "recommendation_date": "http://ontology.naas.ai/abi/recommendation_date",
        "relationship_label": "http://ontology.naas.ai/abi/relationship_label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_recommendation_author",
        "is_recommendation_of",
        "participatesIn",
    }

    # Data properties
    recommendation_content: (
        Annotated[
            str,
            Field(
                description="Full text of the recommendation, as written by its author."
            ),
        ]
        | None
    ) = None
    recommendation_date: (
        Annotated[
            datetime.date,
            Field(description="Date on which the recommendation was written."),
        ]
        | None
    ) = None
    relationship_label: (
        Annotated[
            str,
            Field(
                description="How the author of a recommendation describes their working relationship with the person it is about."
            ),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    has_recommendation_author: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates a recommendation to the person who wrote it. Distinct from the person it is about: a recommendation always has two people."
            ),
        ]
        | None
    ) = None
    is_recommendation_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(description="Relates a recommendation to the person it is about."),
        ]
        | None
    ) = None
    participatesIn: Annotated[list[ActOfProfiling | URIRef | str], Field()] | None = (
        None
    )


class Portrait(GenericallyDependentContinuant, RDFEntity):
    """
    The individual carries the address of the image (abi:portrait_url or abi:portrait_path), never the bytes. Image data belongs in object storage.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/Portrait"
    _name: ClassVar[str] = "Portrait"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_portrait_of": "http://ontology.naas.ai/abi/isPortraitOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "participatesIn": "http://ontology.naas.ai/abi/participatesIn",
        "portrait_path": "http://ontology.naas.ai/abi/portrait_path",
        "portrait_url": "http://ontology.naas.ai/abi/portrait_url",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_concretized_by",
        "is_portrait_of",
        "participatesIn",
    }

    # Data properties
    portrait_url: (
        Annotated[
            Any,
            Field(description="Address at which the portrait image can be retrieved."),
        ]
        | None
    ) = None
    portrait_path: (
        Annotated[
            str,
            Field(
                description="Repository-relative or object-storage path of the portrait image, for portraits that are not published at a public address."
            ),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    generically_depends_on: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
        | None
    ) = None
    is_concretized_by: (
        Annotated[
            list[Disposition | Process | Quality | Role | URIRef | str],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
        | None
    ) = None
    is_portrait_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(description="Relates a portrait image to the person it depicts."),
        ]
        | None
    ) = None
    participatesIn: Annotated[list[ActOfProfiling | URIRef | str], Field()] | None = (
        None
    )


class ProfileSummary(DocumentContentEntity, RDFEntity):
    """
    Person-level, where abi:Mission is job-level: the summary spans a career, a mission describes one act of working. Sourced from a ProfileDocument so every claim it carries stays traceable to where it was published.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ProfileSummary"
    _name: ClassVar[str] = "Profile Summary"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "headline_text": "http://ontology.naas.ai/abi/headline_text",
        "is_profile_summary_of": "http://ontology.naas.ai/abi/isProfileSummaryOf",
        "is_sourced_from": "http://ontology.naas.ai/abi/isSourcedFrom",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "participatesIn": "http://ontology.naas.ai/abi/participatesIn",
        "quote_content": "http://ontology.naas.ai/abi/quote_content",
        "summary_content": "http://ontology.naas.ai/abi/summary_content",
        "years_of_experience": "http://ontology.naas.ai/abi/years_of_experience",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_profile_summary_of",
        "is_sourced_from",
        "participatesIn",
    }

    # Data properties
    headline_text: (
        Annotated[
            str,
            Field(
                description="One-line statement of what a person does, as they present it. Distinct from abi:job_title, which is the title of one occupation role."
            ),
        ]
        | None
    ) = None
    summary_content: (
        Annotated[
            str,
            Field(
                description="Full text of the profile summary: the paragraph a person or their organization publishes about them."
            ),
        ]
        | None
    ) = None
    quote_content: (
        Annotated[
            str,
            Field(
                description="Sentence attributed to the person in their own words, published alongside the summary."
            ),
        ]
        | None
    ) = None
    years_of_experience: (
        Annotated[
            int,
            Field(
                description="Number of years of professional experience the profile summary claims. A claim carried by the summary and traceable to its source, not a figure computed from the acts of working in this graph: the graph holds only the working history that has been recorded."
            ),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    is_profile_summary_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(description="Relates a profile summary to the person it is about."),
        ]
        | None
    ) = None
    is_sourced_from: (
        Annotated[
            list[ProfileDocument | URIRef | str],
            Field(
                description="Relates an information content entity to the profile document it was read from."
            ),
        ]
        | None
    ) = None
    participatesIn: Annotated[list[ActOfProfiling | URIRef | str], Field()] | None = (
        None
    )


class ProfileDocument(DocumentContentEntity, RDFEntity):
    """
    The provenance anchor of the demo graph: everything asserted from a profile page: missions, roles, skills, enrollments, degrees, certifications points back to the ProfileDocument it was read from.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ProfileDocument"
    _name: ClassVar[str] = "Profile Document"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "genericallyDependsOn": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_profile_document_for_profiling": "http://ontology.naas.ai/abi/isProfileDocumentForProfiling",
        "is_profile_document_of": "http://ontology.naas.ai/abi/isProfileDocumentOf",
        "is_source_document_of": "http://ontology.naas.ai/abi/isSourceDocumentOf",
        "is_source_of": "http://ontology.naas.ai/abi/isSourceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "source_url": "http://ontology.naas.ai/abi/source_url",
    }
    _object_properties: ClassVar[set[str]] = {
        "genericallyDependsOn",
        "is_profile_document_for_profiling",
        "is_profile_document_of",
        "is_source_document_of",
        "is_source_of",
    }

    # Data properties
    source_url: (
        Annotated[
            Any,
            Field(description="Address at which a profile document can be retrieved."),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    genericallyDependsOn: Annotated[list[Person | URIRef | str], Field()] | None = None
    is_profile_document_for_profiling: (
        Annotated[
            list[ActOfProfiling | URIRef | str],
            Field(
                description="Relates a profile document to an act of profiling that used it as input."
            ),
        ]
        | None
    ) = None
    is_profile_document_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates a profile document to the person it is about and on which it generically depends."
            ),
        ]
        | None
    ) = None
    is_source_document_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates a profile document to a planned act that was read from it and registered against it."
            ),
        ]
        | None
    ) = None
    is_source_of: (
        Annotated[
            list[GenericallyDependentContinuant | URIRef | str],
            Field(
                description="Relates a profile document to an information content entity read from it."
            ),
        ]
        | None
    ) = None


class OccupationRole(Role, RDFEntity):
    """
    Externally grounded: it exists only while the person works in that capacity, and ends without the person ceasing to exist. What a source says about a job ends here; the employing organization's own view of it (the position it defined, the contract, the record) is internal and specializes this class elsewhere.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/OccupationRole"
    _name: ClassVar[str] = "Occupation Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "hasRealization": "http://ontology.naas.ai/abi/hasRealization",
        "has_mission": "http://ontology.naas.ai/abi/hasMission",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_occupation_role_of": "http://ontology.naas.ai/abi/isOccupationRoleOf",
        "job_title": "http://ontology.naas.ai/abi/job_title",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "hasRealization",
        "has_mission",
        "has_realization",
        "inheres_in",
        "is_occupation_role_of",
    }

    # Data properties
    job_title: (
        Annotated[
            str,
            Field(description="Title of an occupation role as the source states it."),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    concretizes: (
        Annotated[
            list[GenericallyDependentContinuant | URIRef | str],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
        | None
    ) = None
    hasRealization: Annotated[list[ActOfWorking | URIRef | str], Field()] | None = None
    has_mission: (
        Annotated[
            list[Mission | URIRef | str],
            Field(
                description="Relates an occupation role to the mission it concretizes. Named sub-property of abi:concretizes: a role (SDC) concretizes a mission (GDC)."
            ),
        ]
        | None
    ) = None
    has_realization: (
        Annotated[
            list[Process | URIRef | str],
            Field(description="b has realization c =Def c realizes b"),
        ]
        | None
    ) = None
    inheres_in: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
        | None
    ) = None
    is_occupation_role_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates an occupation role to the person in whom it inheres."
            ),
        ]
        | None
    ) = None


class StudentRole(Role, RDFEntity):
    """
    No CCO student-role class; minted in the people namespace. Ends when the enrollment ends, without the person ceasing to exist.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/StudentRole"
    _name: ClassVar[str] = "Student Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "hasRealization": "http://ontology.naas.ai/abi/hasRealization",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_student_role_of": "http://ontology.naas.ai/abi/isStudentRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "hasRealization",
        "has_realization",
        "inheres_in",
        "is_student_role_of",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    concretizes: (
        Annotated[
            list[GenericallyDependentContinuant | URIRef | str],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
        | None
    ) = None
    hasRealization: Annotated[list[ActOfStudying | URIRef | str], Field()] | None = None
    has_realization: (
        Annotated[
            list[Process | URIRef | str],
            Field(description="b has realization c =Def c realizes b"),
        ]
        | None
    ) = None
    inheres_in: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
        | None
    ) = None
    is_student_role_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates a student role to the person in whom it inheres."
            ),
        ]
        | None
    ) = None


class LanguageCapability(Quality, RDFEntity):
    """
    Deliberately NOT equivalent to CCO Language Skill (cco:ont00000181). That class is an Agent Capability and therefore a BFO realizable entity, which is disjoint from quality; this domain already models abi:Skill as a quality, and asserting both would make the ontology inconsistent. The language itself is a CCO Language, reached through abi:ofLanguage. Like a skill, it is borne by the person and outlives any one act: abi:developsLanguageCapability links a planned act, of whatever kind, to the capabilities exercised and grown in it.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/LanguageCapability"
    _name: ClassVar[str] = "Language Capability"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_language_capability_developed_in": "http://ontology.naas.ai/abi/isLanguageCapabilityDevelopedIn",
        "is_language_capability_of": "http://ontology.naas.ai/abi/isLanguageCapabilityOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "language_name": "http://ontology.naas.ai/abi/language_name",
        "of_language": "http://ontology.naas.ai/abi/ofLanguage",
        "participates_in": "http://ontology.naas.ai/abi/participatesIn",
        "proficiency_level": "http://ontology.naas.ai/abi/proficiency_level",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "inheres_in",
        "is_language_capability_developed_in",
        "is_language_capability_of",
        "of_language",
        "participates_in",
    }

    # Data properties
    language_name: (
        Annotated[
            str,
            Field(
                description="Name of the language a capability is held for, as displayed."
            ),
        ]
        | None
    ) = None
    proficiency_level: (
        Annotated[
            str,
            Field(
                description="Reported level of a language capability. Free text rather than a code list: sources state it in incompatible scales (CEFR, 'native', 'professional working proficiency') and converting between them would assert more than the source does."
            ),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    concretizes: (
        Annotated[
            list[GenericallyDependentContinuant | URIRef | str],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
        | None
    ) = None
    inheres_in: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
        | None
    ) = None
    is_language_capability_developed_in: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates a language capability to a planned act in which it is exercised and developed."
            ),
        ]
        | None
    ) = None
    is_language_capability_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates a language capability to the person in whom it inheres."
            ),
        ]
        | None
    ) = None
    of_language: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates a language capability to the language it is held for. The language is a CCO Language: a directive information content entity prescribing a canonical format for communication, shared by every speaker of it."
            ),
        ]
        | None
    ) = None
    participates_in: (
        Annotated[
            list[Process | URIRef | str],
            Field(
                description="(Elucidation) participates in holds between some b that is either a specifically dependent continuant or generically dependent continuant or independent continuant that is not a spatial region & some process p such that b participates in p some way"
            ),
        ]
        | None
    ) = None


class Interest(Quality, RDFEntity):
    """
    Modelled as a quality for consistency with abi:Skill rather than as a disposition. Points at its target with abi:hasInterestTarget where an individual exists for it, and otherwise carries abi:interest_name alone.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/Interest"
    _name: ClassVar[str] = "Interest"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_interest_target": "http://ontology.naas.ai/abi/hasInterestTarget",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "interest_description": "http://ontology.naas.ai/abi/interest_description",
        "interest_kind": "http://ontology.naas.ai/abi/interest_kind",
        "interest_name": "http://ontology.naas.ai/abi/interest_name",
        "is_interest_of": "http://ontology.naas.ai/abi/isInterestOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "participatesIn": "http://ontology.naas.ai/abi/participatesIn",
        "participates_in": "http://ontology.naas.ai/abi/participatesIn",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_interest_target",
        "inheres_in",
        "is_interest_of",
        "participatesIn",
        "participates_in",
    }

    # Data properties
    interest_name: (
        Annotated[
            str,
            Field(
                description="Name of what the interest is in, carried on the interest itself so an interest with no individual to point at is still stated."
            ),
        ]
        | None
    ) = None
    interest_description: (
        Annotated[
            str, Field(description="Sentence stating what the interest consists in.")
        ]
        | None
    ) = None
    interest_kind: (
        Annotated[
            str,
            Field(
                description="Category of the interest target, used to group interests for display, e.g. 'organization', 'school', 'person', 'topic'."
            ),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    concretizes: (
        Annotated[
            list[GenericallyDependentContinuant | URIRef | str],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
        | None
    ) = None
    has_interest_target: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates an interest to the entity it is an interest in. Deliberately unrestricted in range: an interest can be in an organization, a person, a place or a subject that has no individual in this graph, in which case only abi:interest_name is asserted."
            ),
        ]
        | None
    ) = None
    inheres_in: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
        | None
    ) = None
    is_interest_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(description="Relates an interest to the person in whom it inheres."),
        ]
        | None
    ) = None
    participatesIn: Annotated[list[ActOfProfiling | URIRef | str], Field()] | None = (
        None
    )
    participates_in: (
        Annotated[
            list[Process | URIRef | str],
            Field(
                description="(Elucidation) participates in holds between some b that is either a specifically dependent continuant or generically dependent continuant or independent continuant that is not a spatial region & some process p such that b participates in p some way"
            ),
        ]
        | None
    ) = None


class Skill(Quality, RDFEntity):
    """
    Borne by the person, not by the process: the skill outlives any one act of working. abi:developsSkill links a planned act, of whatever kind, to the skills exercised and grown in it.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/Skill"
    _name: ClassVar[str] = "Skill"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "inheresIn": "http://ontology.naas.ai/abi/inheresIn",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_skill_demonstrated_in": "http://ontology.naas.ai/abi/isSkillDemonstratedIn",
        "is_skill_developed_in": "http://ontology.naas.ai/abi/isSkillDevelopedIn",
        "is_skill_of": "http://ontology.naas.ai/abi/isSkillOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "participates_in": "http://ontology.naas.ai/abi/participatesIn",
        "skill_name": "http://ontology.naas.ai/abi/skill_name",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "inheresIn",
        "inheres_in",
        "is_skill_demonstrated_in",
        "is_skill_developed_in",
        "is_skill_of",
        "participates_in",
    }

    # Data properties
    skill_name: (
        Annotated[
            str, Field(description="Name of a skill as stated on the source profile.")
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    concretizes: (
        Annotated[
            list[GenericallyDependentContinuant | URIRef | str],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
        | None
    ) = None
    inheresIn: Annotated[list[Person | URIRef | str], Field()] | None = None
    inheres_in: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
        | None
    ) = None
    is_skill_demonstrated_in: (
        Annotated[
            list[ActOfCertification | URIRef | str],
            Field(
                description="Relates a skill to an act of certification in which it is demonstrated."
            ),
        ]
        | None
    ) = None
    is_skill_developed_in: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates a skill to a planned act in which it is exercised and developed."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(description="Relates a skill to the person in whom it inheres."),
        ]
        | None
    ) = None
    participates_in: (
        Annotated[
            list[Process | URIRef | str],
            Field(
                description="(Elucidation) participates in holds between some b that is either a specifically dependent continuant or generically dependent continuant or independent continuant that is not a spatial region & some process p such that b participates in p some way"
            ),
        ]
        | None
    ) = None


class CertificationCandidateRole(Role, RDFEntity):
    """
    No CCO candidate-role class; minted in the people namespace. Kept apart from the occupation and student roles: a person is a candidate whether or not they were working or enrolled at the time.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CertificationCandidateRole"
    _name: ClassVar[str] = "Certification Candidate Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "hasRealization": "http://ontology.naas.ai/abi/hasRealization",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_certification_candidate_role_of": "http://ontology.naas.ai/abi/isCertificationCandidateRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "hasRealization",
        "has_realization",
        "inheres_in",
        "is_certification_candidate_role_of",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    concretizes: (
        Annotated[
            list[GenericallyDependentContinuant | URIRef | str],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
        | None
    ) = None
    hasRealization: (
        Annotated[list[ActOfCertification | URIRef | str], Field()] | None
    ) = None
    has_realization: (
        Annotated[
            list[Process | URIRef | str],
            Field(description="b has realization c =Def c realizes b"),
        ]
        | None
    ) = None
    inheres_in: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
        | None
    ) = None
    is_certification_candidate_role_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates a certification candidate role to the person in whom it inheres."
            ),
        ]
        | None
    ) = None


class Mission(GenericallyDependentContinuant, RDFEntity):
    """
    Deliberately a GDC and NOT a BFO function. A mission is stated, copied between systems and survives the person leaving the post, which a disposition inhering in the person could not. The WHY that inheres in the person is abi:OccupationRole; the mission is what that role concretizes. rdfs:label carries the opening sentence; abi:mission_content carries the full text.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/Mission"
    _name: ClassVar[str] = "Mission"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "genericallyDependsOn": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "isConcretizedBy": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_mission_carried_by": "http://ontology.naas.ai/abi/isMissionCarriedBy",
        "is_mission_of": "http://ontology.naas.ai/abi/isMissionOf",
        "is_sourced_from": "http://ontology.naas.ai/abi/isSourcedFrom",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "mission_content": "http://ontology.naas.ai/abi/mission_content",
        "mission_context": "http://ontology.naas.ai/abi/mission_context",
    }
    _object_properties: ClassVar[set[str]] = {
        "genericallyDependsOn",
        "generically_depends_on",
        "isConcretizedBy",
        "is_concretized_by",
        "is_mission_carried_by",
        "is_mission_of",
        "is_sourced_from",
    }

    # Data properties
    mission_context: (
        Annotated[
            str,
            Field(
                description="The situation a mission was undertaken in: what the organization needed and why, stated as prose before the mission's own objectives and activities. Optional: a source that states only what was done, not the situation it responded to, leaves this unset."
            ),
        ]
        | None
    ) = None
    mission_content: (
        Annotated[
            str,
            Field(
                description="Full stated text of a mission: the objectives and activities listed under its opening sentence, one per line when the source enumerates them as discrete tasks. The opening sentence alone is carried by rdfs:label; the situation the mission responded to is carried by abi:mission_context, not here."
            ),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    genericallyDependsOn: Annotated[list[Person | URIRef | str], Field()] | None = None
    generically_depends_on: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
        | None
    ) = None
    isConcretizedBy: Annotated[list[OccupationRole | URIRef | str], Field()] | None = (
        None
    )
    is_concretized_by: (
        Annotated[
            list[Disposition | Process | Quality | Role | URIRef | str],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
        | None
    ) = None
    is_mission_carried_by: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates a mission to the person on which it generically depends."
            ),
        ]
        | None
    ) = None
    is_mission_of: (
        Annotated[
            list[OccupationRole | URIRef | str],
            Field(
                description="Relates a mission to the occupation role that concretizes it while the person works in that capacity."
            ),
        ]
        | None
    ) = None
    is_sourced_from: (
        Annotated[
            list[ProfileDocument | URIRef | str],
            Field(
                description="Relates an information content entity to the profile document it was read from."
            ),
        ]
        | None
    ) = None


# Rebuild models to resolve forward references
ActOfCertification.model_rebuild()
ActOfProfiling.model_rebuild()
ActOfStudying.model_rebuild()
ActOfWorking.model_rebuild()
EnrollmentRecord.model_rebuild()
AcademicDegree.model_rebuild()
Certification.model_rebuild()
Recommendation.model_rebuild()
Portrait.model_rebuild()
ProfileSummary.model_rebuild()
ProfileDocument.model_rebuild()
OccupationRole.model_rebuild()
StudentRole.model_rebuild()
LanguageCapability.model_rebuild()
Interest.model_rebuild()
Skill.model_rebuild()
CertificationCandidateRole.model_rebuild()
Mission.model_rebuild()
