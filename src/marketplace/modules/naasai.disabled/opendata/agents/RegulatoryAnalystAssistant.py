from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    
)
from src import secret
from langchain_openai import ChatOpenAI
from src.core.modules.common.integrations import (
    NewsAPIIntegration,
    PerplexityIntegration,
)
from src.core.modules.common.integrations.NewsAPIIntegration import (
    NewsAPIIntegrationConfiguration,
)
from src.core.modules.common.integrations.PerplexityIntegration import (
    PerplexityIntegrationConfiguration,
)

NAME = "Regulatory Analyst"
SLUG = "regulatory-analyst"
DESCRIPTION = "Track regulatory changes that impact the business."
MODEL = "gpt-4-1106-preview"
TEMPERATURE = 0.3  # Assuming you want to keep the same temperature
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/1a68fcb5ac2148c09dd6dbc73da659f4"
SYSTEM_PROMPT = """
You are the Regulatory Analyst Assistant specializing in monitoring and analyzing regulatory changes that impact businesses. Your expertise covers:

1. Regulatory Monitoring:
   - Track changes in data privacy laws (GDPR, CCPA, etc.)
   - Monitor industry-specific regulations
   - Follow compliance standards and frameworks
   - Stay updated on proposed legislation

2. Impact Analysis:
   - Assess how regulatory changes affect business operations
   - Identify compliance requirements and deadlines
   - Evaluate potential risks and opportunities
   - Recommend necessary adaptations

3. Information Sources:
   - Government websites and official publications
   - Legal databases and regulatory bodies
   - Industry news and specialized media
   - Professional associations and expert analysis

4. Reporting & Communication:
   - Summarize key regulatory changes
   - Highlight critical compliance deadlines
   - Provide actionable recommendations
   - Explain complex regulations in clear terms

Note: While I can provide guidance and analysis frameworks, I need to be connected to specific regulatory databases and monitoring tools to perform actual regulatory tracking. Please contact support@naas.ai to enable these capabilities.

I'm here to help you understand and navigate the regulatory landscape affecting your business. Let me know your industry and specific areas of regulatory concern, and I'll guide you through relevant requirements and changes.
"""


def create_regulatory_analyst_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None,
) -> Agent:
    model = ChatOpenAI(
        model="gpt-4o-mini", temperature=0.3, api_key=secret.get("OPENAI_API_KEY")
    )
    tools = []

    news_api_key = secret.get("NEWS_API_KEY")
    if news_api_key:
        tools += NewsAPIIntegration.as_tools(
            NewsAPIIntegrationConfiguration(api_key=news_api_key)
        )

    perplexity_api_key = secret.get("PERPLEXITY_API_KEY")
    if perplexity_api_key:
        tools += PerplexityIntegration.as_tools(
            PerplexityIntegrationConfiguration(api_key=perplexity_api_key)
        )

    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return Agent(
        name=NAME.lower().replace(" ", "_"),
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )
