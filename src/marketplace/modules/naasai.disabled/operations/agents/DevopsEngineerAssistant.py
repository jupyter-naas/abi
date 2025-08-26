from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    
)
from src import secret
from langchain_openai import ChatOpenAI
from src.core.modules.common.integrations import (
    GithubIntegration,
    GithubGraphqlIntegration,
    AWSS3Integration,
    SupabaseIntegration,
    PostgresIntegration,
)
from src.core.modules.common.integrations.GithubIntegration import (
    GithubIntegrationConfiguration,
)
from src.core.modules.common.integrations.GithubGraphqlIntegration import (
    GithubGraphqlIntegrationConfiguration,
)
from src.core.modules.common.integrations.AWSS3Integration import (
    AWSS3IntegrationConfiguration,
)
from src.core.modules.common.integrations.SupabaseIntegration import (
    SupabaseIntegrationConfiguration,
)
from src.core.modules.common.integrations.PostgresIntegration import (
    PostgresIntegrationConfiguration,
)

NAME = "Devops Engineer"
SLUG = "devops-engineer"
DESCRIPTION = "Streamline the development, deployment, and monitoring of applications."
MODEL = "gpt-4"
TEMPERATURE = 0
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/1085d432d2f04aea8dd6cfa2a762ea24"
SYSTEM_PROMPT = """
You are an expert DevOps Engineer Assistant specializing in development operations, deployment automation, and infrastructure management. Your expertise covers:

1. Infrastructure and Cloud:
   - Cloud platforms (AWS, Azure, GCP)
   - Infrastructure as Code (Terraform, CloudFormation)
   - Container orchestration (Kubernetes, Docker)
   - Server management and configuration
   - Network architecture and security

2. CI/CD and Automation:
   - Pipeline design and implementation
   - Continuous Integration tools (Jenkins, GitLab CI, GitHub Actions)
   - Continuous Deployment strategies
   - Build and release automation
   - Testing automation

3. Monitoring and Operations:
   - System monitoring and alerting
   - Log management and analysis
   - Performance optimization
   - Incident response
   - Capacity planning

4. Development Practices:
   - Version control (Git)
   - Code review processes
   - Documentation standards
   - Security best practices
   - Collaboration workflows

I can help with:
- Setting up CI/CD pipelines
- Infrastructure automation
- Container orchestration
- Monitoring and logging solutions
- Cloud architecture design
- Security and compliance implementation
- Performance optimization
- Incident response planning

I aim to provide practical solutions while considering scalability, reliability, and security. Let me know what DevOps challenges you're facing, and I'll help guide you toward effective solutions that align with industry best practices.
"""


def create_devops_engineer_agent(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None,
) -> Agent:
    """Creates a DevOps Engineer assistant agent.

    Args:
        agent_configuration (AgentConfiguration, optional): Configuration for the agent.
            Defaults to None.
        agent_shared_state (AgentSharedState, optional): Shared state for the agent.
            Defaults to None.

    Returns:
        Agent: The configured DevOps Engineer assistant agent
    """
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        openai_api_key=secret.get("OPENAI_API_KEY"),
    )
    tools = []

    if github_key := secret.get("GITHUB_TOKEN"):
        tools += GithubIntegration.as_tools(
            GithubIntegrationConfiguration(access_token=github_key)
        )
        tools += GithubGraphqlIntegration.as_tools(
            GithubGraphqlIntegrationConfiguration(access_token=github_key)
        )

    aws_access_key_id = secret.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = secret.get("AWS_SECRET_ACCESS_KEY")
    if aws_access_key_id and aws_secret_access_key:
        tools += AWSS3Integration.as_tools(
            AWSS3IntegrationConfiguration(
                access_key_id=aws_access_key_id, secret_access_key=aws_secret_access_key
            )
        )

    supabase_key = secret.get("SUPABASE_KEY")
    supabase_url = secret.get("SUPABASE_URL")
    if supabase_key and supabase_url:
        tools += SupabaseIntegration.as_tools(
            SupabaseIntegrationConfiguration(api_key=supabase_key, url=supabase_url)
        )

    postgres_host = secret.get("POSTGRES_HOST")
    postgres_port = secret.get("POSTGRES_PORT")
    postgres_db = secret.get("POSTGRES_DB")
    postgres_user = secret.get("POSTGRES_USER")
    postgres_password = secret.get("POSTGRES_PASSWORD")
    if (
        postgres_host
        and postgres_port
        and postgres_db
        and postgres_user
        and postgres_password
    ):
        tools += PostgresIntegration.as_tools(
            PostgresIntegrationConfiguration(
                host=postgres_host,
                port=postgres_port,
                db=postgres_db,
                user=postgres_user,
                password=postgres_password,
            )
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
