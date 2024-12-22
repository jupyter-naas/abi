from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import GoogleCalendarIntegration
from src.integrations.GoogleCalendarIntegration import GoogleCalendarIntegrationConfiguration
from src.assistants.foundation.SupportAssistant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Google Calendar Assistant for managing calendar events and schedules."
AVATAR_URL = "https://logo.clearbit.com/calendar.google.com"
SYSTEM_PROMPT = f"""
You are a Google Calendar Assistant with access to GoogleCalendarIntegration tools.
If you don't have access to any tool, ask the user to set up their Google Calendar credentials in .env file.
Always be clear and professional in your communication while helping users manage their calendar.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_google_calendar_agent():
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
    if secret.get('GOOGLE_CALENDAR_CREDENTIALS'):    
        integration_config = GoogleCalendarIntegrationConfiguration(
            credentials=secret.get('GOOGLE_CALENDAR_CREDENTIALS'),
            token_path=secret.get('GOOGLE_CALENDAR_TOKEN_PATH', 'calendar_token.json')
        )
        tools += GoogleCalendarIntegration.as_tools(integration_config)

    # Add support assistant
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_assistant.as_tools()
    
    return Agent(
        name="google_calendar_assistant",
        description="Use to manage Google Calendar events and schedules",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 