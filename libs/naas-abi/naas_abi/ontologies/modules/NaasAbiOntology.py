# onto2py-source-sha256: 0afce6f4e1b0a2d0d644b1e99a33b27af9ca9f4117e2f5c96b67a1821541f5ec
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


class ABIExecutionInterval(RDFEntity):
    """
    A one-dimensional temporal region occupied by an execution, distinct from its trigger or schedule description.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ExecutionInterval"
    _name: ClassVar[str] = "ABI execution interval"
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


class ABIExecutionRole(RDFEntity):
    """
    A role borne by a material participant and realised in carrying out a ledger process.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ExecutionRole"
    _name: ClassVar[str] = "ABI execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[ABIMaterialParticipant | URIRef | str], Field()] | None
    ) = None


class ABIProcessStep(RDFEntity):
    """
    A proposed temporal part of a ledger process; no execution occurrence is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ProcessStep"
    _name: ClassVar[str] = "ABI process step"
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


class S1PersonnelProcesses(RDFEntity):
    """
    A proposed process in the Personnel subsystem.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1Process"
    _name: ClassVar[str] = "S1 · Personnel processes"
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


class S2IntelligenceProcesses(RDFEntity):
    """
    A proposed process in the Intelligence subsystem.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2Process"
    _name: ClassVar[str] = "S2 · Intelligence processes"
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


class S3OperationsProcesses(RDFEntity):
    """
    A proposed process in the Operations subsystem.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3Process"
    _name: ClassVar[str] = "S3 · Operations processes"
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


class S4LogisticsProcesses(RDFEntity):
    """
    A proposed process in the Logistics subsystem.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4Process"
    _name: ClassVar[str] = "S4 · Logistics processes"
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


class S5PlansProcesses(RDFEntity):
    """
    A proposed process in the Plans subsystem.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5Process"
    _name: ClassVar[str] = "S5 · Plans processes"
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


class S6SignalProcesses(RDFEntity):
    """
    A proposed process in the Signal subsystem.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6Process"
    _name: ClassVar[str] = "S6 · Signal processes"
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


class S7TrainingProcesses(RDFEntity):
    """
    A proposed process in the Training subsystem.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7Process"
    _name: ClassVar[str] = "S7 · Training processes"
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


class S8FinanceProcesses(RDFEntity):
    """
    A proposed process in the Finance subsystem.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8Process"
    _name: ClassVar[str] = "S8 · Finance processes"
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


class S9ExternalAffairsProcesses(RDFEntity):
    """
    A proposed process in the External Affairs subsystem.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9Process"
    _name: ClassVar[str] = "S9 · External Affairs processes"
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


class AnalystRole(RDFEntity):
    """
    The role borne by the material participant described as 'Analyst'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AnalystRole"
    _name: ClassVar[str] = "Analyst role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[AnalystParticipant | URIRef | str], Field()] | None = (
        None
    )


class ApproverRole(RDFEntity):
    """
    The role borne by the material participant described as 'Approver'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ApproverRole"
    _name: ClassVar[str] = "Approver role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[ApproverParticipant | URIRef | str], Field()] | None = (
        None
    )


class AssessorRole(RDFEntity):
    """
    The role borne by the material participant described as 'Assessor'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AssessorRole"
    _name: ClassVar[str] = "Assessor role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[AssessorParticipant | URIRef | str], Field()] | None = (
        None
    )


class AssetOwnerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Asset owner'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AssetOwnerRole"
    _name: ClassVar[str] = "Asset owner role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[AssetOwnerParticipant | URIRef | str], Field()] | None
    ) = None


class AuditorRole(RDFEntity):
    """
    The role borne by the material participant described as 'Auditor'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AuditorRole"
    _name: ClassVar[str] = "Auditor role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[AuditorParticipant | URIRef | str], Field()] | None = (
        None
    )


class BudgetOwnerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Budget owner'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/BudgetOwnerRole"
    _name: ClassVar[str] = "Budget owner role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[BudgetOwnerParticipant | URIRef | str], Field()] | None
    ) = None


class CommsOfficerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Comms officer'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CommsOfficerRole"
    _name: ClassVar[str] = "Comms officer role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[CommsOfficerParticipant | URIRef | str], Field()] | None
    ) = None


class ContractManagerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Contract manager'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ContractManagerRole"
    _name: ClassVar[str] = "Contract manager role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[ContractManagerParticipant | URIRef | str], Field()] | None
    ) = None


class CyberTeamRole(RDFEntity):
    """
    The role borne by the material participant described as 'Cyber team'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CyberTeamRole"
    _name: ClassVar[str] = "Cyber team role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[CyberTeamParticipant | URIRef | str], Field()] | None
    ) = None


class DispatcherRole(RDFEntity):
    """
    The role borne by the material participant described as 'Dispatcher'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/DispatcherRole"
    _name: ClassVar[str] = "Dispatcher role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[DispatcherParticipant | URIRef | str], Field()] | None
    ) = None


class DriverRole(RDFEntity):
    """
    The role borne by the material participant described as 'Driver'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/DriverRole"
    _name: ClassVar[str] = "Driver role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[DriverParticipant | URIRef | str], Field()] | None = (
        None
    )


class ExecutivePrincipalRole(RDFEntity):
    """
    The role borne by the material participant described as 'Executive principal'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ExecutivePrincipalRole"
    _name: ClassVar[str] = "Executive principal role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[ExecutivePrincipalParticipant | URIRef | str], Field()] | None
    ) = None


class FieldTeamRole(RDFEntity):
    """
    The role borne by the material participant described as 'Field team'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/FieldTeamRole"
    _name: ClassVar[str] = "Field team role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[FieldTeamParticipant | URIRef | str], Field()] | None
    ) = None


class FinanceOfficerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Finance officer'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/FinanceOfficerRole"
    _name: ClassVar[str] = "Finance officer role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[FinanceOfficerParticipant | URIRef | str], Field()] | None
    ) = None


class FunctionLeadsRole(RDFEntity):
    """
    The role borne by the material participant described as 'Function leads'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/FunctionLeadsRole"
    _name: ClassVar[str] = "Function leads role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[FunctionLeadsParticipant | URIRef | str], Field()] | None
    ) = None


class HROfficerRole(RDFEntity):
    """
    The role borne by the material participant described as 'HR officer'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/HROfficerRole"
    _name: ClassVar[str] = "HR officer role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[HROfficerParticipant | URIRef | str], Field()] | None
    ) = None


class ITAdminRole(RDFEntity):
    """
    The role borne by the material participant described as 'IT admin'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ITAdminRole"
    _name: ClassVar[str] = "IT admin role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[ITAdminParticipant | URIRef | str], Field()] | None = (
        None
    )


class ITEngineerRole(RDFEntity):
    """
    The role borne by the material participant described as 'IT engineer'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ITEngineerRole"
    _name: ClassVar[str] = "IT engineer role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[ITEngineerParticipant | URIRef | str], Field()] | None
    ) = None


class LineManagerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Line manager'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/LineManagerRole"
    _name: ClassVar[str] = "Line manager role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[LineManagerParticipant | URIRef | str], Field()] | None
    ) = None


class LineManagersRole(RDFEntity):
    """
    The role borne by the material participant described as 'Line managers'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/LineManagersRole"
    _name: ClassVar[str] = "Line managers role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[LineManagersParticipant | URIRef | str], Field()] | None
    ) = None


class MaintenanceTeamRole(RDFEntity):
    """
    The role borne by the material participant described as 'Maintenance team'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/MaintenanceTeamRole"
    _name: ClassVar[str] = "Maintenance team role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[MaintenanceTeamParticipant | URIRef | str], Field()] | None
    ) = None


class NewJoinerRole(RDFEntity):
    """
    The role borne by the material participant described as 'New joiner'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/NewJoinerRole"
    _name: ClassVar[str] = "New joiner role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[NewJoinerParticipant | URIRef | str], Field()] | None
    ) = None


class OperationsLeadRole(RDFEntity):
    """
    The role borne by the material participant described as 'Operations lead'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/OperationsLeadRole"
    _name: ClassVar[str] = "Operations lead role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[OperationsLeadParticipant | URIRef | str], Field()] | None
    ) = None


class PartnerOrganisationRole(RDFEntity):
    """
    The role borne by the material participant described as 'Partner organisation'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PartnerOrganisationRole"
    _name: ClassVar[str] = "Partner organisation role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[PartnerOrganisationPersonnel | URIRef | str], Field()] | None
    ) = None


class PlannerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Planner'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PlannerRole"
    _name: ClassVar[str] = "Planner role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[PlannerParticipant | URIRef | str], Field()] | None = (
        None
    )


class ProcurementOfficerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Procurement officer'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ProcurementOfficerRole"
    _name: ClassVar[str] = "Procurement officer role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[ProcurementOfficerParticipant | URIRef | str], Field()] | None
    ) = None


class ProgrammeOwnerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Programme owner'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ProgrammeOwnerRole"
    _name: ClassVar[str] = "Programme owner role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[ProgrammeOwnerParticipant | URIRef | str], Field()] | None
    ) = None


class RequesterRole(RDFEntity):
    """
    The role borne by the material participant described as 'Requester'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/RequesterRole"
    _name: ClassVar[str] = "Requester role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[RequesterParticipant | URIRef | str], Field()] | None
    ) = None


class ResourceOwnersRole(RDFEntity):
    """
    The role borne by the material participant described as 'Resource owners'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ResourceOwnersRole"
    _name: ClassVar[str] = "Resource owners role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[ResourceOwnersParticipant | URIRef | str], Field()] | None
    ) = None


class ResponseTeamRole(RDFEntity):
    """
    The role borne by the material participant described as 'Response team'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ResponseTeamRole"
    _name: ClassVar[str] = "Response team role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[ResponseTeamParticipant | URIRef | str], Field()] | None
    ) = None


class RiskOwnerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Risk owner'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/RiskOwnerRole"
    _name: ClassVar[str] = "Risk owner role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[RiskOwnerParticipant | URIRef | str], Field()] | None
    ) = None


class S1LeadRole(RDFEntity):
    """
    The role borne by the material participant described as 'S1 lead'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1LeadRole"
    _name: ClassVar[str] = "S1 lead role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[S1LeadParticipant | URIRef | str], Field()] | None = (
        None
    )


class S2OfficerRole(RDFEntity):
    """
    The role borne by the material participant described as 'S2 officer'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2OfficerRole"
    _name: ClassVar[str] = "S2 officer role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[S2OfficerParticipant | URIRef | str], Field()] | None
    ) = None


class S3SchedulerRole(RDFEntity):
    """
    The role borne by the material participant described as 'S3 scheduler'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3SchedulerRole"
    _name: ClassVar[str] = "S3 scheduler role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[S3SchedulerParticipant | URIRef | str], Field()] | None
    ) = None


class S4ControllerRole(RDFEntity):
    """
    The role borne by the material participant described as 'S4 controller'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4ControllerRole"
    _name: ClassVar[str] = "S4 controller role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[S4ControllerParticipant | URIRef | str], Field()] | None
    ) = None


class S5LeadRole(RDFEntity):
    """
    The role borne by the material participant described as 'S5 lead'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5LeadRole"
    _name: ClassVar[str] = "S5 lead role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[S5LeadParticipant | URIRef | str], Field()] | None = (
        None
    )


class S5PlannerRole(RDFEntity):
    """
    The role borne by the material participant described as 'S5 planner'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5PlannerRole"
    _name: ClassVar[str] = "S5 planner role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[S5PlannerParticipant | URIRef | str], Field()] | None
    ) = None


class S7LeadRole(RDFEntity):
    """
    The role borne by the material participant described as 'S7 lead'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7LeadRole"
    _name: ClassVar[str] = "S7 lead role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[S7LeadParticipant | URIRef | str], Field()] | None = (
        None
    )


class S8ApproverRole(RDFEntity):
    """
    The role borne by the material participant described as 'S8 approver'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8ApproverRole"
    _name: ClassVar[str] = "S8 approver role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[S8ApproverParticipant | URIRef | str], Field()] | None
    ) = None


class S9LeadRole(RDFEntity):
    """
    The role borne by the material participant described as 'S9 lead'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9LeadRole"
    _name: ClassVar[str] = "S9 lead role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[S9LeadParticipant | URIRef | str], Field()] | None = (
        None
    )


class S9OfficerRole(RDFEntity):
    """
    The role borne by the material participant described as 'S9 officer'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9OfficerRole"
    _name: ClassVar[str] = "S9 officer role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[S9OfficerParticipant | URIRef | str], Field()] | None
    ) = None


class SecurityOfficerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Security officer'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SecurityOfficerRole"
    _name: ClassVar[str] = "Security officer role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[SecurityOfficerParticipant | URIRef | str], Field()] | None
    ) = None


class SecurityRole(RDFEntity):
    """
    The role borne by the material participant described as 'Security'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SecurityRole"
    _name: ClassVar[str] = "Security role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[SecurityParticipant | URIRef | str], Field()] | None = (
        None
    )


class StaffMemberRole(RDFEntity):
    """
    The role borne by the material participant described as 'Staff member'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/StaffMemberRole"
    _name: ClassVar[str] = "Staff member role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[StaffMemberParticipant | URIRef | str], Field()] | None
    ) = None


class StaffRole(RDFEntity):
    """
    The role borne by the material participant described as 'Staff'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/StaffRole"
    _name: ClassVar[str] = "Staff role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[StaffParticipant | URIRef | str], Field()] | None = None


class StakeholderRole(RDFEntity):
    """
    The role borne by the material participant described as 'Stakeholder'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/StakeholderRole"
    _name: ClassVar[str] = "Stakeholder role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[StakeholderParticipant | URIRef | str], Field()] | None
    ) = None


class StoreKeeperRole(RDFEntity):
    """
    The role borne by the material participant described as 'Store keeper'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/StoreKeeperRole"
    _name: ClassVar[str] = "Store keeper role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[StoreKeeperParticipant | URIRef | str], Field()] | None
    ) = None


class SubjectRole(RDFEntity):
    """
    The role borne by the material participant described as 'Subject'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SubjectRole"
    _name: ClassVar[str] = "Subject role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[SubjectParticipant | URIRef | str], Field()] | None = (
        None
    )


class SupplierRole(RDFEntity):
    """
    The role borne by the material participant described as 'Supplier'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SupplierRole"
    _name: ClassVar[str] = "Supplier role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[SupplierPersonnel | URIRef | str], Field()] | None = (
        None
    )


class TraineeRole(RDFEntity):
    """
    The role borne by the material participant described as 'Trainee'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/TraineeRole"
    _name: ClassVar[str] = "Trainee role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[TraineeParticipant | URIRef | str], Field()] | None = (
        None
    )


class TrainerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Trainer'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/TrainerRole"
    _name: ClassVar[str] = "Trainer role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[TrainerParticipant | URIRef | str], Field()] | None = (
        None
    )


class VendorRole(RDFEntity):
    """
    The role borne by the material participant described as 'Vendor'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/VendorRole"
    _name: ClassVar[str] = "Vendor role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: Annotated[list[URIRef | VendorPersonnel | str], Field()] | None = None


class WatchOfficerRole(RDFEntity):
    """
    The role borne by the material participant described as 'Watch officer'.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/WatchOfficerRole"
    _name: ClassVar[str] = "Watch officer role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[list[URIRef | WatchOfficerParticipant | str], Field()] | None
    ) = None


class ABIExecutionSite(RDFEntity):
    """
    A physical site at which a proposed ledger process occurs.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ExecutionSite"
    _name: ClassVar[str] = "ABI execution site"
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


class ABIMaterialParticipant(RDFEntity):
    """
    A person, physical group or physical system participating in a proposed ABI process.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/MaterialParticipant"
    _name: ClassVar[str] = "ABI material participant"
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


class ABIInformationArtifact(RDFEntity):
    """
    Recorded information associated with a ledger process, distinct from the physical medium carrying it.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/InformationArtifact"
    _name: ClassVar[str] = "ABI information artifact"
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


class ABIAISystem(RDFEntity):
    """
    A process type proposed in the simulated ABI ledger. Select a child process to inspect its participants, steps, places, timing, roles and evidence. Draft — simulated ledger hypothesis; not validated with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/LedgerProcess"
    _name: ClassVar[str] = "ABI AI System"
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


class AirgappedZone(ABIExecutionSite, RDFEntity):
    """
    A physical site described as 'Air-gapped zone' in the ledger; no concrete location is identified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AirGappedZoneSite"
    _name: ClassVar[str] = "Air-gapped zone"
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


class PhysicalITInfrastructure(ABIMaterialParticipant, RDFEntity):
    """
    Material IT infrastructure participating in provisioning and cyber activities.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/Infrastructure"
    _name: ClassVar[str] = "Physical IT infrastructure"
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


class OSINTSources(ABIInformationArtifact, RDFEntity):
    """
    Open-source intelligence information listed as WHO in the ledger; treated as information used, not a material actor.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/OSINTSourceInformation"
    _name: ClassVar[str] = "OSINT sources"
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


class OnpremisesDataCentre(ABIExecutionSite, RDFEntity):
    """
    A physical site described as 'On-premises data centre' in the ledger; no concrete location is identified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/OnPremisesDataCentreSite"
    _name: ClassVar[str] = "On-premises data centre"
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


class OperationsCentre(ABIExecutionSite, RDFEntity):
    """
    A physical site described as 'Operations centre' in the ledger; no concrete location is identified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/OperationsCentreSite"
    _name: ClassVar[str] = "Operations centre"
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


class ABIProcessSpecification(ABIInformationArtifact, RDFEntity):
    """
    The simulated specification describing a proposed process and its steps.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ProcessSpecification"
    _name: ClassVar[str] = "ABI process specification"
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


class SitesAcrossTheEstate(ABIExecutionSite, RDFEntity):
    """
    A physical site described as 'Sites across the estate' in the ledger; no concrete location is identified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SitesAcrossTheEstateSite"
    _name: ClassVar[str] = "Sites across the estate"
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


class Sites(ABIExecutionSite, RDFEntity):
    """
    A physical site described as 'Sites' in the ledger; no concrete location is identified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SitesSite"
    _name: ClassVar[str] = "Sites"
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


class Stores(ABIExecutionSite, RDFEntity):
    """
    A physical site described as 'Stores' in the ledger; no concrete location is identified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/StoresSite"
    _name: ClassVar[str] = "Stores"
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


class ABIExecutionCondition(ABIInformationArtifact, RDFEntity):
    """
    A trigger, cadence or timing target stated in WHEN; it is not an actual time interval or an achieved service level.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ExecutionCondition"
    _name: ClassVar[str] = "ABI execution condition"
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


class ABIObjectiveSpecification(ABIInformationArtifact, RDFEntity):
    """
    An intended outcome stated in WHY. An objective is information, distinct from the role realised in pursuing it.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ObjectiveSpecification"
    _name: ClassVar[str] = "ABI objective specification"
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


class StakeholderParticipant(ABIMaterialParticipant, RDFEntity):
    """
    The material participant referred to as 'Stakeholder' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/StakeholderParticipant"
    _name: ClassVar[str] = "Stakeholder participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[StakeholderRole | URIRef | str], Field()] | None = None


class SubjectParticipant(ABIMaterialParticipant, RDFEntity):
    """
    The material participant referred to as 'Subject' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SubjectParticipant"
    _name: ClassVar[str] = "Subject participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[SubjectRole | URIRef | str], Field()] | None = None


class ABIPhysicalTeam(ABIMaterialParticipant, RDFEntity):
    """
    The aggregate of people performing a team activity, distinct from an organisation's legal identity.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PhysicalTeam"
    _name: ClassVar[str] = "ABI physical team"
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


class ABIPhysicalComputingSystem(ABIMaterialParticipant, RDFEntity):
    """
    Physical computing equipment carrying the software used in a ledger process. The ledger names software, not particular machines.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ComputingSystem"
    _name: ClassVar[str] = "ABI physical computing system"
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


class ABISoftware(ABIInformationArtifact, RDFEntity):
    """
    Software content, distinct from the material computer on which it executes.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/Software"
    _name: ClassVar[str] = "ABI software"
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


class ABIHumanParticipant(ABIMaterialParticipant, RDFEntity):
    """
    A person participating in a proposed ABI process.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/HumanParticipant"
    _name: ClassVar[str] = "ABI human participant"
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


class ABIEvidenceRecord(ABIInformationArtifact, RDFEntity):
    """
    A kind of record listed in HOW WE KNOW; its existence, production direction and factual accuracy have not been validated.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/EvidenceRecord"
    _name: ClassVar[str] = "ABI evidence record"
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


class ABIIndicatorRecord(ABIInformationArtifact, RDFEntity):
    """
    Recorded status, score or measure listed under HOW IT IS. This record is not itself a BFO quality.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/IndicatorRecord"
    _name: ClassVar[str] = "ABI indicator record"
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


class OnboardingExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Onboarding and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P1ExecutionRole"
    _name: ClassVar[str] = "Onboarding execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                HROfficerParticipant
                | HRSystemPhysicalHost
                | NewJoinerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class OnboardingExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Onboarding; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P1Interval"
    _name: ClassVar[str] = "Onboarding execution interval"
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


class OnboardingCreateStaffRecord(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Onboarding: Create staff record. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P1Step1"
    _name: ClassVar[str] = "Onboarding · Create staff record"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Onboarding | URIRef | str], Field()] | None = None


class OnboardingAssignRole(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Onboarding: Assign role. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P1Step2"
    _name: ClassVar[str] = "Onboarding · Assign role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Onboarding | URIRef | str], Field()] | None = None


class OnboardingGrantAccess(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Onboarding: Grant access. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P1Step3"
    _name: ClassVar[str] = "Onboarding · Grant access"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Onboarding | URIRef | str], Field()] | None = None


class Onboarding(ABIAISystem, S1PersonnelProcesses, RDFEntity):
    """
    A proposed ABI onboarding process. Suggested steps: Create staff record → Assign role → Grant access. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P1"
    _name: ClassVar[str] = "Onboarding"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[OnboardingExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                HROfficerParticipant
                | HRSystemPhysicalHost
                | NewJoinerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[OnboardingSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                OnboardingAssignRole
                | OnboardingCreateStaffRecord
                | OnboardingGrantAccess
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[OnboardingExecutionInterval | URIRef | str], Field()] | None
    ) = None
    documented_by: (
        Annotated[
            list[AccessRegister | HRRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[OnboardingTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[AccessLevelRecord | OnboardingStatusRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[OnboardingObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[HRSystemSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class AccessProvisioningExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Access provisioning and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P2ExecutionRole"
    _name: ClassVar[str] = "Access provisioning execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                HROfficerParticipant
                | ITAdminParticipant
                | IdentitySystemPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class AccessProvisioningExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Access provisioning; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P2Interval"
    _name: ClassVar[str] = "Access provisioning execution interval"
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


class AccessProvisioningRequestAccess(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Access provisioning: Request access. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P2Step1"
    _name: ClassVar[str] = "Access provisioning · Request access"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[AccessProvisioning | URIRef | str], Field()] | None = (
        None
    )


class AccessProvisioningApprove(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Access provisioning: Approve. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P2Step2"
    _name: ClassVar[str] = "Access provisioning · Approve"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[AccessProvisioning | URIRef | str], Field()] | None = (
        None
    )


class AccessProvisioningProvisionLog(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Access provisioning: Provision & log. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P2Step3"
    _name: ClassVar[str] = "Access provisioning · Provision & log"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[AccessProvisioning | URIRef | str], Field()] | None = (
        None
    )


class AccessProvisioning(ABIAISystem, S1PersonnelProcesses, RDFEntity):
    """
    A proposed ABI access provisioning process. Suggested steps: Request access → Approve → Provision & log. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P2"
    _name: ClassVar[str] = "Access provisioning"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[AccessProvisioningExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                HROfficerParticipant
                | ITAdminParticipant
                | IdentitySystemPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[AccessProvisioningSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[ABIExecutionSite | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                AccessProvisioningApprove
                | AccessProvisioningProvisionLog
                | AccessProvisioningRequestAccess
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[AccessProvisioningExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AccessRequestRecord | AuditTrail | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[AccessProvisioningTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[AccessStatusRecord | LeastprivilegeComplianceRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[AccessProvisioningObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[IdentitySystemSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class RotationPlanningExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Rotation planning and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P3ExecutionRole"
    _name: ClassVar[str] = "Rotation planning execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                LineManagersParticipant
                | PlanningSystemPhysicalHost
                | S1LeadParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class RotationPlanningExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Rotation planning; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P3Interval"
    _name: ClassVar[str] = "Rotation planning execution interval"
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


class RotationPlanningForecastNeeds(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Rotation planning: Forecast needs. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P3Step1"
    _name: ClassVar[str] = "Rotation planning · Forecast needs"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[RotationPlanning | URIRef | str], Field()] | None = None


class RotationPlanningDraftRota(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Rotation planning: Draft rota. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P3Step2"
    _name: ClassVar[str] = "Rotation planning · Draft rota"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[RotationPlanning | URIRef | str], Field()] | None = None


class RotationPlanningPublish(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Rotation planning: Publish. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P3Step3"
    _name: ClassVar[str] = "Rotation planning · Publish"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[RotationPlanning | URIRef | str], Field()] | None = None


class RotationPlanning(ABIAISystem, S1PersonnelProcesses, RDFEntity):
    """
    A proposed ABI rotation planning process. Suggested steps: Forecast needs → Draft rota → Publish. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P3"
    _name: ClassVar[str] = "Rotation planning"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[RotationPlanningExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                LineManagersParticipant
                | PlanningSystemPhysicalHost
                | S1LeadParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[RotationPlanningSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                RotationPlanningDraftRota
                | RotationPlanningForecastNeeds
                | RotationPlanningPublish
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[RotationPlanningExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AttendanceRecord | RotationPlan | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[RotationPlanningTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[CoverageRatioRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[RotationPlanningObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[PlanningSystemSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class AttendanceAndLeaveExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Attendance and leave and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P4ExecutionRole"
    _name: ClassVar[str] = "Attendance and leave execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                HRSystemPhysicalHost
                | LineManagerParticipant
                | StaffMemberParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class AttendanceAndLeaveExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Attendance and leave; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P4Interval"
    _name: ClassVar[str] = "Attendance and leave execution interval"
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


class AttendanceAndLeaveRecordAttendance(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Attendance and leave: Record attendance. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P4Step1"
    _name: ClassVar[str] = "Attendance and leave · Record attendance"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[AttendanceAndLeave | URIRef | str], Field()] | None = (
        None
    )


class AttendanceAndLeaveRequestLeave(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Attendance and leave: Request leave. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P4Step2"
    _name: ClassVar[str] = "Attendance and leave · Request leave"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[AttendanceAndLeave | URIRef | str], Field()] | None = (
        None
    )


class AttendanceAndLeaveApprove(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Attendance and leave: Approve. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P4Step3"
    _name: ClassVar[str] = "Attendance and leave · Approve"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[AttendanceAndLeave | URIRef | str], Field()] | None = (
        None
    )


class AttendanceAndLeave(ABIAISystem, S1PersonnelProcesses, RDFEntity):
    """
    A proposed ABI attendance and leave process. Suggested steps: Record attendance → Request leave → Approve. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P4"
    _name: ClassVar[str] = "Attendance and leave"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[AttendanceAndLeaveExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                HRSystemPhysicalHost
                | LineManagerParticipant
                | StaffMemberParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[AttendanceAndLeaveSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                AttendanceAndLeaveApprove
                | AttendanceAndLeaveRecordAttendance
                | AttendanceAndLeaveRequestLeave
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[AttendanceAndLeaveExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AttendanceLog | LeaveRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[AttendanceAndLeaveTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[AttendanceStatusRecord | SLAOnApprovalRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[AttendanceAndLeaveObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[HRSystemSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class OffboardingExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Offboarding and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P5ExecutionRole"
    _name: ClassVar[str] = "Offboarding execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                HROfficerParticipant
                | ITAdminParticipant
                | SecurityParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class OffboardingExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Offboarding; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P5Interval"
    _name: ClassVar[str] = "Offboarding execution interval"
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


class OffboardingRevokeAccess(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Offboarding: Revoke access. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P5Step1"
    _name: ClassVar[str] = "Offboarding · Revoke access"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Offboarding | URIRef | str], Field()] | None = None


class OffboardingReturnAssets(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Offboarding: Return assets. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P5Step2"
    _name: ClassVar[str] = "Offboarding · Return assets"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Offboarding | URIRef | str], Field()] | None = None


class OffboardingCloseRecord(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Offboarding: Close record. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P5Step3"
    _name: ClassVar[str] = "Offboarding · Close record"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Offboarding | URIRef | str], Field()] | None = None


class Offboarding(ABIAISystem, S1PersonnelProcesses, RDFEntity):
    """
    A proposed ABI offboarding process. Suggested steps: Revoke access → Return assets → Close record. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P5"
    _name: ClassVar[str] = "Offboarding"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
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
    bFO_0000055: (
        Annotated[list[OffboardingExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                HROfficerParticipant
                | ITAdminParticipant
                | SecurityParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[OffboardingSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: (
        Annotated[list[ABIExecutionSite | OnpremisesDataCentre | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                OffboardingCloseRecord
                | OffboardingReturnAssets
                | OffboardingRevokeAccess
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[OffboardingExecutionInterval | URIRef | str], Field()] | None
    ) = None
    documented_by: (
        Annotated[
            list[AccessRevocationLog | OffboardingChecklist | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[OffboardingTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[AccessrevokedStatusRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[OffboardingObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None


class ExecutiveBriefingExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Executive briefing and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P1ExecutionRole"
    _name: ClassVar[str] = "Executive briefing execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                AINAgentsPhysicalHost
                | ExecutivePrincipalParticipant
                | S2OfficerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class ExecutiveBriefingExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Executive briefing; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P1Interval"
    _name: ClassVar[str] = "Executive briefing execution interval"
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


class ExecutiveBriefingGatherInputs(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Executive briefing: Gather inputs. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P1Step1"
    _name: ClassVar[str] = "Executive briefing · Gather inputs"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[ExecutiveBriefing | URIRef | str], Field()] | None = (
        None
    )


class ExecutiveBriefingSynthesise(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Executive briefing: Synthesise. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P1Step2"
    _name: ClassVar[str] = "Executive briefing · Synthesise"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[ExecutiveBriefing | URIRef | str], Field()] | None = (
        None
    )


class ExecutiveBriefingDeliverBriefing(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Executive briefing: Deliver briefing. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P1Step3"
    _name: ClassVar[str] = "Executive briefing · Deliver briefing"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[ExecutiveBriefing | URIRef | str], Field()] | None = (
        None
    )


class ExecutiveBriefing(ABIAISystem, S2IntelligenceProcesses, RDFEntity):
    """
    A proposed ABI executive briefing process. Suggested steps: Gather inputs → Synthesise → Deliver briefing. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P1"
    _name: ClassVar[str] = "Executive briefing"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[ExecutiveBriefingExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                AINAgentsPhysicalHost
                | ExecutivePrincipalParticipant
                | S2OfficerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[ExecutiveBriefingSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: (
        Annotated[list[AirgappedZone | OperationsCentre | URIRef | str], Field()] | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                ExecutiveBriefingDeliverBriefing
                | ExecutiveBriefingGatherInputs
                | ExecutiveBriefingSynthesise
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[ExecutiveBriefingExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[BriefingNote | DecisionLog | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[ExecutiveBriefingTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[ConfidenceScoreRecord | TimelinessRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[ExecutiveBriefingObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[AINAgentsSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class SignalSynthesisExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Signal synthesis and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P2ExecutionRole"
    _name: ClassVar[str] = "Signal synthesis execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[AINIntelligenceAgentPhysicalHost | AnalystParticipant | URIRef | str],
            Field(),
        ]
        | None
    ) = None


class SignalSynthesisExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Signal synthesis; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P2Interval"
    _name: ClassVar[str] = "Signal synthesis execution interval"
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


class SignalSynthesisIngestSources(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Signal synthesis: Ingest sources. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P2Step1"
    _name: ClassVar[str] = "Signal synthesis · Ingest sources"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[SignalSynthesis | URIRef | str], Field()] | None = None


class SignalSynthesisCorrelate(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Signal synthesis: Correlate. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P2Step2"
    _name: ClassVar[str] = "Signal synthesis · Correlate"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[SignalSynthesis | URIRef | str], Field()] | None = None


class SignalSynthesisFlagSignals(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Signal synthesis: Flag signals. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P2Step3"
    _name: ClassVar[str] = "Signal synthesis · Flag signals"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[SignalSynthesis | URIRef | str], Field()] | None = None


class SignalSynthesis(ABIAISystem, S2IntelligenceProcesses, RDFEntity):
    """
    A proposed ABI signal synthesis process. Suggested steps: Ingest sources → Correlate → Flag signals. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P2"
    _name: ClassVar[str] = "Signal synthesis"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[SignalSynthesisExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[AINIntelligenceAgentPhysicalHost | AnalystParticipant | URIRef | str],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[SignalSynthesisSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[AirgappedZone | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                SignalSynthesisCorrelate
                | SignalSynthesisFlagSignals
                | SignalSynthesisIngestSources
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[SignalSynthesisExecutionInterval | URIRef | str], Field()] | None
    ) = None
    documented_by: (
        Annotated[
            list[SignalRecord | SourceChain | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[SignalSynthesisTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[ConfidenceScoreRecord | CoverageRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[SignalSynthesisObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[AINIntelligenceAgentSoftware | OSINTSources | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class RiskAndContextAssessmentExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Risk and context assessment and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P3ExecutionRole"
    _name: ClassVar[str] = "Risk and context assessment execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                AINPredictiveAgentPhysicalHost
                | AnalystParticipant
                | RiskOwnerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class RiskAndContextAssessmentExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Risk and context assessment; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P3Interval"
    _name: ClassVar[str] = "Risk and context assessment execution interval"
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


class RiskAndContextAssessmentFrameQuestion(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Risk and context assessment: Frame question. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P3Step1"
    _name: ClassVar[str] = "Risk and context assessment · Frame question"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[RiskAndContextAssessment | URIRef | str], Field()] | None
    ) = None


class RiskAndContextAssessmentAssess(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Risk and context assessment: Assess. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P3Step2"
    _name: ClassVar[str] = "Risk and context assessment · Assess"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[RiskAndContextAssessment | URIRef | str], Field()] | None
    ) = None


class RiskAndContextAssessmentScore(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Risk and context assessment: Score. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P3Step3"
    _name: ClassVar[str] = "Risk and context assessment · Score"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[RiskAndContextAssessment | URIRef | str], Field()] | None
    ) = None


class RiskAndContextAssessment(ABIAISystem, S2IntelligenceProcesses, RDFEntity):
    """
    A proposed ABI risk and context assessment process. Suggested steps: Frame question → Assess → Score. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P3"
    _name: ClassVar[str] = "Risk and context assessment"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[RiskAndContextAssessmentExecutionRole | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                AINPredictiveAgentPhysicalHost
                | AnalystParticipant
                | RiskOwnerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[RiskAndContextAssessmentSpecification | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                RiskAndContextAssessmentAssess
                | RiskAndContextAssessmentFrameQuestion
                | RiskAndContextAssessmentScore
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[
            list[RiskAndContextAssessmentExecutionInterval | URIRef | str], Field()
        ]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AssessmentReport | EvidenceRegister | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[RiskAndContextAssessmentTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[AssessmentCompletenessRecord | RiskScoreRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[RiskAndContextAssessmentObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[AINPredictiveAgentSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class SecurityScreeningExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Security screening and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P4ExecutionRole"
    _name: ClassVar[str] = "Security screening execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                ScreeningSystemPhysicalHost
                | SecurityOfficerParticipant
                | SubjectParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class SecurityScreeningExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Security screening; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P4Interval"
    _name: ClassVar[str] = "Security screening execution interval"
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


class SecurityScreeningReceiveRequest(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Security screening: Receive request. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P4Step1"
    _name: ClassVar[str] = "Security screening · Receive request"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[SecurityScreening | URIRef | str], Field()] | None = (
        None
    )


class SecurityScreeningScreen(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Security screening: Screen. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P4Step2"
    _name: ClassVar[str] = "Security screening · Screen"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[SecurityScreening | URIRef | str], Field()] | None = (
        None
    )


class SecurityScreeningClearOrRefer(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Security screening: Clear or refer. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P4Step3"
    _name: ClassVar[str] = "Security screening · Clear or refer"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[SecurityScreening | URIRef | str], Field()] | None = (
        None
    )


class SecurityScreening(ABIAISystem, S2IntelligenceProcesses, RDFEntity):
    """
    A proposed ABI security screening process. Suggested steps: Receive request → Screen → Clear or refer. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P4"
    _name: ClassVar[str] = "Security screening"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[SecurityScreeningExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                ScreeningSystemPhysicalHost
                | SecurityOfficerParticipant
                | SubjectParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[SecurityScreeningSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[ABIExecutionSite | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                SecurityScreeningClearOrRefer
                | SecurityScreeningReceiveRequest
                | SecurityScreeningScreen
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[SecurityScreeningExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AuditTrail | ScreeningRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[SecurityScreeningTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[ClearanceStatusRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[SecurityScreeningObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[ScreeningSystemSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class WatchAndAlertingExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Watch and alerting and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P5ExecutionRole"
    _name: ClassVar[str] = "Watch and alerting execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                AINGapdetectionAgentPhysicalHost
                | URIRef
                | WatchOfficerParticipant
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class WatchAndAlertingExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Watch and alerting; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P5Interval"
    _name: ClassVar[str] = "Watch and alerting execution interval"
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


class WatchAndAlertingSetThresholds(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Watch and alerting: Set thresholds. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P5Step1"
    _name: ClassVar[str] = "Watch and alerting · Set thresholds"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[URIRef | WatchAndAlerting | str], Field()] | None = None


class WatchAndAlertingMonitor(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Watch and alerting: Monitor. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P5Step2"
    _name: ClassVar[str] = "Watch and alerting · Monitor"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[URIRef | WatchAndAlerting | str], Field()] | None = None


class WatchAndAlertingRaiseAlert(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Watch and alerting: Raise alert. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P5Step3"
    _name: ClassVar[str] = "Watch and alerting · Raise alert"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[URIRef | WatchAndAlerting | str], Field()] | None = None


class WatchAndAlerting(ABIAISystem, S2IntelligenceProcesses, RDFEntity):
    """
    A proposed ABI watch and alerting process. Suggested steps: Set thresholds → Monitor → Raise alert. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P5"
    _name: ClassVar[str] = "Watch and alerting"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[URIRef | WatchAndAlertingExecutionRole | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                AINGapdetectionAgentPhysicalHost
                | URIRef
                | WatchOfficerParticipant
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[URIRef | WatchAndAlertingSpecification | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[AirgappedZone | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                URIRef
                | WatchAndAlertingMonitor
                | WatchAndAlertingRaiseAlert
                | WatchAndAlertingSetThresholds
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[URIRef | WatchAndAlertingExecutionInterval | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AlertFeed | ReasoningChain | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[URIRef | WatchAndAlertingTimingCondition | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[AlertLatencyRecord | FalsepositiveRateRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[URIRef | WatchAndAlertingObjective | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[AINGapdetectionAgentSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class WorkorderProcessingExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Work-order processing and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P1ExecutionRole"
    _name: ClassVar[str] = "Work-order processing execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                FieldTeamParticipant
                | OperationsLeadParticipant
                | OracleERPPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class WorkorderProcessingExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Work-order processing; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P1Interval"
    _name: ClassVar[str] = "Work-order processing execution interval"
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


class WorkorderProcessingRaiseWorkOrder(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Work-order processing: Raise work order. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P1Step1"
    _name: ClassVar[str] = "Work-order processing · Raise work order"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[URIRef | WorkorderProcessing | str], Field()] | None = (
        None
    )


class WorkorderProcessingRoute(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Work-order processing: Route. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P1Step2"
    _name: ClassVar[str] = "Work-order processing · Route"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[URIRef | WorkorderProcessing | str], Field()] | None = (
        None
    )


class WorkorderProcessingExecuteClose(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Work-order processing: Execute & close. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P1Step3"
    _name: ClassVar[str] = "Work-order processing · Execute & close"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[URIRef | WorkorderProcessing | str], Field()] | None = (
        None
    )


class WorkorderProcessing(ABIAISystem, S3OperationsProcesses, RDFEntity):
    """
    A proposed ABI work-order processing process. Suggested steps: Raise work order → Route → Execute & close. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P1"
    _name: ClassVar[str] = "Work-order processing"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[URIRef | WorkorderProcessingExecutionRole | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                FieldTeamParticipant
                | OperationsLeadParticipant
                | OracleERPPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[URIRef | WorkorderProcessingSpecification | str], Field()] | None
    ) = None
    bFO_0000066: (
        Annotated[list[OnpremisesDataCentre | OperationsCentre | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                URIRef
                | WorkorderProcessingExecuteClose
                | WorkorderProcessingRaiseWorkOrder
                | WorkorderProcessingRoute
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[URIRef | WorkorderProcessingExecutionInterval | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AssetRegistryUpdate | URIRef | WorkorderRecord | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[URIRef | WorkorderProcessingTimingCondition | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[OrderStatusRecord | SLAAdherenceRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[URIRef | WorkorderProcessingObjective | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[OracleERPSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class SchedulingExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Scheduling and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P2ExecutionRole"
    _name: ClassVar[str] = "Scheduling execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                ResourceOwnersParticipant
                | S3SchedulerParticipant
                | SchedulingSystemPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class SchedulingExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Scheduling; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P2Interval"
    _name: ClassVar[str] = "Scheduling execution interval"
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


class SchedulingCollectDemand(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Scheduling: Collect demand. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P2Step1"
    _name: ClassVar[str] = "Scheduling · Collect demand"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Scheduling | URIRef | str], Field()] | None = None


class SchedulingOptimise(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Scheduling: Optimise. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P2Step2"
    _name: ClassVar[str] = "Scheduling · Optimise"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Scheduling | URIRef | str], Field()] | None = None


class SchedulingPublishSchedule(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Scheduling: Publish schedule. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P2Step3"
    _name: ClassVar[str] = "Scheduling · Publish schedule"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Scheduling | URIRef | str], Field()] | None = None


class Scheduling(ABIAISystem, S3OperationsProcesses, RDFEntity):
    """
    A proposed ABI scheduling process. Suggested steps: Collect demand → Optimise → Publish schedule. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P2"
    _name: ClassVar[str] = "Scheduling"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[SchedulingExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                ResourceOwnersParticipant
                | S3SchedulerParticipant
                | SchedulingSystemPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[SchedulingSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                SchedulingCollectDemand
                | SchedulingOptimise
                | SchedulingPublishSchedule
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[SchedulingExecutionInterval | URIRef | str], Field()] | None
    ) = None
    documented_by: (
        Annotated[
            list[DecisionLog | ScheduleRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[SchedulingTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[ScheduleFillRateRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[SchedulingObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[SchedulingSystemSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class FleetDispatchExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Fleet dispatch and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P3ExecutionRole"
    _name: ClassVar[str] = "Fleet dispatch execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                DispatcherParticipant
                | DriverParticipant
                | FleetSystemPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class FleetDispatchExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Fleet dispatch; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P3Interval"
    _name: ClassVar[str] = "Fleet dispatch execution interval"
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


class FleetDispatchReceiveRequest(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Fleet dispatch: Receive request. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P3Step1"
    _name: ClassVar[str] = "Fleet dispatch · Receive request"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[FleetDispatch | URIRef | str], Field()] | None = None


class FleetDispatchAssignVehicle(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Fleet dispatch: Assign vehicle. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P3Step2"
    _name: ClassVar[str] = "Fleet dispatch · Assign vehicle"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[FleetDispatch | URIRef | str], Field()] | None = None


class FleetDispatchDispatchTrack(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Fleet dispatch: Dispatch & track. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P3Step3"
    _name: ClassVar[str] = "Fleet dispatch · Dispatch & track"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[FleetDispatch | URIRef | str], Field()] | None = None


class FleetDispatch(ABIAISystem, S3OperationsProcesses, RDFEntity):
    """
    A proposed ABI fleet dispatch process. Suggested steps: Receive request → Assign vehicle → Dispatch & track. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P3"
    _name: ClassVar[str] = "Fleet dispatch"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[FleetDispatchExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                DispatcherParticipant
                | DriverParticipant
                | FleetSystemPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[FleetDispatchSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: (
        Annotated[list[OperationsCentre | SitesAcrossTheEstate | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                FleetDispatchAssignVehicle
                | FleetDispatchDispatchTrack
                | FleetDispatchReceiveRequest
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[FleetDispatchExecutionInterval | URIRef | str], Field()] | None
    ) = None
    documented_by: (
        Annotated[
            list[DispatchRecord | TripLog | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[FleetDispatchTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[OntimeRateRecord | URIRef | VehicleStatusRecord | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[FleetDispatchObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[FleetSystemSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class MaintenanceExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Maintenance and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P4ExecutionRole"
    _name: ClassVar[str] = "Maintenance execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                AssetOwnerParticipant
                | MaintenanceTeamParticipant
                | OracleERPPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class MaintenanceExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Maintenance; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P4Interval"
    _name: ClassVar[str] = "Maintenance execution interval"
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


class MaintenanceDetectNeed(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Maintenance: Detect need. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P4Step1"
    _name: ClassVar[str] = "Maintenance · Detect need"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Maintenance | URIRef | str], Field()] | None = None


class MaintenancePlan(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Maintenance: Plan. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P4Step2"
    _name: ClassVar[str] = "Maintenance · Plan"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Maintenance | URIRef | str], Field()] | None = None


class MaintenanceExecuteVerify(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Maintenance: Execute & verify. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P4Step3"
    _name: ClassVar[str] = "Maintenance · Execute & verify"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Maintenance | URIRef | str], Field()] | None = None


class Maintenance(ABIAISystem, S3OperationsProcesses, RDFEntity):
    """
    A proposed ABI maintenance process. Suggested steps: Detect need → Plan → Execute & verify. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P4"
    _name: ClassVar[str] = "Maintenance"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[MaintenanceExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                AssetOwnerParticipant
                | MaintenanceTeamParticipant
                | OracleERPPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[MaintenanceSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: (
        Annotated[list[OnpremisesDataCentre | Sites | URIRef | str], Field()] | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                MaintenanceDetectNeed
                | MaintenanceExecuteVerify
                | MaintenancePlan
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[MaintenanceExecutionInterval | URIRef | str], Field()] | None
    ) = None
    documented_by: (
        Annotated[
            list[AssetRegistry | MaintenanceRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[MaintenanceTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[AssetConditionRecord | DowntimeRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[MaintenanceObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[OracleERPSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class IncidentResponseExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Incident response and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P5ExecutionRole"
    _name: ClassVar[str] = "Incident response execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                AINAgentsPhysicalHost
                | OperationsLeadParticipant
                | ResponseTeamParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class IncidentResponseExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Incident response; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P5Interval"
    _name: ClassVar[str] = "Incident response execution interval"
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


class IncidentResponseDetect(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Incident response: Detect. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P5Step1"
    _name: ClassVar[str] = "Incident response · Detect"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[IncidentResponse | URIRef | str], Field()] | None = None


class IncidentResponseTriage(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Incident response: Triage. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P5Step2"
    _name: ClassVar[str] = "Incident response · Triage"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[IncidentResponse | URIRef | str], Field()] | None = None


class IncidentResponseResolveReview(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Incident response: Resolve & review. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P5Step3"
    _name: ClassVar[str] = "Incident response · Resolve & review"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[IncidentResponse | URIRef | str], Field()] | None = None


class IncidentResponse(ABIAISystem, S3OperationsProcesses, RDFEntity):
    """
    A proposed ABI incident response process. Suggested steps: Detect → Triage → Resolve & review. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P5"
    _name: ClassVar[str] = "Incident response"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[IncidentResponseExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                AINAgentsPhysicalHost
                | OperationsLeadParticipant
                | ResponseTeamParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[IncidentResponseSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                IncidentResponseDetect
                | IncidentResponseResolveReview
                | IncidentResponseTriage
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[IncidentResponseExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AfteractionNote | IncidentRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[IncidentResponseTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[ResolutionTimeRecord | SeverityRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[IncidentResponseObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[AINAgentsSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class VendorEvaluationExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Vendor evaluation and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P1ExecutionRole"
    _name: ClassVar[str] = "Vendor evaluation execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                OracleERPPhysicalHost
                | ProcurementOfficerParticipant
                | S4ControllerParticipant
                | URIRef
                | VendorPersonnel
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class VendorEvaluationExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Vendor evaluation; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P1Interval"
    _name: ClassVar[str] = "Vendor evaluation execution interval"
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


class VendorEvaluationDefineCriteria(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Vendor evaluation: Define criteria. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P1Step1"
    _name: ClassVar[str] = "Vendor evaluation · Define criteria"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[URIRef | VendorEvaluation | str], Field()] | None = None


class VendorEvaluationScoreVendors(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Vendor evaluation: Score vendors. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P1Step2"
    _name: ClassVar[str] = "Vendor evaluation · Score vendors"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[URIRef | VendorEvaluation | str], Field()] | None = None


class VendorEvaluationRecommend(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Vendor evaluation: Recommend. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P1Step3"
    _name: ClassVar[str] = "Vendor evaluation · Recommend"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[URIRef | VendorEvaluation | str], Field()] | None = None


class VendorEvaluation(ABIAISystem, S4LogisticsProcesses, RDFEntity):
    """
    A proposed ABI vendor evaluation process. Suggested steps: Define criteria → Score vendors → Recommend. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P1"
    _name: ClassVar[str] = "Vendor evaluation"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[URIRef | VendorEvaluationExecutionRole | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                OracleERPPhysicalHost
                | ProcurementOfficerParticipant
                | S4ControllerParticipant
                | URIRef
                | VendorPersonnel
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[URIRef | VendorEvaluationSpecification | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                URIRef
                | VendorEvaluationDefineCriteria
                | VendorEvaluationRecommend
                | VendorEvaluationScoreVendors
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[URIRef | VendorEvaluationExecutionInterval | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[EvaluationRecord | URIRef | VendorCatalogue | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[URIRef | VendorEvaluationTimingCondition | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[ComplianceStatusRecord | URIRef | VendorPerformanceScoreRecord | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[URIRef | VendorEvaluationObjective | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[OracleERPSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class StraightthroughProcurementExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Straight-through procurement and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P2ExecutionRole"
    _name: ClassVar[str] = "Straight-through procurement execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                AINProcurementAgentPhysicalHost
                | OracleERPPhysicalHost
                | ProcurementOfficerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class StraightthroughProcurementExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Straight-through procurement; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P2Interval"
    _name: ClassVar[str] = "Straight-through procurement execution interval"
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


class StraightthroughProcurementRequisition(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Straight-through procurement: Requisition. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P2Step1"
    _name: ClassVar[str] = "Straight-through procurement · Requisition"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[StraightthroughProcurement | URIRef | str], Field()] | None
    ) = None


class StraightthroughProcurementAutoapproveWithinPolicy(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Straight-through procurement: Auto-approve within policy. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P2Step2"
    _name: ClassVar[str] = "Straight-through procurement · Auto-approve within policy"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[StraightthroughProcurement | URIRef | str], Field()] | None
    ) = None


class StraightthroughProcurementOrder(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Straight-through procurement: Order. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P2Step3"
    _name: ClassVar[str] = "Straight-through procurement · Order"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[StraightthroughProcurement | URIRef | str], Field()] | None
    ) = None


class StraightthroughProcurement(ABIAISystem, S4LogisticsProcesses, RDFEntity):
    """
    A proposed ABI straight-through procurement process. Suggested steps: Requisition → Auto-approve within policy → Order. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P2"
    _name: ClassVar[str] = "Straight-through procurement"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[StraightthroughProcurementExecutionRole | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                AINProcurementAgentPhysicalHost
                | OracleERPPhysicalHost
                | ProcurementOfficerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[StraightthroughProcurementSpecification | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000066: (
        Annotated[list[OnpremisesDataCentre | OperationsCentre | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                StraightthroughProcurementAutoapproveWithinPolicy
                | StraightthroughProcurementOrder
                | StraightthroughProcurementRequisition
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[
            list[StraightthroughProcurementExecutionInterval | URIRef | str], Field()
        ]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AuditTrail | ProcurementRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[StraightthroughProcurementTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[CycleTimeRecord | PolicyComplianceRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[StraightthroughProcurementObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[AINProcurementAgentSoftware | OracleERPSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class StockAndInventoryExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Stock and inventory and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P3ExecutionRole"
    _name: ClassVar[str] = "Stock and inventory execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[OracleERPPhysicalHost | StoreKeeperParticipant | URIRef | str], Field()
        ]
        | None
    ) = None


class StockAndInventoryExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Stock and inventory; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P3Interval"
    _name: ClassVar[str] = "Stock and inventory execution interval"
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


class StockAndInventoryCount(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Stock and inventory: Count. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P3Step1"
    _name: ClassVar[str] = "Stock and inventory · Count"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[StockAndInventory | URIRef | str], Field()] | None = (
        None
    )


class StockAndInventoryReconcile(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Stock and inventory: Reconcile. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P3Step2"
    _name: ClassVar[str] = "Stock and inventory · Reconcile"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[StockAndInventory | URIRef | str], Field()] | None = (
        None
    )


class StockAndInventoryReplenish(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Stock and inventory: Replenish. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P3Step3"
    _name: ClassVar[str] = "Stock and inventory · Replenish"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[StockAndInventory | URIRef | str], Field()] | None = (
        None
    )


class StockAndInventory(ABIAISystem, S4LogisticsProcesses, RDFEntity):
    """
    A proposed ABI stock and inventory process. Suggested steps: Count → Reconcile → Replenish. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P3"
    _name: ClassVar[str] = "Stock and inventory"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[StockAndInventoryExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[OracleERPPhysicalHost | StoreKeeperParticipant | URIRef | str], Field()
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[StockAndInventorySpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: (
        Annotated[list[OnpremisesDataCentre | Stores | URIRef | str], Field()] | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                StockAndInventoryCount
                | StockAndInventoryReconcile
                | StockAndInventoryReplenish
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[StockAndInventoryExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AssetRegistry | InventoryRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[StockAndInventoryTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[AccuracyRecord | StockLevelRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[StockAndInventoryObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[OracleERPSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class AssetRegistryExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Asset registry and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P4ExecutionRole"
    _name: ClassVar[str] = "Asset registry execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                AssetOwnerParticipant
                | OracleERPPhysicalHost
                | S4ControllerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class AssetRegistryExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Asset registry; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P4Interval"
    _name: ClassVar[str] = "Asset registry execution interval"
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


class AssetRegistryRegisterAsset(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Asset registry: Register asset. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P4Step1"
    _name: ClassVar[str] = "Asset registry · Register asset"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[AssetRegistry | URIRef | str], Field()] | None = None


class AssetRegistryTag(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Asset registry: Tag. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P4Step2"
    _name: ClassVar[str] = "Asset registry · Tag"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[AssetRegistry | URIRef | str], Field()] | None = None


class AssetRegistryTrackLifecycle(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Asset registry: Track lifecycle. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P4Step3"
    _name: ClassVar[str] = "Asset registry · Track lifecycle"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[AssetRegistry | URIRef | str], Field()] | None = None


class AssetRegistry(ABIAISystem, S4LogisticsProcesses, RDFEntity):
    """
    A proposed ABI asset registry process. Suggested steps: Register asset → Tag → Track lifecycle. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P4"
    _name: ClassVar[str] = "Asset registry"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[AssetRegistryExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                AssetOwnerParticipant
                | OracleERPPhysicalHost
                | S4ControllerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[AssetRegistrySpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: (
        Annotated[list[OnpremisesDataCentre | URIRef | str], Field()] | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                AssetRegistryRegisterAsset
                | AssetRegistryTag
                | AssetRegistryTrackLifecycle
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[AssetRegistryExecutionInterval | URIRef | str], Field()] | None
    ) = None
    documented_by: (
        Annotated[
            list[AssetRegistry | AuditTrail | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[AssetRegistryTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[RegistryCompletenessRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[AssetRegistryObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[OracleERPSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class SupplierOnboardingExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Supplier onboarding and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P5ExecutionRole"
    _name: ClassVar[str] = "Supplier onboarding execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                OracleERPPhysicalHost
                | ProcurementOfficerParticipant
                | SupplierPersonnel
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class SupplierOnboardingExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Supplier onboarding; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P5Interval"
    _name: ClassVar[str] = "Supplier onboarding execution interval"
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


class SupplierOnboardingVetSupplier(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Supplier onboarding: Vet supplier. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P5Step1"
    _name: ClassVar[str] = "Supplier onboarding · Vet supplier"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[SupplierOnboarding | URIRef | str], Field()] | None = (
        None
    )


class SupplierOnboardingSetTerms(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Supplier onboarding: Set terms. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P5Step2"
    _name: ClassVar[str] = "Supplier onboarding · Set terms"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[SupplierOnboarding | URIRef | str], Field()] | None = (
        None
    )


class SupplierOnboardingActivate(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Supplier onboarding: Activate. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P5Step3"
    _name: ClassVar[str] = "Supplier onboarding · Activate"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[SupplierOnboarding | URIRef | str], Field()] | None = (
        None
    )


class SupplierOnboarding(ABIAISystem, S4LogisticsProcesses, RDFEntity):
    """
    A proposed ABI supplier onboarding process. Suggested steps: Vet supplier → Set terms → Activate. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P5"
    _name: ClassVar[str] = "Supplier onboarding"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[SupplierOnboardingExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                OracleERPPhysicalHost
                | ProcurementOfficerParticipant
                | SupplierPersonnel
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[SupplierOnboardingSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                SupplierOnboardingActivate
                | SupplierOnboardingSetTerms
                | SupplierOnboardingVetSupplier
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[SupplierOnboardingExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[URIRef | VendorCatalogue | VendorContract | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[SupplierOnboardingTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[OnboardingStatusRecord | RighttoauditInPlaceRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[SupplierOnboardingObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[OracleERPSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class ProgrammePlanningExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Programme planning and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P1ExecutionRole"
    _name: ClassVar[str] = "Programme planning execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                PlanningSystemPhysicalHost
                | ProgrammeOwnerParticipant
                | S5PlannerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class ProgrammePlanningExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Programme planning; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P1Interval"
    _name: ClassVar[str] = "Programme planning execution interval"
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


class ProgrammePlanningDefineObjectives(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Programme planning: Define objectives. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P1Step1"
    _name: ClassVar[str] = "Programme planning · Define objectives"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[ProgrammePlanning | URIRef | str], Field()] | None = (
        None
    )


class ProgrammePlanningSequence(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Programme planning: Sequence. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P1Step2"
    _name: ClassVar[str] = "Programme planning · Sequence"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[ProgrammePlanning | URIRef | str], Field()] | None = (
        None
    )


class ProgrammePlanningBaseline(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Programme planning: Baseline. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P1Step3"
    _name: ClassVar[str] = "Programme planning · Baseline"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[ProgrammePlanning | URIRef | str], Field()] | None = (
        None
    )


class ProgrammePlanning(ABIAISystem, S5PlansProcesses, RDFEntity):
    """
    A proposed ABI programme planning process. Suggested steps: Define objectives → Sequence → Baseline. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P1"
    _name: ClassVar[str] = "Programme planning"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[ProgrammePlanningExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                PlanningSystemPhysicalHost
                | ProgrammeOwnerParticipant
                | S5PlannerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[ProgrammePlanningSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                ProgrammePlanningBaseline
                | ProgrammePlanningDefineObjectives
                | ProgrammePlanningSequence
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[ProgrammePlanningExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[DecisionLog | ProgrammePlan | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[ProgrammePlanningTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[PlanMaturityRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[ProgrammePlanningObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[PlanningSystemSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class ForecastingExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Forecasting and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P2ExecutionRole"
    _name: ClassVar[str] = "Forecasting execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[AINPredictiveAgentPhysicalHost | PlannerParticipant | URIRef | str],
            Field(),
        ]
        | None
    ) = None


class ForecastingExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Forecasting; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P2Interval"
    _name: ClassVar[str] = "Forecasting execution interval"
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


class ForecastingGatherSignals(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Forecasting: Gather signals. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P2Step1"
    _name: ClassVar[str] = "Forecasting · Gather signals"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Forecasting | URIRef | str], Field()] | None = None


class ForecastingModel(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Forecasting: Model. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P2Step2"
    _name: ClassVar[str] = "Forecasting · Model"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Forecasting | URIRef | str], Field()] | None = None


class ForecastingPublishForecast(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Forecasting: Publish forecast. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P2Step3"
    _name: ClassVar[str] = "Forecasting · Publish forecast"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Forecasting | URIRef | str], Field()] | None = None


class Forecasting(ABIAISystem, S5PlansProcesses, RDFEntity):
    """
    A proposed ABI forecasting process. Suggested steps: Gather signals → Model → Publish forecast. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P2"
    _name: ClassVar[str] = "Forecasting"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[ForecastingExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[AINPredictiveAgentPhysicalHost | PlannerParticipant | URIRef | str],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[ForecastingSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                ForecastingGatherSignals
                | ForecastingModel
                | ForecastingPublishForecast
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[ForecastingExecutionInterval | URIRef | str], Field()] | None
    ) = None
    documented_by: (
        Annotated[
            list[EvidenceRegister | ForecastRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[ForecastingTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[ForecastConfidenceRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[ForecastingObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[AINPredictiveAgentSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class CapabilityRoadmapExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Capability roadmap and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P3ExecutionRole"
    _name: ClassVar[str] = "Capability roadmap execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[FunctionLeadsParticipant | S5LeadParticipant | URIRef | str], Field()
        ]
        | None
    ) = None


class CapabilityRoadmapExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Capability roadmap; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P3Interval"
    _name: ClassVar[str] = "Capability roadmap execution interval"
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


class CapabilityRoadmapAssessGaps(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Capability roadmap: Assess gaps. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P3Step1"
    _name: ClassVar[str] = "Capability roadmap · Assess gaps"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[CapabilityRoadmap | URIRef | str], Field()] | None = (
        None
    )


class CapabilityRoadmapPrioritise(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Capability roadmap: Prioritise. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P3Step2"
    _name: ClassVar[str] = "Capability roadmap · Prioritise"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[CapabilityRoadmap | URIRef | str], Field()] | None = (
        None
    )


class CapabilityRoadmapRoadmap(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Capability roadmap: Roadmap. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P3Step3"
    _name: ClassVar[str] = "Capability roadmap · Roadmap"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[CapabilityRoadmap | URIRef | str], Field()] | None = (
        None
    )


class CapabilityRoadmap(ABIAISystem, S5PlansProcesses, RDFEntity):
    """
    A proposed ABI capability roadmap process. Suggested steps: Assess gaps → Prioritise → Roadmap. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P3"
    _name: ClassVar[str] = "Capability roadmap"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
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
    bFO_0000055: (
        Annotated[list[CapabilityRoadmapExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[FunctionLeadsParticipant | S5LeadParticipant | URIRef | str], Field()
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[CapabilityRoadmapSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                CapabilityRoadmapAssessGaps
                | CapabilityRoadmapPrioritise
                | CapabilityRoadmapRoadmap
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[CapabilityRoadmapExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[GapRegister | RoadmapDocument | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[CapabilityRoadmapTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[GapCoverageRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[CapabilityRoadmapObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None


class ITProvisioningExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in IT provisioning and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P1ExecutionRole"
    _name: ClassVar[str] = "IT provisioning execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                ITEngineerParticipant
                | PhysicalITInfrastructure
                | RequesterParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class ITProvisioningExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of IT provisioning; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P1Interval"
    _name: ClassVar[str] = "IT provisioning execution interval"
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


class ITProvisioningRequest(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of IT provisioning: Request. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P1Step1"
    _name: ClassVar[str] = "IT provisioning · Request"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[ITProvisioning | URIRef | str], Field()] | None = None


class ITProvisioningProvision(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of IT provisioning: Provision. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P1Step2"
    _name: ClassVar[str] = "IT provisioning · Provision"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[ITProvisioning | URIRef | str], Field()] | None = None


class ITProvisioningVerify(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of IT provisioning: Verify. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P1Step3"
    _name: ClassVar[str] = "IT provisioning · Verify"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[ITProvisioning | URIRef | str], Field()] | None = None


class ITProvisioning(ABIAISystem, S6SignalProcesses, RDFEntity):
    """
    A proposed ABI it provisioning process. Suggested steps: Request → Provision → Verify. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P1"
    _name: ClassVar[str] = "IT provisioning"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
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
    bFO_0000055: (
        Annotated[list[ITProvisioningExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                ITEngineerParticipant
                | PhysicalITInfrastructure
                | RequesterParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[ITProvisioningSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: (
        Annotated[list[ABIExecutionSite | OnpremisesDataCentre | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                ITProvisioningProvision
                | ITProvisioningRequest
                | ITProvisioningVerify
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[ITProvisioningExecutionInterval | URIRef | str], Field()] | None
    ) = None
    documented_by: (
        Annotated[
            list[ConfigurationLog | ProvisioningRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[ITProvisioningTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[ProvisioningStatusRecord | URIRef | UptimeRecord | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[ITProvisioningObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None


class CyberPostureblueredTeamExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Cyber posture (blue/red team) and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P2ExecutionRole"
    _name: ClassVar[str] = "Cyber posture (blue/red team) execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                AINAgentsPhysicalHost
                | CyberTeamParticipant
                | PhysicalITInfrastructure
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class CyberPostureblueredTeamExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Cyber posture (blue/red team); actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P2Interval"
    _name: ClassVar[str] = "Cyber posture (blue/red team) execution interval"
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


class CyberPostureblueredTeamAttackred(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Cyber posture (blue/red team): Attack (red). Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P2Step1"
    _name: ClassVar[str] = "Cyber posture (blue/red team) · Attack (red)"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[CyberPostureblueredTeam | URIRef | str], Field()] | None
    ) = None


class CyberPostureblueredTeamDefendblue(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Cyber posture (blue/red team): Defend (blue). Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P2Step2"
    _name: ClassVar[str] = "Cyber posture (blue/red team) · Defend (blue)"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[CyberPostureblueredTeam | URIRef | str], Field()] | None
    ) = None


class CyberPostureblueredTeamRemediate(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Cyber posture (blue/red team): Remediate. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P2Step3"
    _name: ClassVar[str] = "Cyber posture (blue/red team) · Remediate"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[CyberPostureblueredTeam | URIRef | str], Field()] | None
    ) = None


class CyberPostureblueredTeam(ABIAISystem, S6SignalProcesses, RDFEntity):
    """
    A proposed ABI cyber posture (blue/red team) process. Suggested steps: Attack (red) → Defend (blue) → Remediate. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P2"
    _name: ClassVar[str] = "Cyber posture (blue/red team)"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[CyberPostureblueredTeamExecutionRole | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                AINAgentsPhysicalHost
                | CyberTeamParticipant
                | PhysicalITInfrastructure
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[CyberPostureblueredTeamSpecification | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000066: (
        Annotated[list[ABIExecutionSite | AirgappedZone | URIRef | str], Field()] | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                CyberPostureblueredTeamAttackred
                | CyberPostureblueredTeamDefendblue
                | CyberPostureblueredTeamRemediate
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[
            list[CyberPostureblueredTeamExecutionInterval | URIRef | str], Field()
        ]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[PenetrationReport | RemediationLog | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[CyberPostureblueredTeamTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[AirgapComplianceRecord | FindingsSeverityRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[CyberPostureblueredTeamObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[AINAgentsSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class CommunicationsAndCalendarExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Communications and calendar and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P3ExecutionRole"
    _name: ClassVar[str] = "Communications and calendar execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                CommsOfficerParticipant
                | MessagingSystemPhysicalHost
                | StaffParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class CommunicationsAndCalendarExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Communications and calendar; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P3Interval"
    _name: ClassVar[str] = "Communications and calendar execution interval"
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


class CommunicationsAndCalendarSchedule(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Communications and calendar: Schedule. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P3Step1"
    _name: ClassVar[str] = "Communications and calendar · Schedule"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[CommunicationsAndCalendar | URIRef | str], Field()] | None
    ) = None


class CommunicationsAndCalendarNotify(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Communications and calendar: Notify. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P3Step2"
    _name: ClassVar[str] = "Communications and calendar · Notify"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[CommunicationsAndCalendar | URIRef | str], Field()] | None
    ) = None


class CommunicationsAndCalendarRecord(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Communications and calendar: Record. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P3Step3"
    _name: ClassVar[str] = "Communications and calendar · Record"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[CommunicationsAndCalendar | URIRef | str], Field()] | None
    ) = None


class CommunicationsAndCalendar(ABIAISystem, S6SignalProcesses, RDFEntity):
    """
    A proposed ABI communications and calendar process. Suggested steps: Schedule → Notify → Record. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P3"
    _name: ClassVar[str] = "Communications and calendar"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[CommunicationsAndCalendarExecutionRole | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                CommsOfficerParticipant
                | MessagingSystemPhysicalHost
                | StaffParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[CommunicationsAndCalendarSpecification | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                CommunicationsAndCalendarNotify
                | CommunicationsAndCalendarRecord
                | CommunicationsAndCalendarSchedule
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[
            list[CommunicationsAndCalendarExecutionInterval | URIRef | str], Field()
        ]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[CalendarRecord | MessageLog | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[CommunicationsAndCalendarTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[DeliveryStatusRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[CommunicationsAndCalendarObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[MessagingSystemSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class TrainingDeliveryExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Training delivery and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P1ExecutionRole"
    _name: ClassVar[str] = "Training delivery execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                LearningSystemPhysicalHost
                | TraineeParticipant
                | TrainerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class TrainingDeliveryExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Training delivery; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P1Interval"
    _name: ClassVar[str] = "Training delivery execution interval"
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


class TrainingDeliveryPlanCourse(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Training delivery: Plan course. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P1Step1"
    _name: ClassVar[str] = "Training delivery · Plan course"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[TrainingDelivery | URIRef | str], Field()] | None = None


class TrainingDeliveryDeliver(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Training delivery: Deliver. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P1Step2"
    _name: ClassVar[str] = "Training delivery · Deliver"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[TrainingDelivery | URIRef | str], Field()] | None = None


class TrainingDeliveryRecord(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Training delivery: Record. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P1Step3"
    _name: ClassVar[str] = "Training delivery · Record"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[TrainingDelivery | URIRef | str], Field()] | None = None


class TrainingDelivery(ABIAISystem, S7TrainingProcesses, RDFEntity):
    """
    A proposed ABI training delivery process. Suggested steps: Plan course → Deliver → Record. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P1"
    _name: ClassVar[str] = "Training delivery"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[TrainingDeliveryExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                LearningSystemPhysicalHost
                | TraineeParticipant
                | TrainerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[TrainingDeliverySpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                TrainingDeliveryDeliver
                | TrainingDeliveryPlanCourse
                | TrainingDeliveryRecord
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[TrainingDeliveryExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AttendanceLog | TrainingRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[TrainingDeliveryTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[CompletionRateRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[TrainingDeliveryObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[LearningSystemSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class CapabilityDevelopmentExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Capability development and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P2ExecutionRole"
    _name: ClassVar[str] = "Capability development execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[S7LeadParticipant | StaffMemberParticipant | URIRef | str], Field()
        ]
        | None
    ) = None


class CapabilityDevelopmentExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Capability development; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P2Interval"
    _name: ClassVar[str] = "Capability development execution interval"
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


class CapabilityDevelopmentAssess(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Capability development: Assess. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P2Step1"
    _name: ClassVar[str] = "Capability development · Assess"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[CapabilityDevelopment | URIRef | str], Field()] | None
    ) = None


class CapabilityDevelopmentDevelop(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Capability development: Develop. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P2Step2"
    _name: ClassVar[str] = "Capability development · Develop"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[CapabilityDevelopment | URIRef | str], Field()] | None
    ) = None


class CapabilityDevelopmentCertify(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Capability development: Certify. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P2Step3"
    _name: ClassVar[str] = "Capability development · Certify"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[CapabilityDevelopment | URIRef | str], Field()] | None
    ) = None


class CapabilityDevelopment(ABIAISystem, S7TrainingProcesses, RDFEntity):
    """
    A proposed ABI capability development process. Suggested steps: Assess → Develop → Certify. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P2"
    _name: ClassVar[str] = "Capability development"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
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
    bFO_0000055: (
        Annotated[list[CapabilityDevelopmentExecutionRole | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[S7LeadParticipant | StaffMemberParticipant | URIRef | str], Field()
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[CapabilityDevelopmentSpecification | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                CapabilityDevelopmentAssess
                | CapabilityDevelopmentCertify
                | CapabilityDevelopmentDevelop
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[CapabilityDevelopmentExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AssessmentResult | CompetencyRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[CapabilityDevelopmentTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[CompetencyLevelRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[CapabilityDevelopmentObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None


class AssessmentExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Assessment and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P3ExecutionRole"
    _name: ClassVar[str] = "Assessment execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[AssessorParticipant | TraineeParticipant | URIRef | str], Field()
        ]
        | None
    ) = None


class AssessmentExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Assessment; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P3Interval"
    _name: ClassVar[str] = "Assessment execution interval"
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


class AssessmentSetAssessment(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Assessment: Set assessment. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P3Step1"
    _name: ClassVar[str] = "Assessment · Set assessment"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Assessment | URIRef | str], Field()] | None = None


class AssessmentScore(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Assessment: Score. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P3Step2"
    _name: ClassVar[str] = "Assessment · Score"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Assessment | URIRef | str], Field()] | None = None


class AssessmentFeedBack(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Assessment: Feed back. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P3Step3"
    _name: ClassVar[str] = "Assessment · Feed back"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[Assessment | URIRef | str], Field()] | None = None


class Assessment(ABIAISystem, S7TrainingProcesses, RDFEntity):
    """
    A proposed ABI assessment process. Suggested steps: Set assessment → Score → Feed back. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P3"
    _name: ClassVar[str] = "Assessment"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
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
    bFO_0000055: (
        Annotated[list[AssessmentExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[AssessorParticipant | TraineeParticipant | URIRef | str], Field()
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[AssessmentSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                AssessmentFeedBack
                | AssessmentScore
                | AssessmentSetAssessment
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[AssessmentExecutionInterval | URIRef | str], Field()] | None
    ) = None
    documented_by: (
        Annotated[
            list[AssessmentRecord | EvidenceRegister | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[AssessmentTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[PassRateRecord | ScoreRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[AssessmentObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None


class FinanceApprovalChainExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Finance approval chain and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P1ExecutionRole"
    _name: ClassVar[str] = "Finance approval chain execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                OracleERPPhysicalHost
                | RequesterParticipant
                | S8ApproverParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class FinanceApprovalChainExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Finance approval chain; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P1Interval"
    _name: ClassVar[str] = "Finance approval chain execution interval"
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


class FinanceApprovalChainSubmit(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Finance approval chain: Submit. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P1Step1"
    _name: ClassVar[str] = "Finance approval chain · Submit"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[FinanceApprovalChain | URIRef | str], Field()] | None
    ) = None


class FinanceApprovalChainRouteForApproval(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Finance approval chain: Route for approval. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P1Step2"
    _name: ClassVar[str] = "Finance approval chain · Route for approval"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[FinanceApprovalChain | URIRef | str], Field()] | None
    ) = None


class FinanceApprovalChainAuthorise(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Finance approval chain: Authorise. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P1Step3"
    _name: ClassVar[str] = "Finance approval chain · Authorise"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[FinanceApprovalChain | URIRef | str], Field()] | None
    ) = None


class FinanceApprovalChain(ABIAISystem, S8FinanceProcesses, RDFEntity):
    """
    A proposed ABI finance approval chain process. Suggested steps: Submit → Route for approval → Authorise. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P1"
    _name: ClassVar[str] = "Finance approval chain"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[FinanceApprovalChainExecutionRole | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                OracleERPPhysicalHost
                | RequesterParticipant
                | S8ApproverParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[FinanceApprovalChainSpecification | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000066: (
        Annotated[list[OnpremisesDataCentre | OperationsCentre | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                FinanceApprovalChainAuthorise
                | FinanceApprovalChainRouteForApproval
                | FinanceApprovalChainSubmit
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[FinanceApprovalChainExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[ApprovalRecord | DecisionLog | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[FinanceApprovalChainTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[ApprovalStatusRecord | SLAAdherenceRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[FinanceApprovalChainObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[OracleERPSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class BudgetManagementExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Budget management and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P2ExecutionRole"
    _name: ClassVar[str] = "Budget management execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                BudgetOwnerParticipant
                | FinanceOfficerParticipant
                | OracleERPPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class BudgetManagementExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Budget management; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P2Interval"
    _name: ClassVar[str] = "Budget management execution interval"
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


class BudgetManagementSetBudget(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Budget management: Set budget. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P2Step1"
    _name: ClassVar[str] = "Budget management · Set budget"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[BudgetManagement | URIRef | str], Field()] | None = None


class BudgetManagementTrack(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Budget management: Track. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P2Step2"
    _name: ClassVar[str] = "Budget management · Track"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[BudgetManagement | URIRef | str], Field()] | None = None


class BudgetManagementReforecast(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Budget management: Reforecast. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P2Step3"
    _name: ClassVar[str] = "Budget management · Reforecast"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[BudgetManagement | URIRef | str], Field()] | None = None


class BudgetManagement(ABIAISystem, S8FinanceProcesses, RDFEntity):
    """
    A proposed ABI budget management process. Suggested steps: Set budget → Track → Reforecast. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P2"
    _name: ClassVar[str] = "Budget management"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[BudgetManagementExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                BudgetOwnerParticipant
                | FinanceOfficerParticipant
                | OracleERPPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[BudgetManagementSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                BudgetManagementReforecast
                | BudgetManagementSetBudget
                | BudgetManagementTrack
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[BudgetManagementExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AuditTrail | BudgetRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[BudgetManagementTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[BudgetStatusRecord | URIRef | VarianceRecord | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[BudgetManagementObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[OracleERPSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class ContractManagementExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Contract management and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P3ExecutionRole"
    _name: ClassVar[str] = "Contract management execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                ContractManagerParticipant
                | OracleERPPhysicalHost
                | URIRef
                | VendorPersonnel
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class ContractManagementExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Contract management; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P3Interval"
    _name: ClassVar[str] = "Contract management execution interval"
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


class ContractManagementDraft(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Contract management: Draft. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P3Step1"
    _name: ClassVar[str] = "Contract management · Draft"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[ContractManagement | URIRef | str], Field()] | None = (
        None
    )


class ContractManagementSign(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Contract management: Sign. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P3Step2"
    _name: ClassVar[str] = "Contract management · Sign"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[ContractManagement | URIRef | str], Field()] | None = (
        None
    )


class ContractManagementManageLifecycle(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Contract management: Manage lifecycle. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P3Step3"
    _name: ClassVar[str] = "Contract management · Manage lifecycle"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[ContractManagement | URIRef | str], Field()] | None = (
        None
    )


class ContractManagement(ABIAISystem, S8FinanceProcesses, RDFEntity):
    """
    A proposed ABI contract management process. Suggested steps: Draft → Sign → Manage lifecycle. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P3"
    _name: ClassVar[str] = "Contract management"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[ContractManagementExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                ContractManagerParticipant
                | OracleERPPhysicalHost
                | URIRef
                | VendorPersonnel
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[ContractManagementSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                ContractManagementDraft
                | ContractManagementManageLifecycle
                | ContractManagementSign
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[ContractManagementExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AuditTrail | URIRef | VendorContract | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[ContractManagementTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[ContractStatusRecord | RighttoauditRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[ContractManagementObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[OracleERPSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class PaymentsAndExpensesExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Payments and expenses and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P4ExecutionRole"
    _name: ClassVar[str] = "Payments and expenses execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                AINFinanceAgentPhysicalHost
                | FinanceOfficerParticipant
                | OracleERPPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class PaymentsAndExpensesExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Payments and expenses; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P4Interval"
    _name: ClassVar[str] = "Payments and expenses execution interval"
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


class PaymentsAndExpensesCapture(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Payments and expenses: Capture. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P4Step1"
    _name: ClassVar[str] = "Payments and expenses · Capture"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[PaymentsAndExpenses | URIRef | str], Field()] | None = (
        None
    )


class PaymentsAndExpensesValidate(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Payments and expenses: Validate. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P4Step2"
    _name: ClassVar[str] = "Payments and expenses · Validate"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[PaymentsAndExpenses | URIRef | str], Field()] | None = (
        None
    )


class PaymentsAndExpensesPay(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Payments and expenses: Pay. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P4Step3"
    _name: ClassVar[str] = "Payments and expenses · Pay"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[PaymentsAndExpenses | URIRef | str], Field()] | None = (
        None
    )


class PaymentsAndExpenses(ABIAISystem, S8FinanceProcesses, RDFEntity):
    """
    A proposed ABI payments and expenses process. Suggested steps: Capture → Validate → Pay. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P4"
    _name: ClassVar[str] = "Payments and expenses"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[PaymentsAndExpensesExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                AINFinanceAgentPhysicalHost
                | FinanceOfficerParticipant
                | OracleERPPhysicalHost
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[PaymentsAndExpensesSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: (
        Annotated[list[OnpremisesDataCentre | URIRef | str], Field()] | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                PaymentsAndExpensesCapture
                | PaymentsAndExpensesPay
                | PaymentsAndExpensesValidate
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[PaymentsAndExpensesExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AuditTrail | PaymentRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[PaymentsAndExpensesTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[ExceptionRateRecord | PaymentStatusRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[PaymentsAndExpensesObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[AINFinanceAgentSoftware | OracleERPSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class AuditTrailMaintenanceExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Audit trail maintenance and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P5ExecutionRole"
    _name: ClassVar[str] = "Audit trail maintenance execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[
                AINPhysicalHost
                | AuditorParticipant
                | FinanceOfficerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None


class AuditTrailMaintenanceExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Audit trail maintenance; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P5Interval"
    _name: ClassVar[str] = "Audit trail maintenance execution interval"
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


class AuditTrailMaintenanceLogActions(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Audit trail maintenance: Log actions. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P5Step1"
    _name: ClassVar[str] = "Audit trail maintenance · Log actions"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[AuditTrailMaintenance | URIRef | str], Field()] | None
    ) = None


class AuditTrailMaintenanceRetain(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Audit trail maintenance: Retain. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P5Step2"
    _name: ClassVar[str] = "Audit trail maintenance · Retain"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[AuditTrailMaintenance | URIRef | str], Field()] | None
    ) = None


class AuditTrailMaintenanceProduceOnDemand(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Audit trail maintenance: Produce on demand. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P5Step3"
    _name: ClassVar[str] = "Audit trail maintenance · Produce on demand"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[AuditTrailMaintenance | URIRef | str], Field()] | None
    ) = None


class AuditTrailMaintenance(ABIAISystem, S8FinanceProcesses, RDFEntity):
    """
    A proposed ABI audit trail maintenance process. Suggested steps: Log actions → Retain → Produce on demand. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P5"
    _name: ClassVar[str] = "Audit trail maintenance"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
        "uses_information": "http://ontology.naas.ai/abi/usesInformation",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
        "uses_information",
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
    bFO_0000055: (
        Annotated[list[AuditTrailMaintenanceExecutionRole | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[
                AINPhysicalHost
                | AuditorParticipant
                | FinanceOfficerParticipant
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[AuditTrailMaintenanceSpecification | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000066: (
        Annotated[list[AirgappedZone | OnpremisesDataCentre | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000117: (
        Annotated[
            list[
                AuditTrailMaintenanceLogActions
                | AuditTrailMaintenanceProduceOnDemand
                | AuditTrailMaintenanceRetain
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[AuditTrailMaintenanceExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[AuditTrail | DecisionLog | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[AuditTrailMaintenanceTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[TrailCompletenessRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[AuditTrailMaintenanceObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None
    uses_information: (
        Annotated[
            list[AINSoftware | URIRef | str],
            Field(
                description="Relates a process to information used during it, including software or source material."
            ),
        ]
        | None
    ) = None


class StakeholderEngagementExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Stakeholder engagement and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P1ExecutionRole"
    _name: ClassVar[str] = "Stakeholder engagement execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[S9OfficerParticipant | StakeholderParticipant | URIRef | str], Field()
        ]
        | None
    ) = None


class StakeholderEngagementExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Stakeholder engagement; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P1Interval"
    _name: ClassVar[str] = "Stakeholder engagement execution interval"
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


class StakeholderEngagementMapStakeholders(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Stakeholder engagement: Map stakeholders. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P1Step1"
    _name: ClassVar[str] = "Stakeholder engagement · Map stakeholders"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[StakeholderEngagement | URIRef | str], Field()] | None
    ) = None


class StakeholderEngagementEngage(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Stakeholder engagement: Engage. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P1Step2"
    _name: ClassVar[str] = "Stakeholder engagement · Engage"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[StakeholderEngagement | URIRef | str], Field()] | None
    ) = None


class StakeholderEngagementRecord(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Stakeholder engagement: Record. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P1Step3"
    _name: ClassVar[str] = "Stakeholder engagement · Record"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[StakeholderEngagement | URIRef | str], Field()] | None
    ) = None


class StakeholderEngagement(ABIAISystem, S9ExternalAffairsProcesses, RDFEntity):
    """
    A proposed ABI stakeholder engagement process. Suggested steps: Map stakeholders → Engage → Record. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P1"
    _name: ClassVar[str] = "Stakeholder engagement"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
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
    bFO_0000055: (
        Annotated[list[StakeholderEngagementExecutionRole | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[S9OfficerParticipant | StakeholderParticipant | URIRef | str], Field()
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[StakeholderEngagementSpecification | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                StakeholderEngagementEngage
                | StakeholderEngagementMapStakeholders
                | StakeholderEngagementRecord
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[StakeholderEngagementExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[ContactRecord | EngagementLog | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[StakeholderEngagementTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[EngagementStatusRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[StakeholderEngagementObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None


class PartnerCoordinationExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Partner coordination and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P2ExecutionRole"
    _name: ClassVar[str] = "Partner coordination execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[PartnerOrganisationPersonnel | S9LeadParticipant | URIRef | str],
            Field(),
        ]
        | None
    ) = None


class PartnerCoordinationExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Partner coordination; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P2Interval"
    _name: ClassVar[str] = "Partner coordination execution interval"
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


class PartnerCoordinationAlign(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Partner coordination: Align. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P2Step1"
    _name: ClassVar[str] = "Partner coordination · Align"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[PartnerCoordination | URIRef | str], Field()] | None = (
        None
    )


class PartnerCoordinationCoordinate(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Partner coordination: Coordinate. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P2Step2"
    _name: ClassVar[str] = "Partner coordination · Coordinate"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[PartnerCoordination | URIRef | str], Field()] | None = (
        None
    )


class PartnerCoordinationReview(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Partner coordination: Review. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P2Step3"
    _name: ClassVar[str] = "Partner coordination · Review"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: Annotated[list[PartnerCoordination | URIRef | str], Field()] | None = (
        None
    )


class PartnerCoordination(ABIAISystem, S9ExternalAffairsProcesses, RDFEntity):
    """
    A proposed ABI partner coordination process. Suggested steps: Align → Coordinate → Review. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P2"
    _name: ClassVar[str] = "Partner coordination"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
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
    bFO_0000055: (
        Annotated[list[PartnerCoordinationExecutionRole | URIRef | str], Field()] | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[PartnerOrganisationPersonnel | S9LeadParticipant | URIRef | str],
            Field(),
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[PartnerCoordinationSpecification | URIRef | str], Field()] | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                PartnerCoordinationAlign
                | PartnerCoordinationCoordinate
                | PartnerCoordinationReview
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[list[PartnerCoordinationExecutionInterval | URIRef | str], Field()]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[DecisionLog | PartnerRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[PartnerCoordinationTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[AlignmentStatusRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[PartnerCoordinationObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None


class PublicAndCommunicationsExecutionRole(ABIExecutionRole, RDFEntity):
    """
    A proposed role realised in Public and communications and borne by a listed material participant. The accountable bearer must be confirmed with ABI.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P3ExecutionRole"
    _name: ClassVar[str] = "Public and communications execution role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

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
    bFO_0000197: (
        Annotated[
            list[ApproverParticipant | CommsOfficerParticipant | URIRef | str], Field()
        ]
        | None
    ) = None


class PublicAndCommunicationsExecutionInterval(ABIExecutionInterval, RDFEntity):
    """
    The temporal region occupied by an execution of Public and communications; actual dates are unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P3Interval"
    _name: ClassVar[str] = "Public and communications execution interval"
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


class PublicAndCommunicationsPrepare(ABIProcessStep, RDFEntity):
    """
    Suggested step 1 of Public and communications: Prepare. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P3Step1"
    _name: ClassVar[str] = "Public and communications · Prepare"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[PublicAndCommunications | URIRef | str], Field()] | None
    ) = None


class PublicAndCommunicationsClear(ABIProcessStep, RDFEntity):
    """
    Suggested step 2 of Public and communications: Clear. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P3Step2"
    _name: ClassVar[str] = "Public and communications · Clear"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[PublicAndCommunications | URIRef | str], Field()] | None
    ) = None


class PublicAndCommunicationsPublish(ABIProcessStep, RDFEntity):
    """
    Suggested step 3 of Public and communications: Publish. Its ordering is a specification, not observed timing.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P3Step3"
    _name: ClassVar[str] = "Public and communications · Publish"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

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
    bFO_0000132: (
        Annotated[list[PublicAndCommunications | URIRef | str], Field()] | None
    ) = None


class PublicAndCommunications(ABIAISystem, S9ExternalAffairsProcesses, RDFEntity):
    """
    A proposed ABI public and communications process. Suggested steps: Prepare → Clear → Publish. Draft — simulated ledger hypothesis; not validated with ABI. HOW IT IS values are retained as indicator records; quality bearers remain unresolved.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P3"
    _name: ClassVar[str] = "Public and communications"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000117": "http://purl.obolibrary.org/obo/BFO_0000117",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "documented_by": "http://ontology.naas.ai/abi/documentedBy",
        "has_execution_condition": "http://ontology.naas.ai/abi/hasExecutionCondition",
        "has_indicator_record": "http://ontology.naas.ai/abi/hasIndicatorRecord",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "pursues_objective": "http://ontology.naas.ai/abi/pursuesObjective",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000117",
        "bFO_0000199",
        "documented_by",
        "has_execution_condition",
        "has_indicator_record",
        "pursues_objective",
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
    bFO_0000055: (
        Annotated[list[PublicAndCommunicationsExecutionRole | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000057: (
        Annotated[
            list[ApproverParticipant | CommsOfficerParticipant | URIRef | str], Field()
        ]
        | None
    ) = None
    bFO_0000059: (
        Annotated[list[PublicAndCommunicationsSpecification | URIRef | str], Field()]
        | None
    ) = None
    bFO_0000066: Annotated[list[OperationsCentre | URIRef | str], Field()] | None = None
    bFO_0000117: (
        Annotated[
            list[
                PublicAndCommunicationsClear
                | PublicAndCommunicationsPrepare
                | PublicAndCommunicationsPublish
                | URIRef
                | str
            ],
            Field(),
        ]
        | None
    ) = None
    bFO_0000199: (
        Annotated[
            list[PublicAndCommunicationsExecutionInterval | URIRef | str], Field()
        ]
        | None
    ) = None
    documented_by: (
        Annotated[
            list[ApprovalLog | CommsRecord | URIRef | str],
            Field(
                description="Relates a process to a record documenting it; does not assert whether that record is an input or output."
            ),
        ]
        | None
    ) = None
    has_execution_condition: (
        Annotated[
            list[PublicAndCommunicationsTimingCondition | URIRef | str],
            Field(
                description="Relates a process to its described trigger, schedule or timing target."
            ),
        ]
        | None
    ) = None
    has_indicator_record: (
        Annotated[
            list[ApprovalStatusRecord | URIRef | str],
            Field(
                description="Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."
            ),
        ]
        | None
    ) = None
    pursues_objective: (
        Annotated[
            list[PublicAndCommunicationsObjective | URIRef | str],
            Field(
                description="Relates a process to its intended outcome specification, without asserting that the outcome is achieved."
            ),
        ]
        | None
    ) = None


class AINAgentsPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'AIN agents'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AINAgentsHost"
    _name: ClassVar[str] = "AIN agents physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: Annotated[list[AINAgentsSoftware | URIRef | str], Field()] | None = (
        None
    )


class AINFinanceAgentPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'AIN finance agent'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AINFinanceAgentHost"
    _name: ClassVar[str] = "AIN finance agent physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: (
        Annotated[list[AINFinanceAgentSoftware | URIRef | str], Field()] | None
    ) = None


class AINGapdetectionAgentPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'AIN gap-detection agent'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AINGapDetectionAgentHost"
    _name: ClassVar[str] = "AIN gap-detection agent physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: (
        Annotated[list[AINGapdetectionAgentSoftware | URIRef | str], Field()] | None
    ) = None


class AINPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'AIN'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AINHost"
    _name: ClassVar[str] = "AIN physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: Annotated[list[AINSoftware | URIRef | str], Field()] | None = None


class AINIntelligenceAgentPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'AIN intelligence agent'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AINIntelligenceAgentHost"
    _name: ClassVar[str] = "AIN intelligence agent physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: (
        Annotated[list[AINIntelligenceAgentSoftware | URIRef | str], Field()] | None
    ) = None


class AINPredictiveAgentPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'AIN predictive agent'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AINPredictiveAgentHost"
    _name: ClassVar[str] = "AIN predictive agent physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: (
        Annotated[list[AINPredictiveAgentSoftware | URIRef | str], Field()] | None
    ) = None


class AINProcurementAgentPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'AIN procurement agent'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AINProcurementAgentHost"
    _name: ClassVar[str] = "AIN procurement agent physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: (
        Annotated[list[AINProcurementAgentSoftware | URIRef | str], Field()] | None
    ) = None


class AccessLevelRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Access level' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AccessLevelIndicator"
    _name: ClassVar[str] = "Access level record"
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


class AccessRegister(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Access register' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AccessRegisterRecord"
    _name: ClassVar[str] = "Access register"
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


class AccessRequestRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Access request record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AccessRequestRecordRecord"
    _name: ClassVar[str] = "Access request record"
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


class AccessRevocationLog(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Access revocation log' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AccessRevocationLogRecord"
    _name: ClassVar[str] = "Access revocation log"
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


class AccessrevokedStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Access-revoked status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/AccessRevokedStatusIndicator"
    )
    _name: ClassVar[str] = "Access-revoked status record"
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


class AccessStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Access status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AccessStatusIndicator"
    _name: ClassVar[str] = "Access status record"
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


class AccuracyRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Accuracy' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AccuracyIndicator"
    _name: ClassVar[str] = "Accuracy record"
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


class AfteractionNote(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'After-action note' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AfterActionNoteRecord"
    _name: ClassVar[str] = "After-action note"
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


class AirgapComplianceRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Air-gap compliance' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AirGapComplianceIndicator"
    _name: ClassVar[str] = "Air-gap compliance record"
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


class AlertFeed(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Alert feed' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AlertFeedRecord"
    _name: ClassVar[str] = "Alert feed"
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


class AlertLatencyRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Alert latency' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AlertLatencyIndicator"
    _name: ClassVar[str] = "Alert latency record"
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


class AlignmentStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Alignment status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AlignmentStatusIndicator"
    _name: ClassVar[str] = "Alignment status record"
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


class ApprovalLog(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Approval log' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ApprovalLogRecord"
    _name: ClassVar[str] = "Approval log"
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


class ApprovalRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Approval record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ApprovalRecordRecord"
    _name: ClassVar[str] = "Approval record"
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


class ApprovalStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Approval status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ApprovalStatusIndicator"
    _name: ClassVar[str] = "Approval status record"
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


class AssessmentCompletenessRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Assessment completeness' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/AssessmentCompletenessIndicator"
    )
    _name: ClassVar[str] = "Assessment completeness record"
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


class AssessmentRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Assessment record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AssessmentRecordRecord"
    _name: ClassVar[str] = "Assessment record"
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


class AssessmentReport(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Assessment report' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AssessmentReportRecord"
    _name: ClassVar[str] = "Assessment report"
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


class AssessmentResult(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Assessment result' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AssessmentResultRecord"
    _name: ClassVar[str] = "Assessment result"
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


class AssetConditionRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Asset condition' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AssetConditionIndicator"
    _name: ClassVar[str] = "Asset condition record"
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


class AssetRegistryUpdate(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Asset registry update' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AssetRegistryUpdateRecord"
    _name: ClassVar[str] = "Asset registry update"
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


class AttendanceLog(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Attendance log' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AttendanceLogRecord"
    _name: ClassVar[str] = "Attendance log"
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


class AttendanceRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Attendance record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AttendanceRecordRecord"
    _name: ClassVar[str] = "Attendance record"
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


class AttendanceStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Attendance status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AttendanceStatusIndicator"
    _name: ClassVar[str] = "Attendance status record"
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


class AuditTrail(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Audit trail' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AuditTrailRecord"
    _name: ClassVar[str] = "Audit trail"
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


class BriefingNote(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Briefing note' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/BriefingNoteRecord"
    _name: ClassVar[str] = "Briefing note"
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


class BudgetRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Budget record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/BudgetRecordRecord"
    _name: ClassVar[str] = "Budget record"
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


class BudgetStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Budget status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/BudgetStatusIndicator"
    _name: ClassVar[str] = "Budget status record"
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


class CalendarRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Calendar record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CalendarRecordRecord"
    _name: ClassVar[str] = "Calendar record"
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


class ClearanceStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Clearance status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ClearanceStatusIndicator"
    _name: ClassVar[str] = "Clearance status record"
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


class CommsRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Comms record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CommsRecordRecord"
    _name: ClassVar[str] = "Comms record"
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


class CompetencyLevelRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Competency level' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CompetencyLevelIndicator"
    _name: ClassVar[str] = "Competency level record"
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


class CompetencyRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Competency record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CompetencyRecordRecord"
    _name: ClassVar[str] = "Competency record"
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


class CompletionRateRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Completion rate' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CompletionRateIndicator"
    _name: ClassVar[str] = "Completion rate record"
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


class ComplianceStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Compliance status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ComplianceStatusIndicator"
    _name: ClassVar[str] = "Compliance status record"
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


class ConfidenceScoreRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Confidence score' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ConfidenceScoreIndicator"
    _name: ClassVar[str] = "Confidence score record"
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


class ConfigurationLog(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Configuration log' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ConfigurationLogRecord"
    _name: ClassVar[str] = "Configuration log"
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


class ContactRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Contact record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ContactRecordRecord"
    _name: ClassVar[str] = "Contact record"
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


class ContractStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Contract status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ContractStatusIndicator"
    _name: ClassVar[str] = "Contract status record"
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


class CoverageRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Coverage' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CoverageIndicator"
    _name: ClassVar[str] = "Coverage record"
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


class CoverageRatioRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Coverage ratio' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CoverageRatioIndicator"
    _name: ClassVar[str] = "Coverage ratio record"
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


class CycleTimeRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Cycle time' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CycleTimeIndicator"
    _name: ClassVar[str] = "Cycle time record"
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


class DecisionLog(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Decision log' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/DecisionLogRecord"
    _name: ClassVar[str] = "Decision log"
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


class DeliveryStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Delivery status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/DeliveryStatusIndicator"
    _name: ClassVar[str] = "Delivery status record"
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


class DispatchRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Dispatch record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/DispatchRecordRecord"
    _name: ClassVar[str] = "Dispatch record"
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


class DowntimeRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Downtime' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/DowntimeIndicator"
    _name: ClassVar[str] = "Downtime record"
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


class EngagementLog(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Engagement log' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/EngagementLogRecord"
    _name: ClassVar[str] = "Engagement log"
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


class EngagementStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Engagement status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/EngagementStatusIndicator"
    _name: ClassVar[str] = "Engagement status record"
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


class EvaluationRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Evaluation record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/EvaluationRecordRecord"
    _name: ClassVar[str] = "Evaluation record"
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


class EvidenceRegister(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Evidence register' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/EvidenceRegisterRecord"
    _name: ClassVar[str] = "Evidence register"
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


class ExceptionRateRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Exception rate' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ExceptionRateIndicator"
    _name: ClassVar[str] = "Exception rate record"
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


class FalsepositiveRateRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'False-positive rate' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/FalsePositiveRateIndicator"
    _name: ClassVar[str] = "False-positive rate record"
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


class FindingsSeverityRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Findings severity' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/FindingsSeverityIndicator"
    _name: ClassVar[str] = "Findings severity record"
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


class FleetSystemPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'Fleet system'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/FleetSystemHost"
    _name: ClassVar[str] = "Fleet system physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: Annotated[list[FleetSystemSoftware | URIRef | str], Field()] | None = (
        None
    )


class ForecastConfidenceRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Forecast confidence' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/ForecastConfidenceIndicator"
    )
    _name: ClassVar[str] = "Forecast confidence record"
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


class ForecastRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Forecast record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ForecastRecordRecord"
    _name: ClassVar[str] = "Forecast record"
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


class GapCoverageRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Gap coverage' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/GapCoverageIndicator"
    _name: ClassVar[str] = "Gap coverage record"
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


class GapRegister(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Gap register' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/GapRegisterRecord"
    _name: ClassVar[str] = "Gap register"
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


class HRRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'HR record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/HRRecordRecord"
    _name: ClassVar[str] = "HR record"
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


class HRSystemPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'HR system'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/HRSystemHost"
    _name: ClassVar[str] = "HR system physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: Annotated[list[HRSystemSoftware | URIRef | str], Field()] | None = None


class IdentitySystemPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'Identity system'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/IdentitySystemHost"
    _name: ClassVar[str] = "Identity system physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: (
        Annotated[list[IdentitySystemSoftware | URIRef | str], Field()] | None
    ) = None


class IncidentRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Incident record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/IncidentRecordRecord"
    _name: ClassVar[str] = "Incident record"
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


class InventoryRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Inventory record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/InventoryRecordRecord"
    _name: ClassVar[str] = "Inventory record"
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


class LearningSystemPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'Learning system'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/LearningSystemHost"
    _name: ClassVar[str] = "Learning system physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: (
        Annotated[list[LearningSystemSoftware | URIRef | str], Field()] | None
    ) = None


class LeastprivilegeComplianceRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Least-privilege compliance' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/LeastPrivilegeComplianceIndicator"
    )
    _name: ClassVar[str] = "Least-privilege compliance record"
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


class LeaveRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Leave record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/LeaveRecordRecord"
    _name: ClassVar[str] = "Leave record"
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


class MaintenanceRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Maintenance record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/MaintenanceRecordRecord"
    _name: ClassVar[str] = "Maintenance record"
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


class MessageLog(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Message log' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/MessageLogRecord"
    _name: ClassVar[str] = "Message log"
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


class MessagingSystemPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'Messaging system'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/MessagingSystemHost"
    _name: ClassVar[str] = "Messaging system physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: (
        Annotated[list[MessagingSystemSoftware | URIRef | str], Field()] | None
    ) = None


class OffboardingChecklist(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Offboarding checklist' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/OffboardingChecklistRecord"
    _name: ClassVar[str] = "Offboarding checklist"
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


class OntimeRateRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'On-time rate' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/OnTimeRateIndicator"
    _name: ClassVar[str] = "On-time rate record"
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


class OnboardingStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Onboarding status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/OnboardingStatusIndicator"
    _name: ClassVar[str] = "Onboarding status record"
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


class OracleERPPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'Oracle ERP'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/OracleERPHost"
    _name: ClassVar[str] = "Oracle ERP physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: Annotated[list[OracleERPSoftware | URIRef | str], Field()] | None = (
        None
    )


class OrderStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Order status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/OrderStatusIndicator"
    _name: ClassVar[str] = "Order status record"
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


class PartnerRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Partner record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PartnerRecordRecord"
    _name: ClassVar[str] = "Partner record"
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


class PassRateRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Pass rate' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PassRateIndicator"
    _name: ClassVar[str] = "Pass rate record"
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


class PaymentRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Payment record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PaymentRecordRecord"
    _name: ClassVar[str] = "Payment record"
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


class PaymentStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Payment status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PaymentStatusIndicator"
    _name: ClassVar[str] = "Payment status record"
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


class PenetrationReport(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Penetration report' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PenetrationReportRecord"
    _name: ClassVar[str] = "Penetration report"
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


class PlanMaturityRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Plan maturity' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PlanMaturityIndicator"
    _name: ClassVar[str] = "Plan maturity record"
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


class PlanningSystemPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'Planning system'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PlanningSystemHost"
    _name: ClassVar[str] = "Planning system physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: (
        Annotated[list[PlanningSystemSoftware | URIRef | str], Field()] | None
    ) = None


class PolicyComplianceRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Policy compliance' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PolicyComplianceIndicator"
    _name: ClassVar[str] = "Policy compliance record"
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


class ProcurementRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Procurement record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ProcurementRecordRecord"
    _name: ClassVar[str] = "Procurement record"
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


class ProgrammePlan(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Programme plan' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ProgrammePlanRecord"
    _name: ClassVar[str] = "Programme plan"
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


class ProvisioningRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Provisioning record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ProvisioningRecordRecord"
    _name: ClassVar[str] = "Provisioning record"
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


class ProvisioningStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Provisioning status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/ProvisioningStatusIndicator"
    )
    _name: ClassVar[str] = "Provisioning status record"
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


class ReasoningChain(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Reasoning chain' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ReasoningChainRecord"
    _name: ClassVar[str] = "Reasoning chain"
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


class RegistryCompletenessRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Registry completeness' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/RegistryCompletenessIndicator"
    )
    _name: ClassVar[str] = "Registry completeness record"
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


class RemediationLog(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Remediation log' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/RemediationLogRecord"
    _name: ClassVar[str] = "Remediation log"
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


class ResolutionTimeRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Resolution time' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ResolutionTimeIndicator"
    _name: ClassVar[str] = "Resolution time record"
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


class RighttoauditInPlaceRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Right-to-audit in place' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/RightToAuditInPlaceIndicator"
    )
    _name: ClassVar[str] = "Right-to-audit in place record"
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


class RighttoauditRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Right-to-audit' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/RightToAuditIndicator"
    _name: ClassVar[str] = "Right-to-audit record"
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


class RiskScoreRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Risk score' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/RiskScoreIndicator"
    _name: ClassVar[str] = "Risk score record"
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


class RoadmapDocument(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Roadmap document' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/RoadmapDocumentRecord"
    _name: ClassVar[str] = "Roadmap document"
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


class RotationPlan(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Rotation plan' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/RotationPlanRecord"
    _name: ClassVar[str] = "Rotation plan"
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


class SLAAdherenceRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'SLA adherence' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SLAAdherenceIndicator"
    _name: ClassVar[str] = "SLA adherence record"
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


class SLAOnApprovalRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'SLA on approval' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SLAOnApprovalIndicator"
    _name: ClassVar[str] = "SLA on approval record"
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


class ScheduleFillRateRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Schedule fill rate' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ScheduleFillRateIndicator"
    _name: ClassVar[str] = "Schedule fill rate record"
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


class ScheduleRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Schedule record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ScheduleRecordRecord"
    _name: ClassVar[str] = "Schedule record"
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


class SchedulingSystemPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'Scheduling system'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SchedulingSystemHost"
    _name: ClassVar[str] = "Scheduling system physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: (
        Annotated[list[SchedulingSystemSoftware | URIRef | str], Field()] | None
    ) = None


class ScoreRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Score' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ScoreIndicator"
    _name: ClassVar[str] = "Score record"
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


class ScreeningRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Screening record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ScreeningRecordRecord"
    _name: ClassVar[str] = "Screening record"
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


class ScreeningSystemPhysicalHost(ABIPhysicalComputingSystem, RDFEntity):
    """
    Physical computing equipment carrying 'Screening system'. Proposed bearer mapping; no particular machine or deployment is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ScreeningSystemHost"
    _name: ClassVar[str] = "Screening system physical host"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101"}

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
    bFO_0000101: (
        Annotated[list[ScreeningSystemSoftware | URIRef | str], Field()] | None
    ) = None


class SeverityRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Severity' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SeverityIndicator"
    _name: ClassVar[str] = "Severity record"
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


class SignalRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Signal record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SignalRecordRecord"
    _name: ClassVar[str] = "Signal record"
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


class SourceChain(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Source chain' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SourceChainRecord"
    _name: ClassVar[str] = "Source chain"
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


class StockLevelRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Stock level' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/StockLevelIndicator"
    _name: ClassVar[str] = "Stock level record"
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


class TimelinessRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Timeliness' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/TimelinessIndicator"
    _name: ClassVar[str] = "Timeliness record"
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


class TrailCompletenessRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Trail completeness' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/TrailCompletenessIndicator"
    _name: ClassVar[str] = "Trail completeness record"
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


class TrainingRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Training record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/TrainingRecordRecord"
    _name: ClassVar[str] = "Training record"
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


class TripLog(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Trip log' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/TripLogRecord"
    _name: ClassVar[str] = "Trip log"
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


class UptimeRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Uptime' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/UptimeIndicator"
    _name: ClassVar[str] = "Uptime record"
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


class VarianceRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Variance' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/VarianceIndicator"
    _name: ClassVar[str] = "Variance record"
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


class VehicleStatusRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Vehicle status' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/VehicleStatusIndicator"
    _name: ClassVar[str] = "Vehicle status record"
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


class VendorCatalogue(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Vendor catalogue' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/VendorCatalogueRecord"
    _name: ClassVar[str] = "Vendor catalogue"
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


class VendorContract(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Vendor contract' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/VendorContractRecord"
    _name: ClassVar[str] = "Vendor contract"
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


class VendorPerformanceScoreRecord(ABIIndicatorRecord, RDFEntity):
    """
    Information described as 'Vendor performance score' under HOWITIS in the simulated ledger.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/VendorPerformanceScoreIndicator"
    )
    _name: ClassVar[str] = "Vendor performance score record"
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


class WorkorderRecord(ABIEvidenceRecord, RDFEntity):
    """
    Information described as 'Work-order record' under HOWWEKNOW in the simulated ledger.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/WorkOrderRecordRecord"
    _name: ClassVar[str] = "Work-order record"
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


class AINAgentsSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'AIN agents' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AINAgentsSoftware"
    _name: ClassVar[str] = "AIN agents software"
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


class AINFinanceAgentSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'AIN finance agent' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AINFinanceAgentSoftware"
    _name: ClassVar[str] = "AIN finance agent software"
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


class AINGapdetectionAgentSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'AIN gap-detection agent' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/AINGapDetectionAgentSoftware"
    )
    _name: ClassVar[str] = "AIN gap-detection agent software"
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


class AINIntelligenceAgentSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'AIN intelligence agent' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/AINIntelligenceAgentSoftware"
    )
    _name: ClassVar[str] = "AIN intelligence agent software"
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


class AINPredictiveAgentSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'AIN predictive agent' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AINPredictiveAgentSoftware"
    _name: ClassVar[str] = "AIN predictive agent software"
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


class AINProcurementAgentSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'AIN procurement agent' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/AINProcurementAgentSoftware"
    )
    _name: ClassVar[str] = "AIN procurement agent software"
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


class AINSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'AIN' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AINSoftware"
    _name: ClassVar[str] = "AIN software"
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


class AnalystParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Analyst' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AnalystParticipant"
    _name: ClassVar[str] = "Analyst participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[AnalystRole | URIRef | str], Field()] | None = None


class ApproverParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Approver' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ApproverParticipant"
    _name: ClassVar[str] = "Approver participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[ApproverRole | URIRef | str], Field()] | None = None


class AssessorParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Assessor' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AssessorParticipant"
    _name: ClassVar[str] = "Assessor participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[AssessorRole | URIRef | str], Field()] | None = None


class AssetOwnerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Asset owner' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AssetOwnerParticipant"
    _name: ClassVar[str] = "Asset owner participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[AssetOwnerRole | URIRef | str], Field()] | None = None


class AuditorParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Auditor' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/AuditorParticipant"
    _name: ClassVar[str] = "Auditor participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[AuditorRole | URIRef | str], Field()] | None = None


class BudgetOwnerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Budget owner' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/BudgetOwnerParticipant"
    _name: ClassVar[str] = "Budget owner participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[BudgetOwnerRole | URIRef | str], Field()] | None = None


class CommsOfficerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Comms officer' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CommsOfficerParticipant"
    _name: ClassVar[str] = "Comms officer participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[CommsOfficerRole | URIRef | str], Field()] | None = None


class ContractManagerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Contract manager' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ContractManagerParticipant"
    _name: ClassVar[str] = "Contract manager participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[ContractManagerRole | URIRef | str], Field()] | None = (
        None
    )


class CyberTeamParticipant(ABIPhysicalTeam, RDFEntity):
    """
    The material participant referred to as 'Cyber team' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/CyberTeamParticipant"
    _name: ClassVar[str] = "Cyber team participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[CyberTeamRole | URIRef | str], Field()] | None = None


class DispatcherParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Dispatcher' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/DispatcherParticipant"
    _name: ClassVar[str] = "Dispatcher participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[DispatcherRole | URIRef | str], Field()] | None = None


class DriverParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Driver' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/DriverParticipant"
    _name: ClassVar[str] = "Driver participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[DriverRole | URIRef | str], Field()] | None = None


class ExecutivePrincipalParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Executive principal' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/ExecutivePrincipalParticipant"
    )
    _name: ClassVar[str] = "Executive principal participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: (
        Annotated[list[ExecutivePrincipalRole | URIRef | str], Field()] | None
    ) = None


class FieldTeamParticipant(ABIPhysicalTeam, RDFEntity):
    """
    The material participant referred to as 'Field team' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/FieldTeamParticipant"
    _name: ClassVar[str] = "Field team participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[FieldTeamRole | URIRef | str], Field()] | None = None


class FinanceOfficerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Finance officer' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/FinanceOfficerParticipant"
    _name: ClassVar[str] = "Finance officer participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[FinanceOfficerRole | URIRef | str], Field()] | None = (
        None
    )


class FleetSystemSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'Fleet system' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/FleetSystemSoftware"
    _name: ClassVar[str] = "Fleet system software"
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


class FunctionLeadsParticipant(ABIPhysicalTeam, RDFEntity):
    """
    The material participant referred to as 'Function leads' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/FunctionLeadsParticipant"
    _name: ClassVar[str] = "Function leads participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[FunctionLeadsRole | URIRef | str], Field()] | None = (
        None
    )


class HROfficerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'HR officer' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/HROfficerParticipant"
    _name: ClassVar[str] = "HR officer participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[HROfficerRole | URIRef | str], Field()] | None = None


class HRSystemSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'HR system' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/HRSystemSoftware"
    _name: ClassVar[str] = "HR system software"
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


class ITAdminParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'IT admin' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ITAdminParticipant"
    _name: ClassVar[str] = "IT admin participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[ITAdminRole | URIRef | str], Field()] | None = None


class ITEngineerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'IT engineer' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ITEngineerParticipant"
    _name: ClassVar[str] = "IT engineer participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[ITEngineerRole | URIRef | str], Field()] | None = None


class IdentitySystemSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'Identity system' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/IdentitySystemSoftware"
    _name: ClassVar[str] = "Identity system software"
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


class LearningSystemSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'Learning system' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/LearningSystemSoftware"
    _name: ClassVar[str] = "Learning system software"
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


class LineManagerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Line manager' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/LineManagerParticipant"
    _name: ClassVar[str] = "Line manager participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[LineManagerRole | URIRef | str], Field()] | None = None


class LineManagersParticipant(ABIPhysicalTeam, RDFEntity):
    """
    The material participant referred to as 'Line managers' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/LineManagersParticipant"
    _name: ClassVar[str] = "Line managers participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[LineManagersRole | URIRef | str], Field()] | None = None


class MaintenanceTeamParticipant(ABIPhysicalTeam, RDFEntity):
    """
    The material participant referred to as 'Maintenance team' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/MaintenanceTeamParticipant"
    _name: ClassVar[str] = "Maintenance team participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[MaintenanceTeamRole | URIRef | str], Field()] | None = (
        None
    )


class MessagingSystemSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'Messaging system' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/MessagingSystemSoftware"
    _name: ClassVar[str] = "Messaging system software"
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


class NewJoinerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'New joiner' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/NewJoinerParticipant"
    _name: ClassVar[str] = "New joiner participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[NewJoinerRole | URIRef | str], Field()] | None = None


class OperationsLeadParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Operations lead' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/OperationsLeadParticipant"
    _name: ClassVar[str] = "Operations lead participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[OperationsLeadRole | URIRef | str], Field()] | None = (
        None
    )


class OracleERPSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'Oracle ERP' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/OracleERPSoftware"
    _name: ClassVar[str] = "Oracle ERP software"
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


class PartnerOrganisationPersonnel(ABIPhysicalTeam, RDFEntity):
    """
    The material participant referred to as 'Partner organisation' in the ledger. For organisations this denotes the people acting on its behalf, not its legal identity.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/PartnerOrganisationParticipant"
    )
    _name: ClassVar[str] = "Partner organisation personnel"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: (
        Annotated[list[PartnerOrganisationRole | URIRef | str], Field()] | None
    ) = None


class PlannerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Planner' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PlannerParticipant"
    _name: ClassVar[str] = "Planner participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[PlannerRole | URIRef | str], Field()] | None = None


class PlanningSystemSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'Planning system' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/PlanningSystemSoftware"
    _name: ClassVar[str] = "Planning system software"
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


class ProcurementOfficerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Procurement officer' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/ProcurementOfficerParticipant"
    )
    _name: ClassVar[str] = "Procurement officer participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: (
        Annotated[list[ProcurementOfficerRole | URIRef | str], Field()] | None
    ) = None


class ProgrammeOwnerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Programme owner' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ProgrammeOwnerParticipant"
    _name: ClassVar[str] = "Programme owner participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[ProgrammeOwnerRole | URIRef | str], Field()] | None = (
        None
    )


class RequesterParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Requester' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/RequesterParticipant"
    _name: ClassVar[str] = "Requester participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[RequesterRole | URIRef | str], Field()] | None = None


class ResourceOwnersParticipant(ABIPhysicalTeam, RDFEntity):
    """
    The material participant referred to as 'Resource owners' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ResourceOwnersParticipant"
    _name: ClassVar[str] = "Resource owners participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[ResourceOwnersRole | URIRef | str], Field()] | None = (
        None
    )


class ResponseTeamParticipant(ABIPhysicalTeam, RDFEntity):
    """
    The material participant referred to as 'Response team' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ResponseTeamParticipant"
    _name: ClassVar[str] = "Response team participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[ResponseTeamRole | URIRef | str], Field()] | None = None


class RiskOwnerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Risk owner' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/RiskOwnerParticipant"
    _name: ClassVar[str] = "Risk owner participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[RiskOwnerRole | URIRef | str], Field()] | None = None


class S1LeadParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'S1 lead' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1LeadParticipant"
    _name: ClassVar[str] = "S1 lead participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[S1LeadRole | URIRef | str], Field()] | None = None


class S2OfficerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'S2 officer' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2OfficerParticipant"
    _name: ClassVar[str] = "S2 officer participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[S2OfficerRole | URIRef | str], Field()] | None = None


class S3SchedulerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'S3 scheduler' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3SchedulerParticipant"
    _name: ClassVar[str] = "S3 scheduler participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[S3SchedulerRole | URIRef | str], Field()] | None = None


class S4ControllerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'S4 controller' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4ControllerParticipant"
    _name: ClassVar[str] = "S4 controller participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[S4ControllerRole | URIRef | str], Field()] | None = None


class S5LeadParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'S5 lead' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5LeadParticipant"
    _name: ClassVar[str] = "S5 lead participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[S5LeadRole | URIRef | str], Field()] | None = None


class S5PlannerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'S5 planner' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5PlannerParticipant"
    _name: ClassVar[str] = "S5 planner participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[S5PlannerRole | URIRef | str], Field()] | None = None


class S7LeadParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'S7 lead' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7LeadParticipant"
    _name: ClassVar[str] = "S7 lead participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[S7LeadRole | URIRef | str], Field()] | None = None


class S8ApproverParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'S8 approver' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8ApproverParticipant"
    _name: ClassVar[str] = "S8 approver participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[S8ApproverRole | URIRef | str], Field()] | None = None


class S9LeadParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'S9 lead' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9LeadParticipant"
    _name: ClassVar[str] = "S9 lead participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[S9LeadRole | URIRef | str], Field()] | None = None


class S9OfficerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'S9 officer' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9OfficerParticipant"
    _name: ClassVar[str] = "S9 officer participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[S9OfficerRole | URIRef | str], Field()] | None = None


class SchedulingSystemSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'Scheduling system' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SchedulingSystemSoftware"
    _name: ClassVar[str] = "Scheduling system software"
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


class ScreeningSystemSoftware(ABISoftware, RDFEntity):
    """
    Software referred to as 'Screening system' in the ledger. Its material deployment is unspecified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ScreeningSystemSoftware"
    _name: ClassVar[str] = "Screening system software"
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


class SecurityOfficerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Security officer' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SecurityOfficerParticipant"
    _name: ClassVar[str] = "Security officer participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[SecurityOfficerRole | URIRef | str], Field()] | None = (
        None
    )


class SecurityParticipant(ABIPhysicalTeam, RDFEntity):
    """
    The material participant referred to as 'Security' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SecurityParticipant"
    _name: ClassVar[str] = "Security participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[SecurityRole | URIRef | str], Field()] | None = None


class StaffMemberParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Staff member' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/StaffMemberParticipant"
    _name: ClassVar[str] = "Staff member participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[StaffMemberRole | URIRef | str], Field()] | None = None


class StaffParticipant(ABIPhysicalTeam, RDFEntity):
    """
    The material participant referred to as 'Staff' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/StaffParticipant"
    _name: ClassVar[str] = "Staff participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[StaffRole | URIRef | str], Field()] | None = None


class StoreKeeperParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Store keeper' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/StoreKeeperParticipant"
    _name: ClassVar[str] = "Store keeper participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[StoreKeeperRole | URIRef | str], Field()] | None = None


class SupplierPersonnel(ABIPhysicalTeam, RDFEntity):
    """
    The material participant referred to as 'Supplier' in the ledger. For organisations this denotes the people acting on its behalf, not its legal identity.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SupplierParticipant"
    _name: ClassVar[str] = "Supplier personnel"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[SupplierRole | URIRef | str], Field()] | None = None


class TraineeParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Trainee' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/TraineeParticipant"
    _name: ClassVar[str] = "Trainee participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[TraineeRole | URIRef | str], Field()] | None = None


class TrainerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Trainer' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/TrainerParticipant"
    _name: ClassVar[str] = "Trainer participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[TrainerRole | URIRef | str], Field()] | None = None


class VendorPersonnel(ABIPhysicalTeam, RDFEntity):
    """
    The material participant referred to as 'Vendor' in the ledger. For organisations this denotes the people acting on its behalf, not its legal identity.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/VendorParticipant"
    _name: ClassVar[str] = "Vendor personnel"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[URIRef | VendorRole | str], Field()] | None = None


class WatchOfficerParticipant(ABIHumanParticipant, RDFEntity):
    """
    The material participant referred to as 'Watch officer' in the ledger. Its actual identity is not specified.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/WatchOfficerParticipant"
    _name: ClassVar[str] = "Watch officer participant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

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
    bFO_0000196: Annotated[list[URIRef | WatchOfficerRole | str], Field()] | None = None


class OnboardingTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On hire. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P1Condition1"
    _name: ClassVar[str] = "Onboarding timing condition"
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


class OnboardingObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: A ready, cleared workforce. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P1Objective1"
    _name: ClassVar[str] = "Onboarding objective"
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


class OnboardingSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S1-P1. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P1Specification"
    _name: ClassVar[str] = "Onboarding specification"
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


class AccessProvisioningTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On role change. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P2Condition1"
    _name: ClassVar[str] = "Access provisioning timing condition"
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


class AccessProvisioningObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Controlled access to systems. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P2Objective1"
    _name: ClassVar[str] = "Access provisioning objective"
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


class AccessProvisioningSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S1-P2. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P2Specification"
    _name: ClassVar[str] = "Access provisioning specification"
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


class RotationPlanningTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Monthly cycle. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P3Condition1"
    _name: ClassVar[str] = "Rotation planning timing condition"
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


class RotationPlanningObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Continuity of cover for VIP operations. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P3Objective1"
    _name: ClassVar[str] = "Rotation planning objective"
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


class RotationPlanningSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S1-P3. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P3Specification"
    _name: ClassVar[str] = "Rotation planning specification"
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


class AttendanceAndLeaveTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Daily; on request. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P4Condition1"
    _name: ClassVar[str] = "Attendance and leave timing condition"
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


class AttendanceAndLeaveObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Accurate manpower picture. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P4Objective1"
    _name: ClassVar[str] = "Attendance and leave objective"
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


class AttendanceAndLeaveSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S1-P4. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P4Specification"
    _name: ClassVar[str] = "Attendance and leave specification"
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


class OffboardingTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On departure. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P5Condition1"
    _name: ClassVar[str] = "Offboarding timing condition"
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


class OffboardingObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: No residual access after departure. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P5Objective1"
    _name: ClassVar[str] = "Offboarding objective"
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


class OffboardingSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S1-P5. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S1P5Specification"
    _name: ClassVar[str] = "Offboarding specification"
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


class ExecutiveBriefingTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Daily; before movements. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P1Condition1"
    _name: ClassVar[str] = "Executive briefing timing condition"
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


class ExecutiveBriefingObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Informed, timely decisions. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P1Objective1"
    _name: ClassVar[str] = "Executive briefing objective"
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


class ExecutiveBriefingSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S2-P1. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P1Specification"
    _name: ClassVar[str] = "Executive briefing specification"
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


class SignalSynthesisTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Continuous. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P2Condition1"
    _name: ClassVar[str] = "Signal synthesis timing condition"
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


class SignalSynthesisObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Early awareness before events. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P2Objective1"
    _name: ClassVar[str] = "Signal synthesis objective"
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


class SignalSynthesisSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S2-P2. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P2Specification"
    _name: ClassVar[str] = "Signal synthesis specification"
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


class RiskAndContextAssessmentTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On request; per cycle. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P3Condition1"
    _name: ClassVar[str] = "Risk and context assessment timing condition"
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


class RiskAndContextAssessmentObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Anticipatory risk posture. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P3Objective1"
    _name: ClassVar[str] = "Risk and context assessment objective"
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


class RiskAndContextAssessmentSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S2-P3. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P3Specification"
    _name: ClassVar[str] = "Risk and context assessment specification"
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


class SecurityScreeningTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On access request. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P4Condition1"
    _name: ClassVar[str] = "Security screening timing condition"
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


class SecurityScreeningObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Trusted access to sensitive operations. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P4Objective1"
    _name: ClassVar[str] = "Security screening objective"
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


class SecurityScreeningSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S2-P4. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P4Specification"
    _name: ClassVar[str] = "Security screening specification"
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


class WatchAndAlertingTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Continuous; < 2 min alert. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P5Condition1"
    _name: ClassVar[str] = "Watch and alerting timing condition"
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


class WatchAndAlertingObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Act inside the decision window. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P5Objective1"
    _name: ClassVar[str] = "Watch and alerting objective"
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


class WatchAndAlertingSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S2-P5. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S2P5Specification"
    _name: ClassVar[str] = "Watch and alerting specification"
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


class WorkorderProcessingTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On request. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P1Condition1"
    _name: ClassVar[str] = "Work-order processing timing condition"
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


class WorkorderProcessingObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Facilities kept mission-ready. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P1Objective1"
    _name: ClassVar[str] = "Work-order processing objective"
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


class WorkorderProcessingSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S3-P1. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P1Specification"
    _name: ClassVar[str] = "Work-order processing specification"
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


class SchedulingTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Weekly; on change. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P2Condition1"
    _name: ClassVar[str] = "Scheduling timing condition"
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


class SchedulingObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Efficient use of people and assets. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P2Objective1"
    _name: ClassVar[str] = "Scheduling objective"
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


class SchedulingSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S3-P2. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P2Specification"
    _name: ClassVar[str] = "Scheduling specification"
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


class FleetDispatchTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On demand; time-of-day windows. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P3Condition1"
    _name: ClassVar[str] = "Fleet dispatch timing condition"
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


class FleetDispatchObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Reliable VIP movement. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P3Objective1"
    _name: ClassVar[str] = "Fleet dispatch objective"
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


class FleetDispatchSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S3-P3. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P3Specification"
    _name: ClassVar[str] = "Fleet dispatch specification"
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


class MaintenanceTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Scheduled; on fault. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P4Condition1"
    _name: ClassVar[str] = "Maintenance timing condition"
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


class MaintenanceObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Assets available when needed. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P4Objective1"
    _name: ClassVar[str] = "Maintenance objective"
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


class MaintenanceSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S3-P4. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P4Specification"
    _name: ClassVar[str] = "Maintenance specification"
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


class IncidentResponseTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On incident; < 1 h. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P5Condition1"
    _name: ClassVar[str] = "Incident response timing condition"
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


class IncidentResponseObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Continuity under disruption. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P5Objective1"
    _name: ClassVar[str] = "Incident response objective"
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


class IncidentResponseSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S3-P5. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S3P5Specification"
    _name: ClassVar[str] = "Incident response specification"
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


class VendorEvaluationTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On new requirement. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P1Condition1"
    _name: ClassVar[str] = "Vendor evaluation timing condition"
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


class VendorEvaluationObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Best-value, sovereign-fit sourcing. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P1Objective1"
    _name: ClassVar[str] = "Vendor evaluation objective"
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


class VendorEvaluationSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S4-P1. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P1Specification"
    _name: ClassVar[str] = "Vendor evaluation specification"
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


class StraightthroughProcurementTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On requisition. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P2Condition1"
    _name: ClassVar[str] = "Straight-through procurement timing condition"
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


class StraightthroughProcurementObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Fast, compliant purchasing. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P2Objective1"
    _name: ClassVar[str] = "Straight-through procurement objective"
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


class StraightthroughProcurementSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S4-P2. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P2Specification"
    _name: ClassVar[str] = "Straight-through procurement specification"
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


class StockAndInventoryTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Periodic; on threshold. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P3Condition1"
    _name: ClassVar[str] = "Stock and inventory timing condition"
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


class StockAndInventoryObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: No stockouts on critical items. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P3Objective1"
    _name: ClassVar[str] = "Stock and inventory objective"
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


class StockAndInventorySpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S4-P3. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P3Specification"
    _name: ClassVar[str] = "Stock and inventory specification"
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


class AssetRegistryTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On acquisition; on change. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P4Condition1"
    _name: ClassVar[str] = "Asset registry timing condition"
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


class AssetRegistryObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Full accountability of assets. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P4Objective1"
    _name: ClassVar[str] = "Asset registry objective"
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


class AssetRegistrySpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S4-P4. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P4Specification"
    _name: ClassVar[str] = "Asset registry specification"
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


class SupplierOnboardingTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On selection. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P5Condition1"
    _name: ClassVar[str] = "Supplier onboarding timing condition"
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


class SupplierOnboardingObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: A governed supplier base. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P5Objective1"
    _name: ClassVar[str] = "Supplier onboarding objective"
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


class SupplierOnboardingSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S4-P5. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S4P5Specification"
    _name: ClassVar[str] = "Supplier onboarding specification"
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


class ProgrammePlanningTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Per programme cycle. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P1Condition1"
    _name: ClassVar[str] = "Programme planning timing condition"
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


class ProgrammePlanningObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Objectives translated into deliverable work. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P1Objective1"
    _name: ClassVar[str] = "Programme planning objective"
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


class ProgrammePlanningSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S5-P1. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P1Specification"
    _name: ClassVar[str] = "Programme planning specification"
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


class ForecastingTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Rolling; per cycle. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P2Condition1"
    _name: ClassVar[str] = "Forecasting timing condition"
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


class ForecastingObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Anticipation of demand and risk. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P2Objective1"
    _name: ClassVar[str] = "Forecasting objective"
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


class ForecastingSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S5-P2. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P2Specification"
    _name: ClassVar[str] = "Forecasting specification"
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


class CapabilityRoadmapTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Annual; on review. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P3Condition1"
    _name: ClassVar[str] = "Capability roadmap timing condition"
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


class CapabilityRoadmapObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Capabilities aligned to the North Stars. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P3Objective1"
    _name: ClassVar[str] = "Capability roadmap objective"
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


class CapabilityRoadmapSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S5-P3. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S5P3Specification"
    _name: ClassVar[str] = "Capability roadmap specification"
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


class ITProvisioningTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On request. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P1Condition1"
    _name: ClassVar[str] = "IT provisioning timing condition"
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


class ITProvisioningObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: A secured, capable IT estate. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P1Objective1"
    _name: ClassVar[str] = "IT provisioning objective"
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


class ITProvisioningSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S6-P1. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P1Specification"
    _name: ClassVar[str] = "IT provisioning specification"
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


class CyberPostureblueredTeamTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Continuous; per test cycle. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P2Condition1"
    _name: ClassVar[str] = "Cyber posture (blue/red team) timing condition"
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


class CyberPostureblueredTeamObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: A defensible fortress. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P2Objective1"
    _name: ClassVar[str] = "Cyber posture (blue/red team) objective"
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


class CyberPostureblueredTeamSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S6-P2. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P2Specification"
    _name: ClassVar[str] = "Cyber posture (blue/red team) specification"
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


class CommunicationsAndCalendarTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Continuous. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P3Condition1"
    _name: ClassVar[str] = "Communications and calendar timing condition"
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


class CommunicationsAndCalendarObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Coordinated operations. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P3Objective1"
    _name: ClassVar[str] = "Communications and calendar objective"
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


class CommunicationsAndCalendarSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S6-P3. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S6P3Specification"
    _name: ClassVar[str] = "Communications and calendar specification"
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


class TrainingDeliveryTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Per schedule. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P1Condition1"
    _name: ClassVar[str] = "Training delivery timing condition"
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


class TrainingDeliveryObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: A capable workforce. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P1Objective1"
    _name: ClassVar[str] = "Training delivery objective"
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


class TrainingDeliverySpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S7-P1. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P1Specification"
    _name: ClassVar[str] = "Training delivery specification"
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


class CapabilityDevelopmentTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Per development cycle. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P2Condition1"
    _name: ClassVar[str] = "Capability development timing condition"
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


class CapabilityDevelopmentObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Rising internal capability. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P2Objective1"
    _name: ClassVar[str] = "Capability development objective"
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


class CapabilityDevelopmentSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S7-P2. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P2Specification"
    _name: ClassVar[str] = "Capability development specification"
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


class AssessmentTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Post-course. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P3Condition1"
    _name: ClassVar[str] = "Assessment timing condition"
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


class AssessmentObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Verified competence. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P3Objective1"
    _name: ClassVar[str] = "Assessment objective"
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


class AssessmentSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S7-P3. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S7P3Specification"
    _name: ClassVar[str] = "Assessment specification"
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


class FinanceApprovalChainTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On submission. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P1Condition1"
    _name: ClassVar[str] = "Finance approval chain timing condition"
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


class FinanceApprovalChainObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Controlled, authorised spend. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P1Objective1"
    _name: ClassVar[str] = "Finance approval chain objective"
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


class FinanceApprovalChainSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S8-P1. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P1Specification"
    _name: ClassVar[str] = "Finance approval chain specification"
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


class BudgetManagementTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Per financial cycle. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P2Condition1"
    _name: ClassVar[str] = "Budget management timing condition"
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


class BudgetManagementObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Spend within mandate. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P2Objective1"
    _name: ClassVar[str] = "Budget management objective"
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


class BudgetManagementSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S8-P2. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P2Specification"
    _name: ClassVar[str] = "Budget management specification"
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


class ContractManagementTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On award; per renewal. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P3Condition1"
    _name: ClassVar[str] = "Contract management timing condition"
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


class ContractManagementObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Enforceable, auditable commitments. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P3Objective1"
    _name: ClassVar[str] = "Contract management objective"
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


class ContractManagementSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S8-P3. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P3Specification"
    _name: ClassVar[str] = "Contract management specification"
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


class PaymentsAndExpensesTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On invoice; per run. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P4Condition1"
    _name: ClassVar[str] = "Payments and expenses timing condition"
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


class PaymentsAndExpensesObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Timely, correct disbursement. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P4Objective1"
    _name: ClassVar[str] = "Payments and expenses objective"
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


class PaymentsAndExpensesSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S8-P4. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P4Specification"
    _name: ClassVar[str] = "Payments and expenses specification"
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


class AuditTrailMaintenanceTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Continuous. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P5Condition1"
    _name: ClassVar[str] = "Audit trail maintenance timing condition"
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


class AuditTrailMaintenanceObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Defensible evidence for review. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P5Objective1"
    _name: ClassVar[str] = "Audit trail maintenance objective"
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


class AuditTrailMaintenanceSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S8-P5. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S8P5Specification"
    _name: ClassVar[str] = "Audit trail maintenance specification"
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


class StakeholderEngagementTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Continuous; per engagement. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P1Condition1"
    _name: ClassVar[str] = "Stakeholder engagement timing condition"
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


class StakeholderEngagementObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Trusted external relationships. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P1Objective1"
    _name: ClassVar[str] = "Stakeholder engagement objective"
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


class StakeholderEngagementSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S9-P1. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P1Specification"
    _name: ClassVar[str] = "Stakeholder engagement specification"
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


class PartnerCoordinationTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: Per programme. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P2Condition1"
    _name: ClassVar[str] = "Partner coordination timing condition"
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


class PartnerCoordinationObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Effective civil-military cooperation. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P2Objective1"
    _name: ClassVar[str] = "Partner coordination objective"
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


class PartnerCoordinationSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S9-P2. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P2Specification"
    _name: ClassVar[str] = "Partner coordination specification"
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


class PublicAndCommunicationsTimingCondition(ABIExecutionCondition, RDFEntity):
    """
    Ledger trigger/cadence/target: On event. No occurrence or achieved timing is asserted.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P3Condition1"
    _name: ClassVar[str] = "Public and communications timing condition"
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


class PublicAndCommunicationsObjective(ABIObjectiveSpecification, RDFEntity):
    """
    Intended outcome: Consistent external messaging. This is an objective specification, not a role or a guaranteed result.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P3Objective1"
    _name: ClassVar[str] = "Public and communications objective"
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


class PublicAndCommunicationsSpecification(ABIProcessSpecification, RDFEntity):
    """
    The simulated ledger specification for S9-P3. It describes a possible process, not an executed run.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/S9P3Specification"
    _name: ClassVar[str] = "Public and communications specification"
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


# Rebuild models to resolve forward references
ABIExecutionInterval.model_rebuild()
ABIExecutionRole.model_rebuild()
ABIProcessStep.model_rebuild()
S1PersonnelProcesses.model_rebuild()
S2IntelligenceProcesses.model_rebuild()
S3OperationsProcesses.model_rebuild()
S4LogisticsProcesses.model_rebuild()
S5PlansProcesses.model_rebuild()
S6SignalProcesses.model_rebuild()
S7TrainingProcesses.model_rebuild()
S8FinanceProcesses.model_rebuild()
S9ExternalAffairsProcesses.model_rebuild()
AnalystRole.model_rebuild()
ApproverRole.model_rebuild()
AssessorRole.model_rebuild()
AssetOwnerRole.model_rebuild()
AuditorRole.model_rebuild()
BudgetOwnerRole.model_rebuild()
CommsOfficerRole.model_rebuild()
ContractManagerRole.model_rebuild()
CyberTeamRole.model_rebuild()
DispatcherRole.model_rebuild()
DriverRole.model_rebuild()
ExecutivePrincipalRole.model_rebuild()
FieldTeamRole.model_rebuild()
FinanceOfficerRole.model_rebuild()
FunctionLeadsRole.model_rebuild()
HROfficerRole.model_rebuild()
ITAdminRole.model_rebuild()
ITEngineerRole.model_rebuild()
LineManagerRole.model_rebuild()
LineManagersRole.model_rebuild()
MaintenanceTeamRole.model_rebuild()
NewJoinerRole.model_rebuild()
OperationsLeadRole.model_rebuild()
PartnerOrganisationRole.model_rebuild()
PlannerRole.model_rebuild()
ProcurementOfficerRole.model_rebuild()
ProgrammeOwnerRole.model_rebuild()
RequesterRole.model_rebuild()
ResourceOwnersRole.model_rebuild()
ResponseTeamRole.model_rebuild()
RiskOwnerRole.model_rebuild()
S1LeadRole.model_rebuild()
S2OfficerRole.model_rebuild()
S3SchedulerRole.model_rebuild()
S4ControllerRole.model_rebuild()
S5LeadRole.model_rebuild()
S5PlannerRole.model_rebuild()
S7LeadRole.model_rebuild()
S8ApproverRole.model_rebuild()
S9LeadRole.model_rebuild()
S9OfficerRole.model_rebuild()
SecurityOfficerRole.model_rebuild()
SecurityRole.model_rebuild()
StaffMemberRole.model_rebuild()
StaffRole.model_rebuild()
StakeholderRole.model_rebuild()
StoreKeeperRole.model_rebuild()
SubjectRole.model_rebuild()
SupplierRole.model_rebuild()
TraineeRole.model_rebuild()
TrainerRole.model_rebuild()
VendorRole.model_rebuild()
WatchOfficerRole.model_rebuild()
ABIExecutionSite.model_rebuild()
ABIMaterialParticipant.model_rebuild()
ABIInformationArtifact.model_rebuild()
ABIAISystem.model_rebuild()
AirgappedZone.model_rebuild()
PhysicalITInfrastructure.model_rebuild()
OSINTSources.model_rebuild()
OnpremisesDataCentre.model_rebuild()
OperationsCentre.model_rebuild()
ABIProcessSpecification.model_rebuild()
SitesAcrossTheEstate.model_rebuild()
Sites.model_rebuild()
Stores.model_rebuild()
ABIExecutionCondition.model_rebuild()
ABIObjectiveSpecification.model_rebuild()
StakeholderParticipant.model_rebuild()
SubjectParticipant.model_rebuild()
ABIPhysicalTeam.model_rebuild()
ABIPhysicalComputingSystem.model_rebuild()
ABISoftware.model_rebuild()
ABIHumanParticipant.model_rebuild()
ABIEvidenceRecord.model_rebuild()
ABIIndicatorRecord.model_rebuild()
OnboardingExecutionRole.model_rebuild()
OnboardingExecutionInterval.model_rebuild()
OnboardingCreateStaffRecord.model_rebuild()
OnboardingAssignRole.model_rebuild()
OnboardingGrantAccess.model_rebuild()
Onboarding.model_rebuild()
AccessProvisioningExecutionRole.model_rebuild()
AccessProvisioningExecutionInterval.model_rebuild()
AccessProvisioningRequestAccess.model_rebuild()
AccessProvisioningApprove.model_rebuild()
AccessProvisioningProvisionLog.model_rebuild()
AccessProvisioning.model_rebuild()
RotationPlanningExecutionRole.model_rebuild()
RotationPlanningExecutionInterval.model_rebuild()
RotationPlanningForecastNeeds.model_rebuild()
RotationPlanningDraftRota.model_rebuild()
RotationPlanningPublish.model_rebuild()
RotationPlanning.model_rebuild()
AttendanceAndLeaveExecutionRole.model_rebuild()
AttendanceAndLeaveExecutionInterval.model_rebuild()
AttendanceAndLeaveRecordAttendance.model_rebuild()
AttendanceAndLeaveRequestLeave.model_rebuild()
AttendanceAndLeaveApprove.model_rebuild()
AttendanceAndLeave.model_rebuild()
OffboardingExecutionRole.model_rebuild()
OffboardingExecutionInterval.model_rebuild()
OffboardingRevokeAccess.model_rebuild()
OffboardingReturnAssets.model_rebuild()
OffboardingCloseRecord.model_rebuild()
Offboarding.model_rebuild()
ExecutiveBriefingExecutionRole.model_rebuild()
ExecutiveBriefingExecutionInterval.model_rebuild()
ExecutiveBriefingGatherInputs.model_rebuild()
ExecutiveBriefingSynthesise.model_rebuild()
ExecutiveBriefingDeliverBriefing.model_rebuild()
ExecutiveBriefing.model_rebuild()
SignalSynthesisExecutionRole.model_rebuild()
SignalSynthesisExecutionInterval.model_rebuild()
SignalSynthesisIngestSources.model_rebuild()
SignalSynthesisCorrelate.model_rebuild()
SignalSynthesisFlagSignals.model_rebuild()
SignalSynthesis.model_rebuild()
RiskAndContextAssessmentExecutionRole.model_rebuild()
RiskAndContextAssessmentExecutionInterval.model_rebuild()
RiskAndContextAssessmentFrameQuestion.model_rebuild()
RiskAndContextAssessmentAssess.model_rebuild()
RiskAndContextAssessmentScore.model_rebuild()
RiskAndContextAssessment.model_rebuild()
SecurityScreeningExecutionRole.model_rebuild()
SecurityScreeningExecutionInterval.model_rebuild()
SecurityScreeningReceiveRequest.model_rebuild()
SecurityScreeningScreen.model_rebuild()
SecurityScreeningClearOrRefer.model_rebuild()
SecurityScreening.model_rebuild()
WatchAndAlertingExecutionRole.model_rebuild()
WatchAndAlertingExecutionInterval.model_rebuild()
WatchAndAlertingSetThresholds.model_rebuild()
WatchAndAlertingMonitor.model_rebuild()
WatchAndAlertingRaiseAlert.model_rebuild()
WatchAndAlerting.model_rebuild()
WorkorderProcessingExecutionRole.model_rebuild()
WorkorderProcessingExecutionInterval.model_rebuild()
WorkorderProcessingRaiseWorkOrder.model_rebuild()
WorkorderProcessingRoute.model_rebuild()
WorkorderProcessingExecuteClose.model_rebuild()
WorkorderProcessing.model_rebuild()
SchedulingExecutionRole.model_rebuild()
SchedulingExecutionInterval.model_rebuild()
SchedulingCollectDemand.model_rebuild()
SchedulingOptimise.model_rebuild()
SchedulingPublishSchedule.model_rebuild()
Scheduling.model_rebuild()
FleetDispatchExecutionRole.model_rebuild()
FleetDispatchExecutionInterval.model_rebuild()
FleetDispatchReceiveRequest.model_rebuild()
FleetDispatchAssignVehicle.model_rebuild()
FleetDispatchDispatchTrack.model_rebuild()
FleetDispatch.model_rebuild()
MaintenanceExecutionRole.model_rebuild()
MaintenanceExecutionInterval.model_rebuild()
MaintenanceDetectNeed.model_rebuild()
MaintenancePlan.model_rebuild()
MaintenanceExecuteVerify.model_rebuild()
Maintenance.model_rebuild()
IncidentResponseExecutionRole.model_rebuild()
IncidentResponseExecutionInterval.model_rebuild()
IncidentResponseDetect.model_rebuild()
IncidentResponseTriage.model_rebuild()
IncidentResponseResolveReview.model_rebuild()
IncidentResponse.model_rebuild()
VendorEvaluationExecutionRole.model_rebuild()
VendorEvaluationExecutionInterval.model_rebuild()
VendorEvaluationDefineCriteria.model_rebuild()
VendorEvaluationScoreVendors.model_rebuild()
VendorEvaluationRecommend.model_rebuild()
VendorEvaluation.model_rebuild()
StraightthroughProcurementExecutionRole.model_rebuild()
StraightthroughProcurementExecutionInterval.model_rebuild()
StraightthroughProcurementRequisition.model_rebuild()
StraightthroughProcurementAutoapproveWithinPolicy.model_rebuild()
StraightthroughProcurementOrder.model_rebuild()
StraightthroughProcurement.model_rebuild()
StockAndInventoryExecutionRole.model_rebuild()
StockAndInventoryExecutionInterval.model_rebuild()
StockAndInventoryCount.model_rebuild()
StockAndInventoryReconcile.model_rebuild()
StockAndInventoryReplenish.model_rebuild()
StockAndInventory.model_rebuild()
AssetRegistryExecutionRole.model_rebuild()
AssetRegistryExecutionInterval.model_rebuild()
AssetRegistryRegisterAsset.model_rebuild()
AssetRegistryTag.model_rebuild()
AssetRegistryTrackLifecycle.model_rebuild()
AssetRegistry.model_rebuild()
SupplierOnboardingExecutionRole.model_rebuild()
SupplierOnboardingExecutionInterval.model_rebuild()
SupplierOnboardingVetSupplier.model_rebuild()
SupplierOnboardingSetTerms.model_rebuild()
SupplierOnboardingActivate.model_rebuild()
SupplierOnboarding.model_rebuild()
ProgrammePlanningExecutionRole.model_rebuild()
ProgrammePlanningExecutionInterval.model_rebuild()
ProgrammePlanningDefineObjectives.model_rebuild()
ProgrammePlanningSequence.model_rebuild()
ProgrammePlanningBaseline.model_rebuild()
ProgrammePlanning.model_rebuild()
ForecastingExecutionRole.model_rebuild()
ForecastingExecutionInterval.model_rebuild()
ForecastingGatherSignals.model_rebuild()
ForecastingModel.model_rebuild()
ForecastingPublishForecast.model_rebuild()
Forecasting.model_rebuild()
CapabilityRoadmapExecutionRole.model_rebuild()
CapabilityRoadmapExecutionInterval.model_rebuild()
CapabilityRoadmapAssessGaps.model_rebuild()
CapabilityRoadmapPrioritise.model_rebuild()
CapabilityRoadmapRoadmap.model_rebuild()
CapabilityRoadmap.model_rebuild()
ITProvisioningExecutionRole.model_rebuild()
ITProvisioningExecutionInterval.model_rebuild()
ITProvisioningRequest.model_rebuild()
ITProvisioningProvision.model_rebuild()
ITProvisioningVerify.model_rebuild()
ITProvisioning.model_rebuild()
CyberPostureblueredTeamExecutionRole.model_rebuild()
CyberPostureblueredTeamExecutionInterval.model_rebuild()
CyberPostureblueredTeamAttackred.model_rebuild()
CyberPostureblueredTeamDefendblue.model_rebuild()
CyberPostureblueredTeamRemediate.model_rebuild()
CyberPostureblueredTeam.model_rebuild()
CommunicationsAndCalendarExecutionRole.model_rebuild()
CommunicationsAndCalendarExecutionInterval.model_rebuild()
CommunicationsAndCalendarSchedule.model_rebuild()
CommunicationsAndCalendarNotify.model_rebuild()
CommunicationsAndCalendarRecord.model_rebuild()
CommunicationsAndCalendar.model_rebuild()
TrainingDeliveryExecutionRole.model_rebuild()
TrainingDeliveryExecutionInterval.model_rebuild()
TrainingDeliveryPlanCourse.model_rebuild()
TrainingDeliveryDeliver.model_rebuild()
TrainingDeliveryRecord.model_rebuild()
TrainingDelivery.model_rebuild()
CapabilityDevelopmentExecutionRole.model_rebuild()
CapabilityDevelopmentExecutionInterval.model_rebuild()
CapabilityDevelopmentAssess.model_rebuild()
CapabilityDevelopmentDevelop.model_rebuild()
CapabilityDevelopmentCertify.model_rebuild()
CapabilityDevelopment.model_rebuild()
AssessmentExecutionRole.model_rebuild()
AssessmentExecutionInterval.model_rebuild()
AssessmentSetAssessment.model_rebuild()
AssessmentScore.model_rebuild()
AssessmentFeedBack.model_rebuild()
Assessment.model_rebuild()
FinanceApprovalChainExecutionRole.model_rebuild()
FinanceApprovalChainExecutionInterval.model_rebuild()
FinanceApprovalChainSubmit.model_rebuild()
FinanceApprovalChainRouteForApproval.model_rebuild()
FinanceApprovalChainAuthorise.model_rebuild()
FinanceApprovalChain.model_rebuild()
BudgetManagementExecutionRole.model_rebuild()
BudgetManagementExecutionInterval.model_rebuild()
BudgetManagementSetBudget.model_rebuild()
BudgetManagementTrack.model_rebuild()
BudgetManagementReforecast.model_rebuild()
BudgetManagement.model_rebuild()
ContractManagementExecutionRole.model_rebuild()
ContractManagementExecutionInterval.model_rebuild()
ContractManagementDraft.model_rebuild()
ContractManagementSign.model_rebuild()
ContractManagementManageLifecycle.model_rebuild()
ContractManagement.model_rebuild()
PaymentsAndExpensesExecutionRole.model_rebuild()
PaymentsAndExpensesExecutionInterval.model_rebuild()
PaymentsAndExpensesCapture.model_rebuild()
PaymentsAndExpensesValidate.model_rebuild()
PaymentsAndExpensesPay.model_rebuild()
PaymentsAndExpenses.model_rebuild()
AuditTrailMaintenanceExecutionRole.model_rebuild()
AuditTrailMaintenanceExecutionInterval.model_rebuild()
AuditTrailMaintenanceLogActions.model_rebuild()
AuditTrailMaintenanceRetain.model_rebuild()
AuditTrailMaintenanceProduceOnDemand.model_rebuild()
AuditTrailMaintenance.model_rebuild()
StakeholderEngagementExecutionRole.model_rebuild()
StakeholderEngagementExecutionInterval.model_rebuild()
StakeholderEngagementMapStakeholders.model_rebuild()
StakeholderEngagementEngage.model_rebuild()
StakeholderEngagementRecord.model_rebuild()
StakeholderEngagement.model_rebuild()
PartnerCoordinationExecutionRole.model_rebuild()
PartnerCoordinationExecutionInterval.model_rebuild()
PartnerCoordinationAlign.model_rebuild()
PartnerCoordinationCoordinate.model_rebuild()
PartnerCoordinationReview.model_rebuild()
PartnerCoordination.model_rebuild()
PublicAndCommunicationsExecutionRole.model_rebuild()
PublicAndCommunicationsExecutionInterval.model_rebuild()
PublicAndCommunicationsPrepare.model_rebuild()
PublicAndCommunicationsClear.model_rebuild()
PublicAndCommunicationsPublish.model_rebuild()
PublicAndCommunications.model_rebuild()
AINAgentsPhysicalHost.model_rebuild()
AINFinanceAgentPhysicalHost.model_rebuild()
AINGapdetectionAgentPhysicalHost.model_rebuild()
AINPhysicalHost.model_rebuild()
AINIntelligenceAgentPhysicalHost.model_rebuild()
AINPredictiveAgentPhysicalHost.model_rebuild()
AINProcurementAgentPhysicalHost.model_rebuild()
AccessLevelRecord.model_rebuild()
AccessRegister.model_rebuild()
AccessRequestRecord.model_rebuild()
AccessRevocationLog.model_rebuild()
AccessrevokedStatusRecord.model_rebuild()
AccessStatusRecord.model_rebuild()
AccuracyRecord.model_rebuild()
AfteractionNote.model_rebuild()
AirgapComplianceRecord.model_rebuild()
AlertFeed.model_rebuild()
AlertLatencyRecord.model_rebuild()
AlignmentStatusRecord.model_rebuild()
ApprovalLog.model_rebuild()
ApprovalRecord.model_rebuild()
ApprovalStatusRecord.model_rebuild()
AssessmentCompletenessRecord.model_rebuild()
AssessmentRecord.model_rebuild()
AssessmentReport.model_rebuild()
AssessmentResult.model_rebuild()
AssetConditionRecord.model_rebuild()
AssetRegistryUpdate.model_rebuild()
AttendanceLog.model_rebuild()
AttendanceRecord.model_rebuild()
AttendanceStatusRecord.model_rebuild()
AuditTrail.model_rebuild()
BriefingNote.model_rebuild()
BudgetRecord.model_rebuild()
BudgetStatusRecord.model_rebuild()
CalendarRecord.model_rebuild()
ClearanceStatusRecord.model_rebuild()
CommsRecord.model_rebuild()
CompetencyLevelRecord.model_rebuild()
CompetencyRecord.model_rebuild()
CompletionRateRecord.model_rebuild()
ComplianceStatusRecord.model_rebuild()
ConfidenceScoreRecord.model_rebuild()
ConfigurationLog.model_rebuild()
ContactRecord.model_rebuild()
ContractStatusRecord.model_rebuild()
CoverageRecord.model_rebuild()
CoverageRatioRecord.model_rebuild()
CycleTimeRecord.model_rebuild()
DecisionLog.model_rebuild()
DeliveryStatusRecord.model_rebuild()
DispatchRecord.model_rebuild()
DowntimeRecord.model_rebuild()
EngagementLog.model_rebuild()
EngagementStatusRecord.model_rebuild()
EvaluationRecord.model_rebuild()
EvidenceRegister.model_rebuild()
ExceptionRateRecord.model_rebuild()
FalsepositiveRateRecord.model_rebuild()
FindingsSeverityRecord.model_rebuild()
FleetSystemPhysicalHost.model_rebuild()
ForecastConfidenceRecord.model_rebuild()
ForecastRecord.model_rebuild()
GapCoverageRecord.model_rebuild()
GapRegister.model_rebuild()
HRRecord.model_rebuild()
HRSystemPhysicalHost.model_rebuild()
IdentitySystemPhysicalHost.model_rebuild()
IncidentRecord.model_rebuild()
InventoryRecord.model_rebuild()
LearningSystemPhysicalHost.model_rebuild()
LeastprivilegeComplianceRecord.model_rebuild()
LeaveRecord.model_rebuild()
MaintenanceRecord.model_rebuild()
MessageLog.model_rebuild()
MessagingSystemPhysicalHost.model_rebuild()
OffboardingChecklist.model_rebuild()
OntimeRateRecord.model_rebuild()
OnboardingStatusRecord.model_rebuild()
OracleERPPhysicalHost.model_rebuild()
OrderStatusRecord.model_rebuild()
PartnerRecord.model_rebuild()
PassRateRecord.model_rebuild()
PaymentRecord.model_rebuild()
PaymentStatusRecord.model_rebuild()
PenetrationReport.model_rebuild()
PlanMaturityRecord.model_rebuild()
PlanningSystemPhysicalHost.model_rebuild()
PolicyComplianceRecord.model_rebuild()
ProcurementRecord.model_rebuild()
ProgrammePlan.model_rebuild()
ProvisioningRecord.model_rebuild()
ProvisioningStatusRecord.model_rebuild()
ReasoningChain.model_rebuild()
RegistryCompletenessRecord.model_rebuild()
RemediationLog.model_rebuild()
ResolutionTimeRecord.model_rebuild()
RighttoauditInPlaceRecord.model_rebuild()
RighttoauditRecord.model_rebuild()
RiskScoreRecord.model_rebuild()
RoadmapDocument.model_rebuild()
RotationPlan.model_rebuild()
SLAAdherenceRecord.model_rebuild()
SLAOnApprovalRecord.model_rebuild()
ScheduleFillRateRecord.model_rebuild()
ScheduleRecord.model_rebuild()
SchedulingSystemPhysicalHost.model_rebuild()
ScoreRecord.model_rebuild()
ScreeningRecord.model_rebuild()
ScreeningSystemPhysicalHost.model_rebuild()
SeverityRecord.model_rebuild()
SignalRecord.model_rebuild()
SourceChain.model_rebuild()
StockLevelRecord.model_rebuild()
TimelinessRecord.model_rebuild()
TrailCompletenessRecord.model_rebuild()
TrainingRecord.model_rebuild()
TripLog.model_rebuild()
UptimeRecord.model_rebuild()
VarianceRecord.model_rebuild()
VehicleStatusRecord.model_rebuild()
VendorCatalogue.model_rebuild()
VendorContract.model_rebuild()
VendorPerformanceScoreRecord.model_rebuild()
WorkorderRecord.model_rebuild()
AINAgentsSoftware.model_rebuild()
AINFinanceAgentSoftware.model_rebuild()
AINGapdetectionAgentSoftware.model_rebuild()
AINIntelligenceAgentSoftware.model_rebuild()
AINPredictiveAgentSoftware.model_rebuild()
AINProcurementAgentSoftware.model_rebuild()
AINSoftware.model_rebuild()
AnalystParticipant.model_rebuild()
ApproverParticipant.model_rebuild()
AssessorParticipant.model_rebuild()
AssetOwnerParticipant.model_rebuild()
AuditorParticipant.model_rebuild()
BudgetOwnerParticipant.model_rebuild()
CommsOfficerParticipant.model_rebuild()
ContractManagerParticipant.model_rebuild()
CyberTeamParticipant.model_rebuild()
DispatcherParticipant.model_rebuild()
DriverParticipant.model_rebuild()
ExecutivePrincipalParticipant.model_rebuild()
FieldTeamParticipant.model_rebuild()
FinanceOfficerParticipant.model_rebuild()
FleetSystemSoftware.model_rebuild()
FunctionLeadsParticipant.model_rebuild()
HROfficerParticipant.model_rebuild()
HRSystemSoftware.model_rebuild()
ITAdminParticipant.model_rebuild()
ITEngineerParticipant.model_rebuild()
IdentitySystemSoftware.model_rebuild()
LearningSystemSoftware.model_rebuild()
LineManagerParticipant.model_rebuild()
LineManagersParticipant.model_rebuild()
MaintenanceTeamParticipant.model_rebuild()
MessagingSystemSoftware.model_rebuild()
NewJoinerParticipant.model_rebuild()
OperationsLeadParticipant.model_rebuild()
OracleERPSoftware.model_rebuild()
PartnerOrganisationPersonnel.model_rebuild()
PlannerParticipant.model_rebuild()
PlanningSystemSoftware.model_rebuild()
ProcurementOfficerParticipant.model_rebuild()
ProgrammeOwnerParticipant.model_rebuild()
RequesterParticipant.model_rebuild()
ResourceOwnersParticipant.model_rebuild()
ResponseTeamParticipant.model_rebuild()
RiskOwnerParticipant.model_rebuild()
S1LeadParticipant.model_rebuild()
S2OfficerParticipant.model_rebuild()
S3SchedulerParticipant.model_rebuild()
S4ControllerParticipant.model_rebuild()
S5LeadParticipant.model_rebuild()
S5PlannerParticipant.model_rebuild()
S7LeadParticipant.model_rebuild()
S8ApproverParticipant.model_rebuild()
S9LeadParticipant.model_rebuild()
S9OfficerParticipant.model_rebuild()
SchedulingSystemSoftware.model_rebuild()
ScreeningSystemSoftware.model_rebuild()
SecurityOfficerParticipant.model_rebuild()
SecurityParticipant.model_rebuild()
StaffMemberParticipant.model_rebuild()
StaffParticipant.model_rebuild()
StoreKeeperParticipant.model_rebuild()
SupplierPersonnel.model_rebuild()
TraineeParticipant.model_rebuild()
TrainerParticipant.model_rebuild()
VendorPersonnel.model_rebuild()
WatchOfficerParticipant.model_rebuild()
OnboardingTimingCondition.model_rebuild()
OnboardingObjective.model_rebuild()
OnboardingSpecification.model_rebuild()
AccessProvisioningTimingCondition.model_rebuild()
AccessProvisioningObjective.model_rebuild()
AccessProvisioningSpecification.model_rebuild()
RotationPlanningTimingCondition.model_rebuild()
RotationPlanningObjective.model_rebuild()
RotationPlanningSpecification.model_rebuild()
AttendanceAndLeaveTimingCondition.model_rebuild()
AttendanceAndLeaveObjective.model_rebuild()
AttendanceAndLeaveSpecification.model_rebuild()
OffboardingTimingCondition.model_rebuild()
OffboardingObjective.model_rebuild()
OffboardingSpecification.model_rebuild()
ExecutiveBriefingTimingCondition.model_rebuild()
ExecutiveBriefingObjective.model_rebuild()
ExecutiveBriefingSpecification.model_rebuild()
SignalSynthesisTimingCondition.model_rebuild()
SignalSynthesisObjective.model_rebuild()
SignalSynthesisSpecification.model_rebuild()
RiskAndContextAssessmentTimingCondition.model_rebuild()
RiskAndContextAssessmentObjective.model_rebuild()
RiskAndContextAssessmentSpecification.model_rebuild()
SecurityScreeningTimingCondition.model_rebuild()
SecurityScreeningObjective.model_rebuild()
SecurityScreeningSpecification.model_rebuild()
WatchAndAlertingTimingCondition.model_rebuild()
WatchAndAlertingObjective.model_rebuild()
WatchAndAlertingSpecification.model_rebuild()
WorkorderProcessingTimingCondition.model_rebuild()
WorkorderProcessingObjective.model_rebuild()
WorkorderProcessingSpecification.model_rebuild()
SchedulingTimingCondition.model_rebuild()
SchedulingObjective.model_rebuild()
SchedulingSpecification.model_rebuild()
FleetDispatchTimingCondition.model_rebuild()
FleetDispatchObjective.model_rebuild()
FleetDispatchSpecification.model_rebuild()
MaintenanceTimingCondition.model_rebuild()
MaintenanceObjective.model_rebuild()
MaintenanceSpecification.model_rebuild()
IncidentResponseTimingCondition.model_rebuild()
IncidentResponseObjective.model_rebuild()
IncidentResponseSpecification.model_rebuild()
VendorEvaluationTimingCondition.model_rebuild()
VendorEvaluationObjective.model_rebuild()
VendorEvaluationSpecification.model_rebuild()
StraightthroughProcurementTimingCondition.model_rebuild()
StraightthroughProcurementObjective.model_rebuild()
StraightthroughProcurementSpecification.model_rebuild()
StockAndInventoryTimingCondition.model_rebuild()
StockAndInventoryObjective.model_rebuild()
StockAndInventorySpecification.model_rebuild()
AssetRegistryTimingCondition.model_rebuild()
AssetRegistryObjective.model_rebuild()
AssetRegistrySpecification.model_rebuild()
SupplierOnboardingTimingCondition.model_rebuild()
SupplierOnboardingObjective.model_rebuild()
SupplierOnboardingSpecification.model_rebuild()
ProgrammePlanningTimingCondition.model_rebuild()
ProgrammePlanningObjective.model_rebuild()
ProgrammePlanningSpecification.model_rebuild()
ForecastingTimingCondition.model_rebuild()
ForecastingObjective.model_rebuild()
ForecastingSpecification.model_rebuild()
CapabilityRoadmapTimingCondition.model_rebuild()
CapabilityRoadmapObjective.model_rebuild()
CapabilityRoadmapSpecification.model_rebuild()
ITProvisioningTimingCondition.model_rebuild()
ITProvisioningObjective.model_rebuild()
ITProvisioningSpecification.model_rebuild()
CyberPostureblueredTeamTimingCondition.model_rebuild()
CyberPostureblueredTeamObjective.model_rebuild()
CyberPostureblueredTeamSpecification.model_rebuild()
CommunicationsAndCalendarTimingCondition.model_rebuild()
CommunicationsAndCalendarObjective.model_rebuild()
CommunicationsAndCalendarSpecification.model_rebuild()
TrainingDeliveryTimingCondition.model_rebuild()
TrainingDeliveryObjective.model_rebuild()
TrainingDeliverySpecification.model_rebuild()
CapabilityDevelopmentTimingCondition.model_rebuild()
CapabilityDevelopmentObjective.model_rebuild()
CapabilityDevelopmentSpecification.model_rebuild()
AssessmentTimingCondition.model_rebuild()
AssessmentObjective.model_rebuild()
AssessmentSpecification.model_rebuild()
FinanceApprovalChainTimingCondition.model_rebuild()
FinanceApprovalChainObjective.model_rebuild()
FinanceApprovalChainSpecification.model_rebuild()
BudgetManagementTimingCondition.model_rebuild()
BudgetManagementObjective.model_rebuild()
BudgetManagementSpecification.model_rebuild()
ContractManagementTimingCondition.model_rebuild()
ContractManagementObjective.model_rebuild()
ContractManagementSpecification.model_rebuild()
PaymentsAndExpensesTimingCondition.model_rebuild()
PaymentsAndExpensesObjective.model_rebuild()
PaymentsAndExpensesSpecification.model_rebuild()
AuditTrailMaintenanceTimingCondition.model_rebuild()
AuditTrailMaintenanceObjective.model_rebuild()
AuditTrailMaintenanceSpecification.model_rebuild()
StakeholderEngagementTimingCondition.model_rebuild()
StakeholderEngagementObjective.model_rebuild()
StakeholderEngagementSpecification.model_rebuild()
PartnerCoordinationTimingCondition.model_rebuild()
PartnerCoordinationObjective.model_rebuild()
PartnerCoordinationSpecification.model_rebuild()
PublicAndCommunicationsTimingCondition.model_rebuild()
PublicAndCommunicationsObjective.model_rebuild()
PublicAndCommunicationsSpecification.model_rebuild()
