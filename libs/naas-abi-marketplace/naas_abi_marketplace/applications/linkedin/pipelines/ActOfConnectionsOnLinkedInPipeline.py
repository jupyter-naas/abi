import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Annotated, Any

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
    ActOfConnectionOnLinkedIn,
    ConnectionsExportFile,
    ISO8601UTCDateTime,
    LinkedInConnectionRole,
    LinkedInCurrentJobPosition,
    LinkedInCurrentOrganization,
    LinkedInCurrentPublicURL,
    LinkedInEmailAddress,
    LinkedInLocation,
    LinkedInProfilePage,
    Organization,
    Person,
)
from naas_abi_marketplace.applications.linkedin.pipelines.LinkedInExportProfilePipeline import (
    LinkedInExportProfilePipelineConfiguration,
)
from pydantic import Field
from rdflib import Graph, Namespace

LINKEDIN = Namespace("http://ontology.naas.ai/abi/linkedin/")
UNKNOWN_VALUE = "UNKNOWN"


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
    linkedin_export_profile_pipeline_configuration: (
        LinkedInExportProfilePipelineConfiguration
    )
    limit: int | None = None


class LinkedInExportConnectionsPipelineParameters(PipelineParameters):
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


class LinkedInExportConnectionsPipeline(Pipeline):
    """Pipeline for importing data from Excel tables to the triple store."""

    __configuration: LinkedInExportConnectionsPipelineConfiguration
    __sparql_utils: SPARQLUtils

    def __init__(self, configuration: LinkedInExportConnectionsPipelineConfiguration):
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
        return Person(_uri=str(person_uri), label=person_name)

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
        init_person_entity: Person,
        export_file_entity: ConnectionsExportFile,
        all_entities: list[Any],
    ) -> list[Any]:
        """
        Process a single row from the CSV file and create entities with relationships.
        Entities are added to all_entities list for later graph generation.

        Args:
            row: The row data as a dictionary
            row_index: The index of the row (0-based)
            total_rows: Total number of rows being processed
            init_person_entity: Person entity whose connections are being imported
            connections_export_file_uri: URI of the ConnectionsExportFile entity
            all_entities: List to collect all entities for graph generation at the end
        """
        # Get initial person info
        initial_person_name = init_person_entity.label

        logger.debug(f"🔄 Processing row {row_index + 1}/{total_rows}")

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
        person_entity = Person(label=person_name)

        # Create profile page entity
        profile_page_entity = LinkedInProfilePage(label=url)

        # Create organization entity
        organization_entity = Organization(label=company)
        linkedin_org_entity = LinkedInCurrentOrganization(label=company)

        # Step 4: Create LinkedIn Current Public URL
        linkedin_public_url_entity = LinkedInCurrentPublicURL(label=url)

        # Create LinkedIn Email Address
        email_entity = LinkedInEmailAddress(label=email_address)

        # Step 6: Create LinkedIn Current Job Position
        position_entity = LinkedInCurrentJobPosition(label=position)

        # Create connection role for initial person
        connection_role_initial_entity = LinkedInConnectionRole(label=UNKNOWN_VALUE)

        # Create act of connection entity
        act_of_connection_label = f"{initial_person_name} connected with {person_name} on LinkedIn the {connected_on_str}"
        act_of_connection_entity = ActOfConnectionOnLinkedIn(
            label=act_of_connection_label
        )

        # ============================================================
        # PHASE 2: Set all object properties between entities based on schema
        # ============================================================

        # WHAT
        act_of_connection_entity.involves_agent = [init_person_entity, person_entity]
        act_of_connection_entity.connected_at = date_entity
        act_of_connection_entity.concretizes = [export_file_entity, profile_page_entity]
        act_of_connection_entity.realizes = [connection_role_initial_entity]
        act_of_connection_entity.has_associated_linkedin_quality = [
            email_entity,
            position_entity,
            linkedin_org_entity,
            linkedin_public_url_entity,
        ]

        # WHO
        person_entity.is_owner_of = [profile_page_entity]
        person_entity.has_linkedin_public_url = [linkedin_public_url_entity]
        person_entity.has_linkedin_email_address = [email_entity]
        person_entity.has_linkedin_current_job_position = [position_entity]
        person_entity.has_linkedin_current_organization = [linkedin_org_entity]
        person_entity.has_linkedin_connection_role = [connection_role_initial_entity]
        init_person_entity.has_linkedin_connection_role = [
            connection_role_initial_entity
        ]
        organization_entity.holds_linkedin_quality = [linkedin_org_entity]

        # HOW WE KNOW
        profile_page_entity.is_owned_by = [person_entity]
        profile_page_entity.is_concretized_by = [act_of_connection_entity]

        # HOW IT IS
        email_entity.inheres_in = [person_entity]
        email_entity.concretizes = [export_file_entity]
        position_entity.inheres_in = [person_entity]
        position_entity.concretizes = [export_file_entity, profile_page_entity]
        linkedin_org_entity.inheres_in = [person_entity, organization_entity]
        linkedin_org_entity.concretizes = [export_file_entity]
        organization_entity.holds_linkedin_quality = [linkedin_org_entity]
        linkedin_public_url_entity.inheres_in = [person_entity]
        linkedin_public_url_entity.concretizes = [export_file_entity]

        # WHY
        connection_role_initial_entity.inheres_in = [init_person_entity, person_entity]
        connection_role_initial_entity.has_realization = [act_of_connection_entity]

        # Concat all entities to the graph
        all_entities.append(act_of_connection_entity)
        all_entities.append(person_entity)
        all_entities.append(profile_page_entity)
        all_entities.append(organization_entity)
        all_entities.append(linkedin_org_entity)
        all_entities.append(linkedin_public_url_entity)
        all_entities.append(email_entity)
        all_entities.append(position_entity)
        all_entities.append(connection_role_initial_entity)

        return all_entities

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, LinkedInExportConnectionsPipelineParameters):
            raise ValueError(
                "Parameters must be of type LinkedInExportConnectionsPipelineParameters"
            )
        # List to collect all entities for graph generation at the end
        all_entities: list[Any] = []

        # Create person entity
        person_entity = self.get_person_entity_from_name(parameters.person_name)

        # Create linkedin location entity
        linkedin_location_entity = LinkedInLocation(label=UNKNOWN_VALUE)

        # Create export file entity
        export_file_label = f"LinkedIn Connections Export File - {parameters.file_name}"
        export_file_entity = ConnectionsExportFile(
            label=export_file_label,
            # file_path=self.__configuration.linkedin_export_configuration.export_file_path,
        )

        # Create organization entity
        linkedin_org_label = "LinkedIn"
        linkedin_org_entity = Organization(label=linkedin_org_label)

        # Create relationships between entities
        person_entity.is_located_in = [linkedin_location_entity]
        export_file_entity.is_owned_by = [linkedin_org_entity]
        linkedin_org_entity.is_owner_of = [export_file_entity]

        # Add entities to all_entities list
        all_entities.append(person_entity)
        all_entities.append(linkedin_location_entity)
        all_entities.append(linkedin_org_entity)
        all_entities.append(export_file_entity)

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

        # Processing rows from CSV file sequentially
        logger.debug("==> Processing rows sequentially")
        if self.__configuration.limit is not None:
            df = df[: self.__configuration.limit]

        total_rows = len(df)
        processed_count = 0

        # Process rows sequentially
        for idx, (_, row) in enumerate(df.iterrows()):
            try:
                all_entities = self._process_row(
                    row.to_dict(),
                    idx,
                    total_rows,
                    person_entity,
                    export_file_entity,
                    all_entities,
                )
                processed_count += 1
                if processed_count % 10 == 0 or processed_count == total_rows:
                    logger.debug(f"✅ Processed {processed_count}/{total_rows} rows")
            except Exception as e:
                logger.error(f"❌ Error processing row {idx + 1}: {e}")
                continue

        logger.debug(f"✅ Completed processing {processed_count}/{total_rows} rows")

        # Generate ONE graph from all entities at the end
        logger.debug("==> Generating final graph from all entities")
        graph = Graph()
        graph.bind("linkedin", LINKEDIN)
        for entity in all_entities:
            if entity is not None:
                entity_graph = entity.rdf()
                graph += entity_graph

        # Add triples to triple store (single insert)
        logger.debug("==> Adding triples to triple store")
        if len(graph) > 0:
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
    person_name = "Florent Ravenel"
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
        LinkedInExportConnectionsPipelineParameters(person_name=person_name)
    )
    # print(graph.serialize(format="turtle"))

    ontology_tbox_path = "libs/naas-abi-marketplace/naas_abi_marketplace/applications/linkedin/ontologies/modules/ActOfConnectionsOnLinkedIn.ttl"
    graph_tbox = Graph()
    graph_tbox.parse(ontology_tbox_path, format="turtle")

    graph += graph_tbox

    # Save graph to file in the same directory as this script
    import os
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    base_file_name = f"insert_{person_name.replace(' ', '_')}"
    file_name_with_timestamp = f"{timestamp}_{base_file_name}.ttl"
    file_name_without_timestamp = f"{base_file_name}.ttl"
    dir_path = os.path.dirname(os.path.abspath(__file__))
    output_path_with_timestamp = os.path.join(dir_path, file_name_with_timestamp)
    output_path_without_timestamp = os.path.join(dir_path, file_name_without_timestamp)

    # Write the graph with timestamped filename
    with open(output_path_with_timestamp, "w", encoding="utf-8") as f:
        f.write(graph.serialize(format="turtle"))
    print(f"Graph saved to {output_path_with_timestamp}")

    # Write the graph with non-timestamped filename
    with open(output_path_without_timestamp, "w", encoding="utf-8") as f:
        f.write(graph.serialize(format="turtle"))
    print(f"Graph saved to {output_path_without_timestamp}")

    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.naas import ABIModule as NaasABIModule
    from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
        NaasIntegrationConfiguration,
    )
    from naas_abi_marketplace.applications.naas.workflows.CreateWorkspaceOntologyWorkflow import (
        CreateWorkspaceOntologyWorkflowConfiguration,
    )
    from naas_abi_marketplace.domains.ontology_engineer.workflows.ConvertOntologytoYamlWorkflow import (
        ConvertOntologytoYamlWorkflow,
        ConvertOntologytoYamlWorkflowConfiguration,
        ConvertOntologytoYamlWorkflowParameters,
    )

    engine.load(module_names=["naas_abi_marketplace.applications.naas"])
    naas_module: NaasABIModule = NaasABIModule.get_instance()
    create_workspace_ontology_config = CreateWorkspaceOntologyWorkflowConfiguration(
        naas_integration_config=NaasIntegrationConfiguration(
            api_key=engine.services.secret.get("NAAS_API_KEY"),
            workspace_id=naas_module.configuration.workspace_id,
            storage_name=naas_module.configuration.storage_name,
        )
    )
    turtle_path = output_path_with_timestamp
    imported_ontologies = [
        "libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology_engineer/ontologies/BFO7BucketsProcessOntology.ttl",
        "libs/naas-abi-marketplace/naas_abi_marketplace/applications/linkedin/ontologies/imports/LinkedInOntology.ttl",
        "libs/naas-abi-marketplace/naas_abi_marketplace/applications/linkedin/ontologies/modules/ActOfConnectionsOnLinkedIn.ttl",
    ]
    ontology_name = "Florent Ravenel's Act of Connections on LinkedIn"
    display_individuals_classes = False

    # Create workflow configuration and instance
    configuration = ConvertOntologytoYamlWorkflowConfiguration(
        create_workspace_ontology_config=create_workspace_ontology_config
    )
    workflow = ConvertOntologytoYamlWorkflow(configuration)

    # Create parameters
    parameters = ConvertOntologytoYamlWorkflowParameters(
        turtle_path=turtle_path,
        imported_ontologies=imported_ontologies,
        publish_to_workspace=True,
        ontology_name=ontology_name,
        display_individuals_classes=display_individuals_classes,
    )

    # Execute workflow
    yaml_path = workflow.convert_ontology_to_yaml(parameters)
    print(f"YAML file generated at: {yaml_path}")
