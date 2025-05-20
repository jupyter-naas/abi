from src.core.modules.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from src.core.modules.ontology.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlConfiguration,
)
from src.core.modules.ontology.workflows.CreateClassOntologyYamlWorkflow import (
    CreateClassOntologyYamlWorkflow,
    CreateClassOntologyYamlConfiguration,
    CreateClassOntologyYamlParameters,
)
from src import services, secret

# Configuration
naas_integration_config = NaasIntegrationConfiguration(
    api_key=secret.get("NAAS_API_KEY")
)
convert_ontology_graph_config = ConvertOntologyGraphToYamlConfiguration(
    naas_integration_config
)
workflow = CreateClassOntologyYamlWorkflow(
    CreateClassOntologyYamlConfiguration(
        services.triple_store_service, convert_ontology_graph_config
    )
)

# Parameters
parameters = CreateClassOntologyYamlParameters(
    class_uri="https://www.commoncoreontologies.org/ont00001262",
)

# Run workflow
workflow.graph_to_yaml(parameters)
