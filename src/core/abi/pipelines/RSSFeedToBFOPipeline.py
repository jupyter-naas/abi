from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import (
    ITripleStoreService,
)
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from abi import logger
from pydantic import Field
from typing import Annotated, Dict, Any, List
from rdflib import (
    Graph,
    URIRef,
    Literal,
    Namespace,
    RDF,
    OWL,
    RDFS,
    XSD,
    DCTERMS,
)
import uuid
import json
import hashlib
from datetime import datetime
from fastapi import APIRouter
from enum import Enum

# Namespace definitions
BFO = Namespace("http://purl.obolibrary.org/obo/")
CCO = Namespace("https://www.commoncoreontologies.org/")
ABI = Namespace("http://ontology.naas.ai/abi/")
RSS = Namespace("http://ontology.naas.ai/rss/")

@dataclass
class RSSFeedToBFOPipelineConfiguration(PipelineConfiguration):
    """Configuration for RSSFeedToBFOPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """
    triple_store: ITripleStoreService

class RSSFeedToBFOPipelineParameters(PipelineParameters):
    """Parameters for RSSFeedToBFOPipeline execution.
    
    Attributes:
        rss_data (Dict[str, Any]): The consolidated RSS data structure to transform
        collection_id (str): Unique identifier for this collection batch
    """
    rss_data: Annotated[Dict[str, Any], Field(
        description="Consolidated RSS data structure from orchestration system"
    )]
    collection_id: Annotated[str, Field(
        description="Unique identifier for this collection batch",
        default_factory=lambda: str(uuid.uuid4())
    )]

class RSSFeedToBFOPipeline(Pipeline):
    """Pipeline for transforming RSS feed data into BFO-compliant RDF triples."""
    
    __configuration: RSSFeedToBFOPipelineConfiguration
    
    def __init__(self, configuration: RSSFeedToBFOPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
    
    def run(self, parameters: PipelineParameters) -> Graph:
        """Transform RSS data to BFO-compliant RDF graph.
        
        Args:
            parameters: RSSFeedToBFOPipelineParameters containing RSS data
            
        Returns:
            Graph: RDF graph with BFO-compliant triples
        """
        if not isinstance(parameters, RSSFeedToBFOPipelineParameters):
            raise ValueError("Parameters must be of type RSSFeedToBFOPipelineParameters")
        
        logger.info(f"🔄 Transforming RSS data to BFO ontology for collection: {parameters.collection_id}")
        
        # Initialize graph
        graph = Graph()
        graph.bind("bfo", BFO)
        graph.bind("cco", CCO)
        graph.bind("abi", ABI)
        graph.bind("rss", RSS)
        graph.bind("xsd", XSD)
        graph.bind("dcterms", DCTERMS)
        
        # Extract RSS data
        rss_data = parameters.rss_data
        rss_entry = rss_data.get("rss_entry", {})
        
        # Create unique identifiers
        article_id = self._generate_article_id(rss_entry.get("link", ""))
        collection_process_id = f"collection_process_{parameters.collection_id}"
        publication_process_id = f"publication_process_{article_id}"
        
        # Map to BFO 7 Buckets
        self._add_material_entities(graph, rss_data, rss_entry, article_id)
        self._add_qualities(graph, rss_data, rss_entry, article_id)
        self._add_realizable_entities(graph, rss_data, rss_entry, article_id)
        self._add_processes(graph, rss_data, rss_entry, article_id, collection_process_id, publication_process_id)
        self._add_temporal_regions(graph, rss_data, rss_entry, collection_process_id, publication_process_id)
        self._add_spatial_regions(graph, rss_data, rss_entry, article_id)
        self._add_information_content_entities(graph, rss_data, rss_entry, article_id)
        
        # Insert graph into triple store following ABI pattern
        self.__configuration.triple_store.insert(graph)
        logger.info(f"✅ Generated and inserted {len(graph)} RDF triples from RSS data")
        return graph
    
    def _generate_article_id(self, link: str) -> str:
        """Generate unique article ID from URL."""
        return hashlib.md5(link.encode()).hexdigest()[:12]
    
    def _add_material_entities(self, graph: Graph, rss_data: Dict, rss_entry: Dict, article_id: str):
        """Add material entities (WHAT/WHO) to the graph."""
        
        # News article as material entity
        article_uri = RSS[f"news_article_{article_id}"]
        graph.add((article_uri, RDF.type, BFO.BFO_0000040))  # Material Entity
        graph.add((article_uri, RDFS.label, Literal(rss_entry.get("title", "Unknown Article"))))
        graph.add((article_uri, RSS.hasURL, Literal(rss_entry.get("link", ""))))
        
        # News source as organization
        if rss_entry.get("news_source"):
            source_uri = RSS[f"news_source_{self._normalize_name(rss_entry['news_source'])}"]
            graph.add((source_uri, RDF.type, BFO.BFO_0000040))  # Material Entity
            graph.add((source_uri, RDF.type, CCO.Organization))  # More specific type
            graph.add((source_uri, RDFS.label, Literal(rss_entry["news_source"])))
            graph.add((article_uri, RSS.publishedBy, source_uri))
        
        # RSS sensor as material entity
        sensor_name = rss_data.get("sensor_name", "")
        if sensor_name:
            sensor_uri = RSS[f"sensor_{self._normalize_name(sensor_name)}"]
            graph.add((sensor_uri, RDF.type, BFO.BFO_0000040))  # Material Entity
            graph.add((sensor_uri, RDFS.label, Literal(sensor_name)))
            graph.add((sensor_uri, RSS.monitorsQuery, Literal(rss_data.get("query_term", ""))))
    
    def _add_qualities(self, graph: Graph, rss_data: Dict, rss_entry: Dict, article_id: str):
        """Add qualities (HOW-IT-IS) to the graph."""
        
        article_uri = RSS[f"news_article_{article_id}"]
        
        # Article title quality
        if rss_entry.get("title"):
            title_quality_uri = RSS[f"title_quality_{article_id}"]
            graph.add((title_quality_uri, RDF.type, BFO.BFO_0000019))  # Quality
            graph.add((title_quality_uri, RDFS.label, Literal("Article Title")))
            graph.add((title_quality_uri, RSS.hasValue, Literal(rss_entry["title"])))
            graph.add((article_uri, RSS.hasQuality, title_quality_uri))
        
        # Summary quality
        if rss_entry.get("summary"):
            summary_quality_uri = RSS[f"summary_quality_{article_id}"]
            graph.add((summary_quality_uri, RDF.type, BFO.BFO_0000019))  # Quality
            graph.add((summary_quality_uri, RDFS.label, Literal("Article Summary")))
            graph.add((summary_quality_uri, RSS.hasValue, Literal(rss_entry["summary"])))
            graph.add((article_uri, RSS.hasQuality, summary_quality_uri))
        
        # Content type quality
        content_type = rss_entry.get("title_detail", {}).get("type", "text/plain")
        content_type_quality_uri = RSS[f"content_type_quality_{article_id}"]
        graph.add((content_type_quality_uri, RDF.type, BFO.BFO_0000019))  # Quality
        graph.add((content_type_quality_uri, RDFS.label, Literal("Content Type")))
        graph.add((content_type_quality_uri, RSS.hasValue, Literal(content_type)))
        graph.add((article_uri, RSS.hasQuality, content_type_quality_uri))
    
    def _add_realizable_entities(self, graph: Graph, rss_data: Dict, rss_entry: Dict, article_id: str):
        """Add realizable entities (WHY-POTENTIAL) to the graph."""
        
        article_uri = RSS[f"news_article_{article_id}"]
        
        # Information dissemination capability
        dissemination_capability_uri = RSS[f"dissemination_capability_{article_id}"]
        graph.add((dissemination_capability_uri, RDF.type, BFO.BFO_0000017))  # Realizable Entity
        graph.add((dissemination_capability_uri, RDFS.label, Literal("Information Dissemination Capability")))
        graph.add((article_uri, RSS.hasCapability, dissemination_capability_uri))
        
        # News reporting function
        reporting_function_uri = RSS[f"reporting_function_{article_id}"]
        graph.add((reporting_function_uri, RDF.type, BFO.BFO_0000034))  # Function
        graph.add((reporting_function_uri, RDFS.label, Literal("News Reporting Function")))
        graph.add((article_uri, RSS.hasFunction, reporting_function_uri))
    
    def _add_processes(self, graph: Graph, rss_data: Dict, rss_entry: Dict, article_id: str, 
                      collection_process_id: str, publication_process_id: str):
        """Add processes (HOW-IT-HAPPENS) to the graph."""
        
        # News publication process
        publication_process_uri = RSS[publication_process_id]
        graph.add((publication_process_uri, RDF.type, BFO.BFO_0000015))  # Process
        graph.add((publication_process_uri, RDFS.label, Literal("News Publication Process")))
        
        article_uri = RSS[f"news_article_{article_id}"]
        graph.add((publication_process_uri, RSS.hasOutput, article_uri))
        
        # RSS data collection process
        collection_process_uri = RSS[collection_process_id]
        graph.add((collection_process_uri, RDF.type, BFO.BFO_0000015))  # Process
        graph.add((collection_process_uri, RDFS.label, Literal("RSS Data Collection Process")))
        graph.add((collection_process_uri, RSS.collectsFrom, article_uri))
        
        # Connect processes
        graph.add((collection_process_uri, RSS.followsProcess, publication_process_uri))
    
    def _add_temporal_regions(self, graph: Graph, rss_data: Dict, rss_entry: Dict, 
                            collection_process_id: str, publication_process_id: str):
        """Add temporal regions (WHEN) to the graph."""
        
        # Publication temporal region
        if rss_entry.get("published"):
            pub_temporal_uri = RSS[f"publication_time_{publication_process_id}"]
            graph.add((pub_temporal_uri, RDF.type, BFO.BFO_0000008))  # Temporal Region
            graph.add((pub_temporal_uri, RDFS.label, Literal("Publication Time")))
            graph.add((pub_temporal_uri, RSS.hasTimestamp, Literal(rss_entry["published"], datatype=XSD.dateTime)))
            
            publication_process_uri = RSS[publication_process_id]
            graph.add((publication_process_uri, RSS.occursAt, pub_temporal_uri))
        
        # Collection temporal region
        collection_time = rss_data.get("collection_timestamp")
        if collection_time:
            coll_temporal_uri = RSS[f"collection_time_{collection_process_id}"]
            graph.add((coll_temporal_uri, RDF.type, BFO.BFO_0000008))  # Temporal Region
            graph.add((coll_temporal_uri, RDFS.label, Literal("Collection Time")))
            
            # Convert timestamp format YYYYMMDDTHHMMSS to ISO format
            formatted_time = self._format_timestamp(collection_time)
            graph.add((coll_temporal_uri, RSS.hasTimestamp, Literal(formatted_time, datatype=XSD.dateTime)))
            
            collection_process_uri = RSS[collection_process_id]
            graph.add((collection_process_uri, RSS.occursAt, coll_temporal_uri))
    
    def _add_spatial_regions(self, graph: Graph, rss_data: Dict, rss_entry: Dict, article_id: str):
        """Add spatial regions (WHERE) to the graph."""
        
        # Digital location (URL as spatial region)
        if rss_entry.get("link"):
            digital_location_uri = RSS[f"digital_location_{article_id}"]
            graph.add((digital_location_uri, RDF.type, BFO.BFO_0000006))  # Spatial Region
            graph.add((digital_location_uri, RDFS.label, Literal("Digital Location")))
            graph.add((digital_location_uri, RSS.hasURL, Literal(rss_entry["link"])))
            
            article_uri = RSS[f"news_article_{article_id}"]
            graph.add((article_uri, RSS.locatedAt, digital_location_uri))
    
    def _add_information_content_entities(self, graph: Graph, rss_data: Dict, rss_entry: Dict, article_id: str):
        """Add information content entities (HOW-WE-KNOW) to the graph."""
        
        # RSS feed entry as information content entity
        rss_record_uri = RSS[f"rss_record_{article_id}"]
        graph.add((rss_record_uri, RDF.type, BFO.BFO_0000031))  # Information Content Entity
        graph.add((rss_record_uri, RDFS.label, Literal("RSS Feed Record")))
        
        # Add metadata
        graph.add((rss_record_uri, RSS.hasCollectionTimestamp, 
                  Literal(rss_data.get("collection_timestamp", ""))))
        graph.add((rss_record_uri, RSS.hasQueryTerm, 
                  Literal(rss_data.get("query_term", ""))))
        graph.add((rss_record_uri, RSS.hasSensorName, 
                  Literal(rss_data.get("sensor_name", ""))))
        
        # Connect to article
        article_uri = RSS[f"news_article_{article_id}"]
        graph.add((rss_record_uri, RSS.documentsArticle, article_uri))
        
        # Collection metadata document
        collection_metadata_uri = RSS[f"collection_metadata_{article_id}"]
        graph.add((collection_metadata_uri, RDF.type, BFO.BFO_0000031))  # Information Content Entity
        graph.add((collection_metadata_uri, RDFS.label, Literal("Collection Metadata")))
        graph.add((collection_metadata_uri, RSS.hasRawData, 
                  Literal(json.dumps(rss_data), datatype=XSD.string)))
    
    def _normalize_name(self, name: str) -> str:
        """Normalize a name for use as URI fragment."""
        return name.replace(" ", "_").replace(".", "_").replace("/", "_").replace(":", "_")
    
    def _format_timestamp(self, timestamp: str) -> str:
        """Convert YYYYMMDDTHHMMSS to ISO 8601 format."""
        try:
            dt = datetime.strptime(timestamp, "%Y%m%dT%H%M%S")
            return dt.isoformat()
        except ValueError:
            return timestamp  # Return as-is if format is different
    
    def as_tools(self) -> list[BaseTool]:
        """Get pipeline as list of LangChain tools following ABI pattern."""
        return [
            StructuredTool(
                name="rss_feed_to_bfo_pipeline",
                description="Transform RSS feed data into BFO-compliant RDF triples for knowledge graph storage",
                func=lambda **kwargs: self.run(
                    RSSFeedToBFOPipelineParameters(**kwargs)
                ),
                args_schema=RSSFeedToBFOPipelineParameters,
            ),
            StructuredTool(
                name="process_rss_news_article", 
                description="Process a single RSS news article entry into BFO ontology",
                func=lambda **kwargs: self.run(
                    RSSFeedToBFOPipelineParameters(**kwargs)
                ),
                args_schema=RSSFeedToBFOPipelineParameters,
            ),
            StructuredTool(
                name="batch_process_rss_feeds",
                description="Batch process multiple RSS feed entries into BFO-compliant knowledge graph",
                func=lambda **kwargs: self.run(
                    RSSFeedToBFOPipelineParameters(**kwargs)
                ),
                args_schema=RSSFeedToBFOPipelineParameters,
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
        """Expose pipeline as FastAPI endpoints."""
        if tags is None:
            tags = []
        
        # Use route name or default
        if route_name == "":
            route_name = "rss_feed_to_bfo_pipeline"
        
        # Use name or default
        if name == "":
            name = "RSS Feed to BFO Pipeline"
        
        # Use description or default
        if description == "":
            description = "Transform RSS feed data into BFO-compliant RDF triples"
        
        @router.post(f"/{route_name}", tags=tags)
        async def rss_feed_to_bfo_endpoint(parameters: RSSFeedToBFOPipelineParameters):
            """Transform RSS feed data into BFO-compliant RDF triples."""
            try:
                result_graph = self.run(parameters)
                return {
                    "status": "success",
                    "triples_generated": len(result_graph),
                    "collection_id": parameters.collection_id,
                    "message": f"Successfully transformed RSS data into {len(result_graph)} BFO triples"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "error": str(e),
                    "collection_id": parameters.collection_id
                }