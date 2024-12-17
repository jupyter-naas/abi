from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import ClockifyIntegration
from src.integrations.ClockifyIntegration import ClockifyIntegrationConfiguration
from src.assistants.foundation.SupportAssitant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Clockify Assistant with access to Clockify Integration tools."
AVATAR_URL = "https://clockify.me/assets/images/clockify-logo.svg"
SYSTEM_PROMPT = f"""
You are a Clockify Assistant with access to Clockify Integration tools.
If you don't have access to any tool, ask the user to set their access token in .env file.
Always be clear and professional in your communication while helping users interact with Clockify services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_clockify_agent():
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
    if secret.get('CLOCKIFY_API_KEY'):    
        clockify_integration_config = ClockifyIntegrationConfiguration(api_key=secret.get('CLOCKIFY_API_KEY'))
        tools += ClockifyIntegration.as_tools(clockify_integration_config)

    # Add support assistant
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration).as_tool(
        name="support_assistant", 
        description="Use to get any feedbacks/bugs or needs from user."
    )
    tools.append(support_assistant)
    
    return Agent(
        name="clockify_assistant",
        description="Use to manage Clockify workspace, projects and tasks",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 