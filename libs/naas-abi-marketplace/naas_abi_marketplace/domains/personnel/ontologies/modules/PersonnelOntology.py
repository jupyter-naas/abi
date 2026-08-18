from __future__ import annotations

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
from naas_abi_marketplace.domains.personnel.ontologies.processes.ActOfStudyingProcess import (
    ActOfStudying,
)
from naas_abi_marketplace.domains.personnel.ontologies.processes.ActOfWorkingProcess import (
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


class EmploymentRecord(GenericallyDependentContinuant, RDFEntity):
    """
    Generically dependent on the person: the same record can be copied between systems without ceasing to be the record of that person. Concretized by the Act of Working that the relationship consists in.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/EmploymentRecord"
    _name: ClassVar[str] = "Employment Record"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "employee_id": "http://ontology.naas.ai/personnel/employee_id",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "hire_date": "http://ontology.naas.ai/personnel/hire_date",
        "isConcretizedBy": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_employment_record_of": "http://ontology.naas.ai/personnel/isEmploymentRecordOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "termination_date": "http://ontology.naas.ai/personnel/termination_date",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "isConcretizedBy",
        "is_concretized_by",
        "is_employment_record_of",
    }

    # Data properties
    employee_id: Optional[
        Annotated[
            str,
            Field(
                description="Identifier assigned to a person by the employing organization's HR system."
            ),
        ]
    ] = None
    hire_date: Optional[
        Annotated[
            datetime.date,
            Field(
                description="Date on which the employment relationship documented by this record began."
            ),
        ]
    ] = None
    termination_date: Optional[
        Annotated[
            datetime.date,
            Field(
                description="Date on which the employment relationship documented by this record ended. Absent while the relationship is active."
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
    isConcretizedBy: Optional[
        Annotated[List[Union[ActOfWorking, URIRef, str]], Field()]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_employment_record_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates an employment record to the person on which it generically depends."
            ),
        ]
    ] = None


class JobPosition(GenericallyDependentContinuant, RDFEntity):
    """
    Deliberately NOT a subclass of abi:Role. A BFO role must inhere in a bearer, but an open requisition has no occupant. Occupied positions are concretized by personnel:EmployeeRole (allValuesFrom, not someValuesFrom, so a vacant position remains satisfiable).
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/JobPosition"
    _name: ClassVar[str] = "Job Position"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "genericallyDependsOn": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_job_description": "http://ontology.naas.ai/personnel/hasJobDescription",
        "isConcretizedBy": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_job_position_of": "http://ontology.naas.ai/personnel/isJobPositionOf",
        "job_family": "http://ontology.naas.ai/personnel/job_family",
        "job_title": "http://ontology.naas.ai/personnel/job_title",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "genericallyDependsOn",
        "generically_depends_on",
        "has_job_description",
        "isConcretizedBy",
        "is_concretized_by",
        "is_job_position_of",
    }

    # Data properties
    job_title: Optional[
        Annotated[
            str,
            Field(
                description="Title of the job position as published by the organization."
            ),
        ]
    ] = None
    job_family: Optional[
        Annotated[
            str,
            Field(
                description="Grouping of related job positions sharing a common discipline or career track."
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
        Annotated[List[Union[Organization, URIRef, str]], Field()]
    ] = None
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_job_description: Optional[
        Annotated[
            List[Union[JobDescription, URIRef, str]],
            Field(
                description="Relates a job position to the job description document that states its duties and requirements."
            ),
        ]
    ] = None
    isConcretizedBy: Optional[
        Annotated[List[Union[EmployeeRole, URIRef, str]], Field()]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_job_position_of: Optional[
        Annotated[
            List[Union[EmployeeRole, URIRef, str]],
            Field(
                description="Relates a job position to the employee role that concretizes it, when the position is occupied."
            ),
        ]
    ] = None


class EmploymentContract(GenericallyDependentContinuant, RDFEntity):
    """
    Employment Contract
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/EmploymentContract"
    _name: ClassVar[str] = "Employment Contract"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "genericallyDependsOn": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "isConcretizedBy": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_about_job_description": "http://ontology.naas.ai/personnel/isAboutJobDescription",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "genericallyDependsOn",
        "generically_depends_on",
        "isConcretizedBy",
        "is_about_job_description",
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
    isConcretizedBy: Optional[
        Annotated[List[Union[ActOfWorking, URIRef, str]], Field()]
    ] = None
    is_about_job_description: Optional[
        Annotated[
            List[Union[JobDescription, URIRef, str]],
            Field(
                description="Relates an employment contract to the job description it is about."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class EnrollmentRecord(GenericallyDependentContinuant, RDFEntity):
    """
    Enrollment Record
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/EnrollmentRecord"
    _name: ClassVar[str] = "Enrollment Record"
    _property_uris: ClassVar[dict] = {
        "completion_date": "http://ontology.naas.ai/personnel/completion_date",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "enrollment_date": "http://ontology.naas.ai/personnel/enrollment_date",
        "genericallyDependsOn": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "isConcretizedBy": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_enrollment_record_of": "http://ontology.naas.ai/personnel/isEnrollmentRecordOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "program_name": "http://ontology.naas.ai/personnel/program_name",
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

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/AcademicDegree"
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


class EmployeeRole(Role, RDFEntity):
    """
    Externally grounded: it exists only while the employment relationship holds, and ends without the person ceasing to exist. Concretizes a JobPosition (possibly filling a previously vacant requisition).
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/EmployeeRole"
    _name: ClassVar[str] = "Employee Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "hasRealization": "http://ontology.naas.ai/abi/hasRealization",
        "has_job_position": "http://ontology.naas.ai/personnel/hasJobPosition",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_employee_role_of": "http://ontology.naas.ai/personnel/isEmployeeRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "hasRealization",
        "has_job_position",
        "has_realization",
        "inheres_in",
        "is_employee_role_of",
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
        Annotated[List[Union[ActOfWorking, URIRef, str]], Field()]
    ] = None
    has_job_position: Optional[
        Annotated[
            List[Union[JobPosition, URIRef, str]],
            Field(
                description="Relates an employee role to the job position it concretizes. Named sub-property of abi:concretizes: a role (SDC) concretizes a position (GDC)."
            ),
        ]
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
    is_employee_role_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates an employee role to the person in whom it inheres."
            ),
        ]
    ] = None


class StudentRole(Role, RDFEntity):
    """
    No CCO student-role class; minted in the personnel namespace. Ends when the enrollment ends, without the person ceasing to exist.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/StudentRole"
    _name: ClassVar[str] = "Student Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "hasRealization": "http://ontology.naas.ai/abi/hasRealization",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_student_role_of": "http://ontology.naas.ai/personnel/isStudentRoleOf",
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


class EmploymentStatus(Quality, RDFEntity):
    """
    Employment Status
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/EmploymentStatus"
    _name: ClassVar[str] = "Employment Status"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_employment_status_of": "http://ontology.naas.ai/personnel/isEmploymentStatusOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "participates_in": "http://ontology.naas.ai/abi/participatesIn",
        "status_value": "http://ontology.naas.ai/personnel/status_value",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "inheres_in",
        "is_employment_status_of",
        "participates_in",
    }

    # Data properties
    status_value: Optional[
        Annotated[
            str,
            Field(
                description="Value of an employment status, e.g. 'active', 'on-leave', 'notice-period', 'terminated'."
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
        Annotated[List[Union[EmploymentRecord, URIRef, str]], Field()]
    ] = None
    inheres_in: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = None
    is_employment_status_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates an employment status quality to the person in whom it inheres."
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


class Remuneration(Quality, RDFEntity):
    """
    Remuneration
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/Remuneration"
    _name: ClassVar[str] = "Remuneration"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "inheresIn": "http://ontology.naas.ai/abi/inheresIn",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "participatesIn": "http://ontology.naas.ai/abi/participatesIn",
        "participates_in": "http://ontology.naas.ai/abi/participatesIn",
        "remuneration_amount": "http://ontology.naas.ai/personnel/remuneration_amount",
        "remuneration_currency": "http://ontology.naas.ai/personnel/remuneration_currency",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "inheresIn",
        "inheres_in",
        "participatesIn",
        "participates_in",
    }

    # Data properties
    remuneration_amount: Optional[
        Annotated[
            Any,
            Field(description="Annual remuneration amount in the contract currency."),
        ]
    ] = None
    remuneration_currency: Optional[Annotated[str, Field()]] = None
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
    participatesIn: Optional[
        Annotated[List[Union[ActOfWorking, URIRef, str]], Field()]
    ] = None
    participates_in: Optional[
        Annotated[
            List[Union[Process, URIRef, str]],
            Field(
                description="(Elucidation) participates in holds between some b that is either a specifically dependent continuant or generically dependent continuant or independent continuant that is not a spatial region & some process p such that b participates in p some way"
            ),
        ]
    ] = None


class JobDescription(DocumentContentEntity, RDFEntity):
    """
    Job Description
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/JobDescription"
    _name: ClassVar[str] = "Job Description"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "genericallyDependsOn": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_job_description_of": "http://ontology.naas.ai/personnel/isJobDescriptionOf",
        "is_job_description_of_contract": "http://ontology.naas.ai/personnel/isJobDescriptionOfContract",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "genericallyDependsOn",
        "generically_depends_on",
        "is_concretized_by",
        "is_job_description_of",
        "is_job_description_of_contract",
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
        Annotated[List[Union[Organization, URIRef, str]], Field()]
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
    is_job_description_of: Optional[
        Annotated[
            List[Union[JobPosition, URIRef, str]],
            Field(
                description="Relates a job description document to the job position it describes."
            ),
        ]
    ] = None
    is_job_description_of_contract: Optional[
        Annotated[
            List[Union[EmploymentContract, URIRef, str]],
            Field(
                description="Relates a job description to an employment contract that is about it."
            ),
        ]
    ] = None


# Rebuild models to resolve forward references
EmploymentRecord.model_rebuild()
JobPosition.model_rebuild()
EmploymentContract.model_rebuild()
EnrollmentRecord.model_rebuild()
AcademicDegree.model_rebuild()
EmployeeRole.model_rebuild()
StudentRole.model_rebuild()
EmploymentStatus.model_rebuild()
Remuneration.model_rebuild()
JobDescription.model_rebuild()
