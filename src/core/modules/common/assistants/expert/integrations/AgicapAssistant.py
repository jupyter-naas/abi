from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import AgicapIntegration
from src.core.modules.common.integrations.AgicapIntegration import AgicapIntegrationConfiguration
from src.core.modules.common.assistants.foundation.SupportAssistant import create_support_agent
from src.core.modules.common.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "An Agicap Assistant with access to Agicap Integration tools."
AVATAR_URL = "https://logo.clearbit.com/agicap.com"
SYSTEM_PROMPT = f"""
You are an Agicap Assistant with access to AgicapIntegration tools.
If you don't have access to any tool, ask the user to set their AGICAP_API_KEY in .env file.
Always be clear and professional in your communication while helping users interact with Agicap services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_agicap_agent():
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
        on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
        system_prompt=SYSTEM_PROMPT
    )
    model = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []
    
    if secret.get('AGICAP_USERNAME') and secret.get('AGICAP_PASSWORD') and secret.get('AGICAP_BEARER_TOKEN') and secret.get('AGICAP_CLIENT_ID') and secret.get('AGICAP_CLIENT_SECRET') and secret.get('AGICAP_API_TOKEN'):    
        integration_config = AgicapIntegrationConfiguration(
            username=secret.get('AGICAP_USERNAME'),
            password=secret.get('AGICAP_PASSWORD'),
            bearer_token=secret.get('AGICAP_BEARER_TOKEN'),
            client_id=secret.get('AGICAP_CLIENT_ID'),
            client_secret=secret.get('AGICAP_CLIENT_SECRET'),
            api_token=secret.get('AGICAP_API_TOKEN')
        )
        tools += AgicapIntegration.as_tools(integration_config)

    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="agicap_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 