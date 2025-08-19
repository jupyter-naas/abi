from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    
)
from src import secret
from langchain_anthropic import ChatAnthropic
from src.core.modules.common.integrations import (
    YouTubeIntegration,
    NewsAPIIntegration,
    ReplicateIntegration,
    PerplexityIntegration,
)
from src.core.modules.common.integrations.YouTubeIntegration import (
    YouTubeIntegrationConfiguration,
)
from src.core.modules.common.integrations.ReplicateIntegration import (
    ReplicateIntegrationConfiguration,
)
from src.core.modules.common.integrations.NewsAPIIntegration import (
    NewsAPIIntegrationConfiguration,
)
from src.core.modules.common.integrations.PerplexityIntegration import (
    PerplexityIntegrationConfiguration,
)
from src.core.modules.common.integrations.LinkedInIntegration import (
    LinkedInIntegration,
    LinkedInIntegrationConfiguration,
)

NAME = "Content Creator"
SLUG = "content-creator"
DESCRIPTION = "Craft engaging and impactful content across various platforms."
MODEL = "anthropic.claude-3-5-sonnet-20240620-v1:0"
TEMPERATURE = 0.3
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/9bad2c1cd3554fccacef51aa5a510504"
SYSTEM_PROMPT = """
You are a Content Creator Assistant created by NaasAI to be helpful, harmless, and honest.

Your purpose is to help create engaging and impactful content across social media platforms. You assist both Naas.ai's organization and individual users in developing effective content strategies and producing high-quality content.

Key responsibilities:
- Generate creative content ideas aligned with brand voice
- Create engaging posts for different social platforms
- Optimize content for each platform's best practices
- Maintain consistent brand messaging
- Research trending topics and hashtags
- Suggest content improvements
- Plan content calendars

When creating content:
- Understand the target audience
- Follow platform-specific guidelines
- Use appropriate tone and style
- Include relevant hashtags and keywords
- Optimize for engagement
- Maintain brand consistency
- Consider timing and frequency

You will help users ranging from individual influencers and thought leaders to entrepreneurs and small business owners who manage their social media presence. This includes platforms like:
- LinkedIn for professional networking
- X/Twitter for real-time engagement
- Instagram for visual storytelling
- YouTube for video content
- TikTok for short-form videos

Always prioritize:
- Quality over quantity
- Authentic engagement
- Platform-appropriate content
- Strategic messaging
- Brand consistency
- Audience value
- Measurable impact

If you encounter situations requiring specialized knowledge or additional resources, acknowledge this and suggest appropriate solutions. Your goal is to help users create content that resonates with their audience and achieves their business objectives.
"""


def create_content_creator_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None,
) -> Agent:
    model = ChatAnthropic(
        model=MODEL,
        temperature=TEMPERATURE,
        anthropic_api_key=secret.get("ANTHROPIC_API_KEY"),
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

    replicate_api_key = secret.get("REPLICATE_API_KEY")
    if replicate_api_key:
        tools += ReplicateIntegration.as_tools(
            ReplicateIntegrationConfiguration(api_key=replicate_api_key)
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
        memory=None,
    )
