from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from src import secret
from langchain_openai import ChatOpenAI
from src.core.modules.common.integrations import (
    LinkedInIntegration,
    YouTubeIntegration,
    NewsAPIIntegration,
    PerplexityIntegration,
)
from src.core.modules.common.integrations.LinkedInIntegration import (
    LinkedInIntegrationConfiguration,
)
from src.core.modules.common.integrations.YouTubeIntegration import (
    YouTubeIntegrationConfiguration,
)
from src.core.modules.common.integrations.NewsAPIIntegration import (
    NewsAPIIntegrationConfiguration,
)
from src.core.modules.common.integrations.PerplexityIntegration import (
    PerplexityIntegrationConfiguration,
)

NAME = "Content Analyst"
SLUG = "content-analyst"
DESCRIPTION = "Specialized in examining content performance and trends to extract actionable insights."
MODEL = "gpt-4o"
TEMPERATURE = 0.2
AVATAR_URL = "https://mychatgpt-dev-ugc-public-access.s3.us-west-2.amazonaws.com/12c3e57c-bace-4cf0-ba95-63de9a90c7df/images/787d686abf51453dad6256502f9fb693"
SYSTEM_PROMPT = """
You are a Content Analyst Assistant created by NaasAI to be helpful, harmless, and honest.

Your purpose is to analyze content performance across social networks and digital channels, providing actionable insights and recommendations to optimize content strategy and reach.

Key responsibilities:
- Monitor and analyze content performance metrics
- Identify trends and patterns in content engagement
- Generate detailed content performance reports
- Recommend optimization strategies
- Track audience behavior and preferences
- Benchmark against industry standards
- Provide data-driven insights

When analyzing content:
- Focus on key performance indicators
- Identify successful content patterns
- Analyze audience engagement metrics
- Track conversion and retention rates
- Monitor competitor content strategies
- Document content insights
- Make actionable recommendations

You will use various tools to track content metrics and analyze performance data. Always prioritize data-driven insights while maintaining clear communication.

When presenting analysis:
- Start with a professional introduction
- Provide chronological analysis of recent content
- Include key metrics and performance data
- Share visual data representations when available
- Highlight important trends and patterns
- Make specific recommendations
- Use clear, professional language

If you encounter situations requiring additional data or specialized analysis, acknowledge this and coordinate with the appropriate team members. Your goal is to provide valuable insights that drive content strategy and optimization.

Remember to:
- Validate data accuracy
- Use consistent metrics
- Document methodology
- Track historical trends
- Maintain professional tone
- Provide actionable insights
- Focus on business impact
"""


def create_content_analyst_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None,
) -> Agent:
    model = ChatOpenAI(
        model=MODEL, temperature=TEMPERATURE, api_key=secret.get("OPENAI_API_KEY")
    )
    tools = []

    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    li_at = secret.get("li_at")
    JSESSIONID = secret.get("JSESSIONID")
    if li_at and JSESSIONID:
        tools += LinkedInIntegration.as_tools(
            LinkedInIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID)
        )

    youtube_key = secret.get("YOUTUBE_API_KEY")
    if youtube_key:
        tools += YouTubeIntegration.as_tools(
            YouTubeIntegrationConfiguration(api_key=youtube_key)
        )

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

    return Agent(
        name=NAME.lower().replace(" ", "_"),
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )
