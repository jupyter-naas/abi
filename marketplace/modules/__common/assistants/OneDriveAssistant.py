from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from src import secret
from src.core.apps.terminal_agent.terminal_style import (
    print_tool_usage,
    print_tool_response,
)
from src.core.modules.support.agents.SupportAssistant import (
    create_agent as create_support_agent,
)
from src.core.modules.common.integrations import OneDriveIntegration
from src.core.modules.common.integrations.OneDriveIntegration import (
    OneDriveIntegrationConfiguration,
)

DESCRIPTION = (
    "A OneDrive Assistant for managing files and folders in Microsoft OneDrive."
)
AVATAR_URL = "https://upload.wikimedia.org/wikipedia/commons/3/3c/Microsoft_Office_OneDrive_%282019%E2%80%93present%29.svg"
SYSTEM_PROMPT = """
You are a OneDrive Assistant with access to OneDriveIntegration tools.
If you don't have access to any tool, ask the user to set it's access token in .env file following the procedure at https://learn.microsoft.com/en-us/onedrive/developer/rest-api/getting-started/?view=odsp-graph-online

Your responsibilities:
1. Understand user requests and match them to appropriate OneDriveIntegration tools
2. Before executing any tool, you MUST validate all required input arguments with the user in clear, human-readable terms
3. If no suitable tool exists for the request:
   - Ask if the user would like to create a new tool
   - Direct them to the support agent for tool creation

Always be clear and professional in your communication while helping users interact with their OneDrive content.
"""


def create_onedrive_agent():
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]["name"]),
        on_tool_response=lambda message: print_tool_response(f"\n{message.content}"),
        system_prompt=SYSTEM_PROMPT,
    )
    model = ChatOpenAI(
        model="gpt-4o", temperature=0, api_key=secret.get("OPENAI_API_KEY")
    )
    tools = []

    # Add integration based on available credentials
    if secret.get("ONE_DRIVE_ACCESS_TOKEN"):
        one_drive_integration_config = OneDriveIntegrationConfiguration(
            access_token=secret.get("ONE_DRIVE_ACCESS_TOKEN")
        )
        tools += OneDriveIntegration.as_tools(one_drive_integration_config)

    # Add support assistant
    support_agent = create_support_agent(
        AgentSharedState(thread_id=2), agent_configuration
    )
    tools += support_agent.as_tools()

    return Agent(
        name="onedrive_agent",
        description="Use to manage OneDrive files, folders and more",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver(),
    )
