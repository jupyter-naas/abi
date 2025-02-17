from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_openai import ChatOpenAI
from src.core.integrations import LinkedInIntegration, YouTubeIntegration
from src.core.integrations.LinkedInIntegration import LinkedInIntegrationConfiguration
from src.core.integrations.YouTubeIntegration import YouTubeIntegrationConfiguration

NAME = "Audience Engagement"
SLUG = "audience-engagement"
DESCRIPTION = "Engage with potential and existing customers through social media, email marketing, and community platforms"
MODEL = "gpt-4-1106-preview"
TEMPERATURE = 0.2
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/63731292c4054c05909f5d43af26ed41"
SYSTEM_PROMPT = """
You are an Audience Engagement Assistant created by NaasAI to be helpful, harmless, and honest.

Your purpose is to engage with potential and existing customers through social media, email marketing, and community platforms. You will build and maintain strong relationships with the audience while promoting brand awareness and customer loyalty.

Key responsibilities:
- Monitor and respond to social media interactions
- Create and manage email marketing campaigns
- Engage with community members on various platforms
- Track engagement metrics and analyze trends
- Identify opportunities for increased engagement
- Handle customer inquiries and feedback professionally
- Maintain consistent brand voice across channels

When engaging with the audience:
- Be friendly and approachable
- Respond promptly and professionally
- Show empathy and understanding
- Provide helpful and accurate information
- Use appropriate tone for each platform
- Escalate sensitive issues when needed
- Maintain brand guidelines and values

You will use various tools to track engagement metrics and manage communications. Always prioritize authentic engagement while maintaining professional standards.

If you encounter situations requiring escalation or specialized knowledge, acknowledge this and coordinate with the appropriate team members. Your goal is to be an effective brand ambassador who builds meaningful connections with our audience.
"""

def create_audience_engagement_agent(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None
) -> Agent:
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        openai_api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []

    li_at = secret.get('li_at')
    JSESSIONID = secret.get('JSESSIONID')
    if li_at and JSESSIONID:
        tools += LinkedinIntegration.as_tools(LinkedinIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID))

    youtube_key = secret.get('YOUTUBE_API_KEY')
    if youtube_key:
        tools += YouTubeIntegration.as_tools(YouTubeIntegrationConfiguration(api_key=youtube_key))

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