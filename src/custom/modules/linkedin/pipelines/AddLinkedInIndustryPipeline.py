# from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
# from abi.services.triple_store.TripleStorePorts import ITripleStoreService
# from langchain_core.tools import StructuredTool
# from dataclasses import dataclass
# from fastapi import APIRouter
# from pydantic import Field
# from typing import Optional
# from abi.utils.Graph import ABI, URI_REGEX
# from rdflib import URIRef, Literal, Graph
# from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
#     AddIndividualPipeline,
#     AddIndividualPipelineConfiguration,
#     AddIndividualPipelineParameters
# )

# @dataclass
# class AddLinkedInIndustryPipelineConfiguration(PipelineConfiguration):
#     triple_store: ITripleStoreService
#     add_individual_pipeline_configuration: AddIndividualPipelineConfiguration

# class AddLinkedInIndustryPipelineParameters(PipelineParameters):
#     label: Optional[str] = Field(None, description="Industry name to be added in class: http://ontology.naas.ai/abi/LinkedInIndustry")
#     individual_uri: Optional[str] = Field(None, description="URI of the individual if already known.", pattern=URI_REGEX)
#     entity_urn: Optional[str] = Field(None, description="Entity URN of the individual.")
#     organization_uri: Optional[str] = Field(None, description="Organization URI from class: https://www.commoncoreontologies.org/ont00000443", pattern=URI_REGEX)

# class AddLinkedInIndustryPipeline(Pipeline):
#     __configuration: AddLinkedInIndustryPipelineConfiguration
    
#     def __init__(self, configuration: AddLinkedInIndustryPipelineConfiguration):
#         super().__init__(configuration)
#         self.__configuration = configuration
#         self.__add_individual_pipeline = AddIndividualPipeline(configuration.add_individual_pipeline_configuration)

#     def run(self, parameters: AddLinkedInIndustryPipelineParameters) -> str:
#         # Initialize graphs
#         graph_insert = Graph()
#         graph_remove = Graph()

#         # Create or get subject URI & graph
#         individual_uri = parameters.individual_uri
#         if parameters.label and not individual_uri:
#             individual_uri, graph = self.__add_individual_pipeline.run(AddIndividualPipelineParameters(
#                 class_uri=ABI.LinkedInIndustry,
#                 individual_label=parameters.label
#             ))
#         else:
#             individual_uri = URIRef(individual_uri)
#             graph = self.__configuration.triple_store.get_subject_graph(individual_uri)
            
#         # Update existing objects
#         entity_urn_exists = False
#         organization_uri_exists = False
#         for s, p, o in graph:
#             if str(p) == "http://www.w3.org/2000/01/rdf-schema#label":
#                 if parameters.label is not None and str(o) != parameters.label:
#                     graph_remove.add((s, p, o))
#                     graph_insert.add((s, p, Literal(parameters.label)))
#             if str(p) == "http://ontology.naas.ai/abi/entity_urn":
#                 entity_urn_exists = True
#                 if parameters.entity_urn is not None and str(o) != parameters.entity_urn:
#                     graph_remove.add((s, p, o))
#                     graph_insert.add((s, p, Literal(parameters.entity_urn)))
#             if str(p) == "http://ontology.naas.ai/abi/hasOrganization" and str(o) == parameters.organization_uri:
#                 organization_uri_exists = True
                    
#         # Add new objects
#         if parameters.entity_urn and not entity_urn_exists:
#             graph_insert.add((individual_uri, ABI.entity_urn, Literal(parameters.entity_urn)))
#         if parameters.organization_uri and not organization_uri_exists:
#             graph_insert.add((individual_uri, ABI.hasOrganization, URIRef(parameters.organization_uri)))
#             graph_insert.add((URIRef(parameters.organization_uri), ABI.belongsToIndustry, individual_uri))

#         # Save graphs to triple store
#         self.__configuration.triple_store.insert(graph_insert)
#         self.__configuration.triple_store.remove(graph_remove)
#         return individual_uri
    
#     def as_tools(self) -> list[StructuredTool]:
#         return [
#             StructuredTool(
#                 name="ontology_add_linkedin_industry",
#                 description="Add a LinkedIn industry to the ontology. Requires the industry name.",
#                 func=lambda **kwargs: self.run(AddLinkedInIndustryPipelineParameters(**kwargs)),
#                 args_schema=AddLinkedInIndustryPipelineParameters
#             )   
#         ]

#     def as_api(self, router: APIRouter) -> None:
#         pass 