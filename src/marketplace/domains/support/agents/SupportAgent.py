from langchain_openai import ChatOpenAI
from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from src import secret
from pydantic import SecretStr

NAME = "Support"
MODEL = "gpt-4.1-mini"
TEMPERATURE = 0
AVATAR_URL = "https://t3.ftcdn.net/jpg/05/10/88/82/360_F_510888200_EentlrpDCeyf2L5FZEeSfgYaeiZ80qAU.jpg"
DESCRIPTION = "A Support Agent that helps to get any feedbacks/bugs or needs from user."
SYSTEM_PROMPT = """
## ROLE
You are a Support Agent focused on handling user feedback, bug reports, and feature requests efficiently.

## OBJECTIVE
1. Quickly identify if the request is support-related (bugs, features, technical help)
2. For non-support topics, use the request_help tool to redirect to appropriate agent
3. For support requests, gather key details and create tickets
4. Provide clear status updates and next steps

## CONTEXT
You will receive messages from users or the supervisor agent.

## TASKS
1. Answer question about your capabilities
2. Quickly identify if the request is support-related (bugs, features, technical help)
3. For non-support topics, use the request_help tool to redirect to appropriate agent
4. For support requests, gather key details and create tickets
5. Provide clear status updates and next steps

## TOOLS
- `report_bug`: Create GitHub bug reports
- `feature_request`: Create GitHub feature requests
- `request_help`: Redirect non-support queries to supervisor agent

## OPERATING GUIDELINES

### Key Information to Gather
For Bugs:
- Clear description of issue
- Steps to reproduce
- Expected vs actual behavior
- Error messages/screenshots
- Draft format:
```
### Description
[Description of the issue]

### Steps to reproduce
[Steps to reproduce the issue]

### Expected behavior
[Expected behavior]

### Actual behavior
[Actual behavior]
```

For Feature Requests:
- Use case and business value
- Desired functionality
- Success criteria
- Priority level
- Draft format:
```
### Use case
[Use case of the feature request]

### Business value
[Business value of the feature request]

### Success criteria
[Success criteria of the feature request]

### Priority level
[Priority level of the feature request]

### Desired functionality
[Desired functionality of the feature request]
```

### COMMUNICATION GUIDELINES
- Be direct and professional
- Focus on key details only
- Ask for draft approval before creating tickets

## CONSTRAINTS
- Only handle support-related requests
- Request help for non-support topics
- Validate inputs before creating tickets
- Protect sensitive information
- Document all interactions
"""

SUGGESTIONS: list[dict[str, str]] = [
    {
        "label": "I found a bug in the application",
        "value": "I found a bug in the application",
    },
    {
        "label": "I have a feature request", 
        "value": "I have a feature request",
    },
    {
        "label": "I need help with an integration",
        "value": "I need help with an integration",
    },
    {
        "label": "The system is running slowly",
        "value": "The system is running slowly", 
    },
    {
        "label": "I'm getting an error message",
        "value": "I'm getting an error message",
    },
    {
        "label": "I have feedback about the user interface",
        "value": "I have feedback about the user interface",
    },
    {
        "label": "I need technical support",
        "value": "I need technical support",
    },
    {
        "label": "Report a security issue",
        "value": "Report a security issue",
    },
    {
        "label": "Request a new integration",
        "value": "Request a new integration",
    },
    {
        "label": "Suggest a workflow improvement",
        "value": "Suggest a workflow improvement",
    },
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Define model
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )

    # Define tools
    tools: list = []
    from src.marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
        GitHubGraphqlIntegrationConfiguration,
    )
    from src.marketplace.applications.github.integrations.GitHubIntegration import (
        GitHubIntegrationConfiguration,
    )
    from src.marketplace.domains.support.workflows.ReportBugWorkflow import (
        ReportBugWorkflow,
        ReportBugWorkflowConfiguration,
    )
    from src.marketplace.domains.support.workflows.FeatureRequestWorkflow import (
        FeatureRequestWorkflow,
        FeatureRequestWorkflowConfiguration,
    )
    github_access_token = secret.get("GITHUB_ACCESS_TOKEN")
    github_integration_config = GitHubIntegrationConfiguration(
        access_token=github_access_token
    )
    github_graphql_integration_config = GitHubGraphqlIntegrationConfiguration(
        access_token=github_access_token
    )

    # Add ReportBugWorkflow tool
    report_bug_workflow = ReportBugWorkflow(
        ReportBugWorkflowConfiguration(
            github_integration_config=github_integration_config,
            github_graphql_integration_config=github_graphql_integration_config,
        )
    )
    tools += report_bug_workflow.as_tools()

    # Add FeatureRequestWorkflow tool
    feature_request_workflow = FeatureRequestWorkflow(
        FeatureRequestWorkflowConfiguration(
            github_integration_config=github_integration_config,
            github_graphql_integration_config=github_graphql_integration_config,
        )
    )
    tools += feature_request_workflow.as_tools()
    
    # Define specific intents for support operations
    intents: list = [
        # Bug reporting intents
        Intent(intent_value="I found a bug", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="Report a bug", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="Something is broken", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="Error in the system", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="Application crashed", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="Performance issue", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="System not working", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="Integration problem", intent_type=IntentType.TOOL, intent_target="report_bug"),
        
        # Feature request intents
        Intent(intent_value="Feature request", intent_type=IntentType.TOOL, intent_target="feature_request"),
        Intent(intent_value="I need a new feature", intent_type=IntentType.TOOL, intent_target="feature_request"),
        Intent(intent_value="Can you add", intent_type=IntentType.TOOL, intent_target="feature_request"),
        Intent(intent_value="Enhancement request", intent_type=IntentType.TOOL, intent_target="feature_request"),
        Intent(intent_value="New integration", intent_type=IntentType.TOOL, intent_target="feature_request"),
        Intent(intent_value="Workflow improvement", intent_type=IntentType.TOOL, intent_target="feature_request"),
        Intent(intent_value="UI improvement", intent_type=IntentType.TOOL, intent_target="feature_request"),
        Intent(intent_value="API integration", intent_type=IntentType.TOOL, intent_target="feature_request"),
    ]
   
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    # Set shared state
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return SupportAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=[],
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class SupportAgent(IntentAgent):
    pass