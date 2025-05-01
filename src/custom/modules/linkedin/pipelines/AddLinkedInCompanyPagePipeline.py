from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, List
from abi.utils.Graph import CCO, ABI
from rdflib import URIRef, Literal, RDF, OWL, Graph, XSD
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters
)

URI_REGEX = r"http:\/\/ontology\.naas\.ai\/abi\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

@dataclass
class AddLinkedInCompanyPagePipelineConfiguration(PipelineConfiguration):
    """Configuration for AddLinkedInCompanyPagePipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """
    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration

class AddLinkedInCompanyPagePipelineParameters(PipelineParameters):
    label: Optional[str] = Field(None, description="LinkedIn page URL to be added.", pattern="https?:\/\/.+\.linkedin\.com\/company\/[^?]+")
    linkedin_id: Optional[str] = Field(None, description="LinkedIn ID of the LinkedIn company page.", pattern="^\d+$")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn URL of the LinkedIn company page.", pattern="https?:\/\/.+\.linkedin\.com\/company\/[^?]+")
    linkedin_public_id: Optional[str] = Field(None, description="LinkedIn Public ID of the LinkedIn company page.")
    linkedin_public_url: Optional[str] = Field(None, description="LinkedIn Public URL of the LinkedIn company page.", pattern="https?:\/\/.+\.linkedin\.com\/company\/[^?]+")
    individual_uri: Optional[str] = Field(None, description="URI of the individual if already known.", pattern=URI_REGEX)
    page_name: Optional[str] = Field(None, description="Name of the LinkedIn company page.")
    description: Optional[str] = Field(None, description="Description of the LinkedIn company page.")
    entity_urn: Optional[str] = Field(None, description="Entity URN of the LinkedIn company page.")
    organization_uri: Optional[str] = Field(None, description="URI of the owner from class: https://www.commoncoreontologies.org/ont00001262 or https://www.commoncoreontologies.org/ont00000443", pattern=URI_REGEX)

class AddLinkedInCompanyPagePipeline(Pipeline):
    """Pipeline for adding a new LinkedIn company page to the ontology."""
    __configuration: AddLinkedInCompanyPagePipelineConfiguration
    
    def __init__(self, configuration: AddLinkedInCompanyPagePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(configuration.add_individual_pipeline_configuration)

    def run(self, parameters: AddLinkedInCompanyPagePipelineParameters) -> str:
        # Initialize graphs
        graph_insert = Graph()
        graph_remove = Graph()

        # Get class URI based on LinkedIn URL type
        if parameters.label:
            label =  "https://www.linkedin.com/company/" + parameters.label.split("/company/")[-1].split('/')[0]
        
        # Create or get subject URI & graph
        individual_uri = parameters.individual_uri
        if parameters.label and not individual_uri:
            individual_uri, graph = self.__add_individual_pipeline.run(AddIndividualPipelineParameters(
                class_uri=ABI.LinkedInCompanyPage,
                individual_label=label
            ))
        else:
            individual_uri = URIRef(individual_uri)
            graph = self.__configuration.triple_store.get_subject_graph(individual_uri)
        
        # Update existing objects
        linkedin_id_exists = False
        linkedin_url_exists = False
        linkedin_public_id_exists = False
        linkedin_public_url_exists = False
        organization_uri_exists = False
        description_exists = False
        entity_urn_exists = False
        for s, p, o in graph:
            if str(p) == "http://www.w3.org/2000/01/rdf-schema#label":
                if label is not None and str(o) != label:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(label)))
            if str(p) == "http://ontology.naas.ai/abi/page_name":
                if parameters.page_name is not None and str(o) != parameters.page_name:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.name)))
            if str(p) == "http://ontology.naas.ai/abi/linkedin_id":
                linkedin_id_exists = True
                if parameters.linkedin_id is not None and str(o) != parameters.linkedin_id:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.linkedin_id)))
            elif str(p) == "http://ontology.naas.ai/abi/linkedin_url":
                linkedin_url_exists = True
                if parameters.linkedin_url is not None and str(o) != parameters.linkedin_url:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.linkedin_url)))
            elif str(p) == "http://ontology.naas.ai/abi/linkedin_public_id":
                linkedin_public_id_exists = True
                if parameters.linkedin_public_id is not None and str(o) != parameters.linkedin_public_id:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.linkedin_public_id)))
            elif str(p) == "http://ontology.naas.ai/abi/linkedin_public_url":
                linkedin_public_url_exists = True
                if parameters.linkedin_public_url is not None and str(o) != parameters.linkedin_public_url:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.linkedin_public_url)))
            elif str(p) == "http://ontology.naas.ai/abi/isLinkedInPageOf":
                organization_uri_exists = True
                if parameters.organization_uri is not None and str(o) != parameters.organization_uri:
                    graph_remove.add((s, p, o))
                    graph_remove.add((o, ABI.hasLinkedInPage, s))
                    graph_insert.add((s, ABI.isLinkedInPageOf, URIRef(parameters.organization_uri)))
                    graph_insert.add((URIRef(parameters.organization_uri), ABI.hasLinkedInPage, s))
            elif str(p) == "http://ontology.naas.ai/abi/description":
                description_exists = True
                if parameters.description is not None and str(o) != parameters.description:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.description)))
            elif str(p) == "http://ontology.naas.ai/abi/entity_urn":
                entity_urn_exists = True
                if parameters.entity_urn is not None and str(o) != parameters.entity_urn:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.entity_urn)))

        # Add new objects
        if parameters.linkedin_id and not linkedin_id_exists:
            graph_insert.add((individual_uri, ABI.linkedin_id, Literal(parameters.linkedin_id)))
        if parameters.linkedin_url is not None and not linkedin_url_exists:
            graph_insert.add((individual_uri, ABI.linkedin_url, Literal(parameters.linkedin_url)))
        if parameters.linkedin_public_id is not None and not linkedin_public_id_exists:
            graph_insert.add((individual_uri, ABI.linkedin_public_id, Literal(parameters.linkedin_public_id)))
        if parameters.linkedin_public_url is not None and not linkedin_public_url_exists:
            graph_insert.add((individual_uri, ABI.linkedin_public_url, Literal(parameters.linkedin_public_url)))
        if parameters.organization_uri and not organization_uri_exists:
            graph_insert.add((individual_uri, ABI.isLinkedInPageOf, URIRef(parameters.organization_uri)))
            graph_insert.add((URIRef(parameters.organization_uri), ABI.hasLinkedInPage, individual_uri))
        if parameters.description and not description_exists:
            graph_insert.add((individual_uri, ABI.description, Literal(parameters.description)))
        if parameters.entity_urn and not entity_urn_exists:
            graph_insert.add((individual_uri, ABI.entity_urn, Literal(parameters.entity_urn)))

        # Save the graph
        self.__configuration.triple_store.insert(graph_insert)
        self.__configuration.triple_store.remove(graph_remove)
        return individual_uri
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_linkedin_company_page",
                description="Add a LinkedIn company page to the ontology. Requires the LinkedIn company page URL.",
                func=lambda **kwargs: self.run(AddLinkedInCompanyPagePipelineParameters(**kwargs)),
                args_schema=AddLinkedInCompanyPagePipelineParameters
            )   
        ]

    def as_api(self, router: APIRouter) -> None:
        pass 