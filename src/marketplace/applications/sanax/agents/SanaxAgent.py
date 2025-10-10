from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    
)
from typing import Optional

NAME = "Sanax"
DESCRIPTION = "Sanax agent to extract sales navigator data from LinkedIn."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
SYSTEM_PROMPT = """# ROLE
You are Sanax, an AI agent specialized in extracting and analyzing LinkedIn Sales Navigator data.

# OBJECTIVE
Help users access and analyze LinkedIn Sales Navigator data.

# CONTEXT
You receive messages from users or the supervisor agent.

# TASKS
- Search for people by position title
- Look up LinkedIn profile URLs
- Find company information
- Analyze employment relationships
- Answer questions about available data

# TOOLS
[TOOLS]

# OPERATING GUIDELINES
1. Focus on accurate data extraction
2. Return structured, relevant information
3. Respect data privacy requirements
4. Maintain professional communication

# CONSTRAINTS
- Only access authorized data
- Follow LinkedIn usage terms
- Protect sensitive information
- Provide factual responses
"""
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> IntentAgent:
    # Define model based on AI_MODE
    from src import secret
    ai_mode = secret.get("AI_MODE")  # Default to cloud if not set
    if ai_mode == "cloud":
        from src.core.__templates__.models.gpt_4_1 import model as cloud_model
        selected_model = cloud_model.model
    else:
        from src.core.__templates__.models.qwen3_8b import model as local_model
        selected_model = local_model.model
    
    # Define tools
    from src.marketplace.applications.sanax.pipelines.SanaxLinkedInSalesNavigatorExtractorPipeline import (
        SanaxLinkedInSalesNavigatorExtractorPipeline,
        SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration
    )
    from src import services
    tools: list = [
        SanaxLinkedInSalesNavigatorExtractorPipeline(
            configuration=SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration(
                triple_store=services.triple_store_service
            )
        )
    ]

    ## Get tools from intentmapping
    from src.core.templatablesparqlquery import get_tools
    templates_tools = [
        "get_person_info",
        "get_company_employees",
        "get_role_holders",
        "get_person_linkedin_url",
        "get_company_linkedin_url",
        "get_persons_by_name_prefix",
        "get_people_by_location",
        "count_people_by_location",
        "count_people_by_company",
        "get_most_recent_job_starts",
        "get_oldest_job_starts",
        "get_longest_tenure",
    ]
    tools += get_tools(templates_tools)
    
    # Define agents
    agents: list = []

    # Define intents
    intents: list = [
        # Person information queries
        Intent(intent_value="what do you know about", intent_type=IntentType.RAW, intent_target="get_person_info"),
        Intent(intent_value="tell me about", intent_type=IntentType.RAW, intent_target="get_person_info"),
        Intent(intent_value="who is", intent_type=IntentType.RAW, intent_target="get_person_info"),
        Intent(intent_value="information about", intent_type=IntentType.RAW, intent_target="get_person_info"),
        Intent(intent_value="details about", intent_type=IntentType.RAW, intent_target="get_person_info"),
        Intent(intent_value="profile of", intent_type=IntentType.RAW, intent_target="get_person_info"),
        
        # Company employees queries
        Intent(intent_value="who works at", intent_type=IntentType.RAW, intent_target="get_company_employees"),
        Intent(intent_value="who is working for", intent_type=IntentType.RAW, intent_target="get_company_employees"),
        Intent(intent_value="employees at", intent_type=IntentType.RAW, intent_target="get_company_employees"),
        Intent(intent_value="staff at", intent_type=IntentType.RAW, intent_target="get_company_employees"),
        Intent(intent_value="people working at", intent_type=IntentType.RAW, intent_target="get_company_employees"),
        Intent(intent_value="team members at", intent_type=IntentType.RAW, intent_target="get_company_employees"),
        Intent(intent_value="show me employees of", intent_type=IntentType.RAW, intent_target="get_company_employees"),
        
        # Role/position holders queries
        Intent(intent_value="who has the role", intent_type=IntentType.RAW, intent_target="get_role_holders"),
        Intent(intent_value="who is a", intent_type=IntentType.RAW, intent_target="get_role_holders"),
        Intent(intent_value="find all", intent_type=IntentType.RAW, intent_target="get_role_holders"),
        Intent(intent_value="who holds the position", intent_type=IntentType.RAW, intent_target="get_role_holders"),
        Intent(intent_value="people with role", intent_type=IntentType.RAW, intent_target="get_role_holders"),
        Intent(intent_value="show me all", intent_type=IntentType.RAW, intent_target="get_role_holders"),
        Intent(intent_value="list all", intent_type=IntentType.RAW, intent_target="get_role_holders"),
        
        # LinkedIn URL queries for persons
        Intent(intent_value="linkedin profile of", intent_type=IntentType.RAW, intent_target="get_person_linkedin_url"),
        Intent(intent_value="linkedin url for", intent_type=IntentType.RAW, intent_target="get_person_linkedin_url"),
        Intent(intent_value="linkedin link for", intent_type=IntentType.RAW, intent_target="get_person_linkedin_url"),
        Intent(intent_value="find linkedin profile", intent_type=IntentType.RAW, intent_target="get_person_linkedin_url"),
        Intent(intent_value="get linkedin url", intent_type=IntentType.RAW, intent_target="get_person_linkedin_url"),
        
        # LinkedIn URL queries for companies
        Intent(intent_value="company linkedin", intent_type=IntentType.RAW, intent_target="get_company_linkedin_url"),
        Intent(intent_value="linkedin page for", intent_type=IntentType.RAW, intent_target="get_company_linkedin_url"),
        Intent(intent_value="linkedin company page", intent_type=IntentType.RAW, intent_target="get_company_linkedin_url"),
        Intent(intent_value="find company linkedin", intent_type=IntentType.RAW, intent_target="get_company_linkedin_url"),
        
        # Name prefix searches
        Intent(intent_value="people named", intent_type=IntentType.RAW, intent_target="get_persons_by_name_prefix"),
        Intent(intent_value="names starting with", intent_type=IntentType.RAW, intent_target="get_persons_by_name_prefix"),
        Intent(intent_value="find people with name", intent_type=IntentType.RAW, intent_target="get_persons_by_name_prefix"),
        Intent(intent_value="who has name starting", intent_type=IntentType.RAW, intent_target="get_persons_by_name_prefix"),
        Intent(intent_value="search for names", intent_type=IntentType.RAW, intent_target="get_persons_by_name_prefix"),
        
        # Location-based queries
        Intent(intent_value="who is in", intent_type=IntentType.RAW, intent_target="get_people_by_location"),
        Intent(intent_value="people in", intent_type=IntentType.RAW, intent_target="get_people_by_location"),
        Intent(intent_value="who lives in", intent_type=IntentType.RAW, intent_target="get_people_by_location"),
        Intent(intent_value="located in", intent_type=IntentType.RAW, intent_target="get_people_by_location"),
        Intent(intent_value="find people in", intent_type=IntentType.RAW, intent_target="get_people_by_location"),
        Intent(intent_value="who is based in", intent_type=IntentType.RAW, intent_target="get_people_by_location"),
        
        # Location count queries
        Intent(intent_value="how many people in", intent_type=IntentType.RAW, intent_target="count_people_by_location"),
        Intent(intent_value="count people in", intent_type=IntentType.RAW, intent_target="count_people_by_location"),
        Intent(intent_value="number of people in", intent_type=IntentType.RAW, intent_target="count_people_by_location"),
        Intent(intent_value="total people in", intent_type=IntentType.RAW, intent_target="count_people_by_location"),
        
        # Company count queries
        Intent(intent_value="how many people work at", intent_type=IntentType.RAW, intent_target="count_people_by_company"),
        Intent(intent_value="count employees at", intent_type=IntentType.RAW, intent_target="count_people_by_company"),
        Intent(intent_value="number of employees at", intent_type=IntentType.RAW, intent_target="count_people_by_company"),
        Intent(intent_value="total employees at", intent_type=IntentType.RAW, intent_target="count_people_by_company"),
        Intent(intent_value="company size of", intent_type=IntentType.RAW, intent_target="count_people_by_company"),
        
        # Recent job starts
        Intent(intent_value="who started recently", intent_type=IntentType.RAW, intent_target="get_most_recent_job_starts"),
        Intent(intent_value="recent hires", intent_type=IntentType.RAW, intent_target="get_most_recent_job_starts"),
        Intent(intent_value="newest employees", intent_type=IntentType.RAW, intent_target="get_most_recent_job_starts"),
        Intent(intent_value="latest job starts", intent_type=IntentType.RAW, intent_target="get_most_recent_job_starts"),
        Intent(intent_value="who joined recently", intent_type=IntentType.RAW, intent_target="get_most_recent_job_starts"),
        Intent(intent_value="most recent job changes", intent_type=IntentType.RAW, intent_target="get_most_recent_job_starts"),
        
        # Oldest job starts
        Intent(intent_value="who started earliest", intent_type=IntentType.RAW, intent_target="get_oldest_job_starts"),
        Intent(intent_value="oldest employees", intent_type=IntentType.RAW, intent_target="get_oldest_job_starts"),
        Intent(intent_value="earliest hires", intent_type=IntentType.RAW, intent_target="get_oldest_job_starts"),
        Intent(intent_value="who joined first", intent_type=IntentType.RAW, intent_target="get_oldest_job_starts"),
        Intent(intent_value="longest serving", intent_type=IntentType.RAW, intent_target="get_oldest_job_starts"),
        
        # Longest tenure
        Intent(intent_value="who has worked longest", intent_type=IntentType.RAW, intent_target="get_longest_tenure"),
        Intent(intent_value="longest tenure", intent_type=IntentType.RAW, intent_target="get_longest_tenure"),
        Intent(intent_value="most experienced", intent_type=IntentType.RAW, intent_target="get_longest_tenure"),
        Intent(intent_value="senior employees", intent_type=IntentType.RAW, intent_target="get_longest_tenure"),
        Intent(intent_value="veteran employees", intent_type=IntentType.RAW, intent_target="get_longest_tenure"),
    ]

    # Set configuration
    print(tools)
    system_prompt = SYSTEM_PROMPT.replace("[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools]))
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=system_prompt,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return SanaxAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=selected_model,
        tools=tools, 
        agents=agents,
        intents=intents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=None
    )

class SanaxAgent(IntentAgent):
    pass
