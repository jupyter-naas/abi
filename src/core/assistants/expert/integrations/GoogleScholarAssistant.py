from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import GoogleScholarIntegration
from src.core.integrations.GoogleScholarIntegration import GoogleScholarConfiguration
from src.core.assistants.foundation.SupportAssistant import create_support_assistant
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Google Scholar Assistant for searching academic publications and author profiles."
AVATAR_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Google_Scholar_logo.svg/2048px-Google_Scholar_logo.svg.png"
SYSTEM_PROMPT = f"""
You are a Google Scholar Assistant with access to GoogleScholarIntegration tools.
You help users search for academic publications and author profiles on Google Scholar.
Always be clear and professional in your communication while helping users find academic resources.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

You can help users with:
- Searching for academic publications by topic, title, or author
- Finding author profiles and their academic metrics
- Getting citation counts and publication details
- Exploring research in specific fields
- Finding recent publications in a given area

Remember to:
- Suggest relevant search terms when queries are too broad
- Explain citation metrics when providing author profiles
- Help users refine their searches for better results
- Provide context about publication venues and impact

{RESPONSIBILITIES_PROMPT}
"""

def create_google_scholar_assistant(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None
) -> Agent:
    """Create a Google Scholar assistant."""
    
    # Initialize tools
    tools = []
    
    # Add Google Scholar tools
    google_scholar_config = GoogleScholarConfiguration()
    tools += GoogleScholarIntegration.as_tools(google_scholar_config)
    
    # Add support tools
    support_agent = create_support_assistant()
    tools += support_agent.tools
    
    # Create the agent
    return Agent(
        "GoogleScholar Assistant",
        ChatOpenAI(
            model=agent_configuration.model if agent_configuration else "gpt-4-turbo-preview",
            temperature=0.7,
        ),
        tools,
        SYSTEM_PROMPT,
        agent_shared_state if agent_shared_state else AgentSharedState(),
        MemorySaver() if agent_configuration and agent_configuration.memory else None,
    ) 