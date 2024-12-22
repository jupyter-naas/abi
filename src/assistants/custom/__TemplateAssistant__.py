from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import YourIntegration  # Import relevant integrations
from src.integrations.YourIntegration import YourIntegrationConfiguration
from src.assistants.foundation.SupportAssistant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "Description of your assistant and its capabilities."
AVATAR_URL = "URL to assistant's avatar image"
SYSTEM_PROMPT = f"""
You are [Assistant Name] with access to [Integration] tools.
[Specific instructions about credentials/tokens if needed]
[Specific behavioral instructions]

{RESPONSIBILITIES_PROMPT}
"""

def create_your_agent():
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
        on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
        system_prompt=SYSTEM_PROMPT
    )
    model = ChatOpenAI(
        model="gpt-4",  # or whatever model you're using
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []
    
    # Add integration based on available credentials
    if secret.get('YOUR_API_KEY'):    
        integration_config = YourIntegrationConfiguration(api_key=secret.get('YOUR_API_KEY'))
        tools += YourIntegration.as_tools(integration_config)

    # Add support assistant
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_assistant.as_tools()
    
    return Agent(
        name="your_assistant_name",
        description="Description for tool listing",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 