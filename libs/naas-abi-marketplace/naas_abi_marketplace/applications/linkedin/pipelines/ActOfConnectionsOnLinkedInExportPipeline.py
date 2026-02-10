import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.Graph import ABI
from naas_abi_core.utils.SPARQL import SPARQLUtils
from naas_abi_marketplace.applications.linkedin import ABIModule
from naas_abi_marketplace.applications.linkedin.integrations.LinkedInExportIntegration import (
    LinkedInExportIntegration,
    LinkedInExportIntegrationConfiguration,
)
from naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn import (
    ActOfConnection,
    ConnectionRole,
    ConnectionsExportFile,
    CurrentJobPosition,
    CurrentOrganization,
    CurrentPublicURL,
    EmailAddress,
    ISO8601UTCDateTime,
    Location,
    Organization,
    Person,
    ProfilePage,
)
from naas_abi_marketplace.applications.linkedin.pipelines.LinkedInExportProfilePipeline import (
    LinkedInExportProfilePipelineConfiguration,
)
from pydantic import Field
from rdflib import Graph, Namespace, URIRef

LINKEDIN = Namespace("http://ontology.naas.ai/abi/linkedin/")
UNKNOWN_VALUE = "UNKNOWN"


@dataclass
class ActOfConnectionsOnLinkedInExportPipelineConfiguration(PipelineConfiguration):
    """Configuration for ActOfConnectionsOnLinkedInExportPipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service
        linkedin_export_configuration (LinkedInExportIntegrationConfiguration): The LinkedIn export integration configuration
        limit (int | None): The limit of rows to process
        workers (int): Number of worker threads for parallel processing
    """

    triple_store: ITripleStoreService
    linkedin_export_configuration: LinkedInExportIntegrationConfiguration
    linkedin_export_profile_pipeline_configuration: (
        LinkedInExportProfilePipelineConfiguration
    )
    limit: int | None = None
    workers: int = 20


class ActOfConnectionsOnLinkedInExportPipelineParameters(PipelineParameters):
    """Parameters for LinkedInExportConnectionsPipeline.

    Attributes:
        file_name (str): Name of the CSV file to process
    """

    person_name: Annotated[
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


class ActOfConnectionsOnLinkedInExportPipeline(Pipeline):
    """Pipeline for importing data from Excel tables to the triple store."""

    __configuration: ActOfConnectionsOnLinkedInExportPipelineConfiguration
    __sparql_utils: SPARQLUtils

    def __init__(
        self, configuration: ActOfConnectionsOnLinkedInExportPipelineConfiguration
    ):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__linkedin_export_integration = LinkedInExportIntegration(
            configuration.linkedin_export_configuration
        )
        self.__sparql_utils = SPARQLUtils(configuration.triple_store)

    def get_person_entity_from_name(self, person_name: str) -> Person:
        """
        Get person URI and name using the public_url property from LinkedInProfilePage.
        If not found, creates a new Person individual in the triple store.
        Returns: (URIRef, label) if created, or (URIRef, label) if found, or (None, None)
        """
        sparql_query = """
        PREFIX linkedin: <http://ontology.naas.ai/abi/linkedin/>
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX cco: <https://www.commoncoreontologies.org/>

        SELECT ?personUri ?personName
        WHERE {{
            ?person a cco:ont00001262 ; # Person
                   rdfs:label ?personName .
            FILTER(CONTAINS(LCASE(STR(?personName)), LCASE("{person_name}")))
        }}
        """.format(person_name=person_name.replace('"', '\\"'))
        results = self.__sparql_utils.results_to_list(
            self.__configuration.triple_store.query(sparql_query)
        )
        if results and results[0].get("personUri"):
            return Person(
                _uri=str(results[0]["personUri"]), label=results[0]["personName"]
            )

        # If not found, create individual in the graph
        person_uri = ABI[str(uuid.uuid4())]
        return Person(_uri=str(person_uri), label=person_name, given_name=person_name)

    def generate_graph_date(
        self,
        date: datetime | str,
        date_format: str = "%d %b %Y",
        target_date_format: str = "%Y-%m-%dT%H:%M:%S.%fZ",
    ) -> ISO8601UTCDateTime:
        """Generates a URI for a date based on the given datetime object using ISO8601UTCDateTime ontology class."""
        if isinstance(date, datetime):
            date_str = date.strftime(target_date_format)
            date_epoch = int(date.timestamp() * 1000)
            date_uri = ABI[str(date_epoch)]  # Create URI using timestamp
        elif isinstance(date, str):
            date_str = datetime.strptime(date, date_format).strftime(target_date_format)
            date_uri = ABI[date_str]

        # Use ontology class to generate date entity
        date_entity = ISO8601UTCDateTime(_uri=str(date_uri), label=date_str)  # type: ignore[call-arg]
        return date_entity

    def _process_row(
        self,
        row: dict,
        row_index: int,
        total_rows: int,
        init_person_uri: str,
        init_person_name: str,
        export_file_uri: str,
    ) -> Graph:
        """
        Process a single row from the CSV file and create entities with relationships.
        Returns a graph with all entities from this row, ready to be inserted.

        Args:
            row: The row data as a dictionary
            row_index: The index of the row (0-based)
            total_rows: Total number of rows being processed
            init_person_uri: URI of the person entity whose connections are being imported
            init_person_name: Name of the initial person
            export_file_uri: URI of the ConnectionsExportFile entity

        Returns:
            Graph containing all entities created from this row
        """

        print(
            f"🔄 Worker thread processing row {row_index + 1}/{total_rows} "
            f"(Thread: {threading.current_thread().name})"
        )

        # Get variables from row
        first_name = row.get("First Name", UNKNOWN_VALUE).strip()
        last_name = row.get("Last Name", UNKNOWN_VALUE).strip()
        url = row.get("URL", UNKNOWN_VALUE).strip()
        email_address = row.get("Email Address", UNKNOWN_VALUE).strip()
        company = row.get("Company", UNKNOWN_VALUE).strip()
        position = row.get("Position", UNKNOWN_VALUE).strip()
        connected_on_str = row.get("Connected On", UNKNOWN_VALUE).strip()

        # ============================================================
        # PHASE 1: Create all entities (without relationships)
        # ============================================================

        # Create date entity
        date_entity: ISO8601UTCDateTime | None = None
        try:
            connected_on_date = datetime.strptime(connected_on_str, "%d %b %Y")
            date_entity = self.generate_graph_date(connected_on_date)
        except Exception as e:
            logger.warning(
                f"Could not parse 'Connected On' date '{connected_on_str}': {e}"
            )
            date_entity = self.generate_graph_date(connected_on_str)

        # Create person entity
        person_name = f"{first_name} {last_name}"
        person_entity = Person(
            label=person_name,
            first_name=first_name,
            last_name=last_name,
            given_name=person_name,
        )

        # Create profile page entity
        profile_page_entity = ProfilePage(label=url)

        # Create organization entity
        organization_entity = Organization(label=company)
        linkedin_org_entity = CurrentOrganization(label=company)

        # Step 4: Create LinkedIn Current Public URL
        linkedin_public_url_entity = CurrentPublicURL(label=url)

        # Create LinkedIn Email Address
        email_entity = EmailAddress(label=email_address)

        # Step 6: Create LinkedIn Current Job Position
        position_entity = CurrentJobPosition(label=position)

        # Create connection role for initial person
        connection_role_initial_entity = ConnectionRole(label=UNKNOWN_VALUE)

        # Create act of connection entity
        act_of_connection_label = f"{init_person_name} connected with {person_name} on LinkedIn the {connected_on_str}"
        act_of_connection_entity = ActOfConnection(label=act_of_connection_label)

        # Create URI references for shared entities
        init_person_uriref = URIRef(init_person_uri)
        export_file_uriref = URIRef(export_file_uri)

        # ============================================================
        # PHASE 2: Set all object properties between entities based on schema
        # ============================================================

        # WHAT
        act_of_connection_entity.involves_agent = [init_person_uriref, person_entity]
        act_of_connection_entity.connected_at = date_entity
        act_of_connection_entity.concretizes = [export_file_uriref, profile_page_entity]
        act_of_connection_entity.realizes = [connection_role_initial_entity]
        act_of_connection_entity.has_associated_quality = [
            email_entity,
            position_entity,
            linkedin_org_entity,
            linkedin_public_url_entity,
        ]

        # WHO
        person_entity.is_owner_of = [profile_page_entity]
        person_entity.has_public_url = [linkedin_public_url_entity]
        person_entity.has_email_address = [email_entity]
        person_entity.has_current_job_position = [position_entity]
        person_entity.has_current_organization = [linkedin_org_entity]
        person_entity.has_connection_role = [connection_role_initial_entity]
        # Note: init_person_entity relationship is handled via URI reference
        organization_entity.holds_linkedin_quality = [linkedin_org_entity]

        # HOW WE KNOW
        profile_page_entity.is_owned_by = [person_entity]
        profile_page_entity.is_concretized_by = [act_of_connection_entity]

        # HOW IT IS
        email_entity.inheres_in = [person_entity]
        email_entity.concretizes = [export_file_uriref]
        position_entity.inheres_in = [person_entity]
        position_entity.concretizes = [export_file_uriref, profile_page_entity]
        linkedin_org_entity.inheres_in = [person_entity, organization_entity]
        linkedin_org_entity.concretizes = [export_file_uriref]
        organization_entity.holds_linkedin_quality = [linkedin_org_entity]
        linkedin_public_url_entity.inheres_in = [person_entity]
        linkedin_public_url_entity.concretizes = [export_file_uriref]

        # WHY
        connection_role_initial_entity.inheres_in = [init_person_uriref, person_entity]
        connection_role_initial_entity.has_realization = [act_of_connection_entity]

        # Generate graph from all entities created in this row
        row_graph = Graph()
        row_graph.bind("linkedin", LINKEDIN)
        row_entities = [
            act_of_connection_entity,
            person_entity,
            profile_page_entity,
            organization_entity,
            linkedin_org_entity,
            linkedin_public_url_entity,
            email_entity,
            position_entity,
            connection_role_initial_entity,
        ]
        for entity in row_entities:
            if entity is not None:
                entity_graph = entity.rdf()
                row_graph += entity_graph

        return row_graph

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(
            parameters, ActOfConnectionsOnLinkedInExportPipelineParameters
        ):
            raise ValueError(
                "Parameters must be of type ActOfConnectionsOnLinkedInExportPipelineParameters"
            )

        # Create shared entities that will be reused across all rows
        person_entity = self.get_person_entity_from_name(parameters.person_name)

        # Create linkedin location entity
        linkedin_location_entity = Location(label=UNKNOWN_VALUE)

        # Create export file entity
        export_file_label = f"LinkedIn Connections Export File - {parameters.file_name}"
        export_file_entity = ConnectionsExportFile(
            label=export_file_label,
            file_path=self.__configuration.linkedin_export_configuration.export_file_path,
        )

        # Create organization entity
        linkedin_org_label = "LinkedIn"
        linkedin_org_entity = Organization(label=linkedin_org_label)

        # Create relationships between shared entities
        person_entity.is_located_in = [linkedin_location_entity]
        export_file_entity.is_owned_by = [linkedin_org_entity]
        linkedin_org_entity.is_owner_of = [export_file_entity]

        # Generate graph for shared entities and insert them once
        logger.debug("==> Generating graph for shared entities")
        shared_graph = Graph()
        shared_graph.bind("linkedin", LINKEDIN)
        shared_entities = [
            person_entity,
            linkedin_location_entity,
            linkedin_org_entity,
            export_file_entity,
        ]
        for entity in shared_entities:
            if entity is not None:
                entity_graph = entity.rdf()
                shared_graph += entity_graph

        # Insert shared entities into triple store
        logger.debug("==> Inserting shared entities into triple store")
        if len(shared_graph) > 0:
            self.__configuration.triple_store.insert(shared_graph)

        # Store URIs for reuse in row processing
        init_person_uri = person_entity._uri
        init_person_name = person_entity.label
        export_file_uri = export_file_entity._uri

        # Read CSV File
        logger.debug(f"==> Reading CSV file '{parameters.file_name}'")
        df = self.__linkedin_export_integration.read_csv(parameters.file_name).fillna(
            UNKNOWN_VALUE
        )
        if len(df) == 0:
            logger.warning(
                f"❌ No rows to process in CSV file '{parameters.file_name}'"
            )
            return Graph()
        logger.debug(f"✅ {len(df)} rows in CSV file to be processed")

        # Processing rows from CSV file with multi-worker threading
        print(
            f"==> Starting parallel processing with {self.__configuration.workers} workers"
        )
        if self.__configuration.limit is not None:
            df = df[: self.__configuration.limit]
            logger.debug(f"Limited to {self.__configuration.limit} rows")

        total_rows = len(df)
        processed_count = 0
        error_count = 0
        start_time = time.time()

        # Process rows in parallel using ThreadPoolExecutor
        logger.debug(f"Submitting {total_rows} tasks to thread pool...")
        with ThreadPoolExecutor(max_workers=self.__configuration.workers) as executor:
            # Submit all tasks
            future_to_row = {
                executor.submit(
                    self._process_row,
                    row.to_dict(),
                    idx,
                    total_rows,
                    init_person_uri,
                    init_person_name,
                    export_file_uri,
                ): (idx, row)
                for idx, (_, row) in enumerate(df.iterrows())
            }
            print(
                f"✅ Submitted {len(future_to_row)} tasks to {self.__configuration.workers} workers"
            )

            # Collect results as they complete and insert immediately
            logger.debug("Waiting for tasks to complete and inserting results...")
            for future in as_completed(future_to_row):
                idx, row = future_to_row[future]
                try:
                    row_graph = future.result()
                    # Insert row entities immediately into triple store
                    if len(row_graph) > 0:
                        self.__configuration.triple_store.insert(row_graph)
                    processed_count += 1
                    if processed_count % 10 == 0 or processed_count == total_rows:
                        elapsed = time.time() - start_time
                        rate = processed_count / elapsed if elapsed > 0 else 0
                        print(
                            f"✅ Progress: {processed_count}/{total_rows} rows processed and inserted "
                            f"({rate:.2f} rows/sec, {elapsed:.2f}s elapsed)"
                        )
                except Exception as e:
                    error_count += 1
                    logger.error(
                        f"❌ Error processing row {idx + 1}/{total_rows}: {e}",
                        exc_info=True,
                    )
                    continue

        elapsed_time = time.time() - start_time
        avg_rate = processed_count / elapsed_time if elapsed_time > 0 else 0
        print(
            f"✅ Completed processing: {processed_count}/{total_rows} rows successful, "
            f"{error_count} errors, {elapsed_time:.2f}s total ({avg_rate:.2f} rows/sec)"
        )

        # Return the shared graph (row graphs were already inserted)
        return shared_graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="linkedin_export_connections_import_csv",
                description="Import LinkedIn Connections data from a CSV file to the triple store",
                func=lambda **kwargs: self.run(
                    ActOfConnectionsOnLinkedInExportPipelineParameters(**kwargs)
                ),
                args_schema=ActOfConnectionsOnLinkedInExportPipelineParameters,
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
    person_name = "Florent Ravenel"
    limit = None

    pipeline = ActOfConnectionsOnLinkedInExportPipeline(
        ActOfConnectionsOnLinkedInExportPipelineConfiguration(
            triple_store=module.engine.services.triple_store,
            linkedin_export_configuration=linkedin_export_configuration,
            linkedin_export_profile_pipeline_configuration=linkedin_export_profile_pipeline_configuration,
            limit=limit,
        )
    )
    graph = pipeline.run(
        ActOfConnectionsOnLinkedInExportPipelineParameters(person_name=person_name)
    )
