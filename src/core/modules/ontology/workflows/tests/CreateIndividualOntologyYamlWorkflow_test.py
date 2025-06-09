import pytest

from src.core.modules.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from src.core.modules.ontology.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflowConfiguration,
)
from src.core.modules.ontology.workflows.CreateIndividualOntologyYamlWorkflow import (
    CreateIndividualOntologyYamlWorkflow,
    CreateIndividualOntologyYamlWorkflowConfiguration,
    CreateIndividualOntologyYamlWorkflowParameters,
)
from src import services, secret

# Configuration
naas_api_key = secret.get("NAAS_API_KEY")
convert_ontology_graph_config = ConvertOntologyGraphToYamlWorkflowConfiguration(
    NaasIntegrationConfiguration(api_key=naas_api_key)
)
workflow = CreateIndividualOntologyYamlWorkflow(
    CreateIndividualOntologyYamlWorkflowConfiguration(
        services.triple_store_service, convert_ontology_graph_config
    )
)

# Parameters
individual_uri="http://ontology.naas.ai/abi/4d4e6bc4-b396-4d26-b42b-3d257cde1738"
depth=2

# Run workflow
workflow.graph_to_yaml(CreateIndividualOntologyYamlWorkflowParameters(individual_uri=individual_uri, depth=depth))
