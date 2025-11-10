from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from fastapi import APIRouter
from pydantic import Field
from typing import Annotated
from rdflib import URIRef, Literal, RDF, OWL, Graph, RDFS, XSD, Namespace
import os
import uuid
from datetime import datetime
from src.utils.Storage import save_triples, save_csv
from src.utils.SPARQL import get_identifiers
from abi.utils.String import create_hash_from_string
from abi.utils.Graph import ABI, CCO, BFO
from enum import Enum
from abi import logger
from src.marketplace.applications.linkedin.integrations.LinkedInExportIntegration import (
    LinkedInExportIntegration,
    LinkedInExportIntegrationConfiguration
)
import pandas as pd


LINKEDIN = Namespace("http://ontology.naas.ai/abi/linkedin/")


@dataclass
class LinkedInExportProfilePipelineConfiguration(PipelineConfiguration):
    """Configuration for LinkedInExportProfilePipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service
        linkedin_export_configuration (LinkedInExportIntegrationConfiguration): The LinkedIn export integration configuration
    """
    triple_store: ITripleStoreService
    linkedin_export_configuration: LinkedInExportIntegrationConfiguration


class LinkedInExportProfilePipelineParameters(PipelineParameters):
    """Parameters for LinkedInExportProfilePipeline.
    
    Attributes:
        file_name (str): Name of the CSV file to process
    """
    linkedin_public_url: Annotated[str, Field(
        description="LinkedIn public URL of the profile to process",
    )]
    file_name: Annotated[str, Field(
        description="Name of the CSV file to process from the LinkedIn export",
    )] = "Profile.csv"


class LinkedInExportProfilePipeline(Pipeline):
    """Pipeline for importing data from Excel tables to the triple store."""
    
    __configuration: LinkedInExportProfilePipelineConfiguration

    def __init__(self, configuration: LinkedInExportProfilePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__linkedin_export_integration = LinkedInExportIntegration(configuration.linkedin_export_configuration)

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, LinkedInExportProfilePipelineParameters):
            raise ValueError("Parameters must be of type LinkedInExportProfilePipelineParameters")

        # Step 1: Read CSV file
        logger.debug(f"Step 1: Reading CSV file '{parameters.file_name}'")
        df = self.__linkedin_export_integration.read_csv(parameters.file_name)
        if len(df) == 0:
            logger.warning(f"❌ No rows to process in CSV file '{parameters.file_name}'")
            return Graph()
        logger.debug(f"✅ {len(df)} rows in CSV file to be processed")

        # Step 2: Initializing graph and creating backing datasource
        logger.debug("Step 2: Initializing graph and creating backing datasource")
        graph = Graph()
        graph.bind("cco", CCO)
        graph.bind("bfo", BFO)
        graph.bind("abi", ABI)
        graph.bind("rdfs", RDFS)
        graph.bind("rdf", RDF)
        graph.bind("owl", OWL)
        graph.bind("xsd", XSD)
        graph.bind("linkedin", LINKEDIN)

        # Define Class URIs
        DATA_SOURCE = ABI["DataSource"]
        DATA_SOURCE_COMPONENT = ABI["DataSourceComponent"]
        PERSON = CCO["ont00001262"]
        LINKEDIN_PROFILE_PAGE = LINKEDIN["ProfilePage"]

        # Get file metadata
        export_directory = self.__linkedin_export_integration.unzip_export()["extracted_directory"]
        file_path = os.path.join(export_directory, parameters.file_name)
        file_modified_at = self.__linkedin_export_integration.unzip_export()["file_modified_at"]
        file_created_at = self.__linkedin_export_integration.unzip_export()["file_created_at"]

        # Create backing datasource
        data_source_hash = create_hash_from_string(f"{file_modified_at}_{file_path}")
        existing_data_sources: dict[str, URIRef] = get_identifiers(class_uri=DATA_SOURCE)
        logger.debug(f"Existing data sources: {len(existing_data_sources)}")
        data_source_uri = existing_data_sources.get(data_source_hash)

        # Prepare column and row metadata
        columns_list = list(df.columns)
        columns_count = len(columns_list)
        rows_count = len(df)
        col_list_str = ", ".join([str(col) for col in columns_list])

        if data_source_uri is None:
            data_source_uri = ABI[str(uuid.uuid4())]
            graph.add((data_source_uri, RDF.type, OWL.NamedIndividual))
            graph.add((data_source_uri, RDF.type, DATA_SOURCE))
            graph.add((data_source_uri, ABI.filename, Literal(parameters.file_name)))
            graph.add((data_source_uri, ABI.unique_id, Literal(data_source_hash)))
            graph.add((data_source_uri, ABI.extracted_at, Literal(file_modified_at.strftime("%Y-%m-%dT%H:%M:%S"), datatype=XSD.dateTime)))
            graph.add((data_source_uri, ABI.created_at, Literal(file_created_at.strftime("%Y-%m-%dT%H:%M:%S"), datatype=XSD.dateTime)))
            graph.add((data_source_uri, ABI.source_path, Literal(file_path)))
            graph.add((data_source_uri, ABI.source_type, Literal("CSV_FILE")))
            graph.add((data_source_uri, ABI.columns_list, Literal(col_list_str)))
            graph.add((data_source_uri, ABI.columns_count, Literal(columns_count)))
            graph.add((data_source_uri, ABI.rows_count, Literal(rows_count)))
        
        # Step 3: Processing rows from CSV file
        logger.debug("Step 3: Processing rows")
        count_row: int = 0
        for _, row in df.iterrows():
            count_row += 1
            logger.debug(f"🔄 Processing row {count_row}/{len(df)}")
            row_hash = create_hash_from_string(str(tuple(row)))
            existing_data_source_components: dict[str, URIRef] = get_identifiers(class_uri=DATA_SOURCE_COMPONENT)
            logger.debug(f"- Existing Data Source Components: {len(existing_data_source_components)}")
            row_uri = existing_data_source_components.get(row_hash)
            if row_uri is None:
                logger.debug("Step 3.1: Adding backing datasource component for row")
                row_uri = ABI[str(uuid.uuid4())]
                existing_data_source_components[row_hash] = row_uri
                # Add backing datasource component
                graph.add((row_uri, RDF.type, OWL.NamedIndividual))
                graph.add((row_uri, RDF.type, DATA_SOURCE_COMPONENT))
                graph.add((row_uri, ABI.unique_id, Literal(row_hash)))
                graph.add((row_uri, ABI.isComponentOf, data_source_uri))
                graph.add((data_source_uri, ABI.hasComponent, row_uri))

                # Add all column values as data properties (lower case, spaces to underscores)
                for col in row.index:
                    pred_name = col.strip().lower().replace(" ", "_")
                    value = row.get(col)
                    if pd.isnull(value) or str(value) == "":
                        value = "UNKNOWN"
                    predicate = LINKEDIN[pred_name]
                    graph.add((row_uri, predicate, Literal(str(value))))

            # Add LinkedIn profile page
            linkedin_public_url = parameters.linkedin_public_url
            linkedin_public_id = linkedin_public_url.split("/in/")[1].split("/")[0].split("?")[0]
            logger.debug(f"Step 3.2: Adding LinkedIn profile page: '{linkedin_public_url}' (ID: '{linkedin_public_id}')")
            linkedin_profile_page_uris: dict[str, URIRef] = get_identifiers(property_uri=LINKEDIN.public_url, class_uri=LINKEDIN_PROFILE_PAGE)
            logger.debug(f"- Existing LinkedIn profile page: {len(linkedin_profile_page_uris)}")
            linkedin_profile_page_uri = linkedin_profile_page_uris.get(linkedin_public_url)

            # Create linkedin profile page if it doesn't exist
            if linkedin_profile_page_uri is None:
                linkedin_profile_page_uri = ABI[str(uuid.uuid4())]
                linkedin_profile_page_uris[linkedin_public_url] = linkedin_profile_page_uri
                graph.add((linkedin_profile_page_uri, RDF.type, OWL.NamedIndividual))
                graph.add((linkedin_profile_page_uri, RDF.type, LINKEDIN_PROFILE_PAGE))
                graph.add((linkedin_profile_page_uri, RDFS.label, Literal(linkedin_public_url)))
                graph.add((linkedin_profile_page_uri, LINKEDIN.public_url, Literal(linkedin_public_url)))
                graph.add((linkedin_profile_page_uri, LINKEDIN.public_id, Literal(linkedin_public_id)))
                graph.add((linkedin_profile_page_uri, ABI.hasBackingDataSource, row_uri))

            # Create a SPARQL query to check if the LinkedIn profile page has property isLinkedInPageOf to return the person URI
            # We'll use the linkedin_profile_page_uri defined above 
            sparql_query = f"""
            PREFIX abi: <http://ontology.naas.ai/abi/>
            SELECT ?personUri WHERE {{
                <{linkedin_profile_page_uri}> abi:isLinkedInPageOf ?personUri .
            }}
            """

            logger.debug(f"Step 3.3: SPARQL query to check existing LinkedInPageOf for URI:\n{sparql_query}")

            # The invocation of the triple store's query method would depend on your implementation.
            # For illustration, we check for an existing person:
            existing_person_uris = list(self.__configuration.triple_store.query(sparql_query))
            if existing_person_uris:
                # If such a person exists, use the first result (unpack if needed)
                person_uri = existing_person_uris[0][0] if isinstance(existing_person_uris[0], (list, tuple)) else existing_person_uris[0]
                logger.debug(f"Existing person found for LinkedIn page: {person_uri}")
            else:
                # If no such triple, create the new person as before
                first_name = str(row.get("First Name", "")).strip()
                last_name = str(row.get("Last Name", "")).strip()
                maiden_name = str(row.get("Maiden Name", "")).strip()

                def parse_birth_date(birth_date_str: str) -> str:
                    """Convert a birth date string (e.g., 'Aug 18, 1992') to 'YYYY-MM-DD' format."""
                    from datetime import datetime
                    try:
                        if birth_date_str:
                            # Common LinkedIn export format: 'Aug 18, 1992'
                            date_obj = datetime.strptime(birth_date_str, "%b %d, %Y")
                            return date_obj.strftime("%Y-%m-%d")
                    except Exception:
                        pass
                    return ""
                
                birth_date_raw = row.get("Birth Date", "").strip()
                birth_date = parse_birth_date(birth_date_raw)
                person_name = f"{first_name} {last_name}"
                logger.debug(f"Step 3.3: Adding person '{person_name}'")
                person_uri = ABI[str(uuid.uuid4())]
                graph.add((person_uri, RDF.type, OWL.NamedIndividual))
                graph.add((person_uri, RDF.type, PERSON))
                graph.add((person_uri, RDFS.label, Literal(person_name)))
                graph.add((person_uri, ABI.first_name, Literal(first_name)))
                graph.add((person_uri, ABI.last_name, Literal(last_name)))
                graph.add((person_uri, ABI.maiden_name, Literal(maiden_name)))
                graph.add((person_uri, ABI.birth_date, Literal(birth_date, datatype=XSD.date)))
                graph.add((person_uri, ABI.hasBackingDataSource, row_uri))
                graph.add((linkedin_profile_page_uri, ABI.isLinkedInPageOf, person_uri))
                graph.add((person_uri, ABI.hasLinkedInPage, linkedin_profile_page_uri))

        # Add triples to triple store
        logger.debug("Step 4: Adding triples to triple store")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        log_dir_path = os.path.join(export_directory, timestamp, parameters.file_name).replace("storage/", "")
        csv_file_name = parameters.file_name + ".csv"
        ttl_file_name = f"insert_{parameters.file_name}.ttl"
        if len(graph) > 0:
            # Save triples to file
            save_triples(graph, log_dir_path, ttl_file_name, copy=False)
            # Save Excel file
            save_csv(df, log_dir_path, csv_file_name, copy=False)
            # Save graph to triple store
            self.__configuration.triple_store.insert(graph)
        return graph
    

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="linkedin_export_connections_import_csv",
                description="Import LinkedIn Connections data from a CSV file to the triple store",
                func=lambda **kwargs: self.run(LinkedInExportProfilePipelineParameters(**kwargs)),
                args_schema=LinkedInExportProfilePipelineParameters
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
    

if __name__ == "__main__":
    from src import services

    pipeline = LinkedInExportProfilePipeline(
        LinkedInExportProfilePipelineConfiguration(
            triple_store=services.triple_store_service,
            linkedin_export_configuration=LinkedInExportIntegrationConfiguration(
                export_file_path="storage/datastore/linkedin/export/florent-ravenel/Complete_LinkedInDataExport_11-06-2025.zip (1).zip"
            )
        )
    )
    graph = pipeline.run(LinkedInExportProfilePipelineParameters(linkedin_public_url="https://www.linkedin.com/in/florent-ravenel/", file_name="Profile.csv"))
    print(graph.serialize(format="turtle"))