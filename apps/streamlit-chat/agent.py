from langchain.agents import AgentExecutor, create_react_agent
from llm import llm
from langchain.tools import Tool
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate
# from tools.vector import kg_qa
from tools.cypher import cypher_qa

# def run_retriever(query):
#     results = kg_qa.invoke({"query": query})
#     print(results)
#     return results["result"]

def run_cypher(query):
    results = cypher_qa.invoke({"query": query})
    return results["result"]

tools = [
    Tool.from_function(
        name="General Chat",
        description="For content creation and general chat not covered by other tools",
        func=llm.invoke,
        return_direct=True
        ),
    # Tool.from_function(
    #     name="Vector Search Index",
    #     description="""Useful to provide information about content. 
    #     Not useful for any sort of aggregation like counting the number of posts, ranking and filtering by date, etc.
    #     Use full question as input.
    #     """,
    #     func = run_retriever,
    #     return_direct=True
    # ),
    Tool.from_function(
        name="Graph Cypher QA Chain",
        description="""Useful when you need to answer questions about content, concepts, target, objective, content types and their dependencies. 
        Also useful for any sort of aggregation like counting the number of posts, ranking and filtering by date, etc.
        Use full question as input.
        """,
        func = run_cypher,
        return_direct=True
    ),
]

memory = ConversationBufferWindowMemory(
    memory_key='chat_history',
    k=5,
    return_messages=True,
)

agent_prompt = PromptTemplate.from_template("""
Act as a Content Assistant who has access to valuable data and insights about the content strategy. 
Your role is to manage and optimize the content, ensuring it reaches the target audience effectively. 
When a user ask a question related to posts, always returned the title, the url and the date to identify them.
When a user ask for a list of somethings, first always return the number results and the first 3 results as bullet list. 
Then ask if the user wants to have the full list if it is not complete.
                                            
Do not answer any questions that do not relate to content.

Use your pre-trained knowledge only to answer questions about content creation with the information provided in the context.

TOOLS:
------

You have access to the following tools:

{tools}

To use a tool, please use the following format:

```
Thought: Do I need to use a tool? Yes
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
```

When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format:

```
Thought: Do I need to use a tool? No
Final Answer: [your response here]
```

Begin!

Previous conversation history:
{chat_history}

New input: {input}
{agent_scratchpad}
""")

agent = create_react_agent(llm, tools, agent_prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    verbose=True
    )

def generate_response(prompt):
    """
    Create a handler that calls the Conversational agent
    and returns a response to be rendered in the UI
    """

    response = agent_executor.invoke({"input": prompt})

    return response['output']