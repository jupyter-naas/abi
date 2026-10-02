from __future__ import annotations

import contextlib
import datetime
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
    DocumentContentEntity,
    GenericallyDependentContinuant,
    MaterialEntity,
    Organization,
    Person,
    Process,
    Quality,
    Role,
)
from naas_abi_marketplace.domains.intelligence.modules.people.ontologies.processes.ActOfProfilingProcess import (
    ActOfProfiling,
)
from naas_abi_marketplace.domains.intelligence.modules.people.ontologies.processes.ActOfStudyingProcess import (
    ActOfStudying,
)
from naas_abi_marketplace.domains.intelligence.modules.people.ontologies.processes.ActOfWorkingProcess import (
    ActOfWorking,
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


class EnrollmentRecord(GenericallyDependentContinuant, RDFEntity):
    """
    Enrollment Record
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/EnrollmentRecord"
    _name: ClassVar[str] = "Enrollment Record"
    _property_uris: ClassVar[dict] = {
        "completion_date": "http://ontology.naas.ai/people/completion_date",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "enrollment_date": "http://ontology.naas.ai/people/enrollment_date",
        "genericallyDependsOn": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "isConcretizedBy": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_enrollment_record_of": "http://ontology.naas.ai/people/isEnrollmentRecordOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "program_name": "http://ontology.naas.ai/people/program_name",
    }
    _object_properties: ClassVar[set[str]] = {
        "genericallyDependsOn",
        "generically_depends_on",
        "isConcretizedBy",
        "is_concretized_by",
        "is_enrollment_record_of",
    }

    # Data properties
    program_name: Optional[
        Annotated[
            str,
            Field(
                description="Name of the curriculum or programme the enrollment is for."
            ),
        ]
    ] = None
    enrollment_date: Optional[
        Annotated[
            datetime.date,
            Field(
                description="Date on which the course of study documented by this record began."
            ),
        ]
    ] = None
    completion_date: Optional[
        Annotated[
            datetime.date,
            Field(
                description="Date on which the course of study documented by this record ended. Absent while the person is still enrolled."
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
    genericallyDependsOn: Optional[Annotated[Union[URIRef, str], Field()]] = None
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    isConcretizedBy: Optional[
        Annotated[List[Union[ActOfStudying, URIRef, str]], Field()]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_enrollment_record_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates an enrollment record to the person on which it generically depends."
            ),
        ]
    ] = None


class AcademicDegree(GenericallyDependentContinuant, RDFEntity):
    """
    Academic Degree
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/AcademicDegree"
    _name: ClassVar[str] = "Academic Degree"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "genericallyDependsOn": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "genericallyDependsOn",
        "generically_depends_on",
        "is_concretized_by",
    }

    # Data properties
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
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class Certification(GenericallyDependentContinuant, RDFEntity):
    """
    Covers both certifications and licences: the difference is who may withhold it and what it permits, not what kind of entity it is. Where that distinction matters, state it with people:certification_status and the issuing organization.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/Certification"
    _name: ClassVar[str] = "Certification"
    _property_uris: ClassVar[dict] = {
        "certification_name": "http://ontology.naas.ai/people/certification_name",
        "certification_status": "http://ontology.naas.ai/people/certification_status",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "credential_id": "http://ontology.naas.ai/people/credential_id",
        "credential_url": "http://ontology.naas.ai/people/credential_url",
        "expiry_date": "http://ontology.naas.ai/people/expiry_date",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_certification_of": "http://ontology.naas.ai/people/isCertificationOf",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "issue_date": "http://ontology.naas.ai/people/issue_date",
        "issued_by_organization": "http://ontology.naas.ai/people/issuedByOrganization",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_certification_of",
        "is_concretized_by",
        "issued_by_organization",
    }

    # Data properties
    certification_name: Optional[
        Annotated[
            str,
            Field(
                description="Name of the certification as published by the issuing organization."
            ),
        ]
    ] = None
    issue_date: Optional[
        Annotated[
            datetime.date,
            Field(description="Date on which the certification was issued."),
        ]
    ] = None
    expiry_date: Optional[
        Annotated[
            datetime.date,
            Field(
                description="Date on which the certification ceases to be valid. Absent when the certification does not expire."
            ),
        ]
    ] = None
    credential_id: Optional[
        Annotated[
            str,
            Field(
                description="Identifier the issuing organization assigned to this certification, by which it can be verified."
            ),
        ]
    ] = None
    credential_url: Optional[
        Annotated[
            Any,
            Field(
                description="Address at which the issuing organization publishes verification of this certification."
            ),
        ]
    ] = None
    certification_status: Optional[
        Annotated[
            str,
            Field(
                description="State of a certification at a point in time, e.g. 'active', 'expired', 'in-progress'."
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    is_certification_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a certification to the person on which it generically depends."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    issued_by_organization: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="Relates a certification to the organization that issued it and stands behind what it attests."
            ),
        ]
    ] = None


class Portrait(GenericallyDependentContinuant, RDFEntity):
    """
    The individual carries the address of the image (people:portrait_url or people:portrait_path), never the bytes. Image data belongs in object storage.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/Portrait"
    _name: ClassVar[str] = "Portrait"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_portrait_of": "http://ontology.naas.ai/people/isPortraitOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "participatesIn": "http://ontology.naas.ai/abi/participatesIn",
        "portrait_path": "http://ontology.naas.ai/people/portrait_path",
        "portrait_url": "http://ontology.naas.ai/people/portrait_url",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_concretized_by",
        "is_portrait_of",
        "participatesIn",
    }

    # Data properties
    portrait_url: Optional[
        Annotated[
            Any,
            Field(description="Address at which the portrait image can be retrieved."),
        ]
    ] = None
    portrait_path: Optional[
        Annotated[
            str,
            Field(
                description="Repository-relative or object-storage path of the portrait image, for portraits that are not published at a public address."
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_portrait_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(description="Relates a portrait image to the person it depicts."),
        ]
    ] = None
    participatesIn: Optional[
        Annotated[List[Union[ActOfProfiling, URIRef, str]], Field()]
    ] = None


class OccupationRole(Role, RDFEntity):
    """
    Externally grounded: it exists only while the person works in that capacity, and ends without the person ceasing to exist. What a source says about a job ends here; the employing organization's own view of it (the position it defined, the contract, the record) is internal and specializes this class elsewhere.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/OccupationRole"
    _name: ClassVar[str] = "Occupation Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "hasRealization": "http://ontology.naas.ai/abi/hasRealization",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_occupation_role_of": "http://ontology.naas.ai/people/isOccupationRoleOf",
        "job_title": "http://ontology.naas.ai/people/job_title",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "hasRealization",
        "has_realization",
        "inheres_in",
        "is_occupation_role_of",
    }

    # Data properties
    job_title: Optional[
        Annotated[
            str,
            Field(description="Title of an occupation role as the source states it."),
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
    concretizes: Optional[
        Annotated[
            List[Union[GenericallyDependentContinuant, URIRef, str]],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
    ] = None
    hasRealization: Optional[
        Annotated[List[Union[ActOfWorking, URIRef, str]], Field()]
    ] = None
    has_realization: Optional[
        Annotated[
            List[Union[Process, URIRef, str]],
            Field(description="b has realization c =Def c realizes b"),
        ]
    ] = None
    inheres_in: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = None
    is_occupation_role_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates an occupation role to the person in whom it inheres."
            ),
        ]
    ] = None


class StudentRole(Role, RDFEntity):
    """
    No CCO student-role class; minted in the people namespace. Ends when the enrollment ends, without the person ceasing to exist.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/StudentRole"
    _name: ClassVar[str] = "Student Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "hasRealization": "http://ontology.naas.ai/abi/hasRealization",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_student_role_of": "http://ontology.naas.ai/people/isStudentRoleOf",
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
    concretizes: Optional[
        Annotated[
            List[Union[GenericallyDependentContinuant, URIRef, str]],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
    ] = None
    hasRealization: Optional[
        Annotated[List[Union[ActOfStudying, URIRef, str]], Field()]
    ] = None
    has_realization: Optional[
        Annotated[
            List[Union[Process, URIRef, str]],
            Field(description="b has realization c =Def c realizes b"),
        ]
    ] = None
    inheres_in: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = None
    is_student_role_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a student role to the person in whom it inheres."
            ),
        ]
    ] = None


class LanguageCapability(Quality, RDFEntity):
    """
    Deliberately NOT equivalent to CCO Language Skill (cco:ont00000181). That class is an Agent Capability and therefore a BFO realizable entity, which is disjoint from quality; this domain already models people:Skill as a quality, and asserting both would make the ontology inconsistent. The language itself is a CCO Language, reached through people:ofLanguage. Like a skill, it is borne by the person and outlives any one act: people:developsLanguageCapability links a planned act, of whatever kind, to the capabilities exercised and grown in it.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/LanguageCapability"
    _name: ClassVar[str] = "Language Capability"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_language_capability_developed_in": "http://ontology.naas.ai/people/isLanguageCapabilityDevelopedIn",
        "is_language_capability_of": "http://ontology.naas.ai/people/isLanguageCapabilityOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "language_name": "http://ontology.naas.ai/people/language_name",
        "of_language": "http://ontology.naas.ai/people/ofLanguage",
        "participates_in": "http://ontology.naas.ai/abi/participatesIn",
        "proficiency_level": "http://ontology.naas.ai/people/proficiency_level",
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
    language_name: Optional[
        Annotated[
            str,
            Field(
                description="Name of the language a capability is held for, as displayed."
            ),
        ]
    ] = None
    proficiency_level: Optional[
        Annotated[
            str,
            Field(
                description="Reported level of a language capability. Free text rather than a code list: sources state it in incompatible scales (CEFR, 'native', 'professional working proficiency') and converting between them would assert more than the source does."
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
    concretizes: Optional[
        Annotated[
            List[Union[GenericallyDependentContinuant, URIRef, str]],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
    ] = None
    inheres_in: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = None
    is_language_capability_developed_in: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="Relates a language capability to a planned act in which it is exercised and developed."
            ),
        ]
    ] = None
    is_language_capability_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a language capability to the person in whom it inheres."
            ),
        ]
    ] = None
    of_language: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="Relates a language capability to the language it is held for. The language is a CCO Language: a directive information content entity prescribing a canonical format for communication, shared by every speaker of it."
            ),
        ]
    ] = None
    participates_in: Optional[
        Annotated[
            List[Union[Process, URIRef, str]],
            Field(
                description="(Elucidation) participates in holds between some b that is either a specifically dependent continuant or generically dependent continuant or independent continuant that is not a spatial region & some process p such that b participates in p some way"
            ),
        ]
    ] = None


class Interest(Quality, RDFEntity):
    """
    Modelled as a quality for consistency with people:Skill rather than as a disposition. Points at its target with people:hasInterestTarget where an individual exists for it, and otherwise carries people:interest_name alone.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/Interest"
    _name: ClassVar[str] = "Interest"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_interest_target": "http://ontology.naas.ai/people/hasInterestTarget",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "interest_description": "http://ontology.naas.ai/people/interest_description",
        "interest_kind": "http://ontology.naas.ai/people/interest_kind",
        "interest_name": "http://ontology.naas.ai/people/interest_name",
        "is_interest_of": "http://ontology.naas.ai/people/isInterestOf",
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
    interest_name: Optional[
        Annotated[
            str,
            Field(
                description="Name of what the interest is in, carried on the interest itself so an interest with no individual to point at is still stated."
            ),
        ]
    ] = None
    interest_description: Optional[
        Annotated[
            str,
            Field(description="Sentence stating what the interest consists in."),
        ]
    ] = None
    interest_kind: Optional[
        Annotated[
            str,
            Field(
                description="Category of the interest target, used to group interests for display, e.g. 'organization', 'school', 'person', 'topic'."
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
    concretizes: Optional[
        Annotated[
            List[Union[GenericallyDependentContinuant, URIRef, str]],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
    ] = None
    has_interest_target: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="Relates an interest to the entity it is an interest in. Deliberately unrestricted in range: an interest can be in an organization, a person, a place or a subject that has no individual in this graph, in which case only people:interest_name is asserted."
            ),
        ]
    ] = None
    inheres_in: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = None
    is_interest_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(description="Relates an interest to the person in whom it inheres."),
        ]
    ] = None
    participatesIn: Optional[
        Annotated[List[Union[ActOfProfiling, URIRef, str]], Field()]
    ] = None
    participates_in: Optional[
        Annotated[
            List[Union[Process, URIRef, str]],
            Field(
                description="(Elucidation) participates in holds between some b that is either a specifically dependent continuant or generically dependent continuant or independent continuant that is not a spatial region & some process p such that b participates in p some way"
            ),
        ]
    ] = None


class Skill(Quality, RDFEntity):
    """
    Borne by the person, not by the process: the skill outlives any one act of working. people:developsSkill links a planned act, of whatever kind, to the skills exercised and grown in it.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/Skill"
    _name: ClassVar[str] = "Skill"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "inheresIn": "http://ontology.naas.ai/abi/inheresIn",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_skill_developed_in": "http://ontology.naas.ai/people/isSkillDevelopedIn",
        "is_skill_of": "http://ontology.naas.ai/people/isSkillOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "participates_in": "http://ontology.naas.ai/abi/participatesIn",
        "skill_name": "http://ontology.naas.ai/people/skill_name",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "inheresIn",
        "inheres_in",
        "is_skill_developed_in",
        "is_skill_of",
        "participates_in",
    }

    # Data properties
    skill_name: Optional[
        Annotated[
            str,
            Field(description="Name of a skill as stated on the source profile."),
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
    concretizes: Optional[
        Annotated[
            List[Union[GenericallyDependentContinuant, URIRef, str]],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
    ] = None
    inheresIn: Optional[Annotated[List[Union[Person, URIRef, str]], Field()]] = None
    inheres_in: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = None
    is_skill_developed_in: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="Relates a skill to a planned act in which it is exercised and developed."
            ),
        ]
    ] = None
    is_skill_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(description="Relates a skill to the person in whom it inheres."),
        ]
    ] = None
    participates_in: Optional[
        Annotated[
            List[Union[Process, URIRef, str]],
            Field(
                description="(Elucidation) participates in holds between some b that is either a specifically dependent continuant or generically dependent continuant or independent continuant that is not a spatial region & some process p such that b participates in p some way"
            ),
        ]
    ] = None


class Recommendation(DocumentContentEntity, RDFEntity):
    """
    Two people, and both are required: the subject it generically depends on, and the author who wrote it. An anonymous testimonial is not a recommendation in this sense and must not be minted as one.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/Recommendation"
    _name: ClassVar[str] = "Recommendation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_recommendation_author": "http://ontology.naas.ai/people/hasRecommendationAuthor",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_recommendation_of": "http://ontology.naas.ai/people/isRecommendationOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "participatesIn": "http://ontology.naas.ai/abi/participatesIn",
        "recommendation_content": "http://ontology.naas.ai/people/recommendation_content",
        "recommendation_date": "http://ontology.naas.ai/people/recommendation_date",
        "relationship_label": "http://ontology.naas.ai/people/relationship_label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_recommendation_author",
        "is_concretized_by",
        "is_recommendation_of",
        "participatesIn",
    }

    # Data properties
    recommendation_content: Optional[
        Annotated[
            str,
            Field(
                description="Full text of the recommendation, as written by its author."
            ),
        ]
    ] = None
    recommendation_date: Optional[
        Annotated[
            datetime.date,
            Field(description="Date on which the recommendation was written."),
        ]
    ] = None
    relationship_label: Optional[
        Annotated[
            str,
            Field(
                description="How the author of a recommendation describes their working relationship with the person it is about."
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_recommendation_author: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a recommendation to the person who wrote it. Distinct from the person it is about: a recommendation always has two people."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_recommendation_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(description="Relates a recommendation to the person it is about."),
        ]
    ] = None
    participatesIn: Optional[
        Annotated[List[Union[ActOfProfiling, URIRef, str]], Field()]
    ] = None


class ProfileSummary(DocumentContentEntity, RDFEntity):
    """
    Person-level, where people:Mission is job-level: the summary spans a career, a mission describes one act of working. Sourced from a ProfileDocument so every claim it carries stays traceable to where it was published.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/ProfileSummary"
    _name: ClassVar[str] = "Profile Summary"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "headline_text": "http://ontology.naas.ai/people/headline_text",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_profile_summary_of": "http://ontology.naas.ai/people/isProfileSummaryOf",
        "is_sourced_from": "http://ontology.naas.ai/people/isSourcedFrom",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "participatesIn": "http://ontology.naas.ai/abi/participatesIn",
        "quote_content": "http://ontology.naas.ai/people/quote_content",
        "summary_content": "http://ontology.naas.ai/people/summary_content",
        "years_of_experience": "http://ontology.naas.ai/people/years_of_experience",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_concretized_by",
        "is_profile_summary_of",
        "is_sourced_from",
        "participatesIn",
    }

    # Data properties
    headline_text: Optional[
        Annotated[
            str,
            Field(
                description="One-line statement of what a person does, as they present it. Distinct from people:job_title, which is the title of one occupation role."
            ),
        ]
    ] = None
    summary_content: Optional[
        Annotated[
            str,
            Field(
                description="Full text of the profile summary: the paragraph a person or their organization publishes about them."
            ),
        ]
    ] = None
    quote_content: Optional[
        Annotated[
            str,
            Field(
                description="Sentence attributed to the person in their own words, published alongside the summary."
            ),
        ]
    ] = None
    years_of_experience: Optional[
        Annotated[
            int,
            Field(
                description="Number of years of professional experience the profile summary claims. A claim carried by the summary and traceable to its source, not a figure computed from the acts of working in this graph: the graph holds only the working history that has been recorded."
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_profile_summary_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(description="Relates a profile summary to the person it is about."),
        ]
    ] = None
    is_sourced_from: Optional[
        Annotated[
            List[Union[ProfileDocument, URIRef, str]],
            Field(
                description="Relates an information content entity to the profile document it was read from."
            ),
        ]
    ] = None
    participatesIn: Optional[
        Annotated[List[Union[ActOfProfiling, URIRef, str]], Field()]
    ] = None


class ProfileDocument(DocumentContentEntity, RDFEntity):
    """
    The provenance anchor of the demo graph: everything asserted from a profile page: missions, roles, skills, enrollments, degrees, certifications points back to the ProfileDocument it was read from.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/people/ProfileDocument"
    _name: ClassVar[str] = "Profile Document"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "genericallyDependsOn": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_profile_document_of": "http://ontology.naas.ai/people/isProfileDocumentOf",
        "is_source_document_of": "http://ontology.naas.ai/people/isSourceDocumentOf",
        "is_source_of": "http://ontology.naas.ai/people/isSourceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "source_url": "http://ontology.naas.ai/people/source_url",
    }
    _object_properties: ClassVar[set[str]] = {
        "genericallyDependsOn",
        "generically_depends_on",
        "is_concretized_by",
        "is_profile_document_of",
        "is_source_document_of",
        "is_source_of",
    }

    # Data properties
    source_url: Optional[
        Annotated[
            Any,
            Field(description="Address at which a profile document can be retrieved."),
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
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_profile_document_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a profile document to the person it is about and on which it generically depends."
            ),
        ]
    ] = None
    is_source_document_of: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="Relates a profile document to a planned act that was read from it and registered against it."
            ),
        ]
    ] = None
    is_source_of: Optional[
        Annotated[
            List[Union[GenericallyDependentContinuant, URIRef, str]],
            Field(
                description="Relates a profile document to an information content entity read from it."
            ),
        ]
    ] = None


# Rebuild models to resolve forward references
EnrollmentRecord.model_rebuild()
AcademicDegree.model_rebuild()
Certification.model_rebuild()
Portrait.model_rebuild()
OccupationRole.model_rebuild()
StudentRole.model_rebuild()
LanguageCapability.model_rebuild()
Interest.model_rebuild()
Skill.model_rebuild()
Recommendation.model_rebuild()
ProfileSummary.model_rebuild()
ProfileDocument.model_rebuild()
