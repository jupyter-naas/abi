# onto2py-source-sha256: 3aa2fa63360ad12832746f51c280883e4599ebf8825884d1e4df02d823e13cef
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


class Tenant(RDFEntity):
    """
    Tenant
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Tenant"
    _name: ClassVar[str] = "Tenant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_tenant_of": "http://ontology.naas.ai/nexus/isTenantOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_tenant_of"}

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
    is_tenant_of: Optional[
        Annotated[
            List[Union[NexusOrganization, URIRef, str]],
            Field(
                description="Relates a tenant role to the organization in which it inheres."
            ),
        ]
    ] = None


class Server(RDFEntity):
    """
    Server
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Server"
    _name: ClassVar[str] = "Server"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "located_in_deployment_site": "http://ontology.naas.ai/nexus/locatedInDeploymentSite",
    }
    _object_properties: ClassVar[set[str]] = {"located_in_deployment_site"}

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
    located_in_deployment_site: Optional[
        Annotated[
            List[Union[DeploymentSite, URIRef, str]],
            Field(
                description="Relates a server to the deployment site in which it is located."
            ),
        ]
    ] = None


class DeploymentSite(RDFEntity):
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
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class User(RDFEntity):
    """
    User
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/User"
    _name: ClassVar[str] = "User"
    _property_uris: ClassVar[dict] = {
        "bears_visitor_role": "http://ontology.naas.ai/nexus/bearsVisitorRole",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "email": "http://ontology.naas.ai/nexus/email",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "user_id": "http://ontology.naas.ai/nexus/user_id",
    }
    _object_properties: ClassVar[set[str]] = {"bears_visitor_role"}

    # Data properties
    user_id: Optional[
        Annotated[str, Field(description="The platform-internal identifier of a user.")]
    ] = None
    email: Optional[
        Annotated[str, Field(description="The email address of a user.")]
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
    bears_visitor_role: Optional[
        Annotated[
            List[Union[URIRef, VisitorRole, str]],
            Field(
                description="Relates a user to the visitor role it bears when visiting the Nexus platform."
            ),
        ]
    ] = None


class NexusOrganization(RDFEntity):
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
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

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
                description="Relates an organization to a user that is a member of it in the platform."
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


class Workspace(RDFEntity):
    """
    Workspace
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Workspace"
    _name: ClassVar[str] = "Workspace"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_conversation": "http://ontology.naas.ai/nexus/hasConversation",
        "has_marketplace_apps": "http://ontology.naas.ai/nexus/hasMarketplaceApps",
        "has_page": "http://ontology.naas.ai/nexus/hasPage",
        "has_session": "http://ontology.naas.ai/nexus/hasSession",
        "has_workspace_role": "http://ontology.naas.ai/nexus/hasWorkspaceRole",
        "hosted_on": "http://ontology.naas.ai/nexus/hostedOn",
        "is_workspace_of": "http://ontology.naas.ai/nexus/isWorkspaceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "logo_url": "http://ontology.naas.ai/nexus/logo_url",
        "workspace_id": "http://ontology.naas.ai/nexus/workspace_id",
        "workspace_name": "http://ontology.naas.ai/nexus/workspace_name",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_conversation",
        "has_marketplace_apps",
        "has_page",
        "has_session",
        "has_workspace_role",
        "hosted_on",
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
            Field(description="The platform-internal identifier of a workspace."),
        ]
    ] = None
    workspace_name: Optional[
        Annotated[str, Field(description="The display name of a workspace.")]
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
    has_page: Optional[
        Annotated[
            List[Union[Page, URIRef, str]],
            Field(description="Relates a workspace to a navigable page it carries."),
        ]
    ] = None
    has_session: Optional[
        Annotated[
            List[Union[Session, URIRef, str]],
            Field(
                description="Relates a workspace to a session that generically depends on it within the Nexus platform."
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
    is_workspace_of: Optional[
        Annotated[
            List[Union[NexusOrganization, URIRef, str]],
            Field(
                description="Relates a workspace to the organization on which it generically depends."
            ),
        ]
    ] = None


class Search(RDFEntity):
    """
    Search
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Search"
    _name: ClassVar[str] = "Search"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_search_role": "http://ontology.naas.ai/nexus/hasSearchRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_search_role"}

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
    has_search_role: Optional[
        Annotated[
            List[Union[SearchRole, URIRef, str]],
            Field(
                description="Relates a search artifact to a search role that concretizes it in platform use."
            ),
        ]
    ] = None


class Conversation(RDFEntity):
    """
    Conversation
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Conversation"
    _name: ClassVar[str] = "Conversation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_conversation_role": "http://ontology.naas.ai/nexus/hasConversationRole",
        "has_message": "http://ontology.naas.ai/nexus/hasMessage",
        "is_conversation_of": "http://ontology.naas.ai/nexus/isConversationOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_conversation_role",
        "has_message",
        "is_conversation_of",
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
    is_conversation_of: Optional[
        Annotated[
            List[Union[URIRef, Workspace, str]],
            Field(
                description="Relates a conversation to the workspace on which it depends."
            ),
        ]
    ] = None


class Message(RDFEntity):
    """
    Message
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Message"
    _name: ClassVar[str] = "Message"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_message_role": "http://ontology.naas.ai/nexus/hasMessageRole",
        "is_message_of": "http://ontology.naas.ai/nexus/isMessageOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_message_role", "is_message_of"}

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
    has_message_role: Optional[
        Annotated[
            List[Union[MessageRole, URIRef, str]],
            Field(
                description="Relates a message to a message role that concretizes it in platform use."
            ),
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


class Agent(RDFEntity):
    """
    Agent
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Agent"
    _name: ClassVar[str] = "Agent"
    _property_uris: ClassVar[dict] = {
        "class_name": "http://ontology.naas.ai/nexus/class_name",
        "class_path": "http://ontology.naas.ai/nexus/class_path",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/nexus/description",
        "has_agent_role": "http://ontology.naas.ai/nexus/hasAgentRole",
        "has_intent": "http://ontology.naas.ai/nexus/hasAgentIntent",
        "has_subagent": "http://ontology.naas.ai/nexus/hasSubAgent",
        "has_tool": "http://ontology.naas.ai/nexus/hasAgentTool",
        "is_subagent_of": "http://ontology.naas.ai/nexus/isSubAgentOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "logo_url": "http://ontology.naas.ai/nexus/logo_url",
        "module_path": "http://ontology.naas.ai/nexus/module_path",
        "system_prompt": "http://ontology.naas.ai/nexus/system_prompt",
        "uses_model": "http://ontology.naas.ai/nexus/usesModel",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_agent_role",
        "has_intent",
        "has_subagent",
        "has_tool",
        "is_subagent_of",
        "uses_model",
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
    logo_url: Optional[
        Annotated[
            str,
            Field(
                description="A URL to a logo image used in Nexus platform to identify a generically dependent continuant instance."
            ),
        ]
    ] = None
    class_name: Optional[Annotated[str, Field(description="Agent class name.")]] = None
    module_path: Optional[
        Annotated[str, Field(description="Agent module path in naas-abi.")]
    ] = None
    class_path: Optional[
        Annotated[str, Field(description="Agent module path and class name.")]
    ] = None
    system_prompt: Optional[
        Annotated[
            str,
            Field(
                description="A system prompt used in Nexus platform to configure a software agent."
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
    has_agent_role: Optional[
        Annotated[
            List[Union[AgentRole, URIRef, str]],
            Field(
                description="Relates an agent to an agent role that concretizes it in platform use."
            ),
        ]
    ] = None
    has_intent: Optional[
        Annotated[
            List[Union[AgentIntent, URIRef, str]],
            Field(description="Relates an agent to an intent available to it."),
        ]
    ] = None
    has_subagent: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(
                description="Relates a supervisor agent to a sub-agent it orchestrates within the Nexus platform."
            ),
        ]
    ] = None
    has_tool: Optional[
        Annotated[
            List[Union[AgentTool, URIRef, str]],
            Field(description="Relates an agent to a tool available to it."),
        ]
    ] = None
    is_subagent_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(
                description="Relates a sub-agent to the supervisor agent that orchestrates it within the Nexus platform."
            ),
        ]
    ] = None
    uses_model: Optional[
        Annotated[
            List[Union[AIModel, URIRef, str]],
            Field(description="Relates an agent to the AI model it uses."),
        ]
    ] = None


class AgentTool(RDFEntity):
    """
    Agent Tool
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/AgentTool"
    _name: ClassVar[str] = "Agent Tool"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/nexus/description",
        "is_tool_of": "http://ontology.naas.ai/nexus/isToolOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_tool_of"}

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
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_tool_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(description="Relates a tool to the agent on which it depends."),
        ]
    ] = None


class AgentIntent(RDFEntity):
    """
    Agent Intent
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/AgentIntent"
    _name: ClassVar[str] = "Agent Intent"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/nexus/description",
        "intent_scope": "http://ontology.naas.ai/nexus/intent_scope",
        "intent_target": "http://ontology.naas.ai/nexus/intent_target",
        "intent_type": "http://ontology.naas.ai/nexus/intent_type",
        "intent_value": "http://ontology.naas.ai/nexus/intent_value",
        "is_intent_of": "http://ontology.naas.ai/nexus/isIntentOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_intent_of"}

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
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_intent_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(description="Relates an intent to the agent on which it depends."),
        ]
    ] = None


class Ontology(RDFEntity):
    """
    Ontology
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Ontology"
    _name: ClassVar[str] = "Ontology"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_ontology_class": "http://ontology.naas.ai/nexus/hasOntologyClass",
        "has_ontology_module": "http://ontology.naas.ai/nexus/hasOntologyModule",
        "has_ontology_object_property": "http://ontology.naas.ai/nexus/hasOntologyObjectProperty",
        "has_ontology_role": "http://ontology.naas.ai/nexus/hasOntologyRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_ontology_class",
        "has_ontology_module",
        "has_ontology_object_property",
        "has_ontology_role",
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


class OntologyModule(RDFEntity):
    """
    Ontology Module
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyModule"
    _name: ClassVar[str] = "Ontology Module"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_ontology_module_role": "http://ontology.naas.ai/nexus/hasOntologyModuleRole",
        "is_ontology_module_of": "http://ontology.naas.ai/nexus/isOntologyModuleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_ontology_module_role",
        "is_ontology_module_of",
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
    has_ontology_module_role: Optional[
        Annotated[
            List[Union[OntologyModuleRole, URIRef, str]],
            Field(
                description="Relates an ontology module to an ontology module role that concretizes it in platform use."
            ),
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


class OntologyClass(RDFEntity):
    """
    Ontology Class
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyClass"
    _name: ClassVar[str] = "Ontology Class"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_ontology_class_role": "http://ontology.naas.ai/nexus/hasOntologyClassRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_ontology_class_role"}

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
    has_ontology_class_role: Optional[
        Annotated[
            List[Union[OntologyClassRole, URIRef, str]],
            Field(
                description="Relates an ontology class to an ontology class role that concretizes it in platform use."
            ),
        ]
    ] = None


class OntologyObjectProperty(RDFEntity):
    """
    Ontology Object Property
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyObjectProperty"
    _name: ClassVar[str] = "Ontology Object Property"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_ontology_object_property_role": "http://ontology.naas.ai/nexus/hasOntologyObjectPropertyRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_ontology_object_property_role"}

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
    has_ontology_object_property_role: Optional[
        Annotated[
            List[Union[OntologyObjectPropertyRole, URIRef, str]],
            Field(
                description="Relates an ontology object property to an ontology object property role that concretizes it in platform use."
            ),
        ]
    ] = None


class KnowledgeGraph(RDFEntity):
    """
    Knowledge Graph
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/KnowledgeGraph"
    _name: ClassVar[str] = "Knowledge Graph"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/nexus/description",
        "has_graph_view": "http://ontology.naas.ai/nexus/hasGraphView",
        "has_knowledge_graph_role": "http://ontology.naas.ai/nexus/hasKnowledgeGraphRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_graph_view",
        "has_knowledge_graph_role",
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
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
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


class GraphView(RDFEntity):
    """
    Graph View
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/GraphView"
    _name: ClassVar[str] = "Graph View"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/nexus/description",
        "has_graph_filter": "http://ontology.naas.ai/nexus/hasGraphFilter",
        "has_graph_view_role": "http://ontology.naas.ai/nexus/hasGraphViewRole",
        "includes_knowledge_graph": "http://ontology.naas.ai/nexus/includesKnowledgeGraph",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_graph_filter",
        "has_graph_view_role",
        "includes_knowledge_graph",
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
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
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


class GraphFilter(RDFEntity):
    """
    Graph Filter
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/GraphFilter"
    _name: ClassVar[str] = "Graph Filter"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_graph_filter_role": "http://ontology.naas.ai/nexus/hasGraphFilterRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "object_uri": "http://ontology.naas.ai/nexus/object_uri",
        "predicate_uri": "http://ontology.naas.ai/nexus/predicate_uri",
        "subject_uri": "http://ontology.naas.ai/nexus/subject_uri",
    }
    _object_properties: ClassVar[set[str]] = {"has_graph_filter_role"}

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
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_graph_filter_role: Optional[
        Annotated[
            List[Union[GraphFilterRole, URIRef, str]],
            Field(
                description="Relates a graph filter to a graph filter role that concretizes it in platform use."
            ),
        ]
    ] = None


class Files(RDFEntity):
    """
    Files
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Files"
    _name: ClassVar[str] = "Files"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_file_role": "http://ontology.naas.ai/nexus/hasFileRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_file_role"}

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
    has_file_role: Optional[
        Annotated[
            List[Union[FileRole, URIRef, str]],
            Field(
                description="Relates a file artifact to a file role that concretizes it in platform use."
            ),
        ]
    ] = None


class FileSystem(RDFEntity):
    """
    File System
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/FileSystem"
    _name: ClassVar[str] = "File System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_file_system_role": "http://ontology.naas.ai/nexus/hasFileSystemRole",
        "has_files": "http://ontology.naas.ai/nexus/hasFiles",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_file_system_role", "has_files"}

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


class MarketplaceApps(RDFEntity):
    """
    Marketplace Apps
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/MarketplaceApps"
    _name: ClassVar[str] = "Marketplace Apps"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_marketplace_app_role": "http://ontology.naas.ai/nexus/hasMarketplaceAppRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_marketplace_app_role"}

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
    has_marketplace_app_role: Optional[
        Annotated[
            List[Union[MarketplaceAppRole, URIRef, str]],
            Field(
                description="Relates a marketplace application to a marketplace application role that concretizes it in platform use."
            ),
        ]
    ] = None


class WorkspaceRole(RDFEntity):
    """
    Workspace Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/WorkspaceRole"
    _name: ClassVar[str] = "Workspace Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_workspace_role_of": "http://ontology.naas.ai/nexus/isWorkspaceRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_workspace_role_of"}

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
    is_workspace_role_of: Optional[
        Annotated[
            List[Union[URIRef, Workspace, str]],
            Field(
                description="Relates a workspace role to the workspace of which it is the role-side concretization."
            ),
        ]
    ] = None


class SearchRole(RDFEntity):
    """
    Search Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/SearchRole"
    _name: ClassVar[str] = "Search Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_search_role_of": "http://ontology.naas.ai/nexus/isSearchRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_search_role_of"}

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
    is_search_role_of: Optional[
        Annotated[
            List[Union[Search, URIRef, str]],
            Field(
                description="Relates a search role to the search artifact of which it is the role-side concretization."
            ),
        ]
    ] = None


class ConversationRole(RDFEntity):
    """
    Conversation Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/ConversationRole"
    _name: ClassVar[str] = "Conversation Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_conversation_role_of": "http://ontology.naas.ai/nexus/isConversationRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_conversation_role_of"}

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
    is_conversation_role_of: Optional[
        Annotated[
            List[Union[Conversation, URIRef, str]],
            Field(
                description="Relates a conversation role to the conversation of which it is the role-side concretization."
            ),
        ]
    ] = None


class MessageRole(RDFEntity):
    """
    Message Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/MessageRole"
    _name: ClassVar[str] = "Message Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_message_role_of": "http://ontology.naas.ai/nexus/isMessageRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_message_role_of"}

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
    is_message_role_of: Optional[
        Annotated[
            List[Union[Message, URIRef, str]],
            Field(
                description="Relates a message role to the message of which it is the role-side concretization."
            ),
        ]
    ] = None


class AgentRole(RDFEntity):
    """
    Agent Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/AgentRole"
    _name: ClassVar[str] = "Agent Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/nexus/description",
        "is_agent_role_of": "http://ontology.naas.ai/nexus/isAgentRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_agent_role_of"}

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
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_agent_role_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(
                description="Relates an agent role to the agent of which it is the role-side concretization."
            ),
        ]
    ] = None


class OntologyRole(RDFEntity):
    """
    Ontology Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyRole"
    _name: ClassVar[str] = "Ontology Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_ontology_role_of": "http://ontology.naas.ai/nexus/isOntologyRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_ontology_role_of"}

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
    is_ontology_role_of: Optional[
        Annotated[
            List[Union[Ontology, URIRef, str]],
            Field(
                description="Relates an ontology role to the ontology of which it is the role-side concretization."
            ),
        ]
    ] = None


class OntologyModuleRole(RDFEntity):
    """
    Ontology Module Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyModuleRole"
    _name: ClassVar[str] = "Ontology Module Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_ontology_module_role_of": "http://ontology.naas.ai/nexus/isOntologyModuleRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_ontology_module_role_of"}

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
    is_ontology_module_role_of: Optional[
        Annotated[
            List[Union[OntologyModule, URIRef, str]],
            Field(
                description="Relates an ontology module role to the ontology module of which it is the role-side concretization."
            ),
        ]
    ] = None


class OntologyClassRole(RDFEntity):
    """
    Ontology Class Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyClassRole"
    _name: ClassVar[str] = "Ontology Class Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_ontology_class_role_of": "http://ontology.naas.ai/nexus/isOntologyClassRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_ontology_class_role_of"}

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
    is_ontology_class_role_of: Optional[
        Annotated[
            List[Union[OntologyClass, URIRef, str]],
            Field(
                description="Relates an ontology class role to the ontology class of which it is the role-side concretization."
            ),
        ]
    ] = None


class OntologyObjectPropertyRole(RDFEntity):
    """
    Ontology Object Property Role
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/nexus/OntologyObjectPropertyRole"
    )
    _name: ClassVar[str] = "Ontology Object Property Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_ontology_object_property_role_of": "http://ontology.naas.ai/nexus/isOntologyObjectPropertyRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_ontology_object_property_role_of"}

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
    is_ontology_object_property_role_of: Optional[
        Annotated[
            List[Union[OntologyObjectProperty, URIRef, str]],
            Field(
                description="Relates an ontology object property role to the ontology object property of which it is the role-side concretization."
            ),
        ]
    ] = None


class KnowledgeGraphRole(RDFEntity):
    """
    Knowledge Graph Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/KnowledgeGraphRole"
    _name: ClassVar[str] = "Knowledge Graph Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_knowledge_graph_role_of": "http://ontology.naas.ai/nexus/isKnowledgeGraphRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_knowledge_graph_role_of"}

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
    is_knowledge_graph_role_of: Optional[
        Annotated[
            List[Union[KnowledgeGraph, URIRef, str]],
            Field(
                description="Relates a knowledge graph role to the knowledge graph of which it is the role-side concretization."
            ),
        ]
    ] = None


class GraphViewRole(RDFEntity):
    """
    Graph View Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/GraphViewRole"
    _name: ClassVar[str] = "Graph View Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_graph_view_role_of": "http://ontology.naas.ai/nexus/isGraphViewRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_graph_view_role_of"}

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
    is_graph_view_role_of: Optional[
        Annotated[
            List[Union[GraphView, URIRef, str]],
            Field(
                description="Relates a graph view role to the graph view of which it is the role-side concretization."
            ),
        ]
    ] = None


class GraphFilterRole(RDFEntity):
    """
    Graph Filter Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/GraphFilterRole"
    _name: ClassVar[str] = "Graph Filter Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_graph_filter_role_of": "http://ontology.naas.ai/nexus/isGraphFilterRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_graph_filter_role_of"}

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
    is_graph_filter_role_of: Optional[
        Annotated[
            List[Union[GraphFilter, URIRef, str]],
            Field(
                description="Relates a graph filter role to the graph filter of which it is the role-side concretization."
            ),
        ]
    ] = None


class FileRole(RDFEntity):
    """
    File Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/FileRole"
    _name: ClassVar[str] = "File Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_file_role_of": "http://ontology.naas.ai/nexus/isFileRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_file_role_of"}

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
    is_file_role_of: Optional[
        Annotated[
            List[Union[Files, URIRef, str]],
            Field(
                description="Relates a file role to the file artifact of which it is the role-side concretization."
            ),
        ]
    ] = None


class FileSystemRole(RDFEntity):
    """
    File System Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/FileSystemRole"
    _name: ClassVar[str] = "File System Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_file_system_role_of": "http://ontology.naas.ai/nexus/isFileSystemRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_file_system_role_of"}

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
    is_file_system_role_of: Optional[
        Annotated[
            List[Union[FileSystem, URIRef, str]],
            Field(
                description="Relates a file system role to the file system of which it is the role-side concretization."
            ),
        ]
    ] = None


class MarketplaceAppRole(RDFEntity):
    """
    Marketplace App Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/MarketplaceAppRole"
    _name: ClassVar[str] = "Marketplace App Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_marketplace_app_role_of": "http://ontology.naas.ai/nexus/isMarketplaceAppRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_marketplace_app_role_of"}

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
    is_marketplace_app_role_of: Optional[
        Annotated[
            List[Union[MarketplaceApps, URIRef, str]],
            Field(
                description="Relates a marketplace application role to the marketplace application of which it is the role-side concretization."
            ),
        ]
    ] = None


class AIModel(RDFEntity):
    """
    AI Model
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/AIModel"
    _name: ClassVar[str] = "AI Model"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_provider": "http://ontology.naas.ai/nexus/hasProvider",
        "is_model_of": "http://ontology.naas.ai/nexus/isModelOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "model_id": "http://ontology.naas.ai/nexus/model_id",
    }
    _object_properties: ClassVar[set[str]] = {"has_provider", "is_model_of"}

    # Data properties
    model_id: Optional[
        Annotated[str, Field(description="The identifier of the AI model.")]
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
    has_provider: Optional[
        Annotated[
            List[Union[URIRef, str]],
            Field(
                description="Relates an AI model to the organization that provides it."
            ),
        ]
    ] = None
    is_model_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(description="Relates an AI model to the agent that uses it."),
        ]
    ] = None


class Capabilities(RDFEntity):
    """
    Capabilities
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Capabilities"
    _name: ClassVar[str] = "Capabilities"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_capabilities_of": "http://ontology.naas.ai/nexus/isCapabilitiesOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197", "is_capabilities_of"}

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
    bFO_0000197: Optional[Annotated[List[Union[URIRef, str]], Field()]] = None
    is_capabilities_of: Optional[
        Annotated[
            List[Union[URIRef, str]],
            Field(
                description="Relates a capability to the organization in which it inheres."
            ),
        ]
    ] = None


class Session(RDFEntity):
    """
    Session
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Session"
    _name: ClassVar[str] = "Session"
    _property_uris: ClassVar[dict] = {
        "browser": "http://ontology.naas.ai/nexus/browser",
        "country": "http://ontology.naas.ai/nexus/country",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "device": "http://ontology.naas.ai/nexus/device",
        "has_log": "http://ontology.naas.ai/nexus/hasLog",
        "has_session_role": "http://ontology.naas.ai/nexus/hasSessionRole",
        "is_session_of": "http://ontology.naas.ai/nexus/isSessionOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "session_id": "http://ontology.naas.ai/nexus/session_id",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_log",
        "has_session_role",
        "is_session_of",
    }

    # Data properties
    session_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of a session within the Nexus platform."
            ),
        ]
    ] = None
    device: Optional[
        Annotated[
            str,
            Field(description="The device category from which a session is conducted."),
        ]
    ] = None
    browser: Optional[
        Annotated[str, Field(description="The browser used during a session.")]
    ] = None
    country: Optional[
        Annotated[
            str,
            Field(description="The country code from which a session is conducted."),
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
    has_log: Optional[
        Annotated[
            List[Union[Log, URIRef, str]],
            Field(
                description="Relates a session to a log entry generically dependent on it; one session carries the ordered stream of logs emitted during the visit."
            ),
        ]
    ] = None
    has_session_role: Optional[
        Annotated[
            List[Union[SessionRole, URIRef, str]],
            Field(
                description="Relates a session to a session role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_session_of: Optional[
        Annotated[
            List[Union[URIRef, Workspace, str]],
            Field(
                description="Relates a session to the workspace on which it generically depends."
            ),
        ]
    ] = None


class Log(RDFEntity):
    """
    Log
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Log"
    _name: ClassVar[str] = "Log"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "event_id": "http://ontology.naas.ai/nexus/event_id",
        "event_name": "http://ontology.naas.ai/nexus/event_name",
        "event_payload": "http://ontology.naas.ai/nexus/event_payload",
        "has_log_role": "http://ontology.naas.ai/nexus/hasLogRole",
        "is_log_of": "http://ontology.naas.ai/nexus/isLogOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "page_path": "http://ontology.naas.ai/nexus/page_path",
        "page_title": "http://ontology.naas.ai/nexus/page_title",
        "referrer": "http://ontology.naas.ai/nexus/referrer",
        "timestamp": "http://ontology.naas.ai/nexus/timestamp",
    }
    _object_properties: ClassVar[set[str]] = {"has_log_role", "is_log_of"}

    # Data properties
    event_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique identifier of a log entry; corresponds to AnalyticsEvent.event_id."
            ),
        ]
    ] = None
    event_name: Optional[
        Annotated[
            str,
            Field(
                description="The categorical name of the event recorded by a log entry; matches the EventName union in the analytics layer."
            ),
        ]
    ] = None
    timestamp: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The timestamp at which a log entry was emitted; corresponds to AnalyticsEvent.timestamp."
            ),
        ]
    ] = None
    page_path: Optional[
        Annotated[
            str,
            Field(
                description="The path of a page; corresponds to AnalyticsEvent.page_path and Page identity, and feeds the top_pages KPI."
            ),
        ]
    ] = None
    page_title: Optional[
        Annotated[
            str,
            Field(
                description="The human-readable title of a page; corresponds to AnalyticsEvent.page_title and the label used in top_pages."
            ),
        ]
    ] = None
    event_payload: Optional[
        Annotated[
            str,
            Field(
                description="A JSON-encoded payload of structured properties attached to a log entry; corresponds to AnalyticsEvent.properties."
            ),
        ]
    ] = None
    referrer: Optional[
        Annotated[
            str,
            Field(
                description="The referring URL recorded with a log entry; corresponds to AnalyticsEvent.referrer."
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
    has_log_role: Optional[
        Annotated[
            List[Union[LogRole, URIRef, str]],
            Field(
                description="Relates a log entry to a log role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_log_of: Optional[
        Annotated[
            List[Union[Session, URIRef, str]],
            Field(
                description="Relates a log entry to the session on which it generically depends."
            ),
        ]
    ] = None


class VisitSessionInterval(RDFEntity):
    """
    Visit Session Interval
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/VisitSessionInterval"
    _name: ClassVar[str] = "Visit Session Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "duration_seconds": "http://ontology.naas.ai/nexus/duration_seconds",
        "ended_at": "http://ontology.naas.ai/nexus/ended_at",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "started_at": "http://ontology.naas.ai/nexus/started_at",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    started_at: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The opening boundary of a temporal interval; corresponds to the SessionRow.started_at field in the analytics app."
            ),
        ]
    ] = None
    ended_at: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The closing boundary of a temporal interval; corresponds to the SessionRow.ended_at field in the analytics app."
            ),
        ]
    ] = None
    duration_seconds: Optional[
        Annotated[
            int,
            Field(
                description="The size of a temporal interval in seconds; the source quantity behind the avg_session_duration_seconds analytics KPI."
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


class LoginInterval(RDFEntity):
    """
    Login Interval
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/LoginInterval"
    _name: ClassVar[str] = "Login Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "duration_seconds": "http://ontology.naas.ai/nexus/duration_seconds",
        "ended_at": "http://ontology.naas.ai/nexus/ended_at",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "started_at": "http://ontology.naas.ai/nexus/started_at",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    started_at: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The opening boundary of a temporal interval; corresponds to the SessionRow.started_at field in the analytics app."
            ),
        ]
    ] = None
    ended_at: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The closing boundary of a temporal interval; corresponds to the SessionRow.ended_at field in the analytics app."
            ),
        ]
    ] = None
    duration_seconds: Optional[
        Annotated[
            int,
            Field(
                description="The size of a temporal interval in seconds; the source quantity behind the avg_session_duration_seconds analytics KPI."
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


class SessionRole(RDFEntity):
    """
    Session Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/SessionRole"
    _name: ClassVar[str] = "Session Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_session_role_of": "http://ontology.naas.ai/nexus/isSessionRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_session_role_of"}

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
    is_session_role_of: Optional[
        Annotated[
            List[Union[Session, URIRef, str]],
            Field(
                description="Relates a session role to the session of which it is the role-side concretization."
            ),
        ]
    ] = None


class LogRole(RDFEntity):
    """
    Log Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/LogRole"
    _name: ClassVar[str] = "Log Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_log_role_of": "http://ontology.naas.ai/nexus/isLogRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_log_role_of"}

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
    is_log_role_of: Optional[
        Annotated[
            List[Union[Log, URIRef, str]],
            Field(
                description="Relates a log role to the log entry of which it is the role-side concretization."
            ),
        ]
    ] = None


class VisitorRole(RDFEntity):
    """
    Visitor Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/VisitorRole"
    _name: ClassVar[str] = "Visitor Role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000054": "http://purl.obolibrary.org/obo/BFO_0000054",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_visitor_role_of": "http://ontology.naas.ai/nexus/isVisitorRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000054", "is_visitor_role_of"}

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
    bFO_0000054: Optional[
        Annotated[List[Union[URIRef, VisitSession, str]], Field()]
    ] = None
    is_visitor_role_of: Optional[
        Annotated[
            List[Union[URIRef, User, str]],
            Field(
                description="Relates a visitor role to the user in which it inheres."
            ),
        ]
    ] = None


class UserEngagementQuality(RDFEntity):
    """
    User Engagement Quality
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/UserEngagementQuality"
    _name: ClassVar[str] = "User Engagement Quality"
    _property_uris: ClassVar[dict] = {
        "bFO_0000056": "http://purl.obolibrary.org/obo/BFO_0000056",
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000056", "bFO_0000197"}

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
    bFO_0000056: Optional[
        Annotated[List[Union[URIRef, VisitSession, str]], Field()]
    ] = None
    bFO_0000197: Optional[Annotated[List[Union[URIRef, User, str]], Field()]] = None


class AuthenticationStatus(RDFEntity):
    """
    Authentication Status
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/AuthenticationStatus"
    _name: ClassVar[str] = "Authentication Status"
    _property_uris: ClassVar[dict] = {
        "bFO_0000056": "http://purl.obolibrary.org/obo/BFO_0000056",
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000056", "bFO_0000197"}

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
    bFO_0000056: Optional[Annotated[List[Union[Login, URIRef, str]], Field()]] = None
    bFO_0000197: Optional[Annotated[List[Union[URIRef, User, str]], Field()]] = None


class VisitSession(RDFEntity):
    """
    Visit Session
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/VisitSession"
    _name: ClassVar[str] = "Visit Session"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_initiated_by_login": "http://ontology.naas.ai/nexus/isInitiatedByLogin",
        "is_terminated_by_logout": "http://ontology.naas.ai/nexus/isTerminatedByLogout",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000199",
        "is_initiated_by_login",
        "is_terminated_by_logout",
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
    bFO_0000055: Optional[Annotated[List[Union[URIRef, VisitorRole, str]], Field()]] = (
        None
    )
    bFO_0000057: Optional[
        Annotated[List[Union[URIRef, User, UserEngagementQuality, str]], Field()]
    ] = None
    bFO_0000059: Optional[
        Annotated[List[Union[Log, Session, URIRef, str]], Field()]
    ] = None
    bFO_0000066: Optional[
        Annotated[List[Union[DeploymentSite, URIRef, str]], Field()]
    ] = None
    bFO_0000199: Optional[
        Annotated[List[Union[URIRef, VisitSessionInterval, str]], Field()]
    ] = None
    is_initiated_by_login: Optional[
        Annotated[
            List[Union[Login, URIRef, str]],
            Field(
                description="Relates a visit session to the login process that opens it."
            ),
        ]
    ] = None
    is_terminated_by_logout: Optional[
        Annotated[
            List[Union[Logout, URIRef, str]],
            Field(
                description="Relates a visit session to the logout process that closes it."
            ),
        ]
    ] = None


class Page(RDFEntity):
    """
    Page
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Page"
    _name: ClassVar[str] = "Page"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_page_role": "http://ontology.naas.ai/nexus/hasPageRole",
        "is_page_of": "http://ontology.naas.ai/nexus/isPageOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "page_path": "http://ontology.naas.ai/nexus/page_path",
        "page_title": "http://ontology.naas.ai/nexus/page_title",
    }
    _object_properties: ClassVar[set[str]] = {"has_page_role", "is_page_of"}

    # Data properties
    page_path: Optional[
        Annotated[
            str,
            Field(
                description="The path of a page; corresponds to AnalyticsEvent.page_path and Page identity, and feeds the top_pages KPI."
            ),
        ]
    ] = None
    page_title: Optional[
        Annotated[
            str,
            Field(
                description="The human-readable title of a page; corresponds to AnalyticsEvent.page_title and the label used in top_pages."
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
    has_page_role: Optional[
        Annotated[
            List[Union[PageRole, URIRef, str]],
            Field(
                description="Relates a page to a page role that concretizes it in platform use."
            ),
        ]
    ] = None
    is_page_of: Optional[
        Annotated[
            List[Union[URIRef, Workspace, str]],
            Field(
                description="Relates a page to the workspace on which it generically depends."
            ),
        ]
    ] = None


class PageRole(RDFEntity):
    """
    Page Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/PageRole"
    _name: ClassVar[str] = "Page Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_page_role_of": "http://ontology.naas.ai/nexus/isPageRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_page_role_of"}

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
    is_page_role_of: Optional[
        Annotated[
            List[Union[Page, URIRef, str]],
            Field(
                description="Relates a page role to the page of which it is the role-side concretization."
            ),
        ]
    ] = None


class PageViewInterval(RDFEntity):
    """
    Page View Interval
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/PageViewInterval"
    _name: ClassVar[str] = "Page View Interval"
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


class LogoutInterval(RDFEntity):
    """
    Logout Interval
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/LogoutInterval"
    _name: ClassVar[str] = "Logout Interval"
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


class PageView(RDFEntity):
    """
    Page View
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/PageView"
    _name: ClassVar[str] = "Page View"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000199",
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
    bFO_0000055: Optional[Annotated[List[Union[URIRef, VisitorRole, str]], Field()]] = (
        None
    )
    bFO_0000057: Optional[
        Annotated[List[Union[URIRef, User, UserEngagementQuality, str]], Field()]
    ] = None
    bFO_0000059: Optional[Annotated[List[Union[Log, Page, URIRef, str]], Field()]] = (
        None
    )
    bFO_0000066: Optional[
        Annotated[List[Union[DeploymentSite, URIRef, str]], Field()]
    ] = None
    bFO_0000199: Optional[
        Annotated[List[Union[PageViewInterval, URIRef, str]], Field()]
    ] = None


class Logout(RDFEntity):
    """
    Logout
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Logout"
    _name: ClassVar[str] = "Logout"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "terminates_session": "http://ontology.naas.ai/nexus/terminatesSession",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000199",
        "terminates_session",
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
    bFO_0000055: Optional[Annotated[List[Union[URIRef, VisitorRole, str]], Field()]] = (
        None
    )
    bFO_0000057: Optional[Annotated[List[Union[URIRef, User, str]], Field()]] = None
    bFO_0000059: Optional[
        Annotated[List[Union[Log, Session, URIRef, str]], Field()]
    ] = None
    bFO_0000066: Optional[
        Annotated[List[Union[DeploymentSite, URIRef, str]], Field()]
    ] = None
    bFO_0000199: Optional[
        Annotated[List[Union[LogoutInterval, URIRef, str]], Field()]
    ] = None
    terminates_session: Optional[
        Annotated[
            List[Union[URIRef, VisitSession, str]],
            Field(
                description="Relates a logout process to the visit session it closes; both processes share the same temporal boundary at session end."
            ),
        ]
    ] = None


class Login(RDFEntity):
    """
    Login
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/LoginProcess"
    _name: ClassVar[str] = "Login"
    _property_uris: ClassVar[dict] = {
        "bFO_0000055": "http://purl.obolibrary.org/obo/BFO_0000055",
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000059": "http://purl.obolibrary.org/obo/BFO_0000059",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "initiates_session": "http://ontology.naas.ai/nexus/initiatesSession",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000055",
        "bFO_0000057",
        "bFO_0000059",
        "bFO_0000066",
        "bFO_0000199",
        "initiates_session",
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
    bFO_0000055: Optional[Annotated[List[Union[URIRef, VisitorRole, str]], Field()]] = (
        None
    )
    bFO_0000057: Optional[
        Annotated[List[Union[AuthenticationStatus, URIRef, User, str]], Field()]
    ] = None
    bFO_0000059: Optional[
        Annotated[List[Union[Log, Session, URIRef, str]], Field()]
    ] = None
    bFO_0000066: Optional[
        Annotated[List[Union[DeploymentSite, URIRef, str]], Field()]
    ] = None
    bFO_0000199: Optional[
        Annotated[List[Union[LoginInterval, URIRef, str]], Field()]
    ] = None
    initiates_session: Optional[
        Annotated[
            List[Union[URIRef, VisitSession, str]],
            Field(
                description="Relates a login process to the visit session it opens; both processes share the same temporal boundary at session start."
            ),
        ]
    ] = None


# Rebuild models to resolve forward references
Tenant.model_rebuild()
Server.model_rebuild()
DeploymentSite.model_rebuild()
User.model_rebuild()
NexusOrganization.model_rebuild()
Workspace.model_rebuild()
Search.model_rebuild()
Conversation.model_rebuild()
Message.model_rebuild()
Agent.model_rebuild()
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
AIModel.model_rebuild()
Capabilities.model_rebuild()
Session.model_rebuild()
Log.model_rebuild()
VisitSessionInterval.model_rebuild()
LoginInterval.model_rebuild()
SessionRole.model_rebuild()
LogRole.model_rebuild()
VisitorRole.model_rebuild()
UserEngagementQuality.model_rebuild()
AuthenticationStatus.model_rebuild()
VisitSession.model_rebuild()
Page.model_rebuild()
PageRole.model_rebuild()
PageViewInterval.model_rebuild()
LogoutInterval.model_rebuild()
PageView.model_rebuild()
Logout.model_rebuild()
Login.model_rebuild()
