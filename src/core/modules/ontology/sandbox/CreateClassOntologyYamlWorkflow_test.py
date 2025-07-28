from src.core.modules.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from src.core.modules.ontology.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflowConfiguration,
)
from src.core.modules.ontology.workflows.CreateClassOntologyYamlWorkflow import (
    CreateClassOntologyYamlWorkflow,
    CreateClassOntologyYamlWorkflowConfiguration,
    CreateClassOntologyYamlWorkflowParameters,
)
from src import services, secret

# Configuration
naas_api_key = secret.get("NAAS_API_KEY")
convert_ontology_graph_config = ConvertOntologyGraphToYamlWorkflowConfiguration(
    NaasIntegrationConfiguration(api_key=naas_api_key)
)
workflow = CreateClassOntologyYamlWorkflow(
    CreateClassOntologyYamlWorkflowConfiguration(
        services.triple_store_service, convert_ontology_graph_config
    )
)

# Parameters
class_uri="https://www.commoncoreontologies.org/ont00001262"

# Run workflow
workflow.graph_to_yaml(CreateClassOntologyYamlWorkflowParameters(class_uri=class_uri))
