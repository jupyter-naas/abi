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


LINKEDIN = Namespace("http://ontology.naas.ai/abi/linkedin/")


@dataclass
class LinkedInExportConnectionsPipelineConfiguration(PipelineConfiguration):
    """Configuration for LinkedInExportConnectionsPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service
        linkedin_export_configuration (LinkedInExportIntegrationConfiguration): The LinkedIn export integration configuration
        limit (int | None): The limit of rows to process
    """
    triple_store: ITripleStoreService
    linkedin_export_configuration: LinkedInExportIntegrationConfiguration
    limit: int | None = None


class LinkedInExportConnectionsPipelineParameters(PipelineParameters):
    """Parameters for LinkedInExportConnectionsPipeline.
    
    Attributes:
        file_name (str): Name of the CSV file to process
    """
    file_name: Annotated[str, Field(
        description="Name of the CSV file to process from the LinkedIn export",
    )] = "Connections.csv"


class LinkedInExportConnectionsPipeline(Pipeline):
    """Pipeline for importing data from Excel tables to the triple store."""
    
    __configuration: LinkedInExportConnectionsPipelineConfiguration

    def __init__(self, configuration: LinkedInExportConnectionsPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__linkedin_export_integration = LinkedInExportIntegration(configuration.linkedin_export_configuration)

    def generate_graph_date(self, date: datetime | str, date_format: str = "%Y-%m-%dT%H:%M:%S.%fZ") -> tuple[URIRef, Graph]:
        """Generates a URI for a date based on the given datetime object."""
        if isinstance(date, datetime):
            date_str = date.strftime(date_format)
            date_epoch = int(date.timestamp() * 1000)
            date_uri = ABI[str(date_epoch)]  # Create URI using timestamp
        elif isinstance(date, str):
            date_uri = ABI[date]
        graph = Graph()
        graph.add((date_uri, RDF.type, OWL.NamedIndividual))
        graph.add((date_uri, RDF.type, ABI.ISO8601UTCDateTime))
        graph.add((date_uri, RDFS.label, Literal(date_str, datatype=XSD.dateTime)))
        return date_uri, graph

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, LinkedInExportConnectionsPipelineParameters):
            raise ValueError("Parameters must be of type LinkedInExportConnectionsPipelineParameters")

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

        # Define Class URIs
        DATA_SOURCE = ABI["DataSource"]
        DATA_SOURCE_COMPONENT = ABI["DataSourceComponent"]
        PERSON = CCO["ont00001262"]
        LINKEDIN_PROFILE_PAGE = LINKEDIN["ProfilePage"]
        POSITION = BFO["BFO_0000023"]
        ORGANIZATION = CCO["ont00001180"]
        ACT_OF_ASSOCIATION = CCO["ont00000433"]
        ACT_OF_CONNECTION = LINKEDIN["ActOfConnection"]
        EMAIL_ADDRESS = ABI["EmailAddress"]

        # Get file metadata
        export_directory = self.__linkedin_export_integration.unzip_export()["extracted_directory"]
        file_path = os.path.join(export_directory, parameters.file_name)
        file_timestamp = os.path.getmtime(file_path)
        file_datetime = datetime.fromtimestamp(file_timestamp)
        logger.debug(f"File modified at: {file_datetime}")

        # Create backing datasource
        data_source_hash = create_hash_from_string(f"{file_timestamp}_{file_path}")
        existing_data_sources: dict[str, URIRef] = get_identifiers(class_uri=DATA_SOURCE)
        logger.debug(f"Existing data sources: {len(existing_data_sources)}")
        data_source_uri = existing_data_sources.get(data_source_hash)
        if data_source_uri is None:
            data_source_uri = ABI[str(uuid.uuid4())]
            graph.add((data_source_uri, RDF.type, OWL.NamedIndividual))
            graph.add((data_source_uri, RDF.type, DATA_SOURCE))
            graph.add((data_source_uri, ABI.filename, Literal(parameters.file_name)))
            graph.add((data_source_uri, ABI.unique_id, Literal(data_source_hash)))
            graph.add((data_source_uri, ABI.extracted_at, Literal(file_datetime.strftime("%Y-%m-%dT%H:%M:%S"), datatype=XSD.dateTime)))
            graph.add((data_source_uri, ABI.source_path, Literal(file_path)))
            graph.add((data_source_uri, ABI.source_type, Literal("CSV_FILE")))
        
        # Step 3: Processing rows from CSV file
        logger.debug("Step 3: Processing rows")
        count_row: int = 0
        if self.__configuration.limit is not None:
            df = df[:self.__configuration.limit]

        for i, row in df.iterrows():
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
            else:
                logger.warning("Row already processed!")
                continue

            # Add LinkedIn profile page
            linkedin_public_url = row.get("URL", "").strip()
            linkedin_public_id = linkedin_public_url.split("/in/")[1].split("?")[0]
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
            else:
                logger.warning("LinkedIn profile page already processed!")
                continue

            # Add person to the graph
            first_name = row.get("First Name", "").strip()
            last_name = row.get("Last Name", "").strip()
            person_name = f"{first_name} {last_name}"
            logger.debug(f"Step 3.3: Adding person '{person_name}'")
            person_uri = ABI[str(uuid.uuid4())]
            graph.add((person_uri, RDF.type, OWL.NamedIndividual))
            graph.add((person_uri, RDF.type, PERSON))
            graph.add((person_uri, RDFS.label, Literal(person_name)))
            graph.add((person_uri, ABI.first_name, Literal(first_name)))
            graph.add((person_uri, ABI.last_name, Literal(last_name)))
            graph.add((person_uri, ABI.hasBackingDataSource, row_uri))
            graph.add((linkedin_profile_page_uri, ABI.isLinkedInPageOf, person_uri))
            graph.add((person_uri, ABI.hasLinkedInPage, linkedin_profile_page_uri))

            # Add email address to the graph
            email_address = row.get("Email Address", "").strip()
            logger.debug(f"Step 3.4: Adding email address: '{email_address}'")
            if email_address != "":
                email_address_hash = create_hash_from_string(email_address)
                existing_email_addresses: dict[str, URIRef] = get_identifiers(class_uri=EMAIL_ADDRESS)
                logger.debug(f"- Existing Email Addresses: {len(existing_email_addresses)}")
                email_address_uri = existing_email_addresses.get(email_address_hash)
                if email_address_uri is None and email_address != "":
                    email_address_uri = ABI[str(uuid.uuid4())]
                    existing_email_addresses[email_address_hash] = email_address_uri
                    graph.add((email_address_uri, RDF.type, OWL.NamedIndividual))
                    graph.add((email_address_uri, RDF.type, EMAIL_ADDRESS))
                    graph.add((email_address_uri, RDFS.label, Literal(email_address)))
                    graph.add((email_address_uri, ABI.unique_id, Literal(email_address_hash)))
                    graph.add((email_address_uri, ABI.hasBackingDataSource, row_uri))
                graph.add((person_uri, ABI.hasEmailAddress, email_address_uri))
                graph.add((email_address_uri, ABI.isEmailAddressOf, person_uri))
            else:
                logger.debug("Email address is empty!")

            # Add position
            position = row.get("Job Title", "").strip()
            logger.debug(f"Step 3.5: Adding position: '{position}'")
            position_hash = create_hash_from_string(position)
            position_uris: dict[str, URIRef] = get_identifiers(class_uri=POSITION)
            logger.debug(f"- Existing Positions: {len(position_uris)}")
            position_uri = position_uris.get(position_hash) if position != "" else None
            
            # Create position if it doesn't exist
            if position_uri is None:
                position_uri = ABI[str(uuid.uuid4())]
                position_uris[position_hash] = position_uri
                graph.add((position_uri, RDF.type, OWL.NamedIndividual))
                graph.add((position_uri, RDF.type, POSITION))
                graph.add((position_uri, RDFS.label, Literal(position)))
                graph.add((position_uri, ABI.unique_id, Literal(position_hash)))
                graph.add((position_uri, ABI.hasBackingDataSource, row_uri))
            graph.add((person_uri, ABI.holdsPosition, position_uri))

            # Add organization & linkedin company page
            organization = row.get("Company", "").strip()
            logger.debug(f"Step 3.6: Adding organization: '{organization}'")
            organization_uris: dict[str, URIRef] = get_identifiers(RDFS.label, class_uri=ORGANIZATION)
            logger.debug(f"- Existing Organizations: {len(organization_uris)}")
            organization_uri = organization_uris.get(organization) if organization != "" else None
            # Create organization if it doesn't exist
            if organization_uri is None and organization != "":
                organization_uri = ABI[str(uuid.uuid4())]
                organization_uris[organization] = organization_uri
                graph.add((organization_uri, RDF.type, OWL.NamedIndividual))
                graph.add((organization_uri, RDF.type, ORGANIZATION))
                graph.add((organization_uri, RDFS.label, Literal(organization)))
                graph.add((organization_uri, ABI.hasBackingDataSource, row_uri))

            # Create act of association with person, organization and position
            act_of_association_label = f"{person_name} working at {organization} as {position}"
            act_of_association_hash = create_hash_from_string(act_of_association_label)
            logger.debug(f"Step 3.7: Adding act of association with organization and role: '{act_of_association_label}'")
            act_of_association_uri = ABI[str(uuid.uuid4())]
            graph.add((act_of_association_uri, RDF.type, OWL.NamedIndividual))
            graph.add((act_of_association_uri, RDF.type, OWL.NamedIndividual))
            graph.add((act_of_association_uri, RDF.type, ACT_OF_ASSOCIATION))
            graph.add((act_of_association_uri, RDFS.label, Literal(act_of_association_label)))
            graph.add((act_of_association_uri, ABI.unique_id, Literal(act_of_association_hash)))
            graph.add((act_of_association_uri, ABI.hasBackingDataSource, row_uri))
            
            if organization_uri is not None:
                graph.add((act_of_association_uri, BFO.BFO_0000057, organization_uri))
            if person_uri is not None:
                graph.add((act_of_association_uri, BFO.BFO_0000057, person_uri))
            if position_uri is not None:
                graph.add((act_of_association_uri, BFO.BFO_0000055, position_uri))
            date_uri, graph_date = self.generate_graph_date("UNKNOWN")
            graph.add((act_of_association_uri, ABI.startDate, date_uri)) # has start date UNKNOWN
            
            # # Create act of connection with person and organization
            # connected_on_str = row.get("Connected On", "").strip()
            # try:
            #     connected_on_date = datetime.strptime(connected_on_str, "%d %b %Y")
            # except Exception as e:
            #     logger.warning(f"Could not parse 'Connected On' date '{connected_on_str}': {e}")
            #     continue

            # act_of_connection_label = f"{person_name} connected with {person_name} on LinkedIn at {connected_on_date.strftime('%d %b %Y')}"
            # act_of_connection_hash = create_hash_from_string(act_of_connection_label)
            # logger.debug(f"Step 3.8: Adding act of connection LinkedIn: '{act_of_connection_label}'")
            # act_of_connection_uris: dict[str, URIRef] = get_identifiers(class_uri=ACT_OF_CONNECTION)
            # logger.debug(f"- Existing Act of LinkedIn Connection: {len(act_of_connection_uris)}")
            # act_of_connection_uri = act_of_connection_uris.get(act_of_connection_hash)
            # if act_of_connection_uri is None:
            #     logger.debug("Step 3.8: Adding act of connection with person and organization")
            #     act_of_connection_uri = ABI[str(uuid.uuid4())]
            #     act_of_connection_uris[act_of_connection_hash] = act_of_connection_uri
            #     graph.add((act_of_connection_uri, RDF.type, OWL.NamedIndividual))
            #     graph.add((act_of_connection_uri, RDF.type, OWL.NamedIndividual))
            #     graph.add((act_of_connection_uri, RDF.type, ACT_OF_CONNECTION))
            #     graph.add((act_of_connection_uri, RDFS.label, Literal(act_of_connection_label)))
            #     graph.add((act_of_connection_uri, ABI.unique_id, Literal(act_of_connection_hash)))
            #     graph.add((act_of_connection_uri, ABI.hasBackingDataSource, row_uri))
            #     date_uri, graph_date = self.generate_graph_date(connected_on_date)
            #     graph.add((act_of_connection_uri, ABI.connectedOn, date_uri))
            #     graph += graph_date

        # Add triples to triple store
        logger.debug("Step 4: Adding triples to triple store")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        log_dir_path = os.path.join(export_directory, timestamp, parameters.file_name)
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
                func=lambda **kwargs: self.run(LinkedInExportConnectionsPipelineParameters(**kwargs)),
                args_schema=LinkedInExportConnectionsPipelineParameters
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