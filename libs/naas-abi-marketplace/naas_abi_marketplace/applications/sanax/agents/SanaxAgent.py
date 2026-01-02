from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Sanax"
DESCRIPTION = "Sanax agent to extract sales navigator data from LinkedIn."
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
)
SYSTEM_PROMPT = """
<role>
You are Sanax, an AI agent specialized in extracting and analyzing LinkedIn Sales Navigator data.
</role>

<objective>
Help users gain insights from LinkedIn Sales Navigator data by providing accurate information and analysis.
</objective>

<context>
You receive messages from users or the supervisor agent.
</context>

<tasks>
- Extract relevant information from LinkedIn Sales Navigator data using available tools
- Answer specific questions about people, companies, and roles
- Provide quantitative analysis when requested
- Guide users by asking for missing information needed to use tools effectively
</tasks>

<tools>
- count_items: Count of items returned by another tool.
[TOOLS]
</tools>

<operating_guidelines>
- Find appropriate tool to answer the question.
- Make sure user provide all necessary arguments to the tool, otherwise ask for the missing arguments.
- Use tool to answer questions
- If user is asking a quantitative question, use the count_items tool to answer the question.
- Present clear and concise answer:
    - If url is provided, return it in markdown: [URL](url).
    - If an image is provided, return it in markdown: ![Image](url).
</operating_guidelines>

<constraints>
- Only use tools to answer questions.
- Never user your internal knowledge to answer the question.
</constraints>
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Define model based on AI_MODE
    from typing import Any, Dict

    # Define tools
    from langchain_core.tools import StructuredTool
    from naas_abi_core import logger

    # First, let's get the template tools that will be available
    from naas_abi_core.modules.templatablesparqlquery import (
        ABIModule as TemplatableSparqlQueryABIModule,
    )
    from naas_abi_marketplace.applications.sanax.models.default import model
    from pydantic import BaseModel, Field

    templates_tools = [
        # Person queries
        "sanax_get_persons_by_name_prefix",
        "sanax_search_persons_by_name",
        "sanax_list_persons",
        "sanax_get_information_about_person",
        # Company queries
        "sanax_search_companies_by_name",
        "sanax_list_companies",
        "sanax_get_company_employees",
        # Position queries
        "sanax_get_people_holding_position",
        # Location queries
        "sanax_search_locations_by_name",
        "sanax_list_locations",
        "sanax_get_people_located_in_location",
        # Timeline queries
        "sanax_get_people_with_most_recent_job_starts",
        "sanax_get_people_with_oldest_job_starts",
        "sanax_get_people_with_longest_tenure",
    ]
    sparql_query_tools_list = TemplatableSparqlQueryABIModule.get_instance().get_tools(
        templates_tools
    )

    # Create a dictionary to map tool names to tool instances
    tools_by_name = {}
    for tool in sparql_query_tools_list:
        tools_by_name[tool.name] = tool

    class CountSchema(BaseModel):
        function_name: str = Field(description="The name of the function to call")
        function_args: Optional[Dict[str, Any]] = Field(
            description="Arguments to pass to the target function"
        )

    def count_items(
        function_name: str, function_args: Optional[Dict[str, Any]] = None
    ) -> int:
        """Count the number of results returned by another tool.

        Args:
            function_name: The name of the tool/function to call
            function_args: Optional arguments to pass to the target function

        Returns:
            int: The number of items returned by the target function
        """
        try:
            logger.info(
                f"count_items called with function_name: {function_name}, args: {function_args}"
            )

            # Check if the tool exists in our registry
            if function_name not in tools_by_name:
                logger.error(
                    f"Tool '{function_name}' not found in available tools: {list(tools_by_name.keys())}"
                )
                return 0

            # Get the target tool
            target_tool = tools_by_name[function_name]

            # Prepare arguments for the target tool
            args = function_args or {}

            # Call the target tool
            logger.info(f"Calling tool '{function_name}' with args: {args}")
            result = target_tool.invoke(args)

            # Count the results
            if isinstance(result, list):
                count = len(result)
            elif isinstance(result, dict):
                # If it's a dict, count the number of items
                count = len(result)
            elif isinstance(result, str):
                # If it's a string, try to parse it as JSON to count items
                try:
                    import json

                    parsed = json.loads(result)
                    if isinstance(parsed, (list, dict)):
                        count = len(parsed)
                    else:
                        count = 1
                except Exception:
                    count = 1
            else:
                # For other types, assume it's a single result
                count = 1

            logger.info(f"Tool '{function_name}' returned {count} items")
            return count

        except Exception as e:
            logger.error(f"Error in count_items: {str(e)}")
            return 0

    count_items_tool = StructuredTool(
        name="count_items",
        description="Count the number of results returned by another tool by calling it and counting the returned items.",
        func=count_items,
        args_schema=CountSchema,
    )

    tools: list = [count_items_tool]

    # Add the template tools to the tools list
    tools += sparql_query_tools_list

    # Define agents
    agents: list = []

    # Define intents
    intents: list = [
        # Person search and information queries
        Intent(
            intent_value="what do you know about {person}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_information_about_person",
        ),
        Intent(
            intent_value="tell me about {person}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_information_about_person",
        ),
        Intent(
            intent_value="who is {person}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_information_about_person",
        ),
        Intent(
            intent_value="search for people named {name}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_search_persons_by_name",
        ),
        Intent(
            intent_value="find people with name {name}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_search_persons_by_name",
        ),
        Intent(
            intent_value="show me people whose names start with {prefix}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_persons_by_name_prefix",
        ),
        # Company related queries
        Intent(
            intent_value="who works at {company}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_company_employees",
        ),
        Intent(
            intent_value="show me employees at {company}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_company_employees",
        ),
        Intent(
            intent_value="search for companies named {name}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_search_companies_by_name",
        ),
        Intent(
            intent_value="find companies with name {name}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_search_companies_by_name",
        ),
        Intent(
            intent_value="how many people work at {company}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_count_people_working_for_company",
        ),
        # Position/role queries
        Intent(
            intent_value="who has the position of {position}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_people_holding_position",
        ),
        Intent(
            intent_value="show me people with title {position}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_people_holding_position",
        ),
        Intent(
            intent_value="find people who are {position}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_people_holding_position",
        ),
        # Location based queries
        Intent(
            intent_value="who are the people in {location}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_people_located_in_location",
        ),
        Intent(
            intent_value="show me people located in {location}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_people_located_in_location",
        ),
        Intent(
            intent_value="how many people are in {location}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_count_people_located_in_location",
        ),
        Intent(
            intent_value="count people in {location}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_count_people_located_in_location",
        ),
        # Job timing queries
        Intent(
            intent_value="who started their job most recently",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_people_with_most_recent_job_starts",
        ),
        Intent(
            intent_value="show me recent job starts",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_people_with_most_recent_job_starts",
        ),
        Intent(
            intent_value="who started their job longest ago",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_people_with_oldest_job_starts",
        ),
        Intent(
            intent_value="show me oldest job starts",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_people_with_oldest_job_starts",
        ),
        Intent(
            intent_value="who has worked the longest for a {company}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_people_with_longest_tenure",
        ),
        Intent(
            intent_value="show me people with longest tenure for a {company}",
            intent_type=IntentType.TOOL,
            intent_target="sanax_get_people_with_longest_tenure",
        ),
    ]
    # Set configuration
    system_prompt = SYSTEM_PROMPT.replace(
        "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    )
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=system_prompt,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return SanaxAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class SanaxAgent(IntentAgent):
    pass
