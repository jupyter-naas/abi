from src.core.modules.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from src.core.modules.ontology.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlConfiguration,
)
from src.core.modules.ontology.workflows.CreateIndividualOntologyYamlWorkflow import (
    CreateIndividualOntologyYamlWorkflow,
    CreateIndividualOntologyYamlConfiguration,
    CreateIndividualOntologyYamlParameters,
)
from src import services, secret

# Configuration
naas_integration_config = NaasIntegrationConfiguration(
    api_key=secret.get("NAAS_API_KEY")
)
convert_ontology_graph_config = ConvertOntologyGraphToYamlConfiguration(
    naas_integration_config
)
workflow = CreateIndividualOntologyYamlWorkflow(
    CreateIndividualOntologyYamlConfiguration(
        services.triple_store_service, convert_ontology_graph_config
    )
)

# Parameters
parameters = CreateIndividualOntologyYamlParameters(
    individual_uri="http://ontology.naas.ai/abi/67503ee8-f577-4603-96d3-dd5ede825314",
    distance=2,
)

# Run workflow
workflow.graph_to_yaml(parameters)
