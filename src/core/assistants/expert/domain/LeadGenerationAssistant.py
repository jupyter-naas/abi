from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_openai import ChatOpenAI
from src.integrations import HubSpotIntegration, LinkedInIntegration, PipedriveIntegration, YouTubeIntegration, GoogleAnalyticsIntegration
from src.integrations.HubSpotIntegration import HubSpotIntegrationConfiguration
from src.integrations.LinkedInIntegration import LinkedInIntegrationConfiguration
from src.integrations.PipedriveIntegration import PipedriveIntegrationConfiguration
from src.integrations.YouTubeIntegration import YouTubeIntegrationConfiguration
from src.integrations.GoogleAnalyticsIntegration import GoogleAnalyticsIntegrationConfiguration

NAME = "Lead Generation"
SLUG = "lead-generation"
DESCRIPTION = "Attract, capture, and nurture leads through various channels, including social media, paid ads, and email marketing"
MODEL = "gpt-4-1106-preview"
TEMPERATURE = 0.5
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/d8bcd7f3c5184798b8806a3859a7b7ee"
SYSTEM_PROMPT = """
You are a Lead Generation Assistant created by NaasAI to be helpful, harmless, and honest.

Your purpose is to attract, capture, and nurture leads through various channels, including social media, paid advertising, and email marketing. You will identify and engage potential customers while qualifying leads for the sales team.

Key responsibilities:
- Generate and qualify new leads through multiple channels
- Create and optimize lead generation campaigns
- Track and analyze lead generation metrics
- Score and segment leads based on criteria
- Nurture leads through targeted content
- Hand off qualified leads to sales team
- Maintain accurate lead data

When working with leads:
- Focus on quality over quantity
- Use data-driven targeting approaches
- Implement lead scoring systems
- Create personalized nurture sequences
- Monitor conversion rates
- Document lead interactions
- Follow data privacy regulations

You will use various tools to track leads and manage campaigns. Always prioritize lead quality while maintaining efficient processes.

If you encounter situations requiring specialized knowledge or support, acknowledge this and coordinate with the appropriate team members. Your goal is to consistently provide high-quality leads that convert into customers.

Remember to:
- Validate lead information
- Score leads systematically
- Document qualification criteria
- Track engagement metrics
- Maintain GDPR compliance
- Coordinate with sales team
- Optimize based on feedback
"""

def create_lead_generation_assistant(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None
) -> Agent:
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        openai_api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []

    hubspot_access_token = secret.get('HUBSPOT_ACCESS_TOKEN')
    if hubspot_access_token:
        tools += HubSpotIntegration.as_tools(HubSpotIntegrationConfiguration(access_token=hubspot_access_token))

    li_at = secret.get('li_at')
    jsessionid = secret.get('jsessionid')
    if li_at and jsessionid:
        tools += LinkedInIntegration.as_tools(LinkedInIntegrationConfiguration(li_at=li_at, jsessionid=jsessionid))

    pipedrive_api_key = secret.get('PIPEDRIVE_API_KEY')
    if pipedrive_api_key:
        tools += PipedriveIntegration.as_tools(PipedriveIntegrationConfiguration(api_key=pipedrive_api_key))

    youtube_key = secret.get('YOUTUBE_API_KEY')
    if youtube_key:
        tools += YouTubeIntegration.as_tools(YouTubeIntegrationConfiguration(api_key=youtube_key))

    google_analytics_key = secret.get('GOOGLE_ANALYTICS_KEY')
    if google_analytics_key:
        tools += GoogleAnalyticsIntegration.as_tools(GoogleAnalyticsIntegrationConfiguration(api_key=google_analytics_key))

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