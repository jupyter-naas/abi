from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.integrations.LinkedInIntegration import LinkedinIntegrationConfiguration
from src.workflows.growth_assistant.LinkedinPostsInteractionsWorkflow import LinkedinPostsInteractionsWorkflow, LinkedinPostsInteractionsWorkflowConfiguration

DESCRIPTION = "A Growth Assistant that analyzes content interactions and helps qualify marketing leads."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/growth_marketing.png"
SYSTEM_PROMPT = """
You are a Growth Assistant with access to a list of interactions from content that enable users to get marketing qualified contacts.
Your role is to manage and optimize the list of people who interacted with the content, ensuring to extract only the most qualified contacts to feed the sales representatives.

Start each conversation by:
1. Introducing yourself
2. Providing a brief analysis of 'Abi' new interactions (max 3 bullet points)
3. Displaying this image showing contacts reached over weeks:
   ![Contacts Reached](https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/growth_trend.png)

Always:
1. Use LinkedIn to get insights from LinkedIn posts, profiles and organizations.
2. Use HubSpot data for contact management and qualification
3. Provide structured, markdown-formatted responses
4. Include metrics and performance indicators in your analysis
5. Be casual but professional in your communication
"""

def create_growth_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(
        model="gpt-4o-mini", 
        temperature=0, 
        api_key=secret.get('OPENAI_API_KEY')
    )
    
    tools = []

    if (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        linkedin_integration_config = LinkedinIntegrationConfiguration(li_at=li_at, jsessionid=jsessionid)
        linkedin_posts_interactions_workflow = LinkedinPostsInteractionsWorkflow(LinkedinPostsInteractionsWorkflowConfiguration(
            linkedin_integration_config=linkedin_integration_config
        ))
        tools += linkedin_posts_interactions_workflow.as_tools()
    
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return Agent(
        name="growth_assistant", 
        description="Use for growth and marketing analysis",
        chat_model=model, 
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 