from src.core.modules.ontology.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflow,
    ConvertOntologyGraphToYamlWorkflowConfiguration,
    ConvertOntologyGraphToYamlWorkflowParameters,
)
from src.core.modules.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from src import secret
from abi.utils.SPARQL import get_subject_graph

# Configurations
naas_api_key = secret.get("NAAS_API_KEY")
convert_ontology_graph_to_yaml_workflow_configuration = ConvertOntologyGraphToYamlWorkflowConfiguration(
    NaasIntegrationConfiguration(api_key=naas_api_key)
)

# Workflow
convert_ontology_graph_to_yaml_workflow = ConvertOntologyGraphToYamlWorkflow(
    convert_ontology_graph_to_yaml_workflow_configuration
)

# Parameters
graph = get_subject_graph("http://ontology.naas.ai/abi/4d4e6bc4-b396-4d26-b42b-3d257cde1738", 2).serialize(format="turtle")

# Run workflow
convert_ontology_graph_to_yaml_workflow.graph_to_yaml(ConvertOntologyGraphToYamlWorkflowParameters(graph=graph))