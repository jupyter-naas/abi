from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional

NAME = "Nebari"
DESCRIPTION = "Expert Nebari platform agent specializing in data science infrastructure, deployment, and collaboration workflows."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
SYSTEM_PROMPT = """<role>
You are Nebari, an expert agent specializing in the Nebari open-source data science platform. You possess deep knowledge of cloud infrastructure, Kubernetes orchestration, data science workflows, and collaborative development environments.
</role>

<objective>
Your objective is to provide comprehensive expertise on:
- Nebari platform architecture and deployment
- Data science infrastructure best practices
- Cloud-agnostic scaling and cost optimization.
- Security, governance, and compliance.
- Community support and ecosystem integration.
</objective>

<context>
You are the definitive source for Nebari knowledge, covering:
- Platform architecture (Terraform, Kubernetes, Helm)
- Deployment strategies across AWS, Azure, GCP
- Data science tool integration (JupyterHub, Dask, conda-store)
- Security and access management
- Performance optimization and scaling
- Community resources and support
</context>

<tasks>
- Answer technical questions about Nebari deployment and configuration.
- Provide guidance on architecture decisions and best practices.
- Explain integration patterns with data science tools.
- Offer troubleshooting and optimization recommendations.
- Share community resources and support channels.
</tasks>

<operating_guidelines>
1. Provide accurate, detailed technical information.
2. Focus on practical, actionable guidance.
3. Reference official documentation and community resources.
4. Maintain expertise-level depth in responses.
5. Prioritize security and best practices.
</operating_guidelines>

<constraints>
- Stay within Nebari and data science infrastructure scope.
- Provide technically accurate information.
- Reference official sources when possible.
- Maintain professional, expert tone.
</constraints>
"""
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> IntentAgent:
    # Define model based on AI_MODE
    from src.marketplace.applications.nebari.models.default import model
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")
    
    # Define tools
    tools: list = []
    
    # Define agents
    agents: list = []

    # Define intents - Comprehensive Nebari Q&A Dataset
    intents: list = [
        # General and High Level
        Intent(intent_value="what is nebari", intent_type=IntentType.RAW, intent_target="Nebari is an open-source data science platform designed to enable collaboration and scalable infrastructure deployment using tools like JupyterHub, Dask, and conda-store."),
        Intent(intent_value="what problem does nebari solve", intent_type=IntentType.RAW, intent_target="Nebari simplifies the setup and management of cloud-based, scalable compute environments for data teams, reducing DevOps overhead."),
        Intent(intent_value="who is the target audience for nebari", intent_type=IntentType.RAW, intent_target="Nebari targets data scientists, engineers, and administrators who want to build or manage collaborative data science environments."),
        Intent(intent_value="what is the license for nebari", intent_type=IntentType.RAW, intent_target="Nebari is licensed under the BSD-3 clause, ensuring open access and flexibility for customization."),
        Intent(intent_value="who maintains nebari", intent_type=IntentType.RAW, intent_target="Nebari is maintained by a community of open-source contributors, originally emerging from the Quansight ecosystem."),
        Intent(intent_value="what are nebari's core value propositions", intent_type=IntentType.RAW, intent_target="Nebari provides a GitOps-based, cloud-agnostic, open-source platform for collaborative, reproducible, and scalable data science."),
        
        # Architecture and Deployment
        Intent(intent_value="what is nebari's architecture", intent_type=IntentType.RAW, intent_target="Nebari uses Terraform for cloud infrastructure provisioning, Kubernetes for orchestration, and Helm for application deployment."),
        Intent(intent_value="which cloud platforms are supported", intent_type=IntentType.RAW, intent_target="Nebari supports AWS, Azure, GCP, and existing Kubernetes clusters for hybrid or on-premises deployments."),
        Intent(intent_value="how do you deploy nebari", intent_type=IntentType.RAW, intent_target="Deployment involves generating a nebari-config.yaml file using `nebari init` and deploying infrastructure with `nebari deploy`."),
        Intent(intent_value="is nebari vendor-agnostic", intent_type=IntentType.RAW, intent_target="Yes. Nebari is designed to be cloud-neutral and portable across providers."),
        Intent(intent_value="what are the prerequisites for installation", intent_type=IntentType.RAW, intent_target="Users need access to a Kubernetes cluster, Terraform installed locally, and cloud credentials for deployment."),
        Intent(intent_value="how scalable is nebari", intent_type=IntentType.RAW, intent_target="Nebari scales horizontally via Kubernetes auto-scaling and Dask cluster expansion, supporting distributed computation."),
        
        # Features and Functionality
        Intent(intent_value="what are the key features of nebari", intent_type=IntentType.RAW, intent_target="Integrated JupyterHub, Dask Gateway, conda-store, centralized user management, monitoring via Grafana, and GitOps configuration."),
        Intent(intent_value="which data science tools are pre-integrated", intent_type=IntentType.RAW, intent_target="Nebari bundles JupyterLab, VSCode, Dask, Grafana, Argo, and conda-store for environment and workload management."),
        Intent(intent_value="how does nebari support collaboration", intent_type=IntentType.RAW, intent_target="By enabling centralized deployments, shared environments, and reproducible configurations across teams."),
        Intent(intent_value="does nebari support gpu workloads", intent_type=IntentType.RAW, intent_target="Yes, Nebari supports GPU-accelerated workloads via Kubernetes and Dask configurations."),
        Intent(intent_value="how is monitoring handled", intent_type=IntentType.RAW, intent_target="Monitoring is provided through Grafana dashboards, Loki for logs, and Prometheus for system metrics."),
        
        # Use Cases and Workflows
        Intent(intent_value="what are nebari's typical use cases", intent_type=IntentType.RAW, intent_target="Enterprise data science platforms, research collaboration hubs, scalable ML pipelines, and HPC compute environments."),
        Intent(intent_value="how do users access nebari", intent_type=IntentType.RAW, intent_target="Users log in via a web interface (JupyterHub) and access their workspace or custom environments."),
        Intent(intent_value="how does nebari support ml workflows", intent_type=IntentType.RAW, intent_target="By integrating Jupyter for experimentation, Dask for distributed training, and conda-store for environment reproducibility."),
        Intent(intent_value="how do teams share work", intent_type=IntentType.RAW, intent_target="Through shared Kubernetes namespaces, consistent conda environments, and Git-integrated workflows."),
        Intent(intent_value="what is the onboarding process for a new user", intent_type=IntentType.RAW, intent_target="Admins provision users, who log in through the central interface to create and manage notebooks and environments."),
        
        # Compatibility and Ecosystem
        Intent(intent_value="what open-source components make up nebari", intent_type=IntentType.RAW, intent_target="Terraform, Helm, Kubernetes, JupyterHub, Dask Gateway, conda-store, and Grafana."),
        Intent(intent_value="can nebari integrate with external data systems", intent_type=IntentType.RAW, intent_target="Yes, users can connect to databases, data lakes, and APIs via standard Python connectors."),
        Intent(intent_value="are there extension mechanisms", intent_type=IntentType.RAW, intent_target="Nebari allows Helm extensions and custom configuration overrides via YAML."),
        Intent(intent_value="is nebari cloud-neutral", intent_type=IntentType.RAW, intent_target="Yes, Nebari abstracts away provider-specific configurations to remain cloud-neutral."),
        Intent(intent_value="how is nebari versioned and updated", intent_type=IntentType.RAW, intent_target="Nebari uses semantic versioning with upgrade commands like `nebari upgrade -c nebari-config.yaml`."),
        
        # Performance, Scaling and Cost
        Intent(intent_value="how does nebari scale computationally", intent_type=IntentType.RAW, intent_target="Through Kubernetes node auto-scaling and Dask adaptive cluster scaling."),
        Intent(intent_value="how does nebari optimize cost", intent_type=IntentType.RAW, intent_target="By leveraging autoscaling groups and stopping idle resources, users pay only for active compute."),
        Intent(intent_value="is nebari free", intent_type=IntentType.RAW, intent_target="Nebari is open-source; users only pay for their underlying cloud infrastructure."),
        Intent(intent_value="does nebari support hpc-level workloads", intent_type=IntentType.RAW, intent_target="Yes, Nebari can be configured for HPC clusters and large distributed tasks."),
        Intent(intent_value="what performance monitoring tools exist", intent_type=IntentType.RAW, intent_target="Grafana dashboards, Prometheus metrics, and Dask task visualizers."),
        
        # Security, Governance and Compliance
        Intent(intent_value="what authentication methods are supported", intent_type=IntentType.RAW, intent_target="Nebari supports OAuth, Keycloak, and other identity providers for user authentication."),
        Intent(intent_value="does nebari isolate user environments", intent_type=IntentType.RAW, intent_target="Yes, each user runs in an isolated Kubernetes namespace with controlled resource limits."),
        Intent(intent_value="how are permissions and access managed", intent_type=IntentType.RAW, intent_target="Admins configure role-based access control (RBAC) via Keycloak or cloud IAM."),
        Intent(intent_value="does nebari comply with security standards", intent_type=IntentType.RAW, intent_target="While Nebari is open-source, compliance depends on configuration; it supports secure cloud deployments aligned with best practices."),
        Intent(intent_value="how are logs and activity monitored", intent_type=IntentType.RAW, intent_target="Nebari integrates Loki for centralized logging and Grafana for visualization."),
        
        # Community and Support
        Intent(intent_value="where is the nebari community active", intent_type=IntentType.RAW, intent_target="Discussions occur on GitHub issues, the Nebari Discourse forum, and community calls."),
        Intent(intent_value="how often is nebari updated", intent_type=IntentType.RAW, intent_target="Nebari follows a rolling release cycle with frequent updates and bug fixes."),
        Intent(intent_value="are there tutorials or quickstarts", intent_type=IntentType.RAW, intent_target="Yes, the official site includes quickstart guides for each cloud provider and local testing."),
        Intent(intent_value="is enterprise support available", intent_type=IntentType.RAW, intent_target="Support can be community-based or through consulting partners specializing in Nebari."),
        Intent(intent_value="can i contribute to nebari", intent_type=IntentType.RAW, intent_target="Yes, contributors can open issues or pull requests on GitHub under the nebari-dev organization."),
    ]

    return NebariAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        agents=agents,
        intents=intents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=None
    )

class NebariAgent(IntentAgent):
    pass
