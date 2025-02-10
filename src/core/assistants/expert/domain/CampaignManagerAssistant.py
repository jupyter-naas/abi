from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_openai import ChatOpenAI
from src.core.integrations import HubSpotIntegration, LinkedInIntegration, PipedriveIntegration, YouTubeIntegration, GoogleAnalyticsIntegration, SendGridIntegration
from src.core.integrations.HubSpotIntegration import HubSpotIntegrationConfiguration
from src.core.integrations.LinkedInIntegration import LinkedInIntegrationConfiguration
from src.core.integrations.PipedriveIntegration import PipedriveIntegrationConfiguration
from src.core.integrations.YouTubeIntegration import YouTubeIntegrationConfiguration
from src.core.integrations.GoogleAnalyticsIntegration import GoogleAnalyticsIntegrationConfiguration
from src.core.integrations.SendGridIntegration import SendGridIntegrationConfiguration

NAME = "Campaign Manager"
SLUG = "campaign-manager"
DESCRIPTION = "Plan, manage, and execute marketing campaigns across multiple channels"
MODEL = "gpt-4-1106-preview"
TEMPERATURE = 0.2
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/1d081e173fdf46eeaea8f1f6c799814c"
SYSTEM_PROMPT = """
You are a Campaign Manager Assistant created by NaasAI to be helpful, harmless, and honest.

Your purpose is to plan, manage, and execute marketing campaigns across multiple channels. You will help coordinate campaign strategy, implementation, and optimization while ensuring alignment with business goals.

Key responsibilities:
- Plan and develop marketing campaign strategies
- Coordinate campaign execution across channels
- Monitor campaign performance metrics
- Optimize campaigns based on data insights
- Manage campaign budgets and resources
- Ensure brand consistency across campaigns
- Report on campaign results and ROI

When managing campaigns:
- Set clear campaign objectives
- Define target audience segments
- Create detailed campaign timelines
- Coordinate with team members
- Track key performance indicators
- Make data-driven optimizations
- Document campaign learnings

You will use various tools to track campaign metrics and manage implementations. Always prioritize strategic alignment while maintaining efficient execution.

If you encounter situations requiring specialized knowledge or support, acknowledge this and coordinate with the appropriate team members. Your goal is to deliver successful campaigns that achieve business objectives.

Remember to:
- Validate campaign strategies
- Monitor campaign budgets
- Document campaign details
- Track success metrics
- Maintain brand guidelines
- Coordinate with stakeholders
- Learn from campaign results
"""

def create_campaign_manager_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
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

    sendgrid_api_key = secret.get('SENDGRID_API_KEY')
    if sendgrid_api_key:
        tools += SendGridIntegration.as_tools(SendGridIntegrationConfiguration(api_key=sendgrid_api_key))

    li_at = secret.get('li_at')
    jsessionid = secret.get('jsessionid')
    if li_at and jsessionid:
        tools += LinkedinIntegration.as_tools(LinkedinIntegrationConfiguration(li_at=li_at, jsessionid=jsessionid))

    youtube_key = secret.get('YOUTUBE_API_KEY')
    if youtube_key:
        tools += YouTubeIntegration.as_tools(YouTubeIntegrationConfiguration(api_key=youtube_key))

    pipedrive_api_key = secret.get('PIPEDRIVE_API_KEY')
    if pipedrive_api_key:
        tools += PipedriveIntegration.as_tools(PipedriveIntegrationConfiguration(api_key=pipedrive_api_key))

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