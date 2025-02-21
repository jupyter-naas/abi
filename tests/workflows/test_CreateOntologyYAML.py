from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from src.core.workflows.abi.mappings import COLORS_NODES
from src.core.workflows.abi.CreateOntologyYAML import CreateOntologyYAML, CreateOntologyYAMLConfiguration, CreateOntologyYAMLParameters
from src.core.integrations.NaasIntegration import NaasIntegrationConfiguration
from src import config, secret

# Initialize configurations
ontology_store = OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path=config.ontology_store_path))
naas_integration_config = NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY"))

# Initialize the workflow
workflow = CreateOntologyYAML(CreateOntologyYAMLConfiguration(
    naas_integration_config=naas_integration_config,
    ontology_store=ontology_store
))

# Run the workflow
workflow.graph_to_yaml(
    CreateOntologyYAMLParameters(
        ontology_name="github",
        label="Github Ontology",
        description="Represents Github Application Ontology with issues, repositories, projects and pull requests.",
        workspace_id=config.workspace_id,
        class_colors_mapping=COLORS_NODES
    )
)