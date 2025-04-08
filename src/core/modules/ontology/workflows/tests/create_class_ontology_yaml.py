from src.core.modules.naas.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src.core.modules.ontology.workflows.CreateClassOntologyYAML import CreateClassOntologyYAMLWorkflow, CreateClassOntologyYAMLConfiguration, CreateClassOntologyYAMLParameters
from src import services, secret

# Configuration
naas_integration_config = NaasIntegrationConfiguration(api_key=secret.get("NAAS_API_KEY"))
workflow = CreateClassOntologyYAMLWorkflow(CreateClassOntologyYAMLConfiguration(naas_integration_config, services.triple_store_service))

# Parameters
parameters = CreateClassOntologyYAMLParameters(
    class_uri="https://www.commoncoreontologies.org/ont00000443",
    label="Commercial Organization",
    description="Commercial Organization Ontology",
)

# Run workflow
workflow.graph_to_yaml(parameters)
