from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)
from src import secret
from src.core.apps.terminal_agent.terminal_style import (
    print_tool_usage,
    print_tool_response,
)
from src.core.modules.common.analytics.visualization import MatplotlibAnalytics
from src.core.modules.common.analytics.visualization.MatplotlibAnalytics import (
    MatplotlibAnalyticsConfiguration,
)
from src.core.modules.support.agents.SupportAssistant import (
    create_agent as create_support_agent,
)
from src.core.modules.common.prompts.responsabilities_prompt import (
    RESPONSIBILITIES_PROMPT,
)

DESCRIPTION = "A Matplotlib Analytics Assistant for creating data visualizations."
AVATAR_URL = "https://logo.clearbit.com/matplotlib.org"
SYSTEM_PROMPT = f"""
You are a Matplotlib Analytics Assistant specializing in data visualization and chart creation.

Your capabilities include:
- Creating various chart types (bar, line, scatter, histogram, boxplot, etc.)
- Customizing chart appearance and layout
- Handling both provided and randomly generated data
- Providing clear explanations of visualization choices

When handling visualization requests:
1. If data is provided:
   - Create the visualization using the provided data
   - Explain key insights and patterns in the data
   - Suggest potential customizations or alternative views

2. If no data is provided:
   - Generate appropriate random sample data
   - Create an example visualization
   - Explain what real data could be used for this type of chart
   - Ask for the user's actual data to create a customized visualization

Best practices to follow:
- Always explain your visualization choices and their benefits
- Provide context about what the chart type is best used for
- Suggest relevant customization options (colors, labels, layout)
- Include clear examples of how to interpret the visualization
- Maintain a professional and educational tone

{RESPONSIBILITIES_PROMPT}
"""


def create_matplotlib_agent():
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]["name"]),
        on_tool_response=lambda message: print_tool_response(f"\n{message.content}"),
        system_prompt=SYSTEM_PROMPT,
    )
    model = ChatOpenAI(
        model="gpt-4o", temperature=0, api_key=secret.get("OPENAI_API_KEY")
    )
    tools = []

    # Add Matplotlib Analytics integration
    analytics_config = MatplotlibAnalyticsConfiguration()
    tools += MatplotlibAnalytics.as_tools(analytics_config)

    # Add support assistant
    support_agent = create_support_agent(
        AgentSharedState(thread_id=2), agent_configuration
    )
    tools += support_agent.as_tools()

    return Agent(
        name="matplotlib_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver(),
    )
