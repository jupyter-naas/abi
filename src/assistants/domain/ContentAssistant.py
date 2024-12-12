from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.integrations import LinkedinIntegration, ReplicateIntegration
from src.integrations.ReplicateIntegration import ReplicateIntegrationConfiguration
from src.integrations.LinkedinIntegration import LinkedinIntegrationConfiguration
from src.workflows.content_assistant.LinkedinPostsWorkflow import LinkedinPostsWorkflow, LinkedinPostsWorkflowConfiguration

CONTENT_ASSISTANT_INSTRUCTIONS = """
You are a Content Assistant with access to valuable data and insights about content strategy.
Your role is to manage and optimize content, ensuring it reaches the target audience effectively.

Start each conversation by:
1. Introducing yourself
2. Providing analysis of the last 2 weeks with key publications sorted by date including:
   - Content title
   - Concepts
   - Metrics
   - URL
3. Displaying this image showing content views evolution:
   ![Content KPI](https://public.naas.ai/amVyZW15LTQwbmFhcy0yRWFp/asset/c47d672317b4ac839efef8a903fc818a562a79d951ea24f53e6d9d9a0120.png)

Always:
1. Use LinkedIn data for content performance analysis
2. Use Replicate for content creation
3. Provide structured, markdown-formatted responses
4. Include metrics and performance indicators in your analysis
"""

def create_content_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(
        model="gpt-4o-mini", 
        temperature=0.2, 
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []
    
    if (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        linkedin_integration_config = LinkedinIntegrationConfiguration(li_at=li_at, jsessionid=jsessionid)
        
        tools += LinkedinIntegration.as_tools(linkedin_integration_config)

        # Add LinkedinPostsWorkflow tool
        linkedin_posts_workflow = LinkedinPostsWorkflow(LinkedinPostsWorkflowConfiguration(
            linkedin_integration_config=linkedin_integration_config
        ))
        tools += linkedin_posts_workflow.as_tools()

    if replicate_key := secret.get('REPLICATE_API_KEY'):
        tools += ReplicateIntegration.as_tools(ReplicateIntegrationConfiguration(api_key=replicate_key))

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=CONTENT_ASSISTANT_INSTRUCTIONS
        )
    
    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return Agent(
        name="content_assistant",
        description="Use for content analysis and optimization",
        chat_model=model, 
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 