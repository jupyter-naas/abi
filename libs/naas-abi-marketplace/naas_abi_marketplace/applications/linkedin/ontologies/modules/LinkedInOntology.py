# onto2py-source-sha256: c7960d6c3e476536d1b6e87943bfe985edac4639ccaeb15dc151df34cf61cb22
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
    GenericallyDependentContinuant,
    MaterialEntity,
    Process,
    Role,
    TemporalRegion,
)
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


class SocialPage(RDFEntity):
    """
    A social page must be registered on a social media platform
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SocialPage"
    _name: ClassVar[str] = "Social Page"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_social_page_of": "http://ontology.naas.ai/abi/linkedin/isSocialPageOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_social_page_of"}

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
    is_social_page_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates a social media page to the person or organization it represents."
            ),
        ]
        | None
    ) = None


class LinkedInProperty(RDFEntity):
    """
    LinkedIn Property
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Property"
    _name: ClassVar[str] = "LinkedIn Property"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInIndustry(RDFEntity):
    """
    LinkedIn Industry
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Industry"
    _name: ClassVar[str] = "LinkedIn Industry"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

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


class LinkedInLocation(RDFEntity):
    """
    A LinkedIn Location represents a hierarchical geographical designation that can combine multiple location types (country, state/region, metropolitan area, city) into a single concatenated string.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Location"
    _name: ClassVar[str] = "LinkedIn Location"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

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


class ActOfConnection(RDFEntity):
    """
    Act of Connection
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/ActOfConnection"
    _name: ClassVar[str] = "Act of Connection"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "hasParticipant": "http://ontology.naas.ai/abi/hasParticipant",
        "hasSourceDocument": "http://ontology.naas.ai/abi/hasSourceDocument",
        "has_connected_person": "http://ontology.naas.ai/abi/linkedin/hasConnectedPerson",
        "has_connection_owner": "http://ontology.naas.ai/abi/linkedin/hasConnectionOwner",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupiesTemporalRegion": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "realizes": "http://ontology.naas.ai/abi/realizes",
    }
    _object_properties: ClassVar[set[str]] = {
        "hasParticipant",
        "hasSourceDocument",
        "has_connected_person",
        "has_connection_owner",
        "occupiesTemporalRegion",
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
    hasParticipant: Annotated[list[Person | URIRef | str], Field()] | None = None
    hasSourceDocument: (
        Annotated[list[ConnectionsExportFile | URIRef | str], Field()] | None
    ) = None
    has_connected_person: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates an act of connection to the participant listed as a connection in the export owner's LinkedIn data export."
            ),
        ]
        | None
    ) = None
    has_connection_owner: (
        Annotated[
            list[Person | URIRef | str],
            Field(
                description="Relates an act of connection to the participant whose LinkedIn data export states it."
            ),
        ]
        | None
    ) = None
    occupiesTemporalRegion: (
        Annotated[list[TemporalRegion | URIRef | str], Field()] | None
    ) = None
    realizes: Annotated[list[ConnectionRole | URIRef | str], Field()] | None = None


class ConnectionsExportFile(RDFEntity):
    """
    A profile document of the export owner: it is what the owner published about their network, and every act of connection read from it points back to it through abi:hasSourceDocument, as an act of working points to the profile document it was read from.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/linkedin/ConnectionsExportFile"
    )
    _name: ClassVar[str] = "Connections Export File"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

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


class LinkedInPage(SocialPage, RDFEntity):
    """
    A LinkedIn page must be registered in https://www.linkedin.com/
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Page"
    _name: ClassVar[str] = "LinkedIn Page"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/abi/linkedin/description",
        "entity_urn": "http://ontology.naas.ai/abi/linkedin/entityUrn",
        "is_social_page_of": "http://ontology.naas.ai/abi/linkedin/isSocialPageOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "linkedin_id": "http://ontology.naas.ai/abi/linkedin/id",
        "linkedin_public_id": "http://ontology.naas.ai/abi/linkedin/public_id",
        "linkedin_public_url": "http://ontology.naas.ai/abi/linkedin/public_url",
        "linkedin_url": "http://ontology.naas.ai/abi/linkedin/url",
        "localized_name": "http://ontology.naas.ai/abi/linkedin/localizedName",
        "logo": "http://ontology.naas.ai/abi/linkedin/logo",
    }
    _object_properties: ClassVar[set[str]] = {"is_social_page_of"}

    # Data properties
    linkedin_id: (
        Annotated[str, Field(description="The ID of the LinkedIn page.")] | None
    ) = None
    linkedin_url: (
        Annotated[
            str,
            Field(
                description="The URL of the LinkedIn page. It uses the LinkedIn ID as a unique identifier."
            ),
        ]
        | None
    ) = None
    linkedin_public_id: (
        Annotated[
            str,
            Field(
                description="The public ID of the LinkedIn page. It might change over time."
            ),
        ]
        | None
    ) = None
    linkedin_public_url: (
        Annotated[
            str,
            Field(
                description="The public URL of the LinkedIn page. It uses the LinkedIn Public ID as identifier."
            ),
        ]
        | None
    ) = None
    logo: Annotated[str, Field(description="The logo of the LinkedIn page.")] | None = (
        None
    )
    entity_urn: Annotated[str, Field(description="The URN of the entity.")] | None = (
        None
    )
    localized_name: (
        Annotated[str, Field(description="The localized name of the entity.")] | None
    ) = None
    description: (
        Annotated[str, Field(description="The description of the entity.")] | None
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
    is_social_page_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates a social media page to the person or organization it represents."
            ),
        ]
        | None
    ) = None


class LinkedInProfile(LinkedInProperty, RDFEntity):
    """
    LinkedIn Profile
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Profile"
    _name: ClassVar[str] = "LinkedIn Profile"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_certification": "http://ontology.naas.ai/abi/linkedin/hasCertification",
        "has_course": "http://ontology.naas.ai/abi/linkedin/hasCourse",
        "has_education": "http://ontology.naas.ai/abi/linkedin/hasEducation",
        "has_honor": "http://ontology.naas.ai/abi/linkedin/hasHonor",
        "has_language": "http://ontology.naas.ai/abi/linkedin/hasLanguage",
        "has_organization": "http://ontology.naas.ai/abi/linkedin/hasOrganization",
        "has_patent": "http://ontology.naas.ai/abi/linkedin/hasPatent",
        "has_position": "http://ontology.naas.ai/abi/linkedin/hasPosition",
        "has_position_group": "http://ontology.naas.ai/abi/linkedin/hasPositionGroup",
        "has_project": "http://ontology.naas.ai/abi/linkedin/hasProject",
        "has_publication": "http://ontology.naas.ai/abi/linkedin/hasPublication",
        "has_skill": "http://ontology.naas.ai/abi/linkedin/hasSkill",
        "has_test_score": "http://ontology.naas.ai/abi/linkedin/hasTestScore",
        "has_volunteer_cause": "http://ontology.naas.ai/abi/linkedin/hasVolunteerCause",
        "has_volunteer_experience": "http://ontology.naas.ai/abi/linkedin/hasVolunteerExperience",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_profile_of": "http://ontology.naas.ai/abi/linkedin/isProfileOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_certification",
        "has_course",
        "has_education",
        "has_honor",
        "has_language",
        "has_organization",
        "has_patent",
        "has_position",
        "has_position_group",
        "has_project",
        "has_publication",
        "has_skill",
        "has_test_score",
        "has_volunteer_cause",
        "has_volunteer_experience",
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_profile_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    has_certification: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its certifications."),
        ]
        | None
    ) = None
    has_course: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its courses."),
        ]
        | None
    ) = None
    has_education: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its education history."),
        ]
        | None
    ) = None
    has_honor: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its honors."),
        ]
        | None
    ) = None
    has_language: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its languages."),
        ]
        | None
    ) = None
    has_organization: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its organizations."),
        ]
        | None
    ) = None
    has_patent: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its patents."),
        ]
        | None
    ) = None
    has_position: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its positions."),
        ]
        | None
    ) = None
    has_position_group: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its position groups."),
        ]
        | None
    ) = None
    has_project: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its projects."),
        ]
        | None
    ) = None
    has_publication: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its publications."),
        ]
        | None
    ) = None
    has_skill: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its skills."),
        ]
        | None
    ) = None
    has_test_score: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its test scores."),
        ]
        | None
    ) = None
    has_volunteer_cause: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(description="Relates a LinkedIn profile to its volunteer causes."),
        ]
        | None
    ) = None
    has_volunteer_experience: (
        Annotated[
            list[LinkedInProperty | URIRef | str],
            Field(
                description="Relates a LinkedIn profile to its volunteer experience."
            ),
        ]
        | None
    ) = None
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_profile_of: (
        Annotated[
            list[LinkedInProfilePage | URIRef | str],
            Field(
                description="Relates a LinkedIn profile to the LinkedIn profile page it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInPatent(LinkedInProperty, RDFEntity):
    """
    LinkedIn Patent
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Patent"
    _name: ClassVar[str] = "LinkedIn Patent"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInHonor(LinkedInProperty, RDFEntity):
    """
    LinkedIn Honor
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Honor"
    _name: ClassVar[str] = "LinkedIn Honor"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInEducation(LinkedInProperty, RDFEntity):
    """
    LinkedIn Education
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Education"
    _name: ClassVar[str] = "LinkedIn Education"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInVolunteerExperience(LinkedInProperty, RDFEntity):
    """
    LinkedIn Volunteer Experience
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/linkedin/VolunteerExperience"
    )
    _name: ClassVar[str] = "LinkedIn Volunteer Experience"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInVolunteerCause(LinkedInProperty, RDFEntity):
    """
    LinkedIn Volunteer Cause
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/VolunteerCause"
    _name: ClassVar[str] = "LinkedIn Volunteer Cause"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInTestScore(LinkedInProperty, RDFEntity):
    """
    LinkedIn Test Score
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/TestScore"
    _name: ClassVar[str] = "LinkedIn Test Score"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInSkill(LinkedInProperty, RDFEntity):
    """
    LinkedIn Skill
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Skill"
    _name: ClassVar[str] = "LinkedIn Skill"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInProject(LinkedInProperty, RDFEntity):
    """
    LinkedIn Project
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Project"
    _name: ClassVar[str] = "LinkedIn Project"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInCertification(LinkedInProperty, RDFEntity):
    """
    LinkedIn Certification
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Certification"
    _name: ClassVar[str] = "LinkedIn Certification"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInLanguage(LinkedInProperty, RDFEntity):
    """
    LinkedIn Language
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Language"
    _name: ClassVar[str] = "LinkedIn Language"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInCourse(LinkedInProperty, RDFEntity):
    """
    LinkedIn Course
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Course"
    _name: ClassVar[str] = "LinkedIn Course"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInPublication(LinkedInProperty, RDFEntity):
    """
    LinkedIn Publication
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Publication"
    _name: ClassVar[str] = "LinkedIn Publication"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInPositionGroup(LinkedInProperty, RDFEntity):
    """
    LinkedIn Position Group
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/PositionGroup"
    _name: ClassVar[str] = "LinkedIn Position Group"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInOrganization(LinkedInProperty, RDFEntity):
    """
    LinkedIn Organization
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Organization"
    _name: ClassVar[str] = "LinkedIn Organization"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInPosition(LinkedInProperty, RDFEntity):
    """
    LinkedIn Position
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Position"
    _name: ClassVar[str] = "LinkedIn Position"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class LinkedInFollowingInfo(LinkedInProperty, RDFEntity):
    """
    LinkedIn Following Info
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/FollowingInfo"
    _name: ClassVar[str] = "LinkedIn Following Info"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "follower_count": "http://ontology.naas.ai/abi/linkedin/followerCount",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Data properties
    follower_count: (
        Annotated[
            Any, Field(description="The number of followers for a LinkedIn entity.")
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
    is_certification_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a certification to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_course_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a course to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_education_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an education entry to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_honor_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an honor to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_language_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a language to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_organization_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates an organization to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_patent_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a patent to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_group_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position group to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_position_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a position to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_project_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a project to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_publication_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a publication to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_skill_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a skill to the LinkedIn profile it belongs to."),
        ]
        | None
    ) = None
    is_test_score_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a test score to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_cause_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer cause to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None
    is_volunteer_experience_of: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(
                description="Relates a volunteer experience to the LinkedIn profile it belongs to."
            ),
        ]
        | None
    ) = None


class ConnectionRole(Role, RDFEntity):
    """
    Connection Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/ConnectionRole"
    _name: ClassVar[str] = "Connection Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "hasRealization": "http://ontology.naas.ai/abi/hasRealization",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_connection_role_of": "http://ontology.naas.ai/abi/linkedin/isConnectionRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "hasRealization",
        "has_realization",
        "inheres_in",
        "is_connection_role_of",
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
    hasRealization: Annotated[list[ActOfConnection | URIRef | str], Field()] | None = (
        None
    )
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
    is_connection_role_of: (
        Annotated[
            list[Person | URIRef | str],
            Field(description="Relates a connection role to the person it inheres in."),
        ]
        | None
    ) = None


class LinkedInProfilePage(LinkedInPage, RDFEntity):
    """
    A LinkedIn profile page must be registered in https://www.linkedin.com/in/
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/ProfilePage"
    _name: ClassVar[str] = "LinkedIn Profile Page"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/abi/linkedin/description",
        "entity_urn": "http://ontology.naas.ai/abi/linkedin/entityUrn",
        "has_profile": "http://ontology.naas.ai/abi/linkedin/hasProfile",
        "is_social_page_of": "http://ontology.naas.ai/abi/linkedin/isSocialPageOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "linkedin_id": "http://ontology.naas.ai/abi/linkedin/id",
        "linkedin_public_id": "http://ontology.naas.ai/abi/linkedin/public_id",
        "linkedin_public_url": "http://ontology.naas.ai/abi/linkedin/public_url",
        "linkedin_url": "http://ontology.naas.ai/abi/linkedin/url",
        "localized_name": "http://ontology.naas.ai/abi/linkedin/localizedName",
        "logo": "http://ontology.naas.ai/abi/linkedin/logo",
    }
    _object_properties: ClassVar[set[str]] = {"has_profile", "is_social_page_of"}

    # Data properties
    linkedin_id: (
        Annotated[str, Field(description="The ID of the LinkedIn page.")] | None
    ) = None
    linkedin_url: (
        Annotated[
            str,
            Field(
                description="The URL of the LinkedIn page. It uses the LinkedIn ID as a unique identifier."
            ),
        ]
        | None
    ) = None
    linkedin_public_id: (
        Annotated[
            str,
            Field(
                description="The public ID of the LinkedIn page. It might change over time."
            ),
        ]
        | None
    ) = None
    linkedin_public_url: (
        Annotated[
            str,
            Field(
                description="The public URL of the LinkedIn page. It uses the LinkedIn Public ID as identifier."
            ),
        ]
        | None
    ) = None
    logo: Annotated[str, Field(description="The logo of the LinkedIn page.")] | None = (
        None
    )
    entity_urn: Annotated[str, Field(description="The URN of the entity.")] | None = (
        None
    )
    localized_name: (
        Annotated[str, Field(description="The localized name of the entity.")] | None
    ) = None
    description: (
        Annotated[str, Field(description="The description of the entity.")] | None
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
    has_profile: (
        Annotated[
            list[LinkedInProfile | URIRef | str],
            Field(description="Relates a LinkedIn profile page to its profile."),
        ]
        | None
    ) = None
    is_social_page_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates a social media page to the person or organization it represents."
            ),
        ]
        | None
    ) = None


class LinkedInCompanyPage(LinkedInPage, RDFEntity):
    """
    A LinkedIn company page must be registered in https://www.linkedin.com/company/
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/CompanyPage"
    _name: ClassVar[str] = "LinkedIn Company Page"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/abi/linkedin/description",
        "entity_urn": "http://ontology.naas.ai/abi/linkedin/entityUrn",
        "is_social_page_of": "http://ontology.naas.ai/abi/linkedin/isSocialPageOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "linkedin_id": "http://ontology.naas.ai/abi/linkedin/id",
        "linkedin_public_id": "http://ontology.naas.ai/abi/linkedin/public_id",
        "linkedin_public_url": "http://ontology.naas.ai/abi/linkedin/public_url",
        "linkedin_url": "http://ontology.naas.ai/abi/linkedin/url",
        "localized_name": "http://ontology.naas.ai/abi/linkedin/localizedName",
        "logo": "http://ontology.naas.ai/abi/linkedin/logo",
    }
    _object_properties: ClassVar[set[str]] = {"is_social_page_of"}

    # Data properties
    linkedin_id: (
        Annotated[str, Field(description="The ID of the LinkedIn page.")] | None
    ) = None
    linkedin_url: (
        Annotated[
            str,
            Field(
                description="The URL of the LinkedIn page. It uses the LinkedIn ID as a unique identifier."
            ),
        ]
        | None
    ) = None
    linkedin_public_id: (
        Annotated[
            str,
            Field(
                description="The public ID of the LinkedIn page. It might change over time."
            ),
        ]
        | None
    ) = None
    linkedin_public_url: (
        Annotated[
            str,
            Field(
                description="The public URL of the LinkedIn page. It uses the LinkedIn Public ID as identifier."
            ),
        ]
        | None
    ) = None
    logo: Annotated[str, Field(description="The logo of the LinkedIn page.")] | None = (
        None
    )
    entity_urn: Annotated[str, Field(description="The URN of the entity.")] | None = (
        None
    )
    localized_name: (
        Annotated[str, Field(description="The localized name of the entity.")] | None
    ) = None
    description: (
        Annotated[str, Field(description="The description of the entity.")] | None
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
    is_social_page_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates a social media page to the person or organization it represents."
            ),
        ]
        | None
    ) = None


class LinkedInSchoolPage(LinkedInPage, RDFEntity):
    """
    A LinkedIn school page must be registered in https://www.linkedin.com/school/
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/SchoolPage"
    _name: ClassVar[str] = "LinkedIn School Page"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/abi/linkedin/description",
        "entity_urn": "http://ontology.naas.ai/abi/linkedin/entityUrn",
        "is_social_page_of": "http://ontology.naas.ai/abi/linkedin/isSocialPageOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "linkedin_id": "http://ontology.naas.ai/abi/linkedin/id",
        "linkedin_public_id": "http://ontology.naas.ai/abi/linkedin/public_id",
        "linkedin_public_url": "http://ontology.naas.ai/abi/linkedin/public_url",
        "linkedin_url": "http://ontology.naas.ai/abi/linkedin/url",
        "localized_name": "http://ontology.naas.ai/abi/linkedin/localizedName",
        "logo": "http://ontology.naas.ai/abi/linkedin/logo",
    }
    _object_properties: ClassVar[set[str]] = {"is_social_page_of"}

    # Data properties
    linkedin_id: (
        Annotated[str, Field(description="The ID of the LinkedIn page.")] | None
    ) = None
    linkedin_url: (
        Annotated[
            str,
            Field(
                description="The URL of the LinkedIn page. It uses the LinkedIn ID as a unique identifier."
            ),
        ]
        | None
    ) = None
    linkedin_public_id: (
        Annotated[
            str,
            Field(
                description="The public ID of the LinkedIn page. It might change over time."
            ),
        ]
        | None
    ) = None
    linkedin_public_url: (
        Annotated[
            str,
            Field(
                description="The public URL of the LinkedIn page. It uses the LinkedIn Public ID as identifier."
            ),
        ]
        | None
    ) = None
    logo: Annotated[str, Field(description="The logo of the LinkedIn page.")] | None = (
        None
    )
    entity_urn: Annotated[str, Field(description="The URN of the entity.")] | None = (
        None
    )
    localized_name: (
        Annotated[str, Field(description="The localized name of the entity.")] | None
    ) = None
    description: (
        Annotated[str, Field(description="The description of the entity.")] | None
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
    is_social_page_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates a social media page to the person or organization it represents."
            ),
        ]
        | None
    ) = None


class LinkedInJobSearchPage(LinkedInPage, RDFEntity):
    """
    A LinkedIn job search page must be registered in https://www.linkedin.com/jobs/
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/JobSearchPage"
    _name: ClassVar[str] = "LinkedIn Job Search Page"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/abi/linkedin/description",
        "entity_urn": "http://ontology.naas.ai/abi/linkedin/entityUrn",
        "is_social_page_of": "http://ontology.naas.ai/abi/linkedin/isSocialPageOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "linkedin_id": "http://ontology.naas.ai/abi/linkedin/id",
        "linkedin_public_id": "http://ontology.naas.ai/abi/linkedin/public_id",
        "linkedin_public_url": "http://ontology.naas.ai/abi/linkedin/public_url",
        "linkedin_url": "http://ontology.naas.ai/abi/linkedin/url",
        "localized_name": "http://ontology.naas.ai/abi/linkedin/localizedName",
        "logo": "http://ontology.naas.ai/abi/linkedin/logo",
    }
    _object_properties: ClassVar[set[str]] = {"is_social_page_of"}

    # Data properties
    linkedin_id: (
        Annotated[str, Field(description="The ID of the LinkedIn page.")] | None
    ) = None
    linkedin_url: (
        Annotated[
            str,
            Field(
                description="The URL of the LinkedIn page. It uses the LinkedIn ID as a unique identifier."
            ),
        ]
        | None
    ) = None
    linkedin_public_id: (
        Annotated[
            str,
            Field(
                description="The public ID of the LinkedIn page. It might change over time."
            ),
        ]
        | None
    ) = None
    linkedin_public_url: (
        Annotated[
            str,
            Field(
                description="The public URL of the LinkedIn page. It uses the LinkedIn Public ID as identifier."
            ),
        ]
        | None
    ) = None
    logo: Annotated[str, Field(description="The logo of the LinkedIn page.")] | None = (
        None
    )
    entity_urn: Annotated[str, Field(description="The URN of the entity.")] | None = (
        None
    )
    localized_name: (
        Annotated[str, Field(description="The localized name of the entity.")] | None
    ) = None
    description: (
        Annotated[str, Field(description="The description of the entity.")] | None
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
    is_social_page_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates a social media page to the person or organization it represents."
            ),
        ]
        | None
    ) = None


# Rebuild models to resolve forward references
SocialPage.model_rebuild()
LinkedInProperty.model_rebuild()
LinkedInIndustry.model_rebuild()
LinkedInLocation.model_rebuild()
ActOfConnection.model_rebuild()
ConnectionsExportFile.model_rebuild()
LinkedInPage.model_rebuild()
LinkedInProfile.model_rebuild()
LinkedInPatent.model_rebuild()
LinkedInHonor.model_rebuild()
LinkedInEducation.model_rebuild()
LinkedInVolunteerExperience.model_rebuild()
LinkedInVolunteerCause.model_rebuild()
LinkedInTestScore.model_rebuild()
LinkedInSkill.model_rebuild()
LinkedInProject.model_rebuild()
LinkedInCertification.model_rebuild()
LinkedInLanguage.model_rebuild()
LinkedInCourse.model_rebuild()
LinkedInPublication.model_rebuild()
LinkedInPositionGroup.model_rebuild()
LinkedInOrganization.model_rebuild()
LinkedInPosition.model_rebuild()
LinkedInFollowingInfo.model_rebuild()
ConnectionRole.model_rebuild()
LinkedInProfilePage.model_rebuild()
LinkedInCompanyPage.model_rebuild()
LinkedInSchoolPage.model_rebuild()
LinkedInJobSearchPage.model_rebuild()
