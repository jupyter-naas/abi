from typing import Optional

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)

NAME: str = "Knowledge_Graph_Builder"
AVATAR_URL: str = "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Rdf_logo.svg/1200px-Rdf_logo.svg.png"
DESCRIPTION: str = (
    "A Knowledge Graph Builder Agent that helps users to build Knowledge Graphs."
)
SYSTEM_PROMPT: str = """
# ROLE:
You are a friendly and helpful Knowledge Graph Builder Agent and your role is to help users interact with instances within a Knowledge Graph by getting, adding, updating, merging and removing them.

# OBJECTIVE:
- Execute the tasks provided by the user.
- Do not damage the triplestore by removing or merging individuals that are not related to the prompt.
- Do not add individuals that are not related to the prompt.
- Do not update data properties that are not related to the prompt.
- Do not merge individuals that are not related to the prompt.
- Do not remove individuals that are not related to the prompt.

# CONTEXT:
You will receive prompts from users or other agents.

# TOOLS:
- search_class: Search for ontology classes based on their labels, definitions, examples, and comments.
- get_individuals_from_class: Get all individuals that are instances of a specific class.
- search_individuals_from_class: Search for individuals that are instances of a specific class starting with a search string.
- get_subject_graph: Retrieve detailed information about an entity.
- add_individual: Add an individual from label and class URI to the triplestore.
- insert_data_sparql: Insert individual data into the triplestore using SPARQL statement INSERT DATA.
- update_data_property: Update a data property of an entity.
- merge_individuals: Merge two individuals in the triplestore by transferring all triples from one to another.
- remove_individuals: Remove individuals from the triplestore by deleting all their associated triples.

# TASKS:
1. Search for ontology classes based on their labels, definitions, examples, and comments
2. Get all individuals that are instances of a specific class
3. Add new individuals to the triplestore
4. Update data properties for a given individual
5. Merge two individuals in the triplestore by transferring all triples from one to another
6. Remove individuals from the triplestore by deleting all their associated triples

# OPERATING GUIDELINES:
1. Search instances in triplestore using appropriate search tool to find the information you need

2.1 Add Individual by using add_individual tool.
Before using the tool, use get_subject_graph tool to get the individual and validate the individual to add is related to the prompt and provide the correct URI and label like:
"We are going to add the following individual to the triplestore:
- Individual label (rdfs:label): Naas.ai
- Class URI: https://www.commoncoreontologies.org/ont00000443
Are you sure you want to add this individual? (y/n)"
Finish by using the tool get_subject_graph of the uri to add to check if the individual is added.

2.2 Insert data into the triplestore using SPARQL statement INSERT DATA.
If you receive a sparql statement starting with ```sparql	`` and with "INSERT DATA" in it, use the insert_data_sparql tool to insert the data into the triplestore.
Before using the tool, use extract_sparql_from_text tool to get the sparql statement and validate it with the user:
"We are going to insert data from the following sparql statement into the triplestore:
```sparql
INSERT DATA {
    <http://ontology.naas.ai/abi/69a231b9-e87a-4503-8f80-a530ed8eaa4b> <http://www.w3.org/2000/01/rdf-schema#label> "Naas.ai" .
}
```
Are you sure you want to insert this data? (y/n)"
If the user confirms, use the insert_data_sparql tool to insert the data into the triplestore.

3. Update Data Property of an Entity by getting all its triples first using get_subject_graph tool and then use update_data_property tool to update the data property:
"We are going to update the following data property of the following individual:
- Individual URI: http://ontology.naas.ai/abi/69a231b9-e87a-4503-8f80-a530ed8eaa4b
- Data property to update: "http://www.w3.org/2000/01/rdf-schema#label"
- Old value: Naas
- New value: Naas.ai
Are you sure you want to update this data property? (y/n)"
Finish by using the tool get_subject_graph of the uri to update to check if the data property is updated.

4. Merge Individuals by using merge_individuals tool.
Before using the tool, use get_subject_graph tool to get the individuals and validate the individuals to merge are related to the prompt and provide the correct URIs and labels like:
"We are going to merge the following individuals:
- Instance to keep:
    - Label: Naas.ai
    - URI: http://ontology.naas.ai/abi/69a231b9-e87a-4503-8f80-a530ed8eaa4b
    - Class URI: https://www.commoncoreontologies.org/ont00000443
- Instance to merge:
    - Label: Naas.ai
    - URI: http://ontology.naas.ai/abi/4f92bbdd-e710-4e43-9480-9b6cd6d9af80
    - Class URI: https://www.commoncoreontologies.org/ont00000443
Are you sure you want to merge these individuals? (y/n)"
If class URI are not the same, you can NOT merge them.
If class URI are the same, finish by using the tool get_subject_graph of the uri to keep. 

5. Remove Individual by using remove_individuals tool.
Before using the tool, use get_subject_graph tool to get the individual and validate the individual to remove is related to the prompt and provide the correct URI and label like:
"We are going to remove the following individuals from the triplestore:
- URI: http://ontology.naas.ai/abi/69a231b9-e87a-4503-8f80-a530ed8eaa4b
- Label: Naas.ai
- Class URI: https://www.commoncoreontologies.org/ont00000443
Are you sure you want to remove this individual? (y/n)"
Finish by using the tool get_subject_graph of the uri to remove to check if the individual is removed.

# CONSTRAINTS:
- Never use internal knowledge for answers
- Always ask for confirmation before performing UPDATE, MERGE, ADD or REMOVE operations.
"""

SUGGESTIONS: list = [
    {
        "label": "Search classes",
        "value": "Search classes representing a ...",
    },
    {
        "label": "Search individuals",
        "value": "Search for individuals from a class ...",
    },
    {
        "label": "Add individual",
        "value": "Add an individual ...",
    },
    {
        "label": "Update data property",
        "value": "Update a data property of an individual ...",
    },
    {
        "label": "Merge individuals",
        "value": "Merge two individuals ...",
    },
    {
        "label": "Remove individuals",
        "value": "Remove individual from triplestore ...",
    },
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[Agent]:
    # Define model
    from naas_abi.models.default import get_model

    model = get_model()

    from naas_abi import ABIModule

    MODULE: ABIModule = ABIModule.get_instance()

    # Init tools
    tools: list = []
    from naas_abi.pipelines.AddIndividualPipeline import (
        AddIndividualPipeline,
        AddIndividualPipelineConfiguration,
    )

    # Add Foundational Tools
    from naas_abi.workflows.SearchIndividualWorkflow import (
        SearchIndividualWorkflow,
        SearchIndividualWorkflowConfiguration,
    )

    ## Initialize search workflow first since add pipeline depends on it
    search_config = SearchIndividualWorkflowConfiguration(
        MODULE.engine.services.triple_store
    )
    search_workflow = SearchIndividualWorkflow(search_config)
    tools += search_workflow.as_tools()

    ## Initialize add pipeline with search workflow config
    add_config = AddIndividualPipelineConfiguration(
        MODULE.engine.services.triple_store, search_config
    )
    add_pipeline = AddIndividualPipeline(add_config)
    tools += add_pipeline.as_tools()

    from naas_abi.pipelines.InsertDataSPARQLPipeline import (
        InsertDataSPARQLPipeline,
        InsertDataSPARQLPipelineConfiguration,
    )

    insert_data_spql_pipeline = InsertDataSPARQLPipeline(
        InsertDataSPARQLPipelineConfiguration(
            triple_store=MODULE.engine.services.triple_store
        )
    )
    tools += insert_data_spql_pipeline.as_tools()

    # Add GetSubjectGraphWorkflow
    from naas_abi.workflows.GetSubjectGraphWorkflow import (
        GetSubjectGraphWorkflow,
        GetSubjectGraphWorkflowConfiguration,
    )

    get_subject_graph_config = GetSubjectGraphWorkflowConfiguration()
    get_subject_graph_workflow = GetSubjectGraphWorkflow(get_subject_graph_config)
    tools += get_subject_graph_workflow.as_tools()

    # Add UpdateDataPropertyPipeline
    from naas_abi.pipelines.UpdateDataPropertyPipeline import (
        UpdateDataPropertyPipeline,
        UpdateDataPropertyPipelineConfiguration,
    )

    update_data_property_pipeline = UpdateDataPropertyPipeline(
        UpdateDataPropertyPipelineConfiguration(
            triple_store=MODULE.engine.services.triple_store
        )
    )
    tools += update_data_property_pipeline.as_tools()

    # Add MergeIndividualsPipeline
    from naas_abi.pipelines.MergeIndividualsPipeline import (
        MergeIndividualsPipeline,
        MergeIndividualsPipelineConfiguration,
    )

    merge_individuals_pipeline = MergeIndividualsPipeline(
        MergeIndividualsPipelineConfiguration(
            triple_store=MODULE.engine.services.triple_store
        )
    )
    tools += merge_individuals_pipeline.as_tools()

    # Add RemoveIndividualPipeline
    from naas_abi.pipelines.RemoveIndividualPipeline import (
        RemoveIndividualPipeline,
        RemoveIndividualPipelineConfiguration,
    )

    remove_individuals_pipeline = RemoveIndividualPipeline(
        RemoveIndividualPipelineConfiguration(
            triple_store=MODULE.engine.services.triple_store
        )
    )
    tools += remove_individuals_pipeline.as_tools()

    # Add specialized pipelines
    from naas_abi.pipelines.UpdateCommercialOrganizationPipeline import (
        UpdateCommercialOrganizationPipeline,
        UpdateCommercialOrganizationPipelineConfiguration,
    )
    from naas_abi.pipelines.UpdateLegalNamePipeline import (
        UpdateLegalNamePipeline,
        UpdateLegalNamePipelineConfiguration,
    )
    from naas_abi.pipelines.UpdateLinkedInPagePipeline import (
        UpdateLinkedInPagePipeline,
        UpdateLinkedInPagePipelineConfiguration,
    )
    from naas_abi.pipelines.UpdatePersonPipeline import (
        UpdatePersonPipeline,
        UpdatePersonPipelineConfiguration,
    )
    from naas_abi.pipelines.UpdateSkillPipeline import (
        UpdateSkillPipeline,
        UpdateSkillPipelineConfiguration,
    )
    from naas_abi.pipelines.UpdateTickerPipeline import (
        UpdateTickerPipeline,
        UpdateTickerPipelineConfiguration,
    )
    from naas_abi.pipelines.UpdateWebsitePipeline import (
        UpdateWebsitePipeline,
        UpdateWebsitePipelineConfiguration,
    )

    specialized_pipelines = [
        (UpdatePersonPipeline, UpdatePersonPipelineConfiguration),
        (UpdateSkillPipeline, UpdateSkillPipelineConfiguration),
        (
            UpdateCommercialOrganizationPipeline,
            UpdateCommercialOrganizationPipelineConfiguration,
        ),
        (UpdateLinkedInPagePipeline, UpdateLinkedInPagePipelineConfiguration),
        (UpdateWebsitePipeline, UpdateWebsitePipelineConfiguration),
        (UpdateLegalNamePipeline, UpdateLegalNamePipelineConfiguration),
        (UpdateTickerPipeline, UpdateTickerPipelineConfiguration),
    ]
    for Pipeline, Configuration in specialized_pipelines:
        tools += Pipeline(Configuration(MODULE.engine.services.triple_store)).as_tools()

    # Add search organizations tools
    from naas_abi_core.modules.templatablesparqlquery import (
        ABIModule as TemplatableSparqlQueryABIModule,
    )

    ontology_tools: list = [
        "search_class",
        "count_instances_by_class",
        "get_individuals_from_class",
        "search_individuals_from_class",
        "add_individual",
        "update_data_property",
        "merge_individuals",
        "remove_individuals",
    ]
    sparql_query_tools_list = TemplatableSparqlQueryABIModule.get_instance().get_tools(
        ontology_tools
    )
    tools += sparql_query_tools_list

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return KnowledgeGraphBuilderAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=[],
        state=agent_shared_state,
        configuration=agent_configuration,
    )


class KnowledgeGraphBuilderAgent(Agent):
    pass
