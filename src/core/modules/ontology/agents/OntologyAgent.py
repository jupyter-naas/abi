from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from langchain_openai import ChatOpenAI
from fastapi import APIRouter
from src import secret, services
from src.core.modules.ontology.pipelines.AddSkilltoPersonPipeline import AddSkilltoPersonPipeline, AddSkilltoPersonPipelineConfiguration
from src.core.modules.ontology.workflows.GetPersonSkillsWorkflow import GetPersonSkillsWorkflow, GetPersonSkillsConfigurationWorkflow

NAME = "Ontology Agent"
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
DESCRIPTION = "A Ontology Agent that helps users to work with ontologies."
SYSTEM_PROMPT = f"""
You are a Ontology Agent that helps users to work with ontologies.
"""
SUGGESTIONS = []

def create_agent(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    # Init
    tools = []
    agents = []
    ontology_store = services.ontology_store_service

    # Set model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE, 
        api_key=secret.get('OPENAI_API_KEY')
    )

    # Add pipelines
    add_skill_to_person_pipeline = AddSkilltoPersonPipeline(AddSkilltoPersonPipelineConfiguration(ontology_store))
    tools += add_skill_to_person_pipeline.as_tools()

    # Add workflows
    get_person_skills_workflow = GetPersonSkillsWorkflow(GetPersonSkillsConfigurationWorkflow(ontology_store))
    tools += get_person_skills_workflow.as_tools()
    
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