from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import NaasIntegration
from src.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.assistants.foundation.SupportAssitant import create_support_assistant

DESCRIPTION = "A Naas Assistant with access to Naas Integration tools."
AVATAR_URL = "https://raw.githubusercontent.com/jupyter-naas/awesome-notebooks/refs/heads/master/.github/assets/logos/Naas.png"
SYSTEM_PROMPT = """
You are a Naas Assistant with access to NaasIntegration tools.
If you don't have access to any tool, ask the user to set their access token in .env file.

Your responsibilities:
1. Understand user requests and match them to appropriate NaasIntegration tools
2. Before executing any tool, you MUST validate all required input arguments with the user in clear, human-readable terms
3. If no suitable tool exists for the request:
   - Ask if the user would like to create a new tool
   - Direct them to the support agent for tool creation

Always be clear and professional in your communication while helping users interact with Naas services.
"""

def create_naas_agent():
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
    
    # Add integration based on available credentials
    if secret.get('NAAS_API_KEY'):    
        naas_integration_config = NaasIntegrationConfiguration(api_key=secret.get('NAAS_API_KEY'))
        tools += NaasIntegration.as_tools(naas_integration_config)

    # Add support assistant
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration).as_tool(
        name="support_assistant", 
        description="Use to get any feedbacks/bugs or needs from user."
    )
    tools.append(support_assistant)
    
    return Agent(
        model,
        tools, 
        state=AgentSharedState(thread_id=1), 
        configuration=agent_configuration, 
        memory=MemorySaver()
    )