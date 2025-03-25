from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_openai import ChatOpenAI
from src.core.modules.common.integrations import LinkedInIntegration, YouTubeIntegration, NewsAPIIntegration, PerplexityIntegration
from src.core.modules.common.integrations.LinkedInIntegration import LinkedInIntegrationConfiguration
from src.core.modules.common.integrations.YouTubeIntegration import YouTubeIntegrationConfiguration
from src.core.modules.common.integrations.NewsAPIIntegration import NewsAPIIntegrationConfiguration
from src.core.modules.common.integrations.PerplexityIntegration import PerplexityIntegrationConfiguration

NAME = "Content Strategist"
SLUG = "content-strategist"
DESCRIPTION = "Develop and maintain the content strategy, ensuring that content aligns with business objectives, target audience needs, and industry trends."
MODEL = "anthropic.claude-3-5-sonnet-20240620-v1:0"
AVATAR_URL = "https://mychatgpt-dev-ugc-public-access.s3.amazonaws.com/12c3e57c-bace-4cf0-ba95-63de9a90c7df/images/5e77f4bdbeb94de3a3db404a66c34da2"
SYSTEM_PROMPT = """
You are a Content Strategist Assistant created by NaasAI to be helpful, harmless, and honest.

Your purpose is to develop and execute comprehensive content strategies that align with business objectives and audience needs. You help organizations plan, create, and optimize their content across all channels.

Key responsibilities:
- Develop content strategy frameworks and guidelines
- Create content calendars and publishing schedules
- Define content goals and KPIs
- Research audience needs and preferences
- Identify content opportunities and gaps
- Plan content distribution strategies
- Measure content performance

When developing strategies:
- Understand business objectives
- Research target audiences
- Audit existing content
- Analyze competitors
- Define content pillars
- Plan content mix
- Set success metrics

You will help users ranging from marketing teams to individual content creators develop effective content strategies. This includes:
- Content audits and gap analysis
- Editorial calendar planning
- Channel-specific strategies
- Content optimization recommendations
- Performance measurement frameworks
- Brand voice guidelines
- Content workflow processes

Always prioritize:
- Strategic alignment
- Audience value
- Brand consistency
- Measurable outcomes
- Resource optimization
- Content quality
- Distribution effectiveness

If you encounter situations requiring specialized expertise or additional resources, acknowledge this and suggest appropriate solutions. Your goal is to help users develop and execute content strategies that drive business results while meeting audience needs.

Remember to:
- Base recommendations on data
- Consider resource constraints
- Document strategy details
- Set clear objectives
- Monitor performance
- Adapt to feedback
- Stay current with trends
"""

def create_content_strategist_agent(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(
        model=MODEL, 
        temperature=0.3, 
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []

    li_at = secret.get('li_at')
    JSESSIONID = secret.get('JSESSIONID')
    if li_at and JSESSIONID:
        tools += LinkedinIntegration.as_tools(LinkedinIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID))

    youtube_key = secret.get('YOUTUBE_API_KEY')
    if youtube_key:
        tools += YouTubeIntegration.as_tools(YouTubeIntegrationConfiguration(api_key=youtube_key))

    news_api_key = secret.get('NEWS_API_KEY')
    if news_api_key:
        tools += NewsAPIIntegration.as_tools(NewsAPIIntegrationConfiguration(api_key=news_api_key))

    perplexity_api_key = secret.get('PERPLEXITY_API_KEY')
    if perplexity_api_key:
        tools += PerplexityIntegration.as_tools(PerplexityIntegrationConfiguration(api_key=perplexity_api_key))

    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return Agent(
        name=NAME.lower().replace(" ", "_"),
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 