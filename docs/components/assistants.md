# Agents Architecture

Agents in ABI are AI agents powered by Large Language Models (LLMs) that provide domain-specific expertise and capabilities. They serve as the primary interface between users and the ABI system's capabilities.

## Design Philosophy

Agents are designed to be:
1. **Role-based**: Each assistant has a specific role with defined responsibilities
2. **Tool-enhanced**: Agents use tools created from workflows, pipelines, and integrations
3. **Stateful**: Agents maintain conversation history and context 
4. **Configurable**: Customizable through system prompts and model parameters

## Assistant Structure

The Assistant is a key component in the ABI system, designed to interact with users and provide domain-specific expertise. It consists of several important parts:

1. **Agent Configuration**: This section defines how the assistant is set up. It includes:
   - **LLM Configuration**: Settings related to the Large Language Model that powers the assistant.
   - **System Prompt**: A predefined message that guides the assistant's behavior and role.
   - **Tools**: Various tools that the assistant can use to perform tasks.
   - **Memory Configuration**: Settings that determine how the assistant remembers past interactions.

2. **Agent Implementation**: This part focuses on how the assistant operates. It includes:
   - **Conversation Handling**: The process of managing dialogues with users.
   - **Tool Dispatching**: The mechanism for using the tools available to the assistant when needed.
   - **Memory Management**: How the assistant keeps track of conversation history and context.

3. **Tools**: These are specialized resources that the assistant can utilize, which include:
   - **Workflow Tools**: Tools that help manage workflows.
   - **Pipeline Tools**: Tools designed for processing data through pipelines.
   - **Integration Tools**: Tools that connect the assistant with external services or APIs.

Overall, the Assistant is structured to effectively manage interactions, utilize various tools, and maintain context throughout conversations.


## Key Components

1. **Agent Configuration**:
   - Defines the agent's identity, capabilities, and behavior
   - Specifies LLM model, temperature, and other parameters
   - Includes system prompt that defines the assistant's role and behavior
   - Configures memory management and tool access

2. **Agent Implementation**:
   - Instance of the `Agent` class from ABI's agent service
   - Manages conversation flow and context
   - Handles user inputs and generates responses
   - Dispatches tool calls as needed

3. **Tools**:
   - Structured tools from workflows, pipelines, and integrations
   - Provide specific capabilities to the assistant
   - Define input parameters and validation rules
   - Return structured responses that the assistant can interpret

## Implementation Pattern

ABI agents follow a standardized implementation pattern:

```python
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_openai import ChatOpenAI
from src.core.modules.common.integrations import GithubIntegration, NotionIntegration
from src.core.modules.common.integrations.GithubIntegration import GithubIntegrationConfiguration
from src.core.modules.common.integrations.NotionIntegration import NotionIntegrationConfiguration
from src.core.modules.operations.workflows.CreateIssueAndAddToProjectWorkflow import (
CreateIssueAndAddToProjectWorkflow,
CreateIssueAndAddToProjectWorkflowConfiguration
)
Assistant metadata
NAME = "Project Manager"
SLUG = "project-manager"
DESCRIPTION = "Oversee the planning, execution, and completion of projects."
MODEL = "gpt-4"
TEMPERATURE = 0
AVATAR_URL = "https://example.com/avatar.png"
System prompt defining the assistant's behavior
SYSTEM_PROMPT = """
You are the Project Manager Assistant. Your role is to help users plan, execute, and track
projects efficiently. You can help with task management, issue tracking, timeline planning,
and project documentation.
You have access to GitHub and Notion integrations to manage project resources.
Always be helpful, practical, and focused on driving projects to successful completion.
"""
def create_agent() -> Agent:
"""Create and configure the Project Manager agent."""
# Initialize integrations
github_config = GithubIntegrationConfiguration(
token=secret.get("GITHUB_TOKEN"),
base_url="https://api.github.com"
)
github_integration = GithubIntegration(github_config)
notion_config = NotionIntegrationConfiguration(
token=secret.get("NOTION_TOKEN")
)
notion_integration = NotionIntegration(notion_config)
# Initialize workflows
create_issue_workflow_config = CreateIssueAndAddToProjectWorkflowConfiguration(
github_integration_config=github_config,
github_graphql_integration_config=github_graphql_config
)
create_issue_workflow = CreateIssueAndAddToProjectWorkflow(create_issue_workflow_config)
# Collect tools
tools = [
github_integration.as_tools(),
notion_integration.as_tools(),
create_issue_workflow.as_tools()
]
# Create LLM
llm = ChatOpenAI(
model_name=MODEL,
temperature=TEMPERATURE,
openai_api_key=secret.get("OPENAI_API_KEY")
)
# Configure agent
configuration = AgentConfiguration(
agent_name=NAME,
slug=SLUG,
description=DESCRIPTION,
avatar_url=AVATAR_URL,
system_prompt=SYSTEM_PROMPT,
llm=llm,
tools=tools,
memory_saver=MemorySaver(),
shared_state=AgentSharedState()
)
# Create and return agent
return Agent(configuration)
```

## Assistant Roles

ABI includes agents for various domains and roles, including:

1. **Core Agents**:
   - Supervisor Assistant: Manages other agents and handles routing
   - Project Manager: Manages project planning, execution, and tracking
   - Software Engineer: Provides code assistance and software design guidance

2. **Domain-Specific Agents**:
   - Finance agents: Accountant, Financial Controller, Treasurer
   - Operations agents: DevOps Engineer, Data Engineer, HR Manager
   - Support agents: Customer Support, Internal Support

## Communication Patterns

Agents can communicate with users through multiple channels:
1. **Terminal Interface**: Command-line interaction
2. **API Endpoints**: REST API for chat and completions
3. **Web Interface**: When integrated with frontend applications

## LLM Models

Agents can use various LLM models:
- OpenAI models (GPT-4, GPT-3.5)
- Anthropic models (Claude)
- Open-source models (when supported by the LangChain framework)

The choice of model depends on the specific requirements of the assistant's role and the available API keys.