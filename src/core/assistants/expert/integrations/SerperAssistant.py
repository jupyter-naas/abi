from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import SerperIntegration
from src.core.integrations.SerperIntegration import SerperIntegrationConfiguration
from src.core.assistants.foundation.SupportAssistant import create_support_assistant
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Serper Assistant for advanced search operations and data retrieval."
AVATAR_URL = "https://res.cloudinary.com/apideck/image/upload/v1679535605/icons/serper-dev.png"
SYSTEM_PROMPT = f"""
You are a Serper Assistant with access to SerperIntegration tools.
If you don't have access to any tool, ask the user to set their SERPER_API_KEY in .env file.
Always be clear and professional in your communication while helping users perform search operations.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_serper_agent():
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
        on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
        system_prompt=SYSTEM_PROMPT
    )
    model = ChatOpenAI(
        model="gpt-4",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []
    
    # Add integration based on available credentials
    if secret.get('SERPER_API_KEY'):    
        integration_config = SerperIntegrationConfiguration(
            api_key=secret.get('SERPER_API_KEY')
        )
        tools += SerperIntegration.as_tools(integration_config)

    # Add support assistant
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_assistant.as_tools()
    
    return Agent(
        name="serper_assistant",
        description="Use to perform advanced search operations and data retrieval",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 