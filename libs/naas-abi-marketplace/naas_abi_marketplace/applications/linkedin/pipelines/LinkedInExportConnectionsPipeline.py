import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Annotated

import pandas as pd
from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.pipeline import (Pipeline, PipelineConfiguration,
                                    PipelineParameters)
from naas_abi_core.services.triple_store.TripleStorePorts import \
    ITripleStoreService
from naas_abi_core.utils.Graph import ABI, BFO, CCO
from naas_abi_marketplace.applications.linkedin import ABIModule
from naas_abi_marketplace.applications.linkedin.integrations.LinkedInExportIntegration import (
    LinkedInExportIntegration, LinkedInExportIntegrationConfiguration)
# from src.utils.Storage import save_triples, save_csv
# from src.utils.SPARQL import get_identifiers, results_to_list
from naas_abi_marketplace.applications.linkedin.pipelines.BasePipeline import \
    BasePipeline
from naas_abi_marketplace.applications.linkedin.pipelines.LinkedInExportProfilePipeline import (
    LinkedInExportProfilePipeline, LinkedInExportProfilePipelineConfiguration,
    LinkedInExportProfilePipelineParameters)
from pydantic import Field
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

LINKEDIN = Namespace("http://ontology.naas.ai/abi/linkedin/")
DATA_SOURCE = ABI["DataSource"]
DATA_SOURCE_COMPONENT = ABI["DataSourceComponent"]
PERSON = CCO["ont00001262"]
LINKEDIN_PROFILE_PAGE = LINKEDIN["ProfilePage"]
POSITION = BFO["BFO_0000023"]
ORGANIZATION = CCO["ont00001180"]
ACT_OF_ASSOCIATION = CCO["ont00000433"]
ACT_OF_CONNECTION = LINKEDIN["ActOfConnection"]
EMAIL_ADDRESS = ABI["EmailAddress"]


@dataclass
class LinkedInExportConnectionsPipelineConfiguration(PipelineConfiguration):
    """Configuration for LinkedInExportConnectionsPipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service
        linkedin_export_configuration (LinkedInExportIntegrationConfiguration): The LinkedIn export integration configuration
        limit (int | None): The limit of rows to process
        num_workers (int): Number of worker threads for parallel processing. Defaults to 4.
    """

    triple_store: ITripleStoreService
    linkedin_export_configuration: LinkedInExportIntegrationConfiguration
    linkedin_export_profile_pipeline_configuration: (
        LinkedInExportProfilePipelineConfiguration
    )
    limit: int | None = None
    num_workers: int = 20


class LinkedInExportConnectionsPipelineParameters(PipelineParameters):
    """Parameters for LinkedInExportConnectionsPipeline.

    Attributes:
        file_name (str): Name of the CSV file to process
    """

    linkedin_public_url: Annotated[
        str,
        Field(
            description="LinkedIn public URL of the profile to process",
        ),
    ]
    file_name: Annotated[
        str,
        Field(
            description="Name of the CSV file to process from the LinkedIn export",
        ),
    ] = "Connections.csv"


class LinkedInExportConnectionsPipeline(Pipeline, BasePipeline):
    """Pipeline for importing data from Excel tables to the triple store."""

    __configuration: LinkedInExportConnectionsPipelineConfiguration

    def __init__(self, configuration: LinkedInExportConnectionsPipelineConfiguration):
        super().__init__(configuration)
        BasePipeline.__init__(self)
        self.__configuration = configuration
        self.__linkedin_export_integration = LinkedInExportIntegration(
            configuration.linkedin_export_configuration
        )
        self.__linkedin_export_profile_pipeline = LinkedInExportProfilePipeline(
            configuration.linkedin_export_profile_pipeline_configuration
        )

    def get_person_uri_and_name_from_linkedin_profile_page_public_url(
        self, linkedin_profile_page_public_url: str
    ) -> tuple[URIRef, str] | tuple[None, None]:
        """
        Get person URI and name using the public_url property from LinkedInProfilePage.
        """
        sparql_query = f"""
        PREFIX linkedin: <http://ontology.naas.ai/abi/linkedin/>
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?personUri ?personName
        WHERE {{
            ?profilePage a linkedin:ProfilePage ;
                         linkedin:public_url "{linkedin_profile_page_public_url}" ;
                         abi:isLinkedInPageOf ?personUri .
            ?personUri rdfs:label ?personName .
        }}
        """
        results = self.sparql_utils.results_to_list(
            self.__configuration.triple_store.query(sparql_query)
        )
        if results:
            return URIRef(results[0]["personUri"]), results[0]["personName"]
        return None, None

    def generate_graph_date(
        self, date: datetime | str, date_format: str = "%Y-%m-%dT%H:%M:%S.%fZ"
    ) -> tuple[URIRef, Graph]:
        """Generates a URI for a date based on the given datetime object."""
        if isinstance(date, datetime):
            date_str = date.strftime(date_format)
            date_epoch = int(date.timestamp() * 1000)
            date_uri = ABI[str(date_epoch)]  # Create URI using timestamp
            date_literal = Literal(date_str, datatype=XSD.dateTime)
        elif isinstance(date, str):
            date_str = date
            date_uri = ABI[date_str]
            date_literal = Literal(date_str)
        graph = Graph()
        graph.add((date_uri, RDF.type, OWL.NamedIndividual))
        graph.add((date_uri, RDF.type, ABI.ISO8601UTCDateTime))
        graph.add((date_uri, RDFS.label, date_literal))
        return date_uri, graph

    def _process_row(
        self,
        row: dict,
        row_index: int,
        total_rows: int,
        data_source_uri: URIRef,
        initial_person_uri: URIRef,
        initial_person_name: str,
        shared_caches: dict,
        locks: dict,
    ) -> Graph:
        """
        Process a single row from the CSV file and return a graph with all triples for that row.

        Args:
            row: The row data as a dictionary
            row_index: The index of the row (0-based)
            total_rows: Total number of rows being processed
            data_source_uri: URI of the backing data source
            initial_person_uri: URI of the person whose connections are being imported
            initial_person_name: Name of the person whose connections are being imported

        Returns:
            Graph: RDF graph containing all triples for this row
        """
        graph = Graph()
        graph.bind("cco", CCO)
        graph.bind("bfo", BFO)
        graph.bind("abi", ABI)
        graph.bind("rdfs", RDFS)
        graph.bind("rdf", RDF)
        graph.bind("owl", OWL)
        graph.bind("xsd", XSD)
        graph.bind("linkedin", LINKEDIN)

        logger.debug(f"🔄 Processing row {row_index + 1}/{total_rows}")

        # Convert dict back to pandas Series for add_backing_datasource_component
        row_series = pd.Series(row)

        # Add backing datasource component
        graph, row_uri = (
            self.__linkedin_export_profile_pipeline.add_backing_datasource_component(
                graph=graph, data_source_uri=data_source_uri, row=row_series
            )
        )

        # Add LinkedIn profile page
        linkedin_public_url = row.get("URL", "").strip()
        logger.debug(f"Step 3.1: Adding LinkedIn profile page: '{linkedin_public_url}'")
        graph, linkedin_profile_page_uri = (
            self.__linkedin_export_profile_pipeline.add_linkedin_profile_page(
                graph=graph,
                linkedin_public_url=linkedin_public_url,
                backing_datasource_component_uri=row_uri,
            )
        )
        logger.debug(f"Linkedin profile page URI: '{linkedin_profile_page_uri}'")

        # Add person to the graph
        logger.debug("Step 3.2: Adding person to the graph")
        person_name = f"{row.get('First Name', 'UNKNOWN').strip()} {row.get('Last Name', 'UNKNOWN').strip()}"
        graph, person_uri = self.__linkedin_export_profile_pipeline.add_person(
            graph=graph,
            linkedin_profile_page_uri=linkedin_profile_page_uri,
            backing_datasource_component_uri=row_uri,
            first_name=row.get("First Name", "UNKNOWN").strip(),
            last_name=row.get("Last Name", "UNKNOWN").strip(),
        )
        logger.debug(f"Person URI: '{person_uri}'")

        # Add email address to the graph (thread-safe with double-check)
        email_address = row.get("Email Address", "UNKNOWN").strip()
        logger.debug(f"Step 3.3: Adding email address: '{email_address}'")
        email_address_hash = create_hash_from_string(email_address)
        # First check without lock (fast path)
        email_address_uri = shared_caches["email_addresses"].get(email_address_hash)
        if email_address_uri is None:
            # Acquire lock and check again (double-check pattern)
            with locks["email_addresses"]:
                email_address_uri = shared_caches["email_addresses"].get(
                    email_address_hash
                )
                if email_address_uri is None:
                    email_address_uri = ABI[str(uuid.uuid4())]
                    shared_caches["email_addresses"][email_address_hash] = (
                        email_address_uri
                    )
                    graph.add((email_address_uri, RDF.type, OWL.NamedIndividual))
                    graph.add((email_address_uri, RDF.type, EMAIL_ADDRESS))
                    graph.add((email_address_uri, RDFS.label, Literal(email_address)))
                    graph.add(
                        (email_address_uri, ABI.unique_id, Literal(email_address_hash))
                    )
                    graph.add((email_address_uri, ABI.hasBackingDataSource, row_uri))
                    graph.add((person_uri, ABI.hasEmailAddress, email_address_uri))
                    graph.add((email_address_uri, ABI.isEmailAddressOf, person_uri))

        # Add position (thread-safe with double-check)
        position = row.get("Position", "UNKNOWN").strip()
        logger.debug(f"Step 3.4: Adding position: '{position}'")
        position_hash = create_hash_from_string(position)
        position_uri = None
        if position_hash != "":
            # First check without lock (fast path)
            position_uri = shared_caches["positions"].get(position_hash)
            if position_uri is None:
                # Acquire lock and check again (double-check pattern)
                with locks["positions"]:
                    position_uri = shared_caches["positions"].get(position_hash)
                    if position_uri is None:
                        position_uri = ABI[str(uuid.uuid4())]
                        shared_caches["positions"][position_hash] = position_uri
                        graph.add((position_uri, RDF.type, OWL.NamedIndividual))
                        graph.add((position_uri, RDF.type, POSITION))
                        graph.add((position_uri, RDFS.label, Literal(position)))
                        graph.add((position_uri, ABI.unique_id, Literal(position_hash)))
                        graph.add((position_uri, ABI.hasBackingDataSource, row_uri))
        if position_uri is not None:
            graph.add((person_uri, ABI.holdsPosition, position_uri))

        # Add organization & linkedin company page (thread-safe with double-check)
        organization = row.get("Company", "UNKNOWN").strip()
        logger.debug(f"Step 3.5: Adding organization: '{organization}'")
        organization_uri = None
        if organization != "":
            # First check without lock (fast path)
            organization_uri = shared_caches["organizations"].get(organization)
            if organization_uri is None:
                # Acquire lock and check again (double-check pattern)
                with locks["organizations"]:
                    organization_uri = shared_caches["organizations"].get(organization)
                    if organization_uri is None:
                        organization_uri = ABI[str(uuid.uuid4())]
                        shared_caches["organizations"][organization] = organization_uri
                        graph.add((organization_uri, RDF.type, OWL.NamedIndividual))
                        graph.add((organization_uri, RDF.type, ORGANIZATION))
                        graph.add((organization_uri, RDFS.label, Literal(organization)))
                        graph.add((organization_uri, ABI.hasBackingDataSource, row_uri))

        # Create act of association with person, organization and position (thread-safe with double-check)
        act_of_association_label = (
            f"{person_name} working at {organization} as {position}"
        )
        act_of_association_hash = create_hash_from_string(act_of_association_label)
        logger.debug(
            f"Step 3.6: Adding act of association with organization and role: '{act_of_association_label}'"
        )
        act_of_association_uri = None
        if act_of_association_hash != "":
            # First check without lock (fast path)
            act_of_association_uri = shared_caches["act_of_associations"].get(
                act_of_association_hash
            )
            if act_of_association_uri is None:
                # Acquire lock and check again (double-check pattern)
                with locks["act_of_associations"]:
                    act_of_association_uri = shared_caches["act_of_associations"].get(
                        act_of_association_hash
                    )
                    if act_of_association_uri is None:
                        act_of_association_uri = ABI[str(uuid.uuid4())]
                        shared_caches["act_of_associations"][
                            act_of_association_hash
                        ] = act_of_association_uri
                        graph.add(
                            (act_of_association_uri, RDF.type, OWL.NamedIndividual)
                        )
                        graph.add(
                            (act_of_association_uri, RDF.type, OWL.NamedIndividual)
                        )
                        graph.add(
                            (act_of_association_uri, RDF.type, ACT_OF_ASSOCIATION)
                        )
                        graph.add(
                            (
                                act_of_association_uri,
                                RDFS.label,
                                Literal(act_of_association_label),
                            )
                        )
                        graph.add(
                            (
                                act_of_association_uri,
                                ABI.unique_id,
                                Literal(act_of_association_hash),
                            )
                        )
                        graph.add(
                            (act_of_association_uri, ABI.hasBackingDataSource, row_uri)
                        )

                        if organization_uri is not None:
                            graph.add(
                                (
                                    act_of_association_uri,
                                    BFO.BFO_0000057,
                                    organization_uri,
                                )
                            )
                        if person_uri is not None:
                            graph.add(
                                (act_of_association_uri, BFO.BFO_0000057, person_uri)
                            )
                        if position_uri is not None:
                            graph.add(
                                (act_of_association_uri, BFO.BFO_0000055, position_uri)
                            )
                        date_uri, graph_date = self.generate_graph_date("UNKNOWN")
                        graph.add(
                            (act_of_association_uri, ABI.startDate, date_uri)
                        )  # has start date UNKNOWN

        # Create act of connection with person and organization
        connected_on_str = row.get("Connected On", "").strip()
        try:
            connected_on_date = datetime.strptime(connected_on_str, "%d %b %Y")
        except Exception as e:
            logger.warning(
                f"Could not parse 'Connected On' date '{connected_on_str}': {e}"
            )
            return graph  # Return graph without act of connection if date parsing fails

        act_of_connection_label = f"{initial_person_name} connected with {person_name} on LinkedIn the {connected_on_date.strftime('%d %b %Y')}"
        act_of_connection_hash = create_hash_from_string(act_of_connection_label)
        logger.debug(
            f"Step 3.7: Adding act of connection LinkedIn: '{act_of_connection_label}'"
        )
        act_of_connection_uri = None
        if act_of_connection_hash != "":
            # First check without lock (fast path)
            act_of_connection_uri = shared_caches["act_of_connections"].get(
                act_of_connection_hash
            )
            if act_of_connection_uri is None:
                # Acquire lock and check again (double-check pattern)
                with locks["act_of_connections"]:
                    act_of_connection_uri = shared_caches["act_of_connections"].get(
                        act_of_connection_hash
                    )
                    if act_of_connection_uri is None:
                        act_of_connection_uri = ABI[str(uuid.uuid4())]
                        shared_caches["act_of_connections"][act_of_connection_hash] = (
                            act_of_connection_uri
                        )
                        graph.add(
                            (act_of_connection_uri, RDF.type, OWL.NamedIndividual)
                        )
                        graph.add((act_of_connection_uri, RDF.type, ACT_OF_CONNECTION))
                        graph.add(
                            (
                                act_of_connection_uri,
                                RDFS.label,
                                Literal(act_of_connection_label),
                            )
                        )
                        graph.add(
                            (
                                act_of_connection_uri,
                                ABI.unique_id,
                                Literal(act_of_connection_hash),
                            )
                        )
                        graph.add(
                            (act_of_connection_uri, ABI.hasBackingDataSource, row_uri)
                        )
                        graph.add((act_of_connection_uri, BFO.BFO_0000057, person_uri))
                        graph.add(
                            (act_of_connection_uri, BFO.BFO_0000057, initial_person_uri)
                        )
                        date_uri, graph_date = self.generate_graph_date(
                            connected_on_date
                        )
                        graph.add((act_of_connection_uri, ABI.connectedOn, date_uri))
                        graph += graph_date

        return graph

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, LinkedInExportConnectionsPipelineParameters):
            raise ValueError(
                "Parameters must be of type LinkedInExportConnectionsPipelineParameters"
            )

        # Step 0: Run LinkedInExportProfilePipeline to get person URI and name
        logger.debug(
            "Step 0: Running LinkedInExportProfilePipeline to get person URI and name"
        )
        graph = self.__linkedin_export_profile_pipeline.run(
            LinkedInExportProfilePipelineParameters(
                linkedin_public_url=parameters.linkedin_public_url
            )
        )
        initial_person_uri, initial_person_name = (
            self.get_person_uri_and_name_from_linkedin_profile_page_public_url(
                parameters.linkedin_public_url
            )
        )
        if initial_person_uri is None or initial_person_name is None:
            raise ValueError(
                f"Could not get person URI and name from LinkedIn profile page public URL: '{parameters.linkedin_public_url}'"
            )

        # Step 1: Read CSV file
        logger.debug(f"Step 1: Reading CSV file '{parameters.file_name}'")
        df = self.__linkedin_export_integration.read_csv(parameters.file_name).fillna(
            "UNKNOWN"
        )
        if len(df) == 0:
            logger.warning(
                f"❌ No rows to process in CSV file '{parameters.file_name}'"
            )
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

        # Get file metadata
        export_directory = self.__linkedin_export_integration.unzip_export()[
            "extracted_directory"
        ]
        file_path = os.path.join(export_directory, parameters.file_name)
        file_modified_at = self.__linkedin_export_integration.unzip_export()[
            "file_modified_at"
        ]
        file_created_at = self.__linkedin_export_integration.unzip_export()[
            "file_created_at"
        ]

        # Create backing datasource
        graph, data_source_uri = (
            self.__linkedin_export_profile_pipeline.add_backing_datasource(
                graph=graph,
                file_path=file_path,
                file_modified_at=file_modified_at,
                file_created_at=file_created_at,
                df=df,
            )
        )

        # Step 3: Pre-load all identifiers to prevent race conditions
        logger.debug("Step 3: Pre-loading identifiers from triple store")
        shared_caches = {
            "email_addresses": self.sparql_utils.get_identifiers(
                class_uri=EMAIL_ADDRESS
            ),
            "positions": self.sparql_utils.get_identifiers(class_uri=POSITION),
            "organizations": self.sparql_utils.get_identifiers(
                RDFS.label, class_uri=ORGANIZATION
            ),
            "act_of_associations": self.sparql_utils.get_identifiers(
                class_uri=ACT_OF_ASSOCIATION
            ),
            "act_of_connections": self.sparql_utils.get_identifiers(
                class_uri=ACT_OF_CONNECTION
            ),
        }

        # Create locks for thread-safe access to shared caches
        locks = {
            "email_addresses": Lock(),
            "positions": Lock(),
            "organizations": Lock(),
            "act_of_associations": Lock(),
            "act_of_connections": Lock(),
        }

        # Step 4: Processing rows from CSV file with multi-threading
        logger.debug(
            f"Step 4: Processing rows with {self.__configuration.num_workers} workers"
        )
        if self.__configuration.limit is not None:
            df = df[: self.__configuration.limit]

        # Convert DataFrame rows to list of dictionaries for thread-safe processing
        rows_list = [row.to_dict() for _, row in df.iterrows()]
        total_rows = len(rows_list)

        # Process rows in parallel using ThreadPoolExecutor
        processed_count = 0
        with ThreadPoolExecutor(
            max_workers=self.__configuration.num_workers
        ) as executor:
            # Submit all row processing tasks
            future_to_index = {
                executor.submit(
                    self._process_row,
                    row,
                    idx,
                    total_rows,
                    data_source_uri,
                    initial_person_uri,
                    initial_person_name,
                    shared_caches,
                    locks,
                ): idx
                for idx, row in enumerate(rows_list)
            }

            # Collect results as they complete
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    row_graph = future.result()
                    graph += row_graph
                    processed_count += 1
                    if processed_count % 10 == 0 or processed_count == total_rows:
                        logger.debug(
                            f"✅ Processed {processed_count}/{total_rows} rows"
                        )
                except Exception as e:
                    logger.error(f"❌ Error processing row {idx + 1}: {e}")
                    continue

        logger.debug(f"✅ Completed processing {processed_count}/{total_rows} rows")

        # Add triples to triple store
        logger.debug("Step 5: Adding triples to triple store")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_name = parameters.file_name.split(".")[0]
        log_dir_path = os.path.join(export_directory, timestamp, file_name)
        ttl_file_name = f"insert_{file_name}.ttl"
        if len(graph) > 0:
            # Save triples to file
            self.storage_utils.save_triples(
                graph, log_dir_path, ttl_file_name, copy=False
            )
            # Save Excel file
            self.storage_utils.save_csv(
                df, log_dir_path, parameters.file_name, copy=False
            )
            # Save graph to triple store
            self.__configuration.triple_store.insert(graph)
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="linkedin_export_connections_import_csv",
                description="Import LinkedIn Connections data from a CSV file to the triple store",
                func=lambda **kwargs: self.run(
                    LinkedInExportConnectionsPipelineParameters(**kwargs)
                ),
                args_schema=LinkedInExportConnectionsPipelineParameters,
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
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.linkedin"])

    module: ABIModule = ABIModule.get_instance()

    linkedin_export_configuration = LinkedInExportIntegrationConfiguration(
        export_file_path="storage/datastore/linkedin/export/florent-ravenel/Complete_LinkedInDataExport_11-06-2025.zip (1).zip"
    )
    linkedin_export_profile_pipeline_configuration = (
        LinkedInExportProfilePipelineConfiguration(
            triple_store=module.engine.services.triple_store,
            linkedin_export_configuration=linkedin_export_configuration,
        )
    )
    linkedin_public_url = "https://www.linkedin.com/in/florent-ravenel/"
    limit = None

    pipeline = LinkedInExportConnectionsPipeline(
        LinkedInExportConnectionsPipelineConfiguration(
            triple_store=module.engine.services.triple_store,
            linkedin_export_configuration=linkedin_export_configuration,
            linkedin_export_profile_pipeline_configuration=linkedin_export_profile_pipeline_configuration,
            limit=limit,
        )
    )
    graph = pipeline.run(
        LinkedInExportConnectionsPipelineParameters(
            linkedin_public_url=linkedin_public_url
        )
    )
    print(graph.serialize(format="turtle"))
    )
    print(graph.serialize(format="turtle"))
