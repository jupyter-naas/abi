# onto2py-source-sha256: 6a584cb5560f23483ede25d5dc1ce9be7e153a5b5d8cb849a48ad3852ea808a0
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
    Agent,
    Disposition,
    GenericallyDependentContinuant,
    MaterialEntity,
    Organization,
    Person,
    Process,
    Quality,
    Role,
    Site,
    TemporalInstant,
    TemporalRegion,
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


class Server(MaterialEntity, RDFEntity):
    """
    Server
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Server"
    _name: ClassVar[str] = "Server"
    _property_uris: ClassVar[dict] = {
        "bearer_of": "http://ontology.naas.ai/abi/bearerOf",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_member_part": "http://ontology.naas.ai/abi/hasMemberPart",
        "is_carrier_of": "http://ontology.naas.ai/abi/isCarrierOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "located_in": "http://ontology.naas.ai/abi/locatedIn",
        "located_in_deployment_site": "http://ontology.naas.ai/nexus/locatedInDeploymentSite",
        "material_basis_of": "http://ontology.naas.ai/abi/materialBasisOf",
        "participates_in": "http://ontology.naas.ai/abi/participatesIn",
    }
    _object_properties: ClassVar[set[str]] = {
        "bearer_of",
        "has_member_part",
        "is_carrier_of",
        "located_in",
        "located_in_deployment_site",
        "material_basis_of",
        "participates_in",
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
    bearer_of: Optional[
        Annotated[
            List[Union[Disposition, Quality, Role, URIRef, str]],
            Field(description="b bearer of c =Def c inheres in b"),
        ]
    ] = None
    has_member_part: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(description="b has member part c =Def c member part of b"),
        ]
    ] = None
    is_carrier_of: Optional[
        Annotated[
            List[Union[GenericallyDependentContinuant, URIRef, str]],
            Field(
                description="b is carrier of c =Def there is some time t such that c generically depends on b at t"
            ),
        ]
    ] = None
    located_in: Optional[
        Annotated[
            List[Union[Site, URIRef, str]],
            Field(
                description="b located in c =Def b is an independent continuant & c is an independent & neither is a spatial region & there is some time t such that the spatial region which b occupies at t is continuant part of the spatial region which c occupies at t"
            ),
        ]
    ] = None
    located_in_deployment_site: Optional[
        Annotated[
            List[Union[DeploymentSite, URIRef, str]],
            Field(
                description="Relates a server to the deployment site in which it is located."
            ),
        ]
    ] = None
    material_basis_of: Optional[
        Annotated[
            List[Union[Disposition, URIRef, str]],
            Field(description="b material basis of c =Def c has material basis b"),
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


class NexusOrganization(Organization, RDFEntity):
    """
    Nexus Organization
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Organization"
    _name: ClassVar[str] = "Nexus Organization"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_tenant": "http://ontology.naas.ai/nexus/hasTenant",
        "has_user": "http://ontology.naas.ai/nexus/hasUser",
        "has_workspace": "http://ontology.naas.ai/nexus/hasWorkspace",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_tenant", "has_user", "has_workspace"}

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
    has_tenant: Optional[
        Annotated[
            List[Union[Tenant, URIRef, str]],
            Field(description="Relates an organization to the tenant role it bears."),
        ]
    ] = None
    has_user: Optional[
        Annotated[
            List[Union[URIRef, User, str]],
            Field(
                description="Relates an organization to a user account that is a member of it in the platform."
            ),
        ]
    ] = None
    has_workspace: Optional[
        Annotated[
            List[Union[URIRef, Workspace, str]],
            Field(
                description="Relates an organization to a workspace that depends on it within the Nexus platform."
            ),
        ]
    ] = None


class DeploymentSite(Site, RDFEntity):
    """
    Deployment Site
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/DeploymentSite"
    _name: ClassVar[str] = "Deployment Site"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

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


class UserSite(Site, RDFEntity):
    """
    User Site
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/UserSite"
    _name: ClassVar[str] = "User Site"
    _property_uris: ClassVar[dict] = {
        "browser": "http://ontology.naas.ai/nexus/browser",
        "country": "http://ontology.naas.ai/nexus/country",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "device": "http://ontology.naas.ai/nexus/device",
        "is_session_context_of": "http://ontology.naas.ai/nexus/isSessionContextOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "browser",
        "country",
        "device",
        "is_session_context_of",
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
    browser: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="The web browser detected for the end user during a platform process or recorded on a session artifact."
            ),
        ]
    ] = None
    country: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="The ISO 3166-1 alpha-2 country code derived from the end-user network location during a platform process."
            ),
        ]
    ] = None
    device: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="The operating system or device class detected for the end user during a platform process or recorded on a session artifact."
            ),
        ]
    ] = None
    is_session_context_of: Optional[
        Annotated[
            List[Union[Session, URIRef, str]],
            Field(
                description="Relates a user-side site to a platform session artifact that generically depends on it during an application visit."
            ),
        ]
    ] = None


class User(GenericallyDependentContinuant, RDFEntity):
    """
    User
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/User"
    _name: ClassVar[str] = "User"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_session": "http://ontology.naas.ai/nexus/hasSession",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_user_account_of": "http://ontology.naas.ai/nexus/isUserAccountOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "user_email": "http://ontology.naas.ai/nexus/user_email",
        "user_id": "http://ontology.naas.ai/nexus/user_id",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_session",
        "is_concretized_by",
        "is_user_account_of",
    }

    # Data properties
    user_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of the user account in the Nexus platform."
            ),
        ]
    ] = None
    user_email: Optional[
        Annotated[
            str,
            Field(
                description="The email address associated with the user account in the Nexus platform."
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
    has_session: Optional[
        Annotated[
            List[Union[Session, URIRef, str]],
            Field(
                description="Relates a user account to a platform session artifact it carries during an application visit."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_user_account_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a user account to the person on which it generically depends."
            ),
        ]
    ] = None


class Workspace(GenericallyDependentContinuant, RDFEntity):
    """
    Workspace
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Workspace"
    _name: ClassVar[str] = "Workspace"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_conversation": "http://ontology.naas.ai/nexus/hasConversation",
        "has_marketplace_apps": "http://ontology.naas.ai/nexus/hasMarketplaceApps",
        "has_workspace_role": "http://ontology.naas.ai/nexus/hasWorkspaceRole",
        "hosted_on": "http://ontology.naas.ai/nexus/hostedOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_workspace_of": "http://ontology.naas.ai/nexus/isWorkspaceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "logo_url": "http://ontology.naas.ai/nexus/logo_url",
        "workspace_id": "http://ontology.naas.ai/nexus/workspace_id",
        "workspace_name": "http://ontology.naas.ai/nexus/workspace_name",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_conversation",
        "has_marketplace_apps",
        "has_workspace_role",
        "hosted_on",
        "is_concretized_by",
        "is_workspace_of",
    }

    # Data properties
    logo_url: Optional[
        Annotated[
            str,
            Field(
                description="A URL to a logo image used in Nexus platform to identify a generically dependent continuant instance."
            ),
        ]
    ] = None
    workspace_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of a workspace in the Nexus platform."
            ),
        ]
    ] = None
    workspace_name: Optional[
        Annotated[
            str,
            Field(
                description="The human-readable display name of a workspace in the Nexus platform."
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
    has_conversation: Optional[
        Annotated[
            List[Union[Conversation, URIRef, str]],
            Field(
                description="Relates a workspace to a conversation it carries or contains."
            ),
        ]
    ] = None
    has_marketplace_apps: Optional[
        Annotated[
            List[Union[MarketplaceApps, URIRef, str]],
            Field(
                description="Relates a workspace to a marketplace application available in or associated with it."
            ),
        ]
    ] = None
    has_workspace_role: Optional[
        Annotated[
            List[Union[URIRef, WorkspaceRole, str]],
            Field(
                description="Relates a workspace to a workspace role that concretizes it in platform use."
            ),
        ]
    ] = None
    hosted_on: Optional[
        Annotated[
            List[Union[Server, URIRef, str]],
            Field(
                description="Relates a workspace to the physical server on which it depends for hosting."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_workspace_of: Optional[
        Annotated[
            List[Union[NexusOrganization, URIRef, str]],
            Field(
                description="Relates a workspace to the organization on which it generically depends."
            ),
        ]
    ] = None


class Search(GenericallyDependentContinuant, RDFEntity):
    """
    Search
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Search"
    _name: ClassVar[str] = "Search"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_search_role": "http://ontology.naas.ai/nexus/hasSearchRole",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_search_role",
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_search_role: Optional[
        Annotated[
            List[Union[SearchRole, URIRef, str]],
            Field(
                description="Relates a search artifact to a search role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class Conversation(GenericallyDependentContinuant, RDFEntity):
    """
    Conversation
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Conversation"
    _name: ClassVar[str] = "Conversation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_conversation_role": "http://ontology.naas.ai/nexus/hasConversationRole",
        "has_message": "http://ontology.naas.ai/nexus/hasMessage",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_conversation_of": "http://ontology.naas.ai/nexus/isConversationOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_conversation_role",
        "has_message",
        "is_concretized_by",
        "is_conversation_of",
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_conversation_role: Optional[
        Annotated[
            List[Union[ConversationRole, URIRef, str]],
            Field(
                description="Relates a conversation to a conversation role that concretizes it in platform use."
            ),
        ]
    ] = None
    has_message: Optional[
        Annotated[
            List[Union[Message, URIRef, str]],
            Field(description="Relates a conversation to a message it contains."),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_conversation_of: Optional[
        Annotated[
            List[Union[URIRef, Workspace, str]],
            Field(
                description="Relates a conversation to the workspace on which it depends."
            ),
        ]
    ] = None


class Message(GenericallyDependentContinuant, RDFEntity):
    """
    Message
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Message"
    _name: ClassVar[str] = "Message"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_message_role": "http://ontology.naas.ai/nexus/hasMessageRole",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_message_of": "http://ontology.naas.ai/nexus/isMessageOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_message_role",
        "is_concretized_by",
        "is_message_of",
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_message_role: Optional[
        Annotated[
            List[Union[MessageRole, URIRef, str]],
            Field(
                description="Relates a message to a message role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_message_of: Optional[
        Annotated[
            List[Union[Conversation, URIRef, str]],
            Field(
                description="Relates a message to the conversation on which it depends."
            ),
        ]
    ] = None


class AgentTool(GenericallyDependentContinuant, RDFEntity):
    """
    Agent Tool
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/AgentTool"
    _name: ClassVar[str] = "Agent Tool"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/nexus/description",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_tool_of": "http://ontology.naas.ai/nexus/isToolOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_concretized_by",
        "is_tool_of",
    }

    # Data properties
    description: Optional[
        Annotated[
            str,
            Field(
                description="A description used in Nexus platform to identify a generically dependent continuant instance."
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
    is_tool_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(description="Relates a tool to the agent on which it depends."),
        ]
    ] = None


class AgentIntent(GenericallyDependentContinuant, RDFEntity):
    """
    Agent Intent
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/AgentIntent"
    _name: ClassVar[str] = "Agent Intent"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/nexus/description",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "intent_scope": "http://ontology.naas.ai/nexus/intent_scope",
        "intent_target": "http://ontology.naas.ai/nexus/intent_target",
        "intent_type": "http://ontology.naas.ai/nexus/intent_type",
        "intent_value": "http://ontology.naas.ai/nexus/intent_value",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_intent_of": "http://ontology.naas.ai/nexus/isIntentOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_concretized_by",
        "is_intent_of",
    }

    # Data properties
    description: Optional[
        Annotated[
            str,
            Field(
                description="A description used in Nexus platform to identify a generically dependent continuant instance."
            ),
        ]
    ] = None
    intent_type: Optional[
        Annotated[str, Field(description="The type of the intent.")]
    ] = None
    intent_value: Optional[
        Annotated[str, Field(description="The value of the intent.")]
    ] = None
    intent_target: Optional[
        Annotated[str, Field(description="The target of the intent.")]
    ] = None
    intent_scope: Optional[
        Annotated[str, Field(description="The scope of the intent.")]
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
    is_intent_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(description="Relates an intent to the agent on which it depends."),
        ]
    ] = None


class Ontology(GenericallyDependentContinuant, RDFEntity):
    """
    Ontology
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Ontology"
    _name: ClassVar[str] = "Ontology"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_ontology_class": "http://ontology.naas.ai/nexus/hasOntologyClass",
        "has_ontology_module": "http://ontology.naas.ai/nexus/hasOntologyModule",
        "has_ontology_object_property": "http://ontology.naas.ai/nexus/hasOntologyObjectProperty",
        "has_ontology_role": "http://ontology.naas.ai/nexus/hasOntologyRole",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_ontology_class",
        "has_ontology_module",
        "has_ontology_object_property",
        "has_ontology_role",
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_ontology_class: Optional[
        Annotated[
            List[Union[OntologyClass, URIRef, str]],
            Field(description="Relates an ontology to a class defined within it."),
        ]
    ] = None
    has_ontology_module: Optional[
        Annotated[
            List[Union[OntologyModule, URIRef, str]],
            Field(description="Relates an ontology to one of its ontology modules."),
        ]
    ] = None
    has_ontology_object_property: Optional[
        Annotated[
            List[Union[OntologyObjectProperty, URIRef, str]],
            Field(
                description="Relates an ontology to an object property defined within it."
            ),
        ]
    ] = None
    has_ontology_role: Optional[
        Annotated[
            List[Union[OntologyRole, URIRef, str]],
            Field(
                description="Relates an ontology to an ontology role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class OntologyModule(GenericallyDependentContinuant, RDFEntity):
    """
    Ontology Module
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyModule"
    _name: ClassVar[str] = "Ontology Module"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_ontology_module_role": "http://ontology.naas.ai/nexus/hasOntologyModuleRole",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_ontology_module_of": "http://ontology.naas.ai/nexus/isOntologyModuleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_ontology_module_role",
        "is_concretized_by",
        "is_ontology_module_of",
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_ontology_module_role: Optional[
        Annotated[
            List[Union[OntologyModuleRole, URIRef, str]],
            Field(
                description="Relates an ontology module to an ontology module role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_ontology_module_of: Optional[
        Annotated[
            List[Union[Ontology, URIRef, str]],
            Field(
                description="Relates an ontology module to the ontology on which it depends."
            ),
        ]
    ] = None


class OntologyClass(GenericallyDependentContinuant, RDFEntity):
    """
    Ontology Class
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyClass"
    _name: ClassVar[str] = "Ontology Class"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_ontology_class_role": "http://ontology.naas.ai/nexus/hasOntologyClassRole",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_ontology_class_role",
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_ontology_class_role: Optional[
        Annotated[
            List[Union[OntologyClassRole, URIRef, str]],
            Field(
                description="Relates an ontology class to an ontology class role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class OntologyObjectProperty(GenericallyDependentContinuant, RDFEntity):
    """
    Ontology Object Property
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyObjectProperty"
    _name: ClassVar[str] = "Ontology Object Property"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_ontology_object_property_role": "http://ontology.naas.ai/nexus/hasOntologyObjectPropertyRole",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_ontology_object_property_role",
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_ontology_object_property_role: Optional[
        Annotated[
            List[Union[OntologyObjectPropertyRole, URIRef, str]],
            Field(
                description="Relates an ontology object property to an ontology object property role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class KnowledgeGraph(GenericallyDependentContinuant, RDFEntity):
    """
    Knowledge Graph
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/KnowledgeGraph"
    _name: ClassVar[str] = "Knowledge Graph"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/nexus/description",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_graph_view": "http://ontology.naas.ai/nexus/hasGraphView",
        "has_knowledge_graph_role": "http://ontology.naas.ai/nexus/hasKnowledgeGraphRole",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_graph_view",
        "has_knowledge_graph_role",
        "is_concretized_by",
    }

    # Data properties
    description: Optional[
        Annotated[
            str,
            Field(
                description="A description used in Nexus platform to identify a generically dependent continuant instance."
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
    has_graph_view: Optional[
        Annotated[
            List[Union[GraphView, URIRef, str]],
            Field(
                description="Relates a knowledge graph to a graph view derived from it."
            ),
        ]
    ] = None
    has_knowledge_graph_role: Optional[
        Annotated[
            List[Union[KnowledgeGraphRole, URIRef, str]],
            Field(
                description="Relates a knowledge graph to a knowledge graph role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class GraphView(GenericallyDependentContinuant, RDFEntity):
    """
    Graph View
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/GraphView"
    _name: ClassVar[str] = "Graph View"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/nexus/description",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_graph_filter": "http://ontology.naas.ai/nexus/hasGraphFilter",
        "has_graph_view_role": "http://ontology.naas.ai/nexus/hasGraphViewRole",
        "includes_knowledge_graph": "http://ontology.naas.ai/nexus/includesKnowledgeGraph",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_graph_filter",
        "has_graph_view_role",
        "includes_knowledge_graph",
        "is_concretized_by",
    }

    # Data properties
    description: Optional[
        Annotated[
            str,
            Field(
                description="A description used in Nexus platform to identify a generically dependent continuant instance."
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
    has_graph_filter: Optional[
        Annotated[
            List[Union[GraphFilter, URIRef, str]],
            Field(description="Relates a graph view to a graph filter used in it."),
        ]
    ] = None
    has_graph_view_role: Optional[
        Annotated[
            List[Union[GraphViewRole, URIRef, str]],
            Field(
                description="Relates a graph view to a graph view role that concretizes it in platform use."
            ),
        ]
    ] = None
    includes_knowledge_graph: Optional[
        Annotated[
            List[Union[KnowledgeGraph, URIRef, str]],
            Field(description="Relates a graph view to a knowledge graph it includes."),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class GraphFilter(GenericallyDependentContinuant, RDFEntity):
    """
    Graph Filter
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/GraphFilter"
    _name: ClassVar[str] = "Graph Filter"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_graph_filter_role": "http://ontology.naas.ai/nexus/hasGraphFilterRole",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "object_uri": "http://ontology.naas.ai/nexus/object_uri",
        "predicate_uri": "http://ontology.naas.ai/nexus/predicate_uri",
        "subject_uri": "http://ontology.naas.ai/nexus/subject_uri",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_graph_filter_role",
        "is_concretized_by",
    }

    # Data properties
    subject_uri: Optional[
        Annotated[
            str,
            Field(description="The URI of the subject filtering the graph view."),
        ]
    ] = None
    predicate_uri: Optional[
        Annotated[
            str,
            Field(description="The URI of the predicate filtering the graph view."),
        ]
    ] = None
    object_uri: Optional[
        Annotated[
            str,
            Field(
                description="The URI or literal of the object filtering the graph view."
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
    has_graph_filter_role: Optional[
        Annotated[
            List[Union[GraphFilterRole, URIRef, str]],
            Field(
                description="Relates a graph filter to a graph filter role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class Files(GenericallyDependentContinuant, RDFEntity):
    """
    Files
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Files"
    _name: ClassVar[str] = "Files"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_file_role": "http://ontology.naas.ai/nexus/hasFileRole",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_file_role",
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_file_role: Optional[
        Annotated[
            List[Union[FileRole, URIRef, str]],
            Field(
                description="Relates a file artifact to a file role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class FileSystem(GenericallyDependentContinuant, RDFEntity):
    """
    File System
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/FileSystem"
    _name: ClassVar[str] = "File System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_file_system_role": "http://ontology.naas.ai/nexus/hasFileSystemRole",
        "has_files": "http://ontology.naas.ai/nexus/hasFiles",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_file_system_role",
        "has_files",
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_file_system_role: Optional[
        Annotated[
            List[Union[FileSystemRole, URIRef, str]],
            Field(
                description="Relates a file system to a file system role that concretizes it in platform use."
            ),
        ]
    ] = None
    has_files: Optional[
        Annotated[
            List[Union[Files, URIRef, str]],
            Field(description="Relates a file system to files accessible through it."),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class MarketplaceApps(GenericallyDependentContinuant, RDFEntity):
    """
    Marketplace Apps
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/MarketplaceApps"
    _name: ClassVar[str] = "Marketplace Apps"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_marketplace_app_role": "http://ontology.naas.ai/nexus/hasMarketplaceAppRole",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_marketplace_app_role",
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
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_marketplace_app_role: Optional[
        Annotated[
            List[Union[MarketplaceAppRole, URIRef, str]],
            Field(
                description="Relates a marketplace application to a marketplace application role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class AIModel(GenericallyDependentContinuant, RDFEntity):
    """
    AI Model
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/AIModel"
    _name: ClassVar[str] = "AI Model"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_provider": "http://ontology.naas.ai/nexus/hasProvider",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_model_of": "http://ontology.naas.ai/nexus/isModelOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "model_id": "http://ontology.naas.ai/nexus/model_id",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_provider",
        "is_concretized_by",
        "is_model_of",
    }

    # Data properties
    model_id: Optional[
        Annotated[str, Field(description="The identifier of the AI model.")]
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
    has_provider: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="Relates an AI model to the organization that provides it."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_model_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(description="Relates an AI model to the agent that uses it."),
        ]
    ] = None


class Page(GenericallyDependentContinuant, RDFEntity):
    """
    Page
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Page"
    _name: ClassVar[str] = "Page"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_visited_page_of": "http://ontology.naas.ai/nexus/isVisitedPageOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "page_path": "http://ontology.naas.ai/nexus/page_path",
        "page_title": "http://ontology.naas.ai/nexus/page_title",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_concretized_by",
        "is_visited_page_of",
    }

    # Data properties
    page_path: Optional[
        Annotated[
            str,
            Field(description="The URL path of a page within the Nexus platform."),
        ]
    ] = None
    page_title: Optional[
        Annotated[
            str,
            Field(
                description="The HTML document title of a page within the Nexus platform."
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
    is_visited_page_of: Optional[
        Annotated[
            List[Union[PageView, URIRef, str]],
            Field(
                description="Relates a page artifact to the page-view process in which it was visited."
            ),
        ]
    ] = None


class Session(GenericallyDependentContinuant, RDFEntity):
    """
    Session
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Session"
    _name: ClassVar[str] = "Session"
    _property_uris: ClassVar[dict] = {
        "browser": "http://ontology.naas.ai/nexus/browser",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "depends_on_user": "http://ontology.naas.ai/nexus/dependsOnUser",
        "depends_on_user_site": "http://ontology.naas.ai/nexus/dependsOnUserSite",
        "device": "http://ontology.naas.ai/nexus/device",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_created_by": "http://ontology.naas.ai/nexus/isCreatedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "session_id": "http://ontology.naas.ai/nexus/session_id",
    }
    _object_properties: ClassVar[set[str]] = {
        "browser",
        "depends_on_user",
        "depends_on_user_site",
        "device",
        "generically_depends_on",
        "is_concretized_by",
        "is_created_by",
        "session_id",
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
    browser: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="The web browser detected for the end user during a platform process or recorded on a session artifact."
            ),
        ]
    ] = None
    depends_on_user: Optional[
        Annotated[
            List[Union[URIRef, User, str]],
            Field(
                description="Relates a platform session artifact to the user account on which it generically depends when the user visits the application."
            ),
        ]
    ] = None
    depends_on_user_site: Optional[
        Annotated[
            List[Union[URIRef, UserSite, str]],
            Field(
                description="Relates a platform session artifact to the user-side site (device, browser, country context) on which it generically depends when the user visits the application."
            ),
        ]
    ] = None
    device: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="The operating system or device class detected for the end user during a platform process or recorded on a session artifact."
            ),
        ]
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
    is_created_by: Optional[
        Annotated[
            List[Union[URIRef, VisitSession, str]],
            Field(
                description="Relates a generically dependent continuant artifact to the platform process that created it in the application."
            ),
        ]
    ] = None
    session_id: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="The unique identifier of a platform session artifact or visit-session process in the Nexus platform."
            ),
        ]
    ] = None


class AuthenticationStatus(GenericallyDependentContinuant, RDFEntity):
    """
    Authentication Status
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/AuthenticationStatus"
    _name: ClassVar[str] = "Authentication Status"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
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


class Tenant(Role, RDFEntity):
    """
    Tenant
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Tenant"
    _name: ClassVar[str] = "Tenant"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_tenant_of": "http://ontology.naas.ai/nexus/isTenantOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_tenant_of",
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
    is_tenant_of: Optional[
        Annotated[
            List[Union[NexusOrganization, URIRef, str]],
            Field(
                description="Relates a tenant role to the organization in which it inheres."
            ),
        ]
    ] = None


class WorkspaceRole(Role, RDFEntity):
    """
    Workspace Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/WorkspaceRole"
    _name: ClassVar[str] = "Workspace Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_workspace_role_of": "http://ontology.naas.ai/nexus/isWorkspaceRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_workspace_role_of",
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
    is_workspace_role_of: Optional[
        Annotated[
            List[Union[URIRef, Workspace, str]],
            Field(
                description="Relates a workspace role to the workspace of which it is the role-side concretization."
            ),
        ]
    ] = None


class SearchRole(Role, RDFEntity):
    """
    Search Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/SearchRole"
    _name: ClassVar[str] = "Search Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_search_role_of": "http://ontology.naas.ai/nexus/isSearchRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_search_role_of",
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
    is_search_role_of: Optional[
        Annotated[
            List[Union[Search, URIRef, str]],
            Field(
                description="Relates a search role to the search artifact of which it is the role-side concretization."
            ),
        ]
    ] = None


class ConversationRole(Role, RDFEntity):
    """
    Conversation Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/ConversationRole"
    _name: ClassVar[str] = "Conversation Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_conversation_role_of": "http://ontology.naas.ai/nexus/isConversationRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_conversation_role_of",
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
    is_conversation_role_of: Optional[
        Annotated[
            List[Union[Conversation, URIRef, str]],
            Field(
                description="Relates a conversation role to the conversation of which it is the role-side concretization."
            ),
        ]
    ] = None


class MessageRole(Role, RDFEntity):
    """
    Message Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/MessageRole"
    _name: ClassVar[str] = "Message Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_message_role_of": "http://ontology.naas.ai/nexus/isMessageRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_message_role_of",
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
    is_message_role_of: Optional[
        Annotated[
            List[Union[Message, URIRef, str]],
            Field(
                description="Relates a message role to the message of which it is the role-side concretization."
            ),
        ]
    ] = None


class AgentRole(Role, RDFEntity):
    """
    Agent Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/AgentRole"
    _name: ClassVar[str] = "Agent Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/nexus/description",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_agent_role_of": "http://ontology.naas.ai/nexus/isAgentRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_agent_role_of",
    }

    # Data properties
    description: Optional[
        Annotated[
            str,
            Field(
                description="A description used in Nexus platform to identify a generically dependent continuant instance."
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
    is_agent_role_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(
                description="Relates an agent role to the agent of which it is the role-side concretization."
            ),
        ]
    ] = None


class OntologyRole(Role, RDFEntity):
    """
    Ontology Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyRole"
    _name: ClassVar[str] = "Ontology Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_ontology_role_of": "http://ontology.naas.ai/nexus/isOntologyRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_ontology_role_of",
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
    is_ontology_role_of: Optional[
        Annotated[
            List[Union[Ontology, URIRef, str]],
            Field(
                description="Relates an ontology role to the ontology of which it is the role-side concretization."
            ),
        ]
    ] = None


class OntologyModuleRole(Role, RDFEntity):
    """
    Ontology Module Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyModuleRole"
    _name: ClassVar[str] = "Ontology Module Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_ontology_module_role_of": "http://ontology.naas.ai/nexus/isOntologyModuleRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_ontology_module_role_of",
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
    is_ontology_module_role_of: Optional[
        Annotated[
            List[Union[OntologyModule, URIRef, str]],
            Field(
                description="Relates an ontology module role to the ontology module of which it is the role-side concretization."
            ),
        ]
    ] = None


class OntologyClassRole(Role, RDFEntity):
    """
    Ontology Class Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyClassRole"
    _name: ClassVar[str] = "Ontology Class Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_ontology_class_role_of": "http://ontology.naas.ai/nexus/isOntologyClassRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_ontology_class_role_of",
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
    is_ontology_class_role_of: Optional[
        Annotated[
            List[Union[OntologyClass, URIRef, str]],
            Field(
                description="Relates an ontology class role to the ontology class of which it is the role-side concretization."
            ),
        ]
    ] = None


class OntologyObjectPropertyRole(Role, RDFEntity):
    """
    Ontology Object Property Role
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/nexus/OntologyObjectPropertyRole"
    )
    _name: ClassVar[str] = "Ontology Object Property Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_ontology_object_property_role_of": "http://ontology.naas.ai/nexus/isOntologyObjectPropertyRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_ontology_object_property_role_of",
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
    is_ontology_object_property_role_of: Optional[
        Annotated[
            List[Union[OntologyObjectProperty, URIRef, str]],
            Field(
                description="Relates an ontology object property role to the ontology object property of which it is the role-side concretization."
            ),
        ]
    ] = None


class KnowledgeGraphRole(Role, RDFEntity):
    """
    Knowledge Graph Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/KnowledgeGraphRole"
    _name: ClassVar[str] = "Knowledge Graph Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_knowledge_graph_role_of": "http://ontology.naas.ai/nexus/isKnowledgeGraphRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_knowledge_graph_role_of",
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
    is_knowledge_graph_role_of: Optional[
        Annotated[
            List[Union[KnowledgeGraph, URIRef, str]],
            Field(
                description="Relates a knowledge graph role to the knowledge graph of which it is the role-side concretization."
            ),
        ]
    ] = None


class GraphViewRole(Role, RDFEntity):
    """
    Graph View Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/GraphViewRole"
    _name: ClassVar[str] = "Graph View Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_graph_view_role_of": "http://ontology.naas.ai/nexus/isGraphViewRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_graph_view_role_of",
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
    is_graph_view_role_of: Optional[
        Annotated[
            List[Union[GraphView, URIRef, str]],
            Field(
                description="Relates a graph view role to the graph view of which it is the role-side concretization."
            ),
        ]
    ] = None


class GraphFilterRole(Role, RDFEntity):
    """
    Graph Filter Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/GraphFilterRole"
    _name: ClassVar[str] = "Graph Filter Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_graph_filter_role_of": "http://ontology.naas.ai/nexus/isGraphFilterRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_graph_filter_role_of",
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
    is_graph_filter_role_of: Optional[
        Annotated[
            List[Union[GraphFilter, URIRef, str]],
            Field(
                description="Relates a graph filter role to the graph filter of which it is the role-side concretization."
            ),
        ]
    ] = None


class FileRole(Role, RDFEntity):
    """
    File Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/FileRole"
    _name: ClassVar[str] = "File Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_file_role_of": "http://ontology.naas.ai/nexus/isFileRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_file_role_of",
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
    is_file_role_of: Optional[
        Annotated[
            List[Union[Files, URIRef, str]],
            Field(
                description="Relates a file role to the file artifact of which it is the role-side concretization."
            ),
        ]
    ] = None


class FileSystemRole(Role, RDFEntity):
    """
    File System Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/FileSystemRole"
    _name: ClassVar[str] = "File System Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_file_system_role_of": "http://ontology.naas.ai/nexus/isFileSystemRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_file_system_role_of",
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
    is_file_system_role_of: Optional[
        Annotated[
            List[Union[FileSystem, URIRef, str]],
            Field(
                description="Relates a file system role to the file system of which it is the role-side concretization."
            ),
        ]
    ] = None


class MarketplaceAppRole(Role, RDFEntity):
    """
    Marketplace App Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/MarketplaceAppRole"
    _name: ClassVar[str] = "Marketplace App Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_marketplace_app_role_of": "http://ontology.naas.ai/nexus/isMarketplaceAppRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_marketplace_app_role_of",
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
    is_marketplace_app_role_of: Optional[
        Annotated[
            List[Union[MarketplaceApps, URIRef, str]],
            Field(
                description="Relates a marketplace application role to the marketplace application of which it is the role-side concretization."
            ),
        ]
    ] = None


class Capabilities(Disposition, RDFEntity):
    """
    Capabilities
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Capabilities"
    _name: ClassVar[str] = "Capabilities"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_material_basis": "http://ontology.naas.ai/abi/hasMaterialBasis",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheresIn": "http://ontology.naas.ai/abi/inheresIn",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_capabilities_of": "http://ontology.naas.ai/nexus/isCapabilitiesOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_material_basis",
        "has_realization",
        "inheresIn",
        "inheres_in",
        "is_capabilities_of",
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
    has_material_basis: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b has material basis c =Def b is a disposition & c is a material entity & there is some d bearer of b & there is some time t such that c is a continuant part of d at t & d has disposition b because c is a continuant part of d at t"
            ),
        ]
    ] = None
    has_realization: Optional[
        Annotated[
            List[Union[Process, URIRef, str]],
            Field(description="b has realization c =Def c realizes b"),
        ]
    ] = None
    inheresIn: Optional[Annotated[List[Union[Organization, URIRef, str]], Field()]] = (
        None
    )
    inheres_in: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = None
    is_capabilities_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="Relates a capability to the organization in which it inheres."
            ),
        ]
    ] = None


class FrontEndEvent(Process, RDFEntity):
    """
    Front End Event
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/FrontEndEvent"
    _name: ClassVar[str] = "Front End Event"
    _property_uris: ClassVar[dict] = {
        "browser": "http://ontology.naas.ai/nexus/browser",
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "country": "http://ontology.naas.ai/nexus/country",
        "created": "http://purl.org/dc/terms/created",
        "created_at": "http://ontology.naas.ai/nexus/createdAt",
        "creator": "http://purl.org/dc/terms/creator",
        "device": "http://ontology.naas.ai/nexus/device",
        "event_id": "http://ontology.naas.ai/nexus/event_id",
        "event_name": "http://ontology.naas.ai/nexus/event_name",
        "has_participant": "http://ontology.naas.ai/abi/hasParticipant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupies_temporal_region": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occurs_in": "http://ontology.naas.ai/abi/occursIn",
        "page_path": "http://ontology.naas.ai/nexus/page_path",
        "page_title": "http://ontology.naas.ai/nexus/page_title",
        "realizes": "http://ontology.naas.ai/abi/realizes",
        "referrer": "http://ontology.naas.ai/nexus/referrer",
        "session_id": "http://ontology.naas.ai/nexus/session_id",
        "timestamp": "http://ontology.naas.ai/nexus/timestamp",
        "user_email": "http://ontology.naas.ai/nexus/user_email",
        "user_id": "http://ontology.naas.ai/nexus/user_id",
        "workspace_id": "http://ontology.naas.ai/nexus/workspace_id",
        "workspace_name": "http://ontology.naas.ai/nexus/workspace_name",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "created_at",
        "has_participant",
        "occupies_temporal_region",
        "occurs_in",
        "realizes",
    }

    # Data properties
    user_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of the user account in the Nexus platform."
            ),
        ]
    ] = None
    user_email: Optional[
        Annotated[
            str,
            Field(
                description="The email address associated with the user account in the Nexus platform."
            ),
        ]
    ] = None
    event_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of the platform analytics event corresponding to a process instance in the Nexus platform."
            ),
        ]
    ] = None
    event_name: Optional[
        Annotated[
            str,
            Field(
                description="Name/type of the analytics event (e.g. 'page_viewed', 'clicked')."
            ),
        ]
    ] = None
    timestamp: Optional[
        Annotated[
            str,
            Field(description="ISO8601 string timestamp when the event was recorded."),
        ]
    ] = None
    session_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of a platform session artifact or visit-session process in the Nexus platform."
            ),
        ]
    ] = None
    workspace_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of a workspace in the Nexus platform."
            ),
        ]
    ] = None
    workspace_name: Optional[
        Annotated[
            str,
            Field(
                description="The human-readable display name of a workspace in the Nexus platform."
            ),
        ]
    ] = None
    page_path: Optional[
        Annotated[
            str,
            Field(description="The URL path of a page within the Nexus platform."),
        ]
    ] = None
    page_title: Optional[
        Annotated[
            str,
            Field(
                description="The HTML document title of a page within the Nexus platform."
            ),
        ]
    ] = None
    country: Optional[
        Annotated[
            str,
            Field(
                description="The ISO 3166-1 alpha-2 country code derived from the end-user network location during a platform process."
            ),
        ]
    ] = None
    device: Optional[
        Annotated[
            str,
            Field(
                description="The operating system or device class detected for the end user during a platform process or recorded on a session artifact."
            ),
        ]
    ] = None
    browser: Optional[
        Annotated[
            str,
            Field(
                description="The web browser detected for the end user during a platform process or recorded on a session artifact."
            ),
        ]
    ] = None
    referrer: Optional[
        Annotated[
            str,
            Field(
                description="The HTTP referrer (originating page or host) recorded at the time of a page-view process."
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
    created_at: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(
                description="Relates a platform process to the temporal instant at which it occurred."
            ),
        ]
    ] = None
    has_participant: Optional[
        Annotated[
            List[Union[MaterialEntity, Quality, URIRef, str]],
            Field(description="p has participant c =Def c participates in p"),
        ]
    ] = None
    occupies_temporal_region: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="p occupies temporal region t =Def p is a process or process boundary & the spatiotemporal region occupied by p temporally projects onto t"
            ),
        ]
    ] = None
    occurs_in: Optional[
        Annotated[
            List[Union[Site, URIRef, str]],
            Field(
                description="b occurs in c =Def b is a process or a process boundary & c is a material entity or site & there exists a spatiotemporal region r & b occupies spatiotemporal region r & for all time t, if b exists at t then c exists at t & there exist spatial regions s and s' where b spatially projects onto s at t & c occupies spatial region s' at t & s is a continuant part of s' at t"
            ),
        ]
    ] = None
    realizes: Optional[
        Annotated[
            List[Union[Disposition, Role, URIRef, str]],
            Field(
                description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
            ),
        ]
    ] = None


class CreateUser(Process, RDFEntity):
    """
    Create User
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/CreateUser"
    _name: ClassVar[str] = "Create User"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "created_at": "http://ontology.naas.ai/nexus/createdAt",
        "created_by": "http://ontology.naas.ai/nexus/createdBy",
        "created_for": "http://ontology.naas.ai/nexus/createdFor",
        "creates": "http://ontology.naas.ai/nexus/creates",
        "creator": "http://purl.org/dc/terms/creator",
        "has_participant": "http://ontology.naas.ai/abi/hasParticipant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupies_temporal_region": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occurs_in": "http://ontology.naas.ai/abi/occursIn",
        "realizes": "http://ontology.naas.ai/abi/realizes",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "created_at",
        "created_by",
        "created_for",
        "creates",
        "has_participant",
        "occupies_temporal_region",
        "occurs_in",
        "realizes",
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
    created_at: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(
                description="Relates a platform process to the temporal instant at which it occurred."
            ),
        ]
    ] = None
    created_by: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a platform process to the agent (user or person) who initiated it."
            ),
        ]
    ] = None
    created_for: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a platform process to the person for whom it was performed."
            ),
        ]
    ] = None
    creates: Optional[
        Annotated[
            List[Union[URIRef, User, str]],
            Field(
                description="Relates a platform process performed in the application to a generically dependent continuant artifact it creates."
            ),
        ]
    ] = None
    has_participant: Optional[
        Annotated[
            List[Union[MaterialEntity, Quality, URIRef, str]],
            Field(description="p has participant c =Def c participates in p"),
        ]
    ] = None
    occupies_temporal_region: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="p occupies temporal region t =Def p is a process or process boundary & the spatiotemporal region occupied by p temporally projects onto t"
            ),
        ]
    ] = None
    occurs_in: Optional[
        Annotated[
            List[Union[Site, URIRef, str]],
            Field(
                description="b occurs in c =Def b is a process or a process boundary & c is a material entity or site & there exists a spatiotemporal region r & b occupies spatiotemporal region r & for all time t, if b exists at t then c exists at t & there exist spatial regions s and s' where b spatially projects onto s at t & c occupies spatial region s' at t & s is a continuant part of s' at t"
            ),
        ]
    ] = None
    realizes: Optional[
        Annotated[
            List[Union[Disposition, Role, URIRef, str]],
            Field(
                description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
            ),
        ]
    ] = None


class CreateWorkspace(Process, RDFEntity):
    """
    Create Workspace
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/CreateWorkspace"
    _name: ClassVar[str] = "Create Workspace"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "created_at": "http://ontology.naas.ai/nexus/createdAt",
        "created_by": "http://ontology.naas.ai/nexus/createdBy",
        "creates": "http://ontology.naas.ai/nexus/creates",
        "creator": "http://purl.org/dc/terms/creator",
        "has_participant": "http://ontology.naas.ai/abi/hasParticipant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupies_temporal_region": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occurs_in": "http://ontology.naas.ai/abi/occursIn",
        "realizes": "http://ontology.naas.ai/abi/realizes",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "created_at",
        "created_by",
        "creates",
        "has_participant",
        "occupies_temporal_region",
        "occurs_in",
        "realizes",
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
    created_at: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(
                description="Relates a platform process to the temporal instant at which it occurred."
            ),
        ]
    ] = None
    created_by: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a platform process to the agent (user or person) who initiated it."
            ),
        ]
    ] = None
    creates: Optional[
        Annotated[
            List[Union[URIRef, Workspace, str]],
            Field(
                description="Relates a platform process performed in the application to a generically dependent continuant artifact it creates."
            ),
        ]
    ] = None
    has_participant: Optional[
        Annotated[
            List[Union[MaterialEntity, Quality, URIRef, str]],
            Field(description="p has participant c =Def c participates in p"),
        ]
    ] = None
    occupies_temporal_region: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="p occupies temporal region t =Def p is a process or process boundary & the spatiotemporal region occupied by p temporally projects onto t"
            ),
        ]
    ] = None
    occurs_in: Optional[
        Annotated[
            List[Union[Site, URIRef, str]],
            Field(
                description="b occurs in c =Def b is a process or a process boundary & c is a material entity or site & there exists a spatiotemporal region r & b occupies spatiotemporal region r & for all time t, if b exists at t then c exists at t & there exist spatial regions s and s' where b spatially projects onto s at t & c occupies spatial region s' at t & s is a continuant part of s' at t"
            ),
        ]
    ] = None
    realizes: Optional[
        Annotated[
            List[Union[Disposition, Role, URIRef, str]],
            Field(
                description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
            ),
        ]
    ] = None


class AddUserToWorkspace(Process, RDFEntity):
    """
    Add User to Workspace
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/AddUserToWorkspace"
    _name: ClassVar[str] = "Add User to Workspace"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "created_at": "http://ontology.naas.ai/nexus/createdAt",
        "created_by": "http://ontology.naas.ai/nexus/createdBy",
        "creator": "http://purl.org/dc/terms/creator",
        "has_participant": "http://ontology.naas.ai/abi/hasParticipant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupies_temporal_region": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occurs_in": "http://ontology.naas.ai/abi/occursIn",
        "realizes": "http://ontology.naas.ai/abi/realizes",
        "updates": "http://ontology.naas.ai/nexus/updates",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "created_at",
        "created_by",
        "has_participant",
        "occupies_temporal_region",
        "occurs_in",
        "realizes",
        "updates",
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
    created_at: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(
                description="Relates a platform process to the temporal instant at which it occurred."
            ),
        ]
    ] = None
    created_by: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates a platform process to the agent (user or person) who initiated it."
            ),
        ]
    ] = None
    has_participant: Optional[
        Annotated[
            List[Union[MaterialEntity, Quality, URIRef, str]],
            Field(description="p has participant c =Def c participates in p"),
        ]
    ] = None
    occupies_temporal_region: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="p occupies temporal region t =Def p is a process or process boundary & the spatiotemporal region occupied by p temporally projects onto t"
            ),
        ]
    ] = None
    occurs_in: Optional[
        Annotated[
            List[Union[Site, URIRef, str]],
            Field(
                description="b occurs in c =Def b is a process or a process boundary & c is a material entity or site & there exists a spatiotemporal region r & b occupies spatiotemporal region r & for all time t, if b exists at t then c exists at t & there exist spatial regions s and s' where b spatially projects onto s at t & c occupies spatial region s' at t & s is a continuant part of s' at t"
            ),
        ]
    ] = None
    realizes: Optional[
        Annotated[
            List[Union[Disposition, Role, URIRef, str]],
            Field(
                description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
            ),
        ]
    ] = None
    updates: Optional[
        Annotated[
            List[Union[URIRef, User, Workspace, str]],
            Field(
                description="Relates a platform process performed in the application to a generically dependent continuant artifact it modifies."
            ),
        ]
    ] = None


class Login(Process, RDFEntity):
    """
    Login
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Login"
    _name: ClassVar[str] = "Login"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "created_by": "http://ontology.naas.ai/nexus/createdBy",
        "creates": "http://ontology.naas.ai/nexus/creates",
        "creator": "http://purl.org/dc/terms/creator",
        "event_id": "http://ontology.naas.ai/nexus/event_id",
        "has_participant": "http://ontology.naas.ai/abi/hasParticipant",
        "initiates_session": "http://ontology.naas.ai/nexus/initiatesSession",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupiesTemporalRegion": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occupies_temporal_region": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occurs_in": "http://ontology.naas.ai/abi/occursIn",
        "realizes": "http://ontology.naas.ai/nexus/realizes",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "created_by",
        "creates",
        "has_participant",
        "initiates_session",
        "occupiesTemporalRegion",
        "occupies_temporal_region",
        "occurs_in",
        "realizes",
    }

    # Data properties
    event_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of the platform analytics event corresponding to a process instance in the Nexus platform."
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
    created_by: Optional[
        Annotated[
            List[Union[URIRef, User, str]],
            Field(
                description="Relates a platform process to the agent (user or person) who initiated it."
            ),
        ]
    ] = None
    creates: Optional[
        Annotated[
            List[Union[Session, URIRef, str]],
            Field(
                description="Relates a platform process performed in the application to a generically dependent continuant artifact it creates."
            ),
        ]
    ] = None
    has_participant: Optional[
        Annotated[
            List[Union[MaterialEntity, Quality, URIRef, str]],
            Field(description="p has participant c =Def c participates in p"),
        ]
    ] = None
    initiates_session: Optional[
        Annotated[
            List[Union[URIRef, VisitSession, str]],
            Field(
                description="Relates a login process to the visit session that it initiates."
            ),
        ]
    ] = None
    occupiesTemporalRegion: Optional[
        Annotated[List[Union[LoginInterval, URIRef, str]], Field()]
    ] = None
    occupies_temporal_region: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="p occupies temporal region t =Def p is a process or process boundary & the spatiotemporal region occupied by p temporally projects onto t"
            ),
        ]
    ] = None
    occurs_in: Optional[
        Annotated[
            List[Union[Site, URIRef, str]],
            Field(
                description="b occurs in c =Def b is a process or a process boundary & c is a material entity or site & there exists a spatiotemporal region r & b occupies spatiotemporal region r & for all time t, if b exists at t then c exists at t & there exist spatial regions s and s' where b spatially projects onto s at t & c occupies spatial region s' at t & s is a continuant part of s' at t"
            ),
        ]
    ] = None
    realizes: Optional[
        Annotated[
            List[Union[AuthenticationStatus, URIRef, str]],
            Field(
                description="Relates a login process to the authentication status that results from it."
            ),
        ]
    ] = None


class LoginInterval(TemporalRegion, RDFEntity):
    """
    Login Interval
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/LoginInterval"
    _name: ClassVar[str] = "Login Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_first_instant": "http://ontology.naas.ai/abi/hasFirstInstant",
        "has_last_instant": "http://ontology.naas.ai/abi/hasLastInstant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_first_instant", "has_last_instant"}

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
    has_first_instant: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(description="t has first instant t' =Def t' first instant of t"),
        ]
    ] = None
    has_last_instant: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(description="t has last instant t' =Def t' last instant of t"),
        ]
    ] = None


class LogoutInterval(TemporalRegion, RDFEntity):
    """
    Logout Interval
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/LogoutInterval"
    _name: ClassVar[str] = "Logout Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_first_instant": "http://ontology.naas.ai/abi/hasFirstInstant",
        "has_last_instant": "http://ontology.naas.ai/abi/hasLastInstant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_first_instant", "has_last_instant"}

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
    has_first_instant: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(description="t has first instant t' =Def t' first instant of t"),
        ]
    ] = None
    has_last_instant: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(description="t has last instant t' =Def t' last instant of t"),
        ]
    ] = None


class VisitSessionInterval(TemporalRegion, RDFEntity):
    """
    Visit Session Interval
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/VisitSessionInterval"
    _name: ClassVar[str] = "Visit Session Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "ended_at": "http://ontology.naas.ai/nexus/endedAt",
        "has_first_instant": "http://ontology.naas.ai/abi/hasFirstInstant",
        "has_last_instant": "http://ontology.naas.ai/abi/hasLastInstant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "start_at": "http://ontology.naas.ai/nexus/startedAt",
    }
    _object_properties: ClassVar[set[str]] = {
        "ended_at",
        "has_first_instant",
        "has_last_instant",
        "start_at",
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
    ended_at: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(
                description="Relates a visit-session interval to the temporal instant at which the session ends."
            ),
        ]
    ] = None
    has_first_instant: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(description="t has first instant t' =Def t' first instant of t"),
        ]
    ] = None
    has_last_instant: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(description="t has last instant t' =Def t' last instant of t"),
        ]
    ] = None
    start_at: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(
                description="Relates a visit-session interval to the temporal instant at which the session starts."
            ),
        ]
    ] = None


class VisitSession(Process, RDFEntity):
    """
    Visit Session
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/VisitSession"
    _name: ClassVar[str] = "Visit Session"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creates": "http://ontology.naas.ai/nexus/creates",
        "creator": "http://purl.org/dc/terms/creator",
        "event_id": "http://ontology.naas.ai/nexus/event_id",
        "has_participant": "http://ontology.naas.ai/abi/hasParticipant",
        "has_session_interval": "http://ontology.naas.ai/nexus/hasSessionInterval",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupies_temporal_region": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occurs_in": "http://ontology.naas.ai/nexus/occursIn",
        "realizes": "http://ontology.naas.ai/abi/realizes",
        "session_id": "http://ontology.naas.ai/nexus/session_id",
        "started_by": "http://ontology.naas.ai/nexus/startedBy",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "creates",
        "has_participant",
        "has_session_interval",
        "occupies_temporal_region",
        "occurs_in",
        "realizes",
        "started_by",
    }

    # Data properties
    event_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of the platform analytics event corresponding to a process instance in the Nexus platform."
            ),
        ]
    ] = None
    session_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of a platform session artifact or visit-session process in the Nexus platform."
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
    creates: Optional[
        Annotated[
            List[Union[Session, URIRef, str]],
            Field(
                description="Relates a platform process performed in the application to a generically dependent continuant artifact it creates."
            ),
        ]
    ] = None
    has_participant: Optional[
        Annotated[
            List[Union[MaterialEntity, Quality, URIRef, str]],
            Field(description="p has participant c =Def c participates in p"),
        ]
    ] = None
    has_session_interval: Optional[
        Annotated[
            List[Union[URIRef, VisitSessionInterval, str]],
            Field(
                description="Relates a visit-session process to the temporal interval that bounds its start and end."
            ),
        ]
    ] = None
    occupies_temporal_region: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="p occupies temporal region t =Def p is a process or process boundary & the spatiotemporal region occupied by p temporally projects onto t"
            ),
        ]
    ] = None
    occurs_in: Optional[
        Annotated[
            List[Union[URIRef, UserSite, str]],
            Field(
                description="Relates a process (such as a page view or visit session) to the user-side site context (country, device, browser) in which it occurs."
            ),
        ]
    ] = None
    realizes: Optional[
        Annotated[
            List[Union[Disposition, Role, URIRef, str]],
            Field(
                description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
            ),
        ]
    ] = None
    started_by: Optional[
        Annotated[
            List[Union[URIRef, User, str]],
            Field(
                description="Relates a visit-session process to the user account that started it."
            ),
        ]
    ] = None


class PageView(Process, RDFEntity):
    """
    Page View
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/PageView"
    _name: ClassVar[str] = "Page View"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "event_id": "http://ontology.naas.ai/nexus/event_id",
        "has_participant": "http://ontology.naas.ai/abi/hasParticipant",
        "has_visited_page": "http://ontology.naas.ai/nexus/hasVisitedPage",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupies_temporal_region": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occurs_during_session": "http://ontology.naas.ai/nexus/occursDuringSession",
        "occurs_in": "http://ontology.naas.ai/nexus/occursIn",
        "occurs_in_workspace": "http://ontology.naas.ai/nexus/occursInWorkspace",
        "realizes": "http://ontology.naas.ai/abi/realizes",
        "referrer": "http://ontology.naas.ai/nexus/referrer",
        "viewed_at": "http://ontology.naas.ai/nexus/viewedAt",
        "viewed_by": "http://ontology.naas.ai/nexus/viewedBy",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_participant",
        "has_visited_page",
        "occupies_temporal_region",
        "occurs_during_session",
        "occurs_in",
        "occurs_in_workspace",
        "realizes",
        "viewed_at",
        "viewed_by",
    }

    # Data properties
    event_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of the platform analytics event corresponding to a process instance in the Nexus platform."
            ),
        ]
    ] = None
    referrer: Optional[
        Annotated[
            str,
            Field(
                description="The HTTP referrer (originating page or host) recorded at the time of a page-view process."
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
    has_participant: Optional[
        Annotated[
            List[Union[MaterialEntity, Quality, URIRef, str]],
            Field(description="p has participant c =Def c participates in p"),
        ]
    ] = None
    has_visited_page: Optional[
        Annotated[
            List[Union[Page, URIRef, str]],
            Field(
                description="Relates a page-view process to the page artifact (generically dependent continuant) that the user viewed during that process."
            ),
        ]
    ] = None
    occupies_temporal_region: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="p occupies temporal region t =Def p is a process or process boundary & the spatiotemporal region occupied by p temporally projects onto t"
            ),
        ]
    ] = None
    occurs_during_session: Optional[
        Annotated[
            List[Union[URIRef, VisitSession, str]],
            Field(
                description="Relates a page-view process to the visit session of which it is a temporal part."
            ),
        ]
    ] = None
    occurs_in: Optional[
        Annotated[
            List[Union[URIRef, UserSite, str]],
            Field(
                description="Relates a process (such as a page view or visit session) to the user-side site context (country, device, browser) in which it occurs."
            ),
        ]
    ] = None
    occurs_in_workspace: Optional[
        Annotated[
            List[Union[URIRef, Workspace, str]],
            Field(
                description="Relates a platform process (such as a page view or visit session) to the workspace generic context in which it occurs."
            ),
        ]
    ] = None
    realizes: Optional[
        Annotated[
            List[Union[Disposition, Role, URIRef, str]],
            Field(
                description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
            ),
        ]
    ] = None
    viewed_at: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(
                description="Relates a page-view process to the temporal instant at which the view occurred."
            ),
        ]
    ] = None
    viewed_by: Optional[
        Annotated[
            List[Union[URIRef, User, str]],
            Field(
                description="Relates a page-view process to the user account that participates in it."
            ),
        ]
    ] = None


class Logout(Process, RDFEntity):
    """
    Logout
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Logout"
    _name: ClassVar[str] = "Logout"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "created_by": "http://ontology.naas.ai/nexus/createdBy",
        "creator": "http://purl.org/dc/terms/creator",
        "event_id": "http://ontology.naas.ai/nexus/event_id",
        "has_participant": "http://ontology.naas.ai/abi/hasParticipant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupiesTemporalRegion": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occupies_temporal_region": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occurs_in": "http://ontology.naas.ai/abi/occursIn",
        "realizes": "http://ontology.naas.ai/abi/realizes",
        "terminates": "http://ontology.naas.ai/nexus/terminates",
        "terminates_session": "http://ontology.naas.ai/nexus/terminatesSession",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "created_by",
        "has_participant",
        "occupiesTemporalRegion",
        "occupies_temporal_region",
        "occurs_in",
        "realizes",
        "terminates",
        "terminates_session",
    }

    # Data properties
    event_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of the platform analytics event corresponding to a process instance in the Nexus platform."
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
    created_by: Optional[
        Annotated[
            List[Union[URIRef, User, str]],
            Field(
                description="Relates a platform process to the agent (user or person) who initiated it."
            ),
        ]
    ] = None
    has_participant: Optional[
        Annotated[
            List[Union[MaterialEntity, Quality, URIRef, str]],
            Field(description="p has participant c =Def c participates in p"),
        ]
    ] = None
    occupiesTemporalRegion: Optional[
        Annotated[List[Union[LogoutInterval, URIRef, str]], Field()]
    ] = None
    occupies_temporal_region: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="p occupies temporal region t =Def p is a process or process boundary & the spatiotemporal region occupied by p temporally projects onto t"
            ),
        ]
    ] = None
    occurs_in: Optional[
        Annotated[
            List[Union[Site, URIRef, str]],
            Field(
                description="b occurs in c =Def b is a process or a process boundary & c is a material entity or site & there exists a spatiotemporal region r & b occupies spatiotemporal region r & for all time t, if b exists at t then c exists at t & there exist spatial regions s and s' where b spatially projects onto s at t & c occupies spatial region s' at t & s is a continuant part of s' at t"
            ),
        ]
    ] = None
    realizes: Optional[
        Annotated[
            List[Union[Disposition, Role, URIRef, str]],
            Field(
                description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
            ),
        ]
    ] = None
    terminates: Optional[
        Annotated[
            List[Union[Session, URIRef, str]],
            Field(
                description="Relates a logout process to the session artifact it terminates."
            ),
        ]
    ] = None
    terminates_session: Optional[
        Annotated[
            List[Union[URIRef, VisitSession, str]],
            Field(
                description="Relates a logout process to the visit session it terminates."
            ),
        ]
    ] = None


# Rebuild models to resolve forward references
Server.model_rebuild()
NexusOrganization.model_rebuild()
DeploymentSite.model_rebuild()
UserSite.model_rebuild()
User.model_rebuild()
Workspace.model_rebuild()
Search.model_rebuild()
Conversation.model_rebuild()
Message.model_rebuild()
AgentTool.model_rebuild()
AgentIntent.model_rebuild()
Ontology.model_rebuild()
OntologyModule.model_rebuild()
OntologyClass.model_rebuild()
OntologyObjectProperty.model_rebuild()
KnowledgeGraph.model_rebuild()
GraphView.model_rebuild()
GraphFilter.model_rebuild()
Files.model_rebuild()
FileSystem.model_rebuild()
MarketplaceApps.model_rebuild()
AIModel.model_rebuild()
Page.model_rebuild()
Session.model_rebuild()
AuthenticationStatus.model_rebuild()
Tenant.model_rebuild()
WorkspaceRole.model_rebuild()
SearchRole.model_rebuild()
ConversationRole.model_rebuild()
MessageRole.model_rebuild()
AgentRole.model_rebuild()
OntologyRole.model_rebuild()
OntologyModuleRole.model_rebuild()
OntologyClassRole.model_rebuild()
OntologyObjectPropertyRole.model_rebuild()
KnowledgeGraphRole.model_rebuild()
GraphViewRole.model_rebuild()
GraphFilterRole.model_rebuild()
FileRole.model_rebuild()
FileSystemRole.model_rebuild()
MarketplaceAppRole.model_rebuild()
Capabilities.model_rebuild()
FrontEndEvent.model_rebuild()
CreateUser.model_rebuild()
CreateWorkspace.model_rebuild()
AddUserToWorkspace.model_rebuild()
Login.model_rebuild()
LoginInterval.model_rebuild()
LogoutInterval.model_rebuild()
VisitSessionInterval.model_rebuild()
VisitSession.model_rebuild()
PageView.model_rebuild()
Logout.model_rebuild()
