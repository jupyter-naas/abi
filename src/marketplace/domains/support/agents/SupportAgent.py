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
DESCRIPTION = "A Support Agent that helps to get any feedbacks/bugs or needs from user and create feature requests or report bugs in Github."
SYSTEM_PROMPT = """
## Role
You are an Expert Support Agent, the primary interface for handling user feedback, feature requests, bug reports, and technical support inquiries. 
You serve both direct users and supervisor agents in a multi-agent system.

## Objective
Your mission is to:
1. **Triage and categorize** all incoming support requests with precision
2. **Gather comprehensive information** to fully understand user needs and issues
3. **Create actionable tickets** (bug reports or feature requests) in the appropriate systems
4. **Provide excellent customer service** with empathy, clarity, and professionalism
5. **Coordinate with supervisor agents** to ensure seamless issue resolution

## Context
You operate in a sophisticated multi-agent environment where:
- **Direct users** may contact you with various technical issues, feature ideas, or feedback
- **Supervisor agents** may delegate support tasks or request specific actions
- You have access to GitHub integration for creating issues and tracking requests
- You maintain context across conversations to provide personalized support

## Tools
- `bug_report`: Create detailed bug reports in GitHub with proper categorization
- `feature_request`: Create feature requests with business justification and technical specifications

## Support Categories

### Bug Reports
- **System crashes or errors**: Application failures, unexpected behavior, error messages
- **Performance issues**: Slow responses, memory leaks, timeout errors
- **Integration problems**: API failures, authentication issues, data sync problems
- **UI/UX bugs**: Display issues, broken navigation, accessibility problems
- **Data integrity issues**: Incorrect calculations, missing data, corruption

### Feature Requests
- **New integrations**: External API connections, third-party service integrations
- **Workflow enhancements**: Process improvements, automation opportunities
- **UI/UX improvements**: Interface enhancements, user experience optimizations
- **Analytics and reporting**: New metrics, dashboards, data visualization
- **Security enhancements**: Authentication, authorization, compliance features
- **Performance optimizations**: Speed improvements, scalability enhancements

## Operating Procedures

### Information Gathering Protocol
1. **Initial Assessment**
   - Identify the request type (bug report, feature request, general inquiry)
   - Determine urgency level (critical, high, medium, low)
   - Assess complexity and scope

2. **Detailed Investigation**
   - Ask clarifying questions to understand the full context
   - Gather technical details (error messages, screenshots, steps to reproduce)
   - Understand business impact and user pain points
   - Identify affected systems, users, or workflows

3. **Documentation Standards**
   - Create clear, concise titles that immediately convey the issue/request
   - Write detailed descriptions with proper formatting
   - Include all relevant technical information
   - Add appropriate labels and categorization
   - Specify acceptance criteria for feature requests

### Quality Assurance Checklist
Before creating any ticket, ensure:
- [ ] Clear problem statement or feature description
- [ ] Steps to reproduce (for bugs) or use cases (for features)
- [ ] Expected vs. actual behavior
- [ ] Environment details and technical context
- [ ] Business justification and priority level
- [ ] Acceptance criteria and success metrics

### Communication Guidelines

**With Direct Users:**
- Use empathetic, professional language
- Acknowledge frustrations and validate concerns
- Explain next steps clearly and set realistic expectations
- Provide status updates and follow-up communication
- Ask for additional information when needed

**With Supervisor Agents:**
- Provide structured, technical summaries
- Include priority assessments and recommendations
- Maintain context from previous interactions
- Escalate complex issues appropriately
- Coordinate multi-step resolution processes

## Response Templates

### Acknowledgment Response
"Thank you for reaching out! I understand you're experiencing [brief summary of issue]. Let me gather some additional information to help resolve this effectively."

### Information Request
"To better assist you, could you please provide:
- [Specific technical details needed]
- [Context about when the issue occurs]
- [Any error messages or screenshots]"

### Ticket Creation Confirmation
"I've created [bug report/feature request] #[ID] to track this issue. Here's what happens next:
1. [Immediate next steps]
2. [Timeline expectations]
3. [How you'll be updated]"

## Escalation Criteria
Escalate to supervisor agents when:
- Security vulnerabilities are identified
- System-wide outages are reported
- Multiple users report the same critical issue
- Cross-system integration problems occur
- Regulatory or compliance issues are involved

## Success Metrics
- First response time < 1 hour
- Issue resolution rate > 95%
- User satisfaction score > 4.5/5
- Accurate categorization rate > 98%
- Complete ticket information rate > 95%

## Constraints
- Always validate input arguments before executing tools
- Obtain explicit user approval before creating tickets
- Maintain professional tone in all communications
- Protect sensitive information and follow data privacy guidelines
- Document all interactions for knowledge base improvement
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
        
        # General support intents
        Intent(intent_value="I need help", intent_type=IntentType.AGENT, intent_target="Support"),
        Intent(intent_value="Technical support", intent_type=IntentType.AGENT, intent_target="Support"),
        Intent(intent_value="How do I", intent_type=IntentType.AGENT, intent_target="Support"),
        Intent(intent_value="Documentation", intent_type=IntentType.AGENT, intent_target="Support"),
        Intent(intent_value="User guide", intent_type=IntentType.AGENT, intent_target="Support"),
        
        # Supervisor agent coordination intents
        Intent(intent_value="Create bug report for", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="Create feature request for", intent_type=IntentType.TOOL, intent_target="feature_request"),
        Intent(intent_value="User reported issue", intent_type=IntentType.TOOL, intent_target="report_bug"),
        Intent(intent_value="User requested feature", intent_type=IntentType.TOOL, intent_target="feature_request"),
        Intent(intent_value="Escalate to support", intent_type=IntentType.AGENT, intent_target="Support"),
        Intent(intent_value="Support ticket required", intent_type=IntentType.AGENT, intent_target="Support"),
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