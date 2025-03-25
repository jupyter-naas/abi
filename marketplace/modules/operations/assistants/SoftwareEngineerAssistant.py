from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_openai import ChatOpenAI
from src.core.modules.common.integrations import GithubIntegration, GithubGraphqlIntegration, AWSS3Integration, SupabaseIntegration, PostgresIntegration
from src.core.modules.common.integrations.GithubIntegration import GithubIntegrationConfiguration
from src.core.modules.common.integrations.GithubGraphqlIntegration import GithubGraphqlIntegrationConfiguration
from src.core.modules.common.integrations.AWSS3Integration import AWSS3IntegrationConfiguration
from src.core.modules.common.integrations.SupabaseIntegration import SupabaseIntegrationConfiguration
from src.core.modules.common.integrations.PostgresIntegration import PostgresIntegrationConfiguration

NAME = "Software Engineer"
SLUG = "software-engineer"
DESCRIPTION = "Design, develop, and maintain software solutions that meet business and user requirements."
MODEL = "gpt-4"
TEMPERATURE = 0
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/09db836cc8f74bd3b80bcc1a40ca04b6"
SYSTEM_PROMPT = """
You are an expert Software Engineer Assistant specializing in software design, development, and maintenance. Your expertise covers:

1. Software Development:
   - Full-stack development (frontend, backend, databases)
   - API design and implementation
   - Code optimization and refactoring
   - Testing and debugging
   - Version control (Git)

2. Software Architecture:
   - System design and architecture patterns
   - Microservices architecture
   - Cloud infrastructure (AWS, Azure, GCP)
   - Database design and optimization
   - Security best practices

3. Development Practices:
   - Clean code principles
   - Test-driven development (TDD)
   - Continuous Integration/Continuous Deployment (CI/CD)
   - Code review best practices
   - Documentation standards

4. Problem-Solving:
   - Technical requirements analysis
   - Algorithm optimization
   - Performance troubleshooting
   - Scalability planning
   - Technical debt management

I can help with:
- Code review and improvement suggestions
- Architecture and design decisions
- Best practices and patterns implementation
- Technical documentation
- Problem-solving and debugging
- Technology stack recommendations

I aim to provide clear, practical advice while following industry best practices and considering factors like maintainability, scalability, and security. Let me know what software engineering challenges you're facing, and I'll help guide you toward effective solutions.
"""

def create_software_engineer_agent(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None
) -> Agent:
    """Creates a Software Engineer assistant agent.
    
    Args:
        agent_configuration (AgentConfiguration, optional): Configuration for the agent.
            Defaults to None.
        agent_shared_state (AgentSharedState, optional): Shared state for the agent.
            Defaults to None.
    
    Returns:
        Agent: The configured Software Engineer assistant agent
    """
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        openai_api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []

    github_key = secret.get('GITHUB_TOKEN')
    if github_key:
        tools += GithubIntegration.as_tools(GithubIntegrationConfiguration(access_token=github_key))
        tools += GithubGraphqlIntegration.as_tools(GithubGraphqlIntegrationConfiguration(access_token=github_key))  

    aws_access_key_id = secret.get('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = secret.get('AWS_SECRET_ACCESS_KEY')
    if aws_access_key_id and aws_secret_access_key:
        tools += AWSS3Integration.as_tools(AWSS3IntegrationConfiguration(access_key_id=aws_access_key_id, secret_access_key=aws_secret_access_key))

    supabase_key = secret.get('SUPABASE_KEY')
    supabase_url = secret.get('SUPABASE_URL')
    if supabase_key and supabase_url:
        tools += SupabaseIntegration.as_tools(SupabaseIntegrationConfiguration(api_key=supabase_key, url=supabase_url))

    postgres_host = secret.get('POSTGRES_HOST')
    postgres_port = secret.get('POSTGRES_PORT')
    postgres_db = secret.get('POSTGRES_DB')
    postgres_user = secret.get('POSTGRES_USER')
    postgres_password = secret.get('POSTGRES_PASSWORD')
    if postgres_host and postgres_port and postgres_db and postgres_user and postgres_password:
        tools += PostgresIntegration.as_tools(PostgresIntegrationConfiguration(host=postgres_host, port=postgres_port, db=postgres_db, user=postgres_user, password=postgres_password))

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