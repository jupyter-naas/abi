from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, List
from abi.utils.Graph import CCO, ABI
from rdflib import URIRef, Literal, RDF, OWL, Graph
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
)


@dataclass
class AddLinkedInPagePipelineConfiguration(PipelineConfiguration):
    """Configuration for AddLinkedInPagePipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration


class AddLinkedInPagePipelineParameters(PipelineParameters):
    label: str = Field(
        ...,
        description="LinkedIn page URL (e.g., 'https://www.linkedin.com/(in|company|school|edu)/[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*') to be added in class: http://ontology.naas.ai/abi/LinkedInProfilePage or http://ontology.naas.ai/abi/LinkedInCompanyPage or http://ontology.naas.ai/abi/LinkedInSchoolPage or http://ontology.naas.ai/abi/LinkedInEducationPage",
    )
    individual_uri: Optional[str] = Field(
        None,
        description="URI of the individual if already known. It must start with 'http://ontology.naas.ai/abi/'.",
    )
    linkedin_id: Optional[str] = Field(
        None,
        description="LinkedIn unique ID of the individual. It must starts with 'ACoAAA'",
    )
    linkedin_url: Optional[str] = Field(
        None,
        description="LinkedIn URL with the LinkedIn ID as identifier. It must starts with 'https://www.linkedin.com/in/ACoAAA'",
    )
    linkedin_public_id: Optional[str] = Field(
        None, description="LinkedIn Public ID of the individual."
    )
    linkedin_public_url: Optional[str] = Field(
        None,
        description="LinkedIn Public URL of the individual with the LinkedIn Public ID as identifier. It must starts with 'https://www.linkedin.com/in/'",
    )
    owner_uris: Optional[List[str]] = Field(
        None,
        description="Owners URI from class: https://www.commoncoreontologies.org/ont00001262 or https://www.commoncoreontologies.org/ont00000443. It must start with 'http://ontology.naas.ai/abi/'.",
    )


class AddLinkedInPagePipeline(Pipeline):
    """Pipeline for adding a new LinkedIn page to the ontology."""

    __configuration: AddLinkedInPagePipelineConfiguration

    def __init__(self, configuration: AddLinkedInPagePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(
            configuration.add_individual_pipeline_configuration
        )

    def run(self, parameters: AddLinkedInPagePipelineParameters) -> str:
        # Initialize a new graph
        graph = Graph()

        # Get class URI
        if "/in/" in parameters.label:
            identifier = "/in/"
            class_uri = ABI.LinkedInProfilePage
        elif "/company/" in parameters.label:
            identifier = "/company/"
            class_uri = ABI.LinkedInCompanyPage
        elif "/school/" in parameters.label:
            identifier = "/school/"
            class_uri = ABI.LinkedInSchoolPage
        else:
            raise ValueError(
                f"Invalid LinkedIn URL: {parameters.label}. It must start with 'https://www.linkedin.com/(in|company|school|edu)/[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*'."
            )

        # Create LinkedIn page URI
        linkedin_page_uri = parameters.individual_uri
        if parameters.label and not linkedin_page_uri:
            linkedin_page_uri, graph = self.__add_individual_pipeline.run(
                AddIndividualPipelineParameters(
                    class_uri=class_uri, individual_label=parameters.label
                )
            )
        else:
            if linkedin_page_uri.startswith("http://ontology.naas.ai/abi/"):
                linkedin_page_uri = URIRef(linkedin_page_uri)
            else:
                raise ValueError(
                    f"Invalid LinkedIn Page URI: {linkedin_page_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        # Add LinkedIn Public ID if provided
        linkedin_public_id = parameters.linkedin_public_id
        if not linkedin_public_id:
            linkedin_public_id = parameters.label.split(identifier)[-1].split("/")[0]
        graph.add(
            (linkedin_page_uri, ABI.linkedin_public_id, Literal(linkedin_public_id))
        )

        # Add LinkedIn Public URL if provided
        linkedin_public_url = parameters.linkedin_public_url
        if not linkedin_public_url:
            linkedin_public_url = (
                "https://www.linkedin.com" + identifier + linkedin_public_id
            )
        graph.add(
            (linkedin_page_uri, ABI.linkedin_public_url, Literal(linkedin_public_url))
        )

        # Add LinkedIn ID if provided
        if parameters.linkedin_id:
            graph.add(
                (linkedin_page_uri, ABI.linkedin_id, Literal(parameters.linkedin_id))
            )

        # Add LinkedIn URL if provided
        if parameters.linkedin_url:
            graph.add(
                (linkedin_page_uri, ABI.linkedin_url, Literal(parameters.linkedin_url))
            )

        # Add owners URI if provided
        if parameters.owner_uris:
            for owner_uri in parameters.owner_uris:
                if owner_uri.startswith("http://ontology.naas.ai/abi/"):
                    graph.add(
                        (linkedin_page_uri, ABI.isLinkedInPageOf, URIRef(owner_uri))
                    )
                    graph.add(
                        (URIRef(owner_uri), ABI.hasLinkedInPage, linkedin_page_uri)
                    )
                else:
                    raise ValueError(
                        f"Invalid Owner URI: {owner_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                    )

        # Save the graph
        self.__configuration.triple_store.insert(graph)
        return linkedin_page_uri

    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_linkedin_page",
                description="Add a LinkedIn page to the ontology. Requires the LinkedIn page URL.",
                func=lambda **kwargs: self.run(
                    AddLinkedInPagePipelineParameters(**kwargs)
                ),
                args_schema=AddLinkedInPagePipelineParameters,
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
