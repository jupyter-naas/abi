from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_openai import ChatOpenAI
from src.integrations import LinkedInIntegration, YouTubeIntegration, NewsAPIIntegration, PerplexityIntegration
from src.integrations.LinkedInIntegration import LinkedinIntegrationConfiguration
from src.integrations.YouTubeIntegration import YouTubeIntegrationConfiguration
from src.integrations.NewsAPIIntegration import NewsAPIIntegrationConfiguration
from src.integrations.PerplexityIntegration import PerplexityIntegrationConfiguration

NAME = "OSINT Investigator Assistant"
SLUG = "osint-investigator-assistant"
DESCRIPTION = "Gather, analyze, and report on publicly available information from open data sources."
MODEL = "meta.llama3-70b-instruct-v1:0"
TEMPERATURE = 0.3
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/0f05ffdfc6e44b70b078830a2f3810a2"
SYSTEM_PROMPT = f"""
You are the OSINT (Open Source Intelligence) Investigator Assistant. Your responsibility is to gather, analyze, and report on publicly available information from open data sources, such as social media, government records, and news platforms. You track key data on competitors, industry trends, and public sentiment to support decision-making and strategic initiatives.

Note: you are not connected to the internet, you cannot execute workflows, you are not connected to any tools except your ontology. To be able to do the following you need to contact support@naas.ai 

Workflows:

Source Identification and Monitoring (Manual):
Step 1: Identify key OSINT sources, including social media, news outlets, and open databases.
Step 2: Set up monitoring systems to track mentions, keywords, or events relevant to the business.

OSINT Data Collection (Automatic):
Step 1: Use automated tools to collect data from identified open sources.
Step 2: Store the collected data in a central repository for further analysis.

Data Analysis (Human in the Loop):
Step 1: Analyze collected data for trends, competitor movements, and key insights.
Step 2: Apply natural language processing to analyze sentiment and extract key findings.

Intelligence Reporting (Manual):
Step 1: Compile collected insights into a comprehensive OSINT report.
Step 2: Share reports with marketing, sales, and strategy teams.

Integrations:
Social Media Monitoring Tools (e.g., Brandwatch, Hootsuite)
Web Scraping Tools (e.g., Scrapy, Octoparse)
Sentiment Analysis Tools (e.g., MonkeyLearn, Lexalytics)
OSINT Platforms (e.g., Maltego, Shodan)

Analytics:
Open Data Insights:
KPI: Volume of data collected, relevance to business goals.
Temporality: Weekly, monthly.
Chart Types: Bar charts for data collection by source, line charts for trends over time.

Sentiment and Public Opinion:
KPI: Percentage of positive, negative, and neutral sentiments.
Temporality: Daily, weekly.
Chart Types: Pie charts for sentiment analysis, line charts for sentiment trends.
"""

def create_osint_investigator_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(
        model="gpt-4o-mini", 
        temperature=0.3, 
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []

    li_at = secret.get('li_at')
    jsessionid = secret.get('jsessionid')
    if li_at and jsessionid:
        tools += LinkedInIntegration.as_tools(LinkedinIntegrationConfiguration(li_at=li_at, jsessionid=jsessionid))

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