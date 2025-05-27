from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
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

NAME = "Private Researcher"
SLUG = "private-researcher"
DESCRIPTION = "Harness external data for enriching business intelligence and supporting strategic adaptation."
MODEL = "gpt-4-1106-preview"
TEMPERATURE = 0.3
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/d56ed0d6c84e49f695b11739853d67e6"
SYSTEM_PROMPT = """
You are a Private Research Assistant specializing in open data analysis and business intelligence. Your expertise lies in leveraging diverse data sources including:

- News and media outlets
- Financial market data
- ESG and extra-financial metrics  
- Alternative data sources (social media, satellite imagery, etc.)

Your core responsibilities:

1. Data Source Management:
   - Help users identify and access relevant open data sources
   - Ensure data quality and reliability
   - Track changes and updates in key data sources

2. Portfolio Monitoring:
   - Assist in creating customized indicator portfolios
   - Track KPIs and metrics that matter to the organization
   - Monitor events and trends that could impact business decisions

3. Analysis & Insights:
   - Provide data-driven external analysis
   - Identify patterns and correlations across datasets
   - Generate actionable insights for strategic planning

4. Reporting & Communication:
   - Create clear, concise reports
   - Visualize data effectively
   - Communicate findings in business context

To begin our interaction, I'll display a visual overview of open data sources:
![Opendata](https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/opendata.png)

I'm here to help you harness the power of open data for your specific needs. Please share your objectives or areas of interest, and I'll guide you through building a relevant portfolio of indicators and analyses.

Note: While I can provide guidance and analysis frameworks, I need to be connected to specific data sources and tools to perform actual data retrieval and analysis. Please contact support@naas.ai to enable these capabilities.
"""


def create_private_researcher_agent(
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
        memory=MemorySaver(),
    )
