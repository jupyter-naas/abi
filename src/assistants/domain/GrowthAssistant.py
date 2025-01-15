from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from src.assistants.foundation.SupportAssistant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import HubSpotIntegration
from src.integrations.HubSpotIntegration import HubSpotIntegrationConfiguration
from src.integrations.LinkedInIntegration import LinkedInIntegrationConfiguration
from src.workflows.growth_assistant.LinkedinPostsInteractionsWorkflow import LinkedinPostsInteractionsWorkflow, LinkedinPostsInteractionsWorkflowConfiguration

DESCRIPTION = "A Growth Assistant that analyzes content interactions and helps qualify marketing leads."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/growth_marketing.png"
SYSTEM_PROMPT = f"""
You are a Growth Assistant with access to a list of interactions from content that enable users to get marketing qualified contacts.
Your role is to manage and optimize the list of people who interacted with the content, ensuring to extract only the most qualified contacts to feed the sales representatives.

Start each conversation by:
1. Introducing yourself
2. Providing a brief analysis of 'Abi' new interactions (max 3 bullet points)
3. Displaying this image showing contacts reached over weeks:
   ![Contacts Reached](https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/growth_trend.png)

Always:
1. Use LinkedIn to get insights from LinkedIn posts, profiles and organizations.
2. Use HubSpot data for contact management and qualification
3. Provide structured, markdown-formatted responses
4. Include metrics and performance indicators in your analysis
5. Be casual but professional in your communication

RESPONSIBILITIES
-----------------
{RESPONSIBILITIES_PROMPT}
"""

def create_growth_assistant(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model 
    model = ChatOpenAI(
        model="gpt-4o-mini", 
        temperature=0, 
        api_key=secret.get('OPENAI_API_KEY')
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
            on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Add tools
    if (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        linkedin_integration_config = LinkedInIntegrationConfiguration(li_at=li_at, jsessionid=jsessionid)
        linkedin_posts_interactions_workflow = LinkedinPostsInteractionsWorkflow(LinkedinPostsInteractionsWorkflowConfiguration(
            linkedin_integration_config=linkedin_integration_config
        ))
        tools += linkedin_posts_interactions_workflow.as_tools()
    
    if hubspot_access_token := secret.get('HUBSPOT_ACCESS_TOKEN'):
        tools += HubSpotIntegration.as_tools(HubSpotIntegrationConfiguration(access_token=hubspot_access_token))
    
    # Add agents
    agents.append(create_support_assistant(AgentSharedState(thread_id=1), agent_configuration))
    
    return GrowthAssistant(
        name="growth_assistant", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class GrowthAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "growth", 
        name: str = "Growth Assistant", 
        description: str = "API endpoints to call the Growth assistant completion.", 
        description_stream: str = "API endpoints to call the Growth assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)