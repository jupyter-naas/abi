from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import GoogleSheetsIntegration
from src.core.integrations.GoogleSheetsIntegration import GoogleSheetsIntegrationConfiguration
from src.core.assistants.foundation.SupportAssistant import create_support_agent
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Google Sheets Assistant for managing spreadsheet operations."
AVATAR_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Google_Sheets_logo_%282014-2020%29.svg/1498px-Google_Sheets_logo_%282014-2020%29.svg.png"
SYSTEM_PROMPT = f"""
You are a Google Sheets Assistant with access to GoogleSheetsIntegration tools.
If you don't have access to any tool, ask the user to set up their Google Sheets credentials in .env file.
Always be clear and professional in your communication while helping users manage their spreadsheets.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_google_sheets_agent():
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
    if secret.get('GOOGLE_SHEETS_CREDENTIALS'):    
        integration_config = GoogleSheetsIntegrationConfiguration(
            credentials=secret.get('GOOGLE_SHEETS_CREDENTIALS'),
            token_path=secret.get('GOOGLE_SHEETS_TOKEN_PATH', 'token.json')
        )
        tools += GoogleSheetsIntegration.as_tools(integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_agent.as_tools()
    
    return Agent(
        name="google_sheets_agent",
        description="Use to manage Google Sheets operations and spreadsheet tasks",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 