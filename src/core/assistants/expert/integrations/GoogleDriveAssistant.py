from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import GoogleDriveIntegration
from src.core.integrations.GoogleDriveIntegration import GoogleDriveIntegrationConfiguration
from src.core.assistants.foundation.SupportAssistant import create_support_assistant
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Google Drive Assistant for managing files and folders in Google Drive."
AVATAR_URL = "https://image.similarpng.com/very-thumbnail/2020/12/Google-drive-logo-Premium-vector--PNG.png"
SYSTEM_PROMPT = f"""
You are a Google Drive Assistant with access to GoogleDriveIntegration tools.
If you don't have access to any tool, ask the user to set up their Google Drive credentials in .env file.
Always be clear and professional in your communication while helping users manage their Google Drive content.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

You can help users with:
- Uploading and downloading files
- Creating and managing folders
- Searching for files and folders
- Managing file permissions and sharing
- Listing files and folders
- Getting file metadata

Remember to:
- Confirm operations that modify or delete content
- Provide clear feedback about operation results
- Handle file paths and IDs appropriately
- Explain sharing settings when relevant

{RESPONSIBILITIES_PROMPT}
"""

def create_google_drive_agent():
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
    if secret.get('GOOGLE_DRIVE_CREDENTIALS'):    
        integration_config = GoogleDriveIntegrationConfiguration(
            credentials=secret.get('GOOGLE_DRIVE_CREDENTIALS'),
            token_path=secret.get('GOOGLE_DRIVE_TOKEN_PATH', 'drive_token.json')
        )
        tools += GoogleDriveIntegration.as_tools(integration_config)

    # Add support assistant
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_assistant.as_tools()
    
    return Agent(
        name="google_drive_assistant",
        description="Use to manage Google Drive files, folders, and sharing",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 