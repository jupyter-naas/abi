from __future__ import annotations

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

from naas_abi_marketplace.domains.intelligence.ontologies.organizations.ontologies.modules.OrganizationOntology import (
    Organization,
)
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
        try:
            return row[key]  # type: ignore[index]
        except Exception:
            pass

        labels = getattr(row, "labels", None)
        if labels and key in labels:
            try:
                return row[key]  # type: ignore[index]
            except Exception:
                pass

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


class ActOfPartnership(RDFEntity):
    """
    Act of Partnership
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ActOfPartnership"
    _name: ClassVar[str] = "Act of Partnership"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_alliance_participant": "http://ontology.naas.ai/abi/hasAllianceParticipant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_alliance_participant"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_alliance_participant: (
        Annotated[
            list[Organization | URIRef | str],
            Field(
                description="Relates an act of alliance to an organization taking part in it. An alliance has two or more participants, none of which loses its separate identity."
            ),
        ]
        | None
    ) = None


class ActOfJointVenture(RDFEntity):
    """
    Act of Joint Venture
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ActOfJointVenture"
    _name: ClassVar[str] = "Act of Joint Venture"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_alliance_participant": "http://ontology.naas.ai/abi/hasAllianceParticipant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_alliance_participant"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_alliance_participant: (
        Annotated[
            list[Organization | URIRef | str],
            Field(
                description="Relates an act of alliance to an organization taking part in it. An alliance has two or more participants, none of which loses its separate identity."
            ),
        ]
        | None
    ) = None


class ActOfMarketingAlliance(RDFEntity):
    """
    Act of Marketing Alliance
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ActOfMarketingAlliance"
    _name: ClassVar[str] = "Act of Marketing Alliance"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_alliance_participant": "http://ontology.naas.ai/abi/hasAllianceParticipant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_alliance_participant"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_alliance_participant: (
        Annotated[
            list[Organization | URIRef | str],
            Field(
                description="Relates an act of alliance to an organization taking part in it. An alliance has two or more participants, none of which loses its separate identity."
            ),
        ]
        | None
    ) = None


class ActOfResearchCollaboration(RDFEntity):
    """
    Research Collaborations represent formal partnerships focused on research and development activities.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ActOfResearchCollaboration"
    _name: ClassVar[str] = "Act of Research Collaboration"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_alliance_participant": "http://ontology.naas.ai/abi/hasAllianceParticipant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_alliance_participant"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_alliance_participant: (
        Annotated[
            list[Organization | URIRef | str],
            Field(
                description="Relates an act of alliance to an organization taking part in it. An alliance has two or more participants, none of which loses its separate identity."
            ),
        ]
        | None
    ) = None


class ActOfTechnologyLicensing(RDFEntity):
    """
    Act of Technology Licensing
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ActOfTechnologyLicensing"
    _name: ClassVar[str] = "Act of Technology Licensing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_alliance_participant": "http://ontology.naas.ai/abi/hasAllianceParticipant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_alliance_participant"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_alliance_participant: (
        Annotated[
            list[Organization | URIRef | str],
            Field(
                description="Relates an act of alliance to an organization taking part in it. An alliance has two or more participants, none of which loses its separate identity."
            ),
        ]
        | None
    ) = None


class ActOfDistributionAgreement(RDFEntity):
    """
    Act of Distribution Agreement
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ActOfDistributionAgreement"
    _name: ClassVar[str] = "Act of Distribution Agreement"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_alliance_participant": "http://ontology.naas.ai/abi/hasAllianceParticipant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_alliance_participant"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_alliance_participant: (
        Annotated[
            list[Organization | URIRef | str],
            Field(
                description="Relates an act of alliance to an organization taking part in it. An alliance has two or more participants, none of which loses its separate identity."
            ),
        ]
        | None
    ) = None


class StrategicAlliance(RDFEntity):
    """
    Strategic alliances are typically formalized through documents and agreements, making them apt to be represented as Descriptive Information Content Entities.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/StrategicAlliance"
    _name: ClassVar[str] = "Strategic Alliance"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_alliance_agreement_of": "http://ontology.naas.ai/abi/isAllianceAgreementOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_alliance_agreement_of"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_alliance_agreement_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates an alliance agreement document to the act of alliance it records."
            ),
        ]
        | None
    ) = None


class Partnership(StrategicAlliance, RDFEntity):
    """
    A partnership is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/Partnership"
    _name: ClassVar[str] = "Partnership"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_alliance_agreement_of": "http://ontology.naas.ai/abi/isAllianceAgreementOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_alliance_agreement_of"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_alliance_agreement_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates an alliance agreement document to the act of alliance it records."
            ),
        ]
        | None
    ) = None


class JointVenture(StrategicAlliance, RDFEntity):
    """
    A joint venture is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/JointVenture"
    _name: ClassVar[str] = "Joint Venture"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_alliance_agreement_of": "http://ontology.naas.ai/abi/isAllianceAgreementOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_alliance_agreement_of"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_alliance_agreement_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates an alliance agreement document to the act of alliance it records."
            ),
        ]
        | None
    ) = None


class MarketingAlliance(StrategicAlliance, RDFEntity):
    """
    A marketing alliance is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/MarketingAlliance"
    _name: ClassVar[str] = "Marketing Alliance"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_alliance_agreement_of": "http://ontology.naas.ai/abi/isAllianceAgreementOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_alliance_agreement_of"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_alliance_agreement_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates an alliance agreement document to the act of alliance it records."
            ),
        ]
        | None
    ) = None


class ResearchCollaboration(StrategicAlliance, RDFEntity):
    """
    A research collaboration is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ResearchCollaboration"
    _name: ClassVar[str] = "Research Collaboration"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_alliance_agreement_of": "http://ontology.naas.ai/abi/isAllianceAgreementOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_alliance_agreement_of"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_alliance_agreement_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates an alliance agreement document to the act of alliance it records."
            ),
        ]
        | None
    ) = None


class TechnologyLicensing(StrategicAlliance, RDFEntity):
    """
    A technology licensing is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/TechnologyLicensing"
    _name: ClassVar[str] = "Technology Licensing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_alliance_agreement_of": "http://ontology.naas.ai/abi/isAllianceAgreementOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_alliance_agreement_of"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_alliance_agreement_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates an alliance agreement document to the act of alliance it records."
            ),
        ]
        | None
    ) = None


class DistributionAgreement(StrategicAlliance, RDFEntity):
    """
    A distribution agreement is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/DistributionAgreement"
    _name: ClassVar[str] = "Distribution Agreement"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_alliance_agreement_of": "http://ontology.naas.ai/abi/isAllianceAgreementOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_alliance_agreement_of"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: Annotated[
        datetime.datetime | None,
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Any | None,
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_alliance_agreement_of: (
        Annotated[
            URIRef | str,
            Field(
                description="Relates an alliance agreement document to the act of alliance it records."
            ),
        ]
        | None
    ) = None


# Rebuild models to resolve forward references
ActOfPartnership.model_rebuild()
ActOfJointVenture.model_rebuild()
ActOfMarketingAlliance.model_rebuild()
ActOfResearchCollaboration.model_rebuild()
ActOfTechnologyLicensing.model_rebuild()
ActOfDistributionAgreement.model_rebuild()
StrategicAlliance.model_rebuild()
Partnership.model_rebuild()
JointVenture.model_rebuild()
MarketingAlliance.model_rebuild()
ResearchCollaboration.model_rebuild()
TechnologyLicensing.model_rebuild()
DistributionAgreement.model_rebuild()
