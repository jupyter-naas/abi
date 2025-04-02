from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from langchain_openai import ChatOpenAI
from fastapi import APIRouter
from src import secret, services
from src.core.modules.ontology.pipelines.AddIndividualPipeline import AddIndividualPipeline, AddIndividualPipelineConfiguration
from src.core.modules.ontology.workflows.GetClassWorkflow import GetClassWorkflow, GetClassConfigurationWorkflow
from src.core.modules.ontology.pipelines.AddSkilltoPersonPipeline import AddSkilltoPersonPipeline, AddSkilltoPersonPipelineConfiguration
from src.core.modules.ontology.workflows.GetPersonsAssociatedwithSkillsWorkflow import GetPersonsAssociatedwithSkillsWorkflow, GetPersonsAssociatedwithSkillsConfigurationWorkflow
from src.core.modules.ontology.workflows.GetSkillsAssociatedwithPersonsWorkflow import GetSkillsAssociatedwithPersonsWorkflow, GetSkillsAssociatedwithPersonsConfigurationWorkflow

NAME = "Ontology Agent"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
DESCRIPTION = "A Ontology Agent that helps users to work with ontologies."
SYSTEM_PROMPT = f"""You are a Ontology Agent that helps users to work with ontologies.
You must always use your tools to perform the actions you need to do.
You can't use your internal knowledge.

Before adding or updating an individual in an ontology:
- Search the class that could be used to add the individual using the `ontology_search_class` tool.
- Search if the individual already exists using the `ontology_search_individual` tool.
- If the individual doesn't exist, add it to the ontology using the `ontology_add_individual` tool.
"""
SUGGESTIONS = [
    {
        "label": "Learn About Ontology",
        "value": "What's the ontology about?"
    },
    {
        "label": "Ontology Object Explorer",
        "value": "What is a {{Github Issue}} in the ontology?"
    },
    {
        "label": "Add Data To Ontology",
        "value": "Add the following data in ontology: {{Data}}"
    }
]

def create_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []
    triple_store = services.triple_store_service

    # Set model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE, 
        api_key=secret.get('OPENAI_API_KEY')
    )

    # Add pipelines
    add_individual_pipeline = AddIndividualPipeline(AddIndividualPipelineConfiguration(triple_store))
    tools += add_individual_pipeline.as_tools()

    add_skill_to_person_pipeline = AddSkilltoPersonPipeline(AddSkilltoPersonPipelineConfiguration(triple_store))
    tools += add_skill_to_person_pipeline.as_tools()

    # Add workflows
    get_class_workflow = GetClassWorkflow(GetClassConfigurationWorkflow(triple_store))
    tools += get_class_workflow.as_tools()

    get_persons_associated_with_skills_workflow = GetPersonsAssociatedwithSkillsWorkflow(GetPersonsAssociatedwithSkillsConfigurationWorkflow(triple_store))
    tools += get_persons_associated_with_skills_workflow.as_tools()

    get_skills_associated_with_persons_workflow = GetSkillsAssociatedwithPersonsWorkflow(GetSkillsAssociatedwithPersonsConfigurationWorkflow(triple_store))
    tools += get_skills_associated_with_persons_workflow.as_tools()

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    
    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return OntologyAgent(
        name="ontology_agent", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    )

class OntologyAgent(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "ontology", 
        name: str = "Ontology Agent", 
        description: str = "API endpoints to call the Ontology agent completion.", 
        description_stream: str = "API endpoints to call the Ontology agent stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)