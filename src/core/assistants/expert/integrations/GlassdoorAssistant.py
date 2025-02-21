from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import GlassdoorIntegration
from src.core.integrations.GlassdoorIntegration import GlassdoorIntegrationConfiguration
from src.core.assistants.foundation.SupportAssistant import create_support_agent
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Glassdoor Assistant with access to Glassdoor Integration tools."
AVATAR_URL = "https://www.glassdoor.com/app/static/img/partners/glassdoor-logo-icon.svg"
SYSTEM_PROMPT = f"""
You are a Glassdoor Assistant with access to Glassdoor Integration tools.
If you don't have access to any tool, ask the user to set their partner_id and api_key in .env file.
Always be clear and professional in your communication while helping users interact with Glassdoor services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_glassdoor_agent():
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
        on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
        system_prompt=SYSTEM_PROMPT
    )
    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []
    
    # Add integration based on available credentials
    if secret.get('GLASSDOOR_PARTNER_ID') and secret.get('GLASSDOOR_API_KEY'):    
        glassdoor_integration_config = GlassdoorIntegrationConfiguration(
            partner_id=secret.get('GLASSDOOR_PARTNER_ID'),
            api_key=secret.get('GLASSDOOR_API_KEY')
        )
        tools += GlassdoorIntegration.as_tools(glassdoor_integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()   
    
    return Agent(
        name="glassdoor_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        state=AgentSharedState(thread_id=1), 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 