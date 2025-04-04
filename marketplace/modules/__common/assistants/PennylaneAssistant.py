from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import PennylaneIntegration
from src.core.modules.common.integrations.PennylaneIntegration import PennylaneIntegrationConfiguration
from src.core.modules.support.agents.SupportAssistant import create_agent as create_support_agent
from src.core.modules.common.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Pennylane Assistant for managing accounting and financial operations."
AVATAR_URL = "https://logo.clearbit.com/pennylane.tech"
SYSTEM_PROMPT = f"""
You are a Pennylane Assistant with access to PennylaneIntegration tools.
If you don't have access to any tool, ask the user to set their PENNYLANE_API_TOKEN in .env file.
Always be clear and professional in your communication while helping users manage their accounting data.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_pennylane_agent():
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
    if secret.get('PENNYLANE_API_TOKEN'):    
        integration_config = PennylaneIntegrationConfiguration(
            api_key=secret.get('PENNYLANE_API_TOKEN')
        )
        tools += PennylaneIntegration.as_tools(integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="pennylane_agent",
        description="Use to manage Pennylane accounting and financial operations",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 