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
                description="Relates a server to the deployment site in which it is located or operates."
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
            Field(
                description="Relates an organization to the tenant role it bears in relation to the Nexus platform."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_user: Optional[
        Annotated[
            List[Union[URIRef, User, str]],
            Field(
                description="Relates an organization to a user that is a member of it within the Nexus platform."
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
        "hosted_on": "http://ontology.naas.ai/nexus/hostedOn",
        "is_workspace_of": "http://ontology.naas.ai/nexus/isWorkspaceOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"hosted_on", "is_workspace_of"}

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
    hosted_on: Optional[
        Annotated[
            List[Union[Server, URIRef, str]],
            Field(
                description="Relates a workspace to the physical server on which its realization depends."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_workspace_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="Relates a workspace to the organization on which it generically depends within the Nexus platform."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


# Rebuild models to resolve forward references
Tenant.model_rebuild()
Server.model_rebuild()
DeploymentSite.model_rebuild()
User.model_rebuild()
Organization.model_rebuild()
Workspace.model_rebuild()
