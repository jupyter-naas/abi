# onto2py-source-sha256: 7dcabde2439ebe8e4dcc628a5c5457b85ebd6562fc8659009ff9fd30cb75cb62
from __future__ import annotations

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

        # Add label when explicitly set (process occurrents omit rdfs:label).
        if hasattr(self, "label") and self.label is not None:
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


class Birth(RDFEntity):
    """
    This process may be constrained to represent only the birth process in mammals. There are potentially other birth processes, such as the birth of a plant.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001237"
    _name: ClassVar[str] = "Birth"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_father": "http://ontology.naas.ai/personnel/hasFather",
        "has_mother": "http://ontology.naas.ai/personnel/hasMother",
        "is_birth_of": "http://ontology.naas.ai/personnel/isBirthOf",
        "is_registered_by": "http://ontology.naas.ai/personnel/isRegisteredBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000066",
        "bFO_0000199",
        "has_father",
        "has_mother",
        "is_birth_of",
        "is_registered_by",
    }

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000055: Optional[
        Annotated[List[Union[BirthFunction, NewbornDisposition, URIRef, str]], Field()]
    ] = None
    bFO_0000057: Optional[
        Annotated[
            List[
                Union[
                    BiologicalSex,
                    BirthFunction,
                    EyeColor,
                    GestationalAge,
                    Length,
                    NewbornDisposition,
                    URIRef,
                    Weight,
                    str,
                ]
            ],
            Field(),
        ]
    ] = None
    bFO_0000066: Optional[Annotated[List[Union[Site, URIRef, str]], Field()]] = None
    bFO_0000199: Optional[
        Annotated[List[Union[TemporalRegion, URIRef, str]], Field()]
    ] = None
    is_birth_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(description="Relates a birth process to the person born in it."),
        ]
    ] = None
    has_mother: Optional[
        Annotated[
            List[Union["Person", URIRef, str]],
            Field(
                description="Relates a birth process to the person asserted as the newborn's mother in the registration that recorded it."
            ),
        ]
    ] = None
    has_father: Optional[
        Annotated[
            List[Union["Person", URIRef, str]],
            Field(
                description="Relates a birth process to the person asserted as the newborn's father in the registration that recorded it."
            ),
        ]
    ] = None
    is_registered_by: Optional[
        Annotated[
            List[Union[BirthRegistrationProcess, URIRef, str]],
            Field(
                description="Relates a birth process to the registration processes that record it. A birth registered independently by two declarants has two."
            ),
        ]
    ] = None


class BirthDeclarationAct(RDFEntity):
    """
    CCO defines ont00000379 as an Act of Communication that commits a speaker to the truth of the expressed proposition — which is exactly what attestation is. Everything about who declared, when, through what channel and what they said hangs off this act, so the registration process does not have to carry it.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/BirthDeclarationAct"
    _name: ClassVar[str] = "Birth Declaration Act"
    _property_uris: ClassVar[dict] = {
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "declared_content": "http://ontology.naas.ai/personnel/declared_content",
        "is_information_source_of": "http://ontology.naas.ai/personnel/isInformationSourceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001829": "https://www.commoncoreontologies.org/ont00001829",
        "ont00001833": "https://www.commoncoreontologies.org/ont00001833",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000199",
        "is_information_source_of",
        "ont00001829",
        "ont00001833",
    }

    # Data properties
    declared_content: Optional[
        Annotated[
            str,
            Field(
                description="Verbatim text of what the declarant asserted, retained so the registration can be retraced to its wording."
            ),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000199: Optional[
        Annotated[List[Union[TemporalRegion, URIRef, str]], Field()]
    ] = None
    is_information_source_of: Optional[
        Annotated[
            List[Union[BirthRegistrationProcess, URIRef, str]],
            Field(
                description="Relates a birth declaration act to the registration processes that record its asserted content."
            ),
        ]
    ] = None
    ont00001829: Optional[Annotated[Union[URIRef, str], Field()]] = None
    ont00001833: Optional[Annotated[List[Union[Person, URIRef, str]], Field()]] = None


class BirthRegistrationProcess(RDFEntity):
    """
    Process ontology for birth registration, decomposed across the BFO seven buckets.
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/personnel/BirthRegistrationProcess"
    )
    _name: ClassVar[str] = "Birth Registration Process"
    _property_uris: ClassVar[dict] = {
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_declarant": "http://ontology.naas.ai/personnel/hasDeclarant",
        "has_information_source": "http://ontology.naas.ai/personnel/hasInformationSource",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001829": "https://www.commoncoreontologies.org/ont00001829",
        "registers_birth": "http://ontology.naas.ai/personnel/registersBirth",
        "updates_prior_registration": "http://ontology.naas.ai/personnel/updatesPriorRegistration",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000199",
        "has_declarant",
        "has_information_source",
        "ont00001829",
        "registers_birth",
        "updates_prior_registration",
    }

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000199: Optional[
        Annotated[List[Union[TemporalRegion, URIRef, str]], Field()]
    ] = None
    has_declarant: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a birth registration process to the person who made the declaration it records. Entailed by the chain has information source ∘ has agent; assert personnel:hasInformationSource instead of this."
            ),
        ]
    ] = None
    has_information_source: Optional[
        Annotated[
            List[Union[BirthDeclarationAct, URIRef, str]],
            Field(
                description="Relates a birth registration process to the declaration act whose asserted content it records."
            ),
        ]
    ] = None
    ont00001829: Optional[Annotated[List[Union[BirthRecord, URIRef, str]], Field()]] = (
        None
    )
    registers_birth: Optional[
        Annotated[
            List[Union[Birth, URIRef, str]],
            Field(
                description="Relates a birth registration process to the single mind-independent birth process it records."
            ),
        ]
    ] = None
    updates_prior_registration: Optional[
        Annotated[
            List[Union[BirthRegistrationProcess, URIRef, str]],
            Field(
                description="Relates a birth registration process that adds complementary information to an earlier registration of the same birth."
            ),
        ]
    ] = None


class Animal(RDFEntity):
    """
    Animal
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000562"
    _name: ClassVar[str] = "Animal"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000196"}

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000196: Optional[
        Annotated[
            List[
                Union[
                    BiologicalSex,
                    GestationalAge,
                    Length,
                    NewbornDisposition,
                    URIRef,
                    Weight,
                    str,
                ]
            ],
            Field(),
        ]
    ] = None


class TemporalRegion(RDFEntity):
    """
    temporal region
    """

    _class_uri: ClassVar[str] = "http://purl.obolibrary.org/obo/BFO_0000008"
    _name: ClassVar[str] = "temporal region"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Site(RDFEntity):
    """
    site
    """

    _class_uri: ClassVar[str] = "http://purl.obolibrary.org/obo/BFO_0000029"
    _name: ClassVar[str] = "site"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class BirthRecord(RDFEntity):
    """
    Previously minted as cco:BirthRecord — an IRI that does not exist in CCO — and carrying an 'is concretized by' restriction onto the intersection of Birth, Weight, Length, GestationalAge, BiologicalSex and NewbornDisposition. That intersection is necessarily empty, since BFO processes and qualities are disjoint, which made the class unsatisfiable. The record is instead about the birth, and is the output of the registration.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/BirthRecord"
    _name: ClassVar[str] = "Birth Record"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001808": "https://www.commoncoreontologies.org/ont00001808",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001808"}

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    ont00001808: Optional[Annotated[List[Union[Birth, URIRef, str]], Field()]] = None


class Weight(RDFEntity):
    """
    Weight
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/Weight"
    _name: ClassVar[str] = "Weight"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[Annotated[List[Union[Animal, URIRef, str]], Field()]] = None


class Length(RDFEntity):
    """
    Length
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/Length"
    _name: ClassVar[str] = "Length"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[Annotated[List[Union[Animal, URIRef, str]], Field()]] = None


class BiologicalSex(RDFEntity):
    """
    Biological sex
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/BiologicalSex"
    _name: ClassVar[str] = "Biological sex"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[Annotated[List[Union[Animal, URIRef, str]], Field()]] = None


class EyeColor(RDFEntity):
    """Eye color quality inhering in a person."""

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/EyeColor"
    _name: ClassVar[str] = "Eye color"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")
    bFO_0000197: Optional[Annotated[List[Union[Animal, URIRef, str]], Field()]] = None


class GestationalAge(RDFEntity):
    """
    No CCO equivalent; minted in the personnel namespace.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/GestationalAge"
    _name: ClassVar[str] = "Gestational age"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[Annotated[List[Union[Animal, URIRef, str]], Field()]] = None


class BirthFunction(RDFEntity):
    """
    Birth function
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/BirthFunction"
    _name: ClassVar[str] = "Birth function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[Annotated[List[Union[Animal, URIRef, str]], Field()]] = None


class NewbornDisposition(RDFEntity):
    """
    Newborn disposition
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/NewbornDisposition"
    _name: ClassVar[str] = "Newborn disposition"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[Annotated[List[Union[Animal, URIRef, str]], Field()]] = None


class Person(Animal, RDFEntity):
    """
    Every person has exactly one birth, whether or not it has been registered and whether or not its date is known. A person with no registration yet is still a person; what is missing is the record, not the birth.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/Person"
    _name: ClassVar[str] = "Person"
    _property_uris: ClassVar[dict] = {
        "bFO_0000196": "http://purl.obolibrary.org/obo/BFO_0000196",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "family_name": "http://ontology.naas.ai/personnel/family_name",
        "given_name": "http://ontology.naas.ai/personnel/given_name",
        "has_birth": "http://ontology.naas.ai/personnel/hasBirth",
        "has_father": "http://ontology.naas.ai/personnel/hasFather",
        "has_mother": "http://ontology.naas.ai/personnel/hasMother",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000196",
        "has_birth",
        "has_father",
        "has_mother",
    }

    # Data properties
    given_name: Optional[
        Annotated[
            str,
            Field(
                description="The name conferred on a person individually, typically at or near birth, as distinct from the family name they share with kin."
            ),
        ]
    ] = None
    family_name: Optional[
        Annotated[
            str,
            Field(
                description="The name a person shares with or inherits from kin, as distinct from the given name conferred on them individually."
            ),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000196: Optional[
        Annotated[
            List[
                Union[
                    BiologicalSex,
                    GestationalAge,
                    Length,
                    NewbornDisposition,
                    URIRef,
                    Weight,
                    str,
                ]
            ],
            Field(),
        ]
    ] = None
    has_birth: Optional[
        Annotated[
            List[Union[Birth, URIRef, str]],
            Field(
                description="Relates a person to the birth process in which they participate as the newborn."
            ),
        ]
    ] = None
    has_father: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a person to the person asserted as their father in a birth registration."
            ),
        ]
    ] = None
    has_mother: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a person to the person asserted as their mother in a birth registration."
            ),
        ]
    ] = None


# Rebuild models to resolve forward references
Birth.model_rebuild()
BirthDeclarationAct.model_rebuild()
BirthRegistrationProcess.model_rebuild()
Animal.model_rebuild()
TemporalRegion.model_rebuild()
Site.model_rebuild()
BirthRecord.model_rebuild()
Weight.model_rebuild()
Length.model_rebuild()
BiologicalSex.model_rebuild()
GestationalAge.model_rebuild()
BirthFunction.model_rebuild()
NewbornDisposition.model_rebuild()
Person.model_rebuild()
