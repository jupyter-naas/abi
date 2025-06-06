from src.core.modules.ontology.workflows.GetSubjectGraphWorkflow import (
    GetSubjectGraphWorkflow,
    GetSubjectGraphWorkflowConfiguration,
    GetSubjectGraphWorkflowParameters
)

# Configurations
get_subject_graph_workflow_configuration = GetSubjectGraphWorkflowConfiguration()

# Workflow
get_subject_graph_workflow = GetSubjectGraphWorkflow(
    configuration=get_subject_graph_workflow_configuration
)

# Test
result = get_subject_graph_workflow.get_subject_graph(
    GetSubjectGraphWorkflowParameters(
        uri="http://ontology.naas.ai/abi/4d4e6bc4-b396-4d26-b42b-3d257cde1738",
        depth=2
    )
)
print(result)