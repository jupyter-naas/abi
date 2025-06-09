from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService, OntologyEvent
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from abi import logger
from fastapi import APIRouter
from pydantic import Field
from typing import Any, Optional, Annotated
from rdflib import Literal, Graph, URIRef
import hashlib
import requests
from src import config
from src.core.modules.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from rdflib import URIRef
from enum import Enum

@dataclass
class ImageURLtoAssetPipelineConfiguration(PipelineConfiguration):
    """Configuration for ImageURLtoAssetPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """
    triple_store: ITripleStoreService
    naas_integration_config: NaasIntegrationConfiguration
    data_store_path: str = "datastore/images"

class ImageURLtoAssetPipelineParameters(PipelineParameters):
    """Parameters for ImageURLtoAssetPipeline.
    
    Attributes:
        image_url (str): URL of the image to be added
        subject_uri (str): URI of the subject to add the image asset to
        predicate_uri (str): URI of the predicate to add the image asset to
    """
    image_url: Annotated[str, Field(
        description="URL of the image to be added", 
        pattern=r"^(?!https:\/\/api\.naas\.ai\/)https?:\/\/\S+$"
    )]
    subject_uri: Annotated[str, Field(
        description="URI of the subject to add the image asset to",
    )]
    predicate_uri: Annotated[str, Field(
        description="URI of the predicate to add the image asset to"
    )]

class ImageURLtoAssetPipeline(Pipeline):
    """Pipeline for adding a new image asset to the ontology."""
    __configuration: ImageURLtoAssetPipelineConfiguration
    
    def __init__(self, configuration: ImageURLtoAssetPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__naas_integration = NaasIntegration(configuration.naas_integration_config)

    def trigger(self, event: OntologyEvent, ontology_name: str, triple: tuple[Any, Any, Any]) -> Optional[Graph]:
        s, p, o = triple
        if str(event) == str(OntologyEvent.INSERT) and not str(o).startswith("https://api.naas.ai/"):
            return self.run(ImageURLtoAssetPipelineParameters(image_url=o, subject_uri=s, predicate_uri=p))
        return None
    
    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, ImageURLtoAssetPipelineParameters):
            raise ValueError("Parameters must be of type ImageURLtoAssetPipelineParameters")
        
        # Check if image URL is already in Storage
        graph = self.__configuration.triple_store.get_subject_graph(parameters.subject_uri)
        for s, p, o in graph:
            if str(p) == str(parameters.predicate_uri) and str(o).startswith("https://api.naas.ai/"):
                logger.debug(f"🛑 Image URL exists in Storage: {parameters.image_url}")
                # Return a graph with the existing asset URL
                result_graph = Graph()
                result_graph.add((URIRef(parameters.subject_uri), URIRef(parameters.predicate_uri), Literal(str(o))))
                return result_graph
            
        try:
            file_name = self._generate_file_name(parameters.image_url)
            image_data = self._download_image(parameters.image_url)
            asset_url = self._upload_to_storage(image_data, file_name)
            logger.debug(f"✅ Image uploaded to Storage: {asset_url}")
        except Exception as e:
            logger.error(f"Error uploading image from URL '{parameters.image_url}' to Storage: {e}")
            return Graph()
        
        # Remove old image URL from triple store
        graph_remove = Graph()
        graph_remove.add((URIRef(parameters.subject_uri), URIRef(parameters.predicate_uri), Literal(parameters.image_url)))
        self.__configuration.triple_store.remove(graph_remove)

        # Replace image URL in triple store with asset URL
        graph_insert = Graph()
        graph_insert.add((URIRef(parameters.subject_uri), URIRef(parameters.predicate_uri), Literal(asset_url)))
        self.__configuration.triple_store.insert(graph_insert)
        return graph_insert

    def _generate_file_name(self, url: str) -> str:
        """Generate a unique file name from the URL."""
        return f"image_{hashlib.md5(url.encode()).hexdigest()}.png"

    def _download_image(self, url: str) -> bytes:
        """Download image from URL."""
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for bad status codes
        return response.content

    def _upload_to_storage(self, image_data: bytes, file_name: str) -> str:
        """Upload image to Storage and return the asset URL."""
        asset = self.__naas_integration.upload_asset(
            data=image_data,
            workspace_id=config.workspace_id,
            storage_name=config.storage_name,
            prefix=str(self.__configuration.data_store_path),
            object_name=str(file_name),
            visibility="public"
        )
        asset_url = asset.get("asset").get("url")
        if asset_url.endswith("/"):
            asset_url = asset_url[:-1]
        return asset_url
    
    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="image_url_to_asset",
                description="Download an image from a URL and add it as an asset to the ontology.",
                func=lambda **kwargs: self.run(ImageURLtoAssetPipelineParameters(**kwargs)),
                args_schema=ImageURLtoAssetPipelineParameters
            )   
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None