from abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import (
    TripleStoreService__SecondaryAdaptor__Filesystem,
)
from abi.services.triple_store.TripleStoreService import TripleStoreService
from src.core.modules.common.workflows.abi.mappings import COLORS_NODES
from src.core.modules.common.workflows.abi.CreateOntologyYAML import (
    CreateOntologyYAML,
    CreateOntologyYAMLConfiguration,
    CreateOntologyYAMLParameters,
)
from src.core.modules.common.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from src import config, secret

# Initialize configurations
triple_store = TripleStoreService(
    TripleStoreService__SecondaryAdaptor__Filesystem(
        store_path=config.triple_store_path
    )
)
naas_integration_config = NaasIntegrationConfiguration(
    api_key=secret.get("NAAS_API_KEY")
)

# Initialize the workflow
workflow = CreateOntologyYAML(
    CreateOntologyYAMLConfiguration(
        naas_integration_config=naas_integration_config, triple_store=triple_store
    )
)

# Run the workflow
workflow.graph_to_yaml(
    CreateOntologyYAMLParameters(
        ontology_name="github",
        label="Github Ontology",
        description="Represents Github Application Ontology with issues, repositories, projects and pull requests.",
        workspace_id=config.workspace_id,
        class_colors_mapping=COLORS_NODES,
    )
)
