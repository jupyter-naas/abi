import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Annotated

import pandas as pd
from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Graph import ABI, BFO, CCO
from naas_abi_core.utils.String import create_hash_from_string
from naas_abi_marketplace.applications.linkedin import ABIModule
from naas_abi_marketplace.applications.linkedin.integrations.LinkedInExportIntegration import (
    LinkedInExportIntegration,
    LinkedInExportIntegrationConfiguration,
)
from naas_abi_marketplace.applications.linkedin.pipelines.BasePipeline import (
    BasePipeline,
)
from pydantic import Field
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

LINKEDIN = Namespace("http://ontology.naas.ai/abi/linkedin/")
DATA_SOURCE = ABI["DataSource"]
DATA_SOURCE_COMPONENT = ABI["DataSourceComponent"]
PERSON = CCO["ont00001262"]
LINKEDIN_PROFILE_PAGE = LINKEDIN["ProfilePage"]


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
    ] = "Profile.csv"


class LinkedInExportProfilePipeline(Pipeline, BasePipeline):
    """Pipeline for importing data from Excel tables to the triple store."""

    __configuration: LinkedInExportProfilePipelineConfiguration

    def __init__(self, configuration: LinkedInExportProfilePipelineConfiguration):
        super().__init__(configuration)
        BasePipeline.__init__(self)
        self.__configuration = configuration
        self.__linkedin_export_integration = LinkedInExportIntegration(
            configuration.linkedin_export_configuration
        )

    def add_backing_datasource(
        self,
        graph: Graph,
        file_path: str,
        file_modified_at: datetime,
        file_created_at: datetime,
        df: pd.DataFrame,
    ) -> tuple[Graph, URIRef]:
        """Add a backing datasource to the graph."""
        # Create backing datasource
        data_source_hash = create_hash_from_string(f"{file_modified_at}_{file_path}")
        existing_data_sources: dict[str, URIRef] = self.sparql_utils.get_identifiers(
            class_uri=DATA_SOURCE
        )
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
            graph.add(
                (data_source_uri, ABI.filename, Literal(os.path.basename(file_path)))
            )
            graph.add((data_source_uri, ABI.unique_id, Literal(data_source_hash)))
            graph.add(
                (
                    data_source_uri,
                    ABI.extracted_at,
                    Literal(
                        file_modified_at.strftime("%Y-%m-%dT%H:%M:%S"),
                        datatype=XSD.dateTime,
                    ),
                )
            )
            graph.add(
                (
                    data_source_uri,
                    ABI.created_at,
                    Literal(
                        file_created_at.strftime("%Y-%m-%dT%H:%M:%S"),
                        datatype=XSD.dateTime,
                    ),
                )
            )
            graph.add((data_source_uri, ABI.source_path, Literal(file_path)))
            graph.add((data_source_uri, ABI.source_type, Literal("CSV_FILE")))
            graph.add((data_source_uri, ABI.columns_list, Literal(col_list_str)))
            graph.add((data_source_uri, ABI.columns_count, Literal(columns_count)))
            graph.add((data_source_uri, ABI.rows_count, Literal(rows_count)))

        return graph, URIRef(data_source_uri)

    def add_backing_datasource_component(
        self, graph: Graph, data_source_uri: URIRef, row: pd.Series
    ) -> tuple[Graph, URIRef]:
        """Add a backing datasource component to the graph."""
        row_hash = create_hash_from_string(str(tuple(row)))
        existing_data_source_components: dict[str, URIRef] = (
            self.sparql_utils.get_identifiers(class_uri=DATA_SOURCE_COMPONENT)
        )
        row_uri = existing_data_source_components.get(row_hash)
        logger.debug("Adding backing datasource component for row")
        if row_uri is None:
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

        return graph, URIRef(row_uri)

    def add_linkedin_profile_page(
        self,
        graph: Graph,
        linkedin_public_url: str,
        backing_datasource_component_uri: URIRef,
    ) -> tuple[Graph, URIRef]:
        """Add a LinkedIn profile page to the graph."""
        linkedin_public_id = (
            linkedin_public_url.split("/in/")[1].split("/")[0].split("?")[0]
        )
        linkedin_profile_page_uris: dict[str, URIRef] = (
            self.sparql_utils.get_identifiers(
                property_uri=LINKEDIN.public_url, class_uri=LINKEDIN_PROFILE_PAGE
            )
        )
        linkedin_profile_page_uri = linkedin_profile_page_uris.get(linkedin_public_url)

        # Create linkedin profile page if it doesn't exist
        if linkedin_profile_page_uri is None:
            linkedin_profile_page_uri = ABI[str(uuid.uuid4())]
            linkedin_profile_page_uris[linkedin_public_url] = linkedin_profile_page_uri
            graph.add((linkedin_profile_page_uri, RDF.type, OWL.NamedIndividual))
            graph.add((linkedin_profile_page_uri, RDF.type, LINKEDIN_PROFILE_PAGE))
            graph.add(
                (linkedin_profile_page_uri, RDFS.label, Literal(linkedin_public_url))
            )
            graph.add(
                (
                    linkedin_profile_page_uri,
                    LINKEDIN.public_url,
                    Literal(linkedin_public_url),
                )
            )
            graph.add(
                (
                    linkedin_profile_page_uri,
                    LINKEDIN.public_id,
                    Literal(linkedin_public_id),
                )
            )
            graph.add(
                (
                    linkedin_profile_page_uri,
                    ABI.hasBackingDataSource,
                    backing_datasource_component_uri,
                )
            )

        return graph, URIRef(linkedin_profile_page_uri)

    def add_person(
        self,
        graph: Graph,
        linkedin_profile_page_uri: URIRef,
        backing_datasource_component_uri: URIRef,
        first_name: str,
        last_name: str,
        maiden_name: str | None = None,
        birth_date: str | None = None,
    ) -> tuple[Graph, URIRef]:
        """Add a person to the graph."""
        person_uri = self.get_person_uri_from_linkedin_profile_page_uri(
            linkedin_profile_page_uri
        )
        if person_uri is None:
            # If no such person, create the new person as before
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

            person_name = f"{first_name} {last_name}"
            logger.debug(f"Step 3.3: Adding person '{person_name}'")
            person_uri = ABI[str(uuid.uuid4())]
            graph.add((person_uri, RDF.type, OWL.NamedIndividual))
            graph.add((person_uri, RDF.type, PERSON))
            graph.add((person_uri, RDFS.label, Literal(person_name)))
            graph.add((person_uri, ABI.first_name, Literal(first_name)))
            graph.add((person_uri, ABI.last_name, Literal(last_name)))
            if maiden_name:
                graph.add((person_uri, ABI.maiden_name, Literal(maiden_name)))
            if birth_date:
                birth_date = parse_birth_date(birth_date)
                graph.add(
                    (person_uri, ABI.birth_date, Literal(birth_date, datatype=XSD.date))
                )
            graph.add(
                (person_uri, ABI.hasBackingDataSource, backing_datasource_component_uri)
            )
            graph.add((linkedin_profile_page_uri, ABI.isLinkedInPageOf, person_uri))
            graph.add((person_uri, ABI.hasLinkedInPage, linkedin_profile_page_uri))

        return graph, URIRef(person_uri)

    def get_person_uri_from_linkedin_profile_page_uri(
        self, linkedin_profile_page_uri: URIRef
    ) -> URIRef | None:
        """Get a person from a LinkedIn profile page."""
        sparql_query = f"""
        PREFIX abi: <http://ontology.naas.ai/abi/>
        SELECT ?personUri 
        WHERE {{
            <{linkedin_profile_page_uri}> abi:isLinkedInPageOf ?personUri .
        }}
        """
        existing_person_uris = self.sparql_utils.results_to_list(
            self.__configuration.triple_store.query(sparql_query)
        )
        if existing_person_uris:
            return URIRef(existing_person_uris[0]["personUri"])
        return None

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, LinkedInExportProfilePipelineParameters):
            raise ValueError(
                "Parameters must be of type LinkedInExportProfilePipelineParameters"
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
        graph, data_source_uri = self.add_backing_datasource(
            graph=graph,
            file_path=file_path,
            file_modified_at=file_modified_at,
            file_created_at=file_created_at,
            df=df,
        )

        # Step 3: Processing rows from CSV file
        logger.debug("Step 3: Processing rows")
        count_row: int = 0
        for _, row in df.iterrows():
            count_row += 1
            logger.debug(f"🔄 Processing row {count_row}/{len(df)}")
            graph, row_uri = self.add_backing_datasource_component(
                graph, data_source_uri, row
            )

            # Add LinkedIn profile page
            linkedin_public_url = parameters.linkedin_public_url
            logger.debug(
                f"Step 3.1: Adding LinkedIn profile page: '{linkedin_public_url}'"
            )
            graph, linkedin_profile_page_uri = self.add_linkedin_profile_page(
                graph=graph,
                linkedin_public_url=linkedin_public_url,
                backing_datasource_component_uri=row_uri,
            )

            logger.debug("Step 3.2: Adding person to the graph")
            graph, person_uri = self.add_person(
                graph=graph,
                linkedin_profile_page_uri=linkedin_profile_page_uri,
                backing_datasource_component_uri=row_uri,
                first_name=row.get("First Name", "UNKNOWN").strip(),
                last_name=row.get("Last Name", "UNKNOWN").strip(),
                maiden_name=row.get("Maiden Name", "UNKNOWN").strip(),
                birth_date=row.get("Birth Date", "UNKNOWN").strip(),
            )

        # Add triples to triple store
        logger.debug("Step 4: Adding triples to triple store")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        log_dir_path = os.path.join(export_directory, timestamp, parameters.file_name)
        ttl_file_name = f"insert_{parameters.file_name.split('.')[0]}.ttl"
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
                    LinkedInExportProfilePipelineParameters(**kwargs)
                ),
                args_schema=LinkedInExportProfilePipelineParameters,
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

    pipeline = LinkedInExportProfilePipeline(
        LinkedInExportProfilePipelineConfiguration(
            triple_store=module.engine.services.triple_store,
            linkedin_export_configuration=LinkedInExportIntegrationConfiguration(
                export_file_path="storage/datastore/linkedin/export/florent-ravenel/Complete_LinkedInDataExport_11-06-2025.zip (1).zip"
            ),
        )
    )
    profile_url = "https://www.linkedin.com/in/florent-ravenel/"
    graph = pipeline.run(
        LinkedInExportProfilePipelineParameters(linkedin_public_url=profile_url)
    )
    print(graph.serialize(format="turtle"))
