from __future__ import annotations
from typing import Annotated, Any, ClassVar, List, Optional, Union
from pydantic import BaseModel, Field
import uuid
import datetime
import os
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD

BFO = Namespace("http://purl.obolibrary.org/obo/")
ABI = Namespace("http://ontology.naas.ai/abi/")
CCO = Namespace("https://www.commoncoreontologies.org/")


# Base class for all RDF entities
class RDFEntity(BaseModel):
    """Base class for all RDF entities with URI and namespace management"""

    _namespace: ClassVar[str] = "http://ontology.naas.ai/abi/"
    _uri: str = ""
    _object_properties: ClassVar[set[str]] = set()

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
    label: Annotated[str, Field(description="Label of the resource.")]
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
            List[Union[Organization, URIRef, str]],
            Field(
                description="Relates a tenant role to the organization in which it inheres."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


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
    label: Annotated[str, Field(description="Label of the resource.")]
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
    ] = ["http://ontology.naas.ai/abi/unknown"]


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
    label: Annotated[str, Field(description="Label of the resource.")]
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
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Organization(RDFEntity):
    """
    Organization
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Organization"
    _name: ClassVar[str] = "Organization"
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
    label: Annotated[str, Field(description="Label of the resource.")]
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
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_user: Optional[
        Annotated[
            List[Union[URIRef, User, str]],
            Field(
                description="Relates an organization to a user that is a member of it in the platform."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_workspace: Optional[
        Annotated[
            List[Union[URIRef, Workspace, str]],
            Field(
                description="Relates an organization to a workspace that depends on it within the Nexus platform."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


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
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "hosted_on": "http://ontology.naas.ai/nexus/hostedOn",
        "is_workspace_of": "http://ontology.naas.ai/nexus/isWorkspaceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_conversation",
        "has_marketplace_apps",
        "has_role",
        "hosted_on",
        "is_workspace_of",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
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
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_marketplace_apps: Optional[
        Annotated[
            List[Union[MarketplaceApps, URIRef, str]],
            Field(
                description="Relates a workspace to a marketplace application available in or associated with it."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_role: Optional[
        Annotated[
            List[Union[URIRef, WorkspaceRole, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    hosted_on: Optional[
        Annotated[
            List[Union[Server, URIRef, str]],
            Field(
                description="Relates a workspace to the physical server on which it depends for hosting."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_workspace_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="Relates a workspace to the organization on which it generically depends."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Search(RDFEntity):
    """
    Search
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Search"
    _name: ClassVar[str] = "Search"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_role"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_role: Optional[
        Annotated[
            List[Union[SearchRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Conversation(RDFEntity):
    """
    Conversation
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Conversation"
    _name: ClassVar[str] = "Conversation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_message": "http://ontology.naas.ai/nexus/hasMessage",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "is_conversation_of": "http://ontology.naas.ai/nexus/isConversationOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_message",
        "has_role",
        "is_conversation_of",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_message: Optional[
        Annotated[
            List[Union[Message, URIRef, str]],
            Field(description="Relates a conversation to a message it contains."),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_role: Optional[
        Annotated[
            List[Union[ConversationRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_conversation_of: Optional[
        Annotated[
            List[Union[URIRef, Workspace, str]],
            Field(
                description="Relates a conversation to the workspace on which it depends."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Message(RDFEntity):
    """
    Message
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Message"
    _name: ClassVar[str] = "Message"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "is_message_of": "http://ontology.naas.ai/nexus/isMessageOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_role", "is_message_of"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_role: Optional[
        Annotated[
            List[Union[MessageRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_message_of: Optional[
        Annotated[
            List[Union[Conversation, URIRef, str]],
            Field(
                description="Relates a message to the conversation on which it depends."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Agent(RDFEntity):
    """
    Agent
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Agent"
    _name: ClassVar[str] = "Agent"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_role"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_role: Optional[
        Annotated[
            List[Union[AgentRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


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
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_ontology_class",
        "has_ontology_module",
        "has_ontology_object_property",
        "has_role",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
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
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_ontology_module: Optional[
        Annotated[
            List[Union[OntologyModule, URIRef, str]],
            Field(description="Relates an ontology to one of its ontology modules."),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_ontology_object_property: Optional[
        Annotated[
            List[Union[OntologyObjectProperty, URIRef, str]],
            Field(
                description="Relates an ontology to an object property defined within it."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_role: Optional[
        Annotated[
            List[Union[OntologyRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OntologyModule(RDFEntity):
    """
    Ontology Module
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyModule"
    _name: ClassVar[str] = "Ontology Module"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "is_ontology_module_of": "http://ontology.naas.ai/nexus/isOntologyModuleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_role", "is_ontology_module_of"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_role: Optional[
        Annotated[
            List[Union[OntologyModuleRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_ontology_module_of: Optional[
        Annotated[
            List[Union[Ontology, URIRef, str]],
            Field(
                description="Relates an ontology module to the ontology on which it depends."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OntologyClass(RDFEntity):
    """
    Ontology Class
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyClass"
    _name: ClassVar[str] = "Ontology Class"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_role"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_role: Optional[
        Annotated[
            List[Union[OntologyClassRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OntologyObjectProperty(RDFEntity):
    """
    Ontology Object Property
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyObjectProperty"
    _name: ClassVar[str] = "Ontology Object Property"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_role"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_role: Optional[
        Annotated[
            List[Union[OntologyObjectPropertyRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class KnowledgeGraph(RDFEntity):
    """
    Knowledge Graph
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/KnowledgeGraph"
    _name: ClassVar[str] = "Knowledge Graph"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_graph_view": "http://ontology.naas.ai/nexus/hasGraphView",
        "has_named_graph": "http://ontology.naas.ai/nexus/hasNamedGraph",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_graph_view",
        "has_named_graph",
        "has_role",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
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
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_named_graph: Optional[
        Annotated[
            List[Union[NamedGraph, URIRef, str]],
            Field(
                description="Relates a knowledge graph to a named graph that composes it."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_role: Optional[
        Annotated[
            List[Union[KnowledgeGraphRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class NamedGraph(RDFEntity):
    """
    Named Graph
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/NamedGraph"
    _name: ClassVar[str] = "Named Graph"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "is_named_graph_of": "http://ontology.naas.ai/nexus/isNamedGraphOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_role", "is_named_graph_of"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_role: Optional[
        Annotated[
            List[Union[NamedGraphRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_named_graph_of: Optional[
        Annotated[
            List[Union[KnowledgeGraph, URIRef, str]],
            Field(
                description="Relates a named graph to the knowledge graph on which it depends."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GraphView(RDFEntity):
    """
    Graph View
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/GraphView"
    _name: ClassVar[str] = "Graph View"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_graph_filter": "http://ontology.naas.ai/nexus/hasGraphFilter",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "selects_named_graph": "http://ontology.naas.ai/nexus/selectsNamedGraph",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_graph_filter",
        "has_role",
        "selects_named_graph",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
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
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_role: Optional[
        Annotated[
            List[Union[GraphViewRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    selects_named_graph: Optional[
        Annotated[
            List[Union[NamedGraph, URIRef, str]],
            Field(description="Relates a graph view to a named graph it selects."),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GraphFilter(RDFEntity):
    """
    Graph Filter
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/GraphFilter"
    _name: ClassVar[str] = "Graph Filter"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_role"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_role: Optional[
        Annotated[
            List[Union[GraphFilterRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Files(RDFEntity):
    """
    Files
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/Files"
    _name: ClassVar[str] = "Files"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_role"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_role: Optional[
        Annotated[
            List[Union[FileRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FileSystem(RDFEntity):
    """
    File System
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/FileSystem"
    _name: ClassVar[str] = "File System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_files": "http://ontology.naas.ai/nexus/hasFiles",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_files", "has_role"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_files: Optional[
        Annotated[
            List[Union[Files, URIRef, str]],
            Field(description="Relates a file system to files accessible through it."),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_role: Optional[
        Annotated[
            List[Union[FileSystemRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MarketplaceApps(RDFEntity):
    """
    Marketplace Apps
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/MarketplaceApps"
    _name: ClassVar[str] = "Marketplace Apps"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_role": "http://ontology.naas.ai/nexus/hasRole",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_role"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_role: Optional[
        Annotated[
            List[Union[MarketplaceAppRole, URIRef, str]],
            Field(
                description="Relates a generically dependent continuant in the Nexus platform to a role that concretizes it in platform use."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class WorkspaceRole(RDFEntity):
    """
    Workspace Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/WorkspaceRole"
    _name: ClassVar[str] = "Workspace Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SearchRole(RDFEntity):
    """
    Search Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/SearchRole"
    _name: ClassVar[str] = "Search Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ConversationRole(RDFEntity):
    """
    Conversation Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/ConversationRole"
    _name: ClassVar[str] = "Conversation Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MessageRole(RDFEntity):
    """
    Message Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/MessageRole"
    _name: ClassVar[str] = "Message Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AgentRole(RDFEntity):
    """
    Agent Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/AgentRole"
    _name: ClassVar[str] = "Agent Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OntologyRole(RDFEntity):
    """
    Ontology Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyRole"
    _name: ClassVar[str] = "Ontology Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OntologyModuleRole(RDFEntity):
    """
    Ontology Module Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyModuleRole"
    _name: ClassVar[str] = "Ontology Module Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OntologyClassRole(RDFEntity):
    """
    Ontology Class Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/OntologyClassRole"
    _name: ClassVar[str] = "Ontology Class Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


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
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class KnowledgeGraphRole(RDFEntity):
    """
    Knowledge Graph Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/KnowledgeGraphRole"
    _name: ClassVar[str] = "Knowledge Graph Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class NamedGraphRole(RDFEntity):
    """
    Named Graph Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/NamedGraphRole"
    _name: ClassVar[str] = "Named Graph Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GraphViewRole(RDFEntity):
    """
    Graph View Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/GraphViewRole"
    _name: ClassVar[str] = "Graph View Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GraphFilterRole(RDFEntity):
    """
    Graph Filter Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/GraphFilterRole"
    _name: ClassVar[str] = "Graph Filter Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FileRole(RDFEntity):
    """
    File Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/FileRole"
    _name: ClassVar[str] = "File Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FileSystemRole(RDFEntity):
    """
    File System Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/FileSystemRole"
    _name: ClassVar[str] = "File System Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MarketplaceAppRole(RDFEntity):
    """
    Marketplace App Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/nexus/MarketplaceAppRole"
    _name: ClassVar[str] = "Marketplace App Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


# Rebuild models to resolve forward references
Tenant.model_rebuild()
Server.model_rebuild()
DeploymentSite.model_rebuild()
User.model_rebuild()
Organization.model_rebuild()
Workspace.model_rebuild()
Search.model_rebuild()
Conversation.model_rebuild()
Message.model_rebuild()
Agent.model_rebuild()
Ontology.model_rebuild()
OntologyModule.model_rebuild()
OntologyClass.model_rebuild()
OntologyObjectProperty.model_rebuild()
KnowledgeGraph.model_rebuild()
NamedGraph.model_rebuild()
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
NamedGraphRole.model_rebuild()
GraphViewRole.model_rebuild()
GraphFilterRole.model_rebuild()
FileRole.model_rebuild()
FileSystemRole.model_rebuild()
MarketplaceAppRole.model_rebuild()
