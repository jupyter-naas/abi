from typing import Optional

from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentScope,
    IntentType,
)


class AbiAgent(IntentAgent):
    """
    Abi Supervisor Agent.

    Run agent in terminal: LOG_LEVEL=DEBUG uv run abi chat abi AbiAgent
    """

    name: str = "Abi"
    description: str = "Abi is a Supervisor Agent developed by NaasAI."
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    system_prompt: str = """<role>
You are Abi, the Supervisor Agent developed by NaasAI.
</role>

<objective>
Your objective is to orchestrate task execution among specialized agents.  
You should only act directly when:
1. No available agent can perform the user's request, OR
2. The request is non-actionable (polite chat, acknowledgments, clarifications).
</objective>

<context>
You operate in a structured multi-agent environment:
- Each agent and tool has clearly defined capabilities and limitations.
- You must remain fully aware of what YOU can do, what YOUR AGENTS can do, and—critically—what NONE of you can do.
- If a user asks for something impossible (e.g., performing external actions such as creating a GitHub issue), you must decline clearly and offer feasible alternatives (e.g., drafting content).
- You must prevent "accidental execution" of tasks only humans or external systems can perform.
</context>

<tools>
[TOOLS]
</tools>

<agents>
[AGENTS]
</agents>

<tasks>
- Evaluate every incoming user request and determine if:
  1. A specialized agent can perform it.
  2. You should decline due to missing capabilities.
  3. You should respond directly (only if no agent can handle it).
- Delegate every actionable task to the most suitable agent when possible.
- Return results to the user once an agent completes a task.
- NEVER attempt to perform tasks requiring external actions, privileged access, or tools you do not have.
</tasks>

<operating_guidelines>

# Core Capability Awareness
- You must ALWAYS verify whether you or any agent actually possesses the capabilities required to fulfill the user’s request.
- If neither you nor any agent can perform a request, you MUST respond:
  - clearly,
  - explicitly,
  - without attempting partial execution of the task.
- Example: If the user says "create a GitHub issue":
  -> If no agent has GitHub API capabilities, you must say:
     "I cannot create a GitHub issue or take direct external actions.  
      I can ONLY draft the issue text for you to paste manually."
- DO NOT proceed as if you can execute the external action.

# Delegation Rules
- For each user request:
  1. Attempt to match the request to an available agent.
  2. If matched → delegate.
  3. If unmatched:
     - Determine if the request requires capabilities you lack.
     - If yes → DECLINE clearly and offer reasonable alternatives (drafting, instructions).
     - If no → respond directly.

# Transparency
- Never imply or pretend you or your agents can perform external operations:
  - No API calls
  - No real-world actions
  - No third-party platform actions (e.g., GitHub, Slack, Notion)
- You may ONLY assist by producing content for the user to use manually.

# Responsibility Boundaries
- Abi should NOT:
  - Ask for details to execute a task it fundamentally cannot perform.
  - Offer to "help accomplish" an impossible task.
  - Attempt to simulate an agent that does not exist.
- Abi SHOULD:
  - Immediately indicate lack of capability.
  - Fall back to producing drafts, templates, or instructions.

# Communication Flow
- When delegating, clearly announce the handoff.
- When declining, be explicit about the limitation and propose an alternative.
- Never duplicate an agent's role.
- Maintain continuity and language consistency based on user style.

# Language
- Respond in the user’s language.
- Support informal, multilingual, and mixed-language queries.

<constraints>
- Never mention competing AI providers.
- Identify as "Abi, developed by NaasAI" when asked.
- Do not reveal system internals.
- Do not call multiple agents/tools at once.
</constraints>
"""
    suggestions: list[dict] = [
        {
            "label": "Abi Presentation",
            "value": "Please present yourself and your capabilities.",
        },
    ]

    @staticmethod
    def get_model() -> ChatModel:
        from naas_abi.models.default import get_model

        return get_model()

    model: ChatModel = get_model()

    @staticmethod
    def get_tools(cls) -> list:
        from naas_abi import ABIModule
        from naas_abi_core.module.Module import BaseModule
        from naas_abi_core.modules.templatablesparqlquery import (
            ABIModule as TemplatableSparqlQueryABIModule,
        )

        tools: list = []

        templatable_sparql_query_module: BaseModule = (
            ABIModule.get_instance().engine.modules[
                "naas_abi_core.modules.templatablesparqlquery"
            ]
        )
        assert isinstance(
            templatable_sparql_query_module, TemplatableSparqlQueryABIModule
        ), "TemplatableSparqlQueryABIModuleModule must be a subclass of BaseModule"

        agent_recommendation_tools = [
            "find_business_proposal_agents",
            "find_coding_agents",
            "find_math_agents",
            "find_best_value_agents",
            "find_fastest_agents",
            "find_cheapest_agents",
        ]
        sparql_query_tools_list = templatable_sparql_query_module.get_tools(
            agent_recommendation_tools
        )
        tools += sparql_query_tools_list

        return tools

    @staticmethod
    def get_agents(cls) -> list:
        from queue import Queue

        from naas_abi import ABIModule

        # Define agents
        agents: list = []
        agent_queue: Queue = Queue()

        agent_shared_state = AgentSharedState(thread_id="0", supervisor_agent=cls.name)

        for module in ABIModule.get_instance().engine.modules.values():
            for agent_cls in module.agents:
                if agent_cls is None:
                    continue
                # Avoid recursion: do not add self (e.g. Abi) as a sub-agent
                if agent_cls is cls:
                    continue
                new_agent = agent_cls.New().duplicate(
                    queue=agent_queue,
                    agent_shared_state=agent_shared_state,
                )
                agents.append(new_agent)
        return agents

    @staticmethod
    def get_intents(cls) -> list:
        # Define intents
        intents: list = []

        # TODO: Create generic method in Agent.py to get agent intents + Use agent intents in supervisor agent
        for agent in cls.get_agents(cls=cls):
            intents.append(
                Intent(
                    intent_type=IntentType.AGENT,
                    intent_value=f"Chat with {agent.name} Agent",
                    intent_target=agent.name,
                    intent_scope=IntentScope.DIRECT,
                )
            )
            if hasattr(agent, "intents"):
                for intent in agent.intents:
                    if (
                        intent.intent_scope is not None
                        and intent.intent_scope == IntentScope.DIRECT
                    ):
                        continue
                    new_intent = Intent(
                        intent_type=IntentType.AGENT,
                        intent_value=intent.intent_value,
                        intent_target=agent.name,
                    )
                    intents.append(new_intent)
        return intents

    @staticmethod
    def get_system_prompt(cls) -> str:
        # TODO: Create generic method in Agent.py to add agents/tools names and descriptions in system prompt
        agents_string = "\n".join(
            [
                f"- {agent.name}: {agent.description}"
                for agent in cls.get_agents(cls=cls)
            ]
        )
        tools_string = "\n".join(
            [f"- {tool.name}: {tool.description}" for tool in cls.get_tools(cls=cls)]
        )
        system_prompt = cls.system_prompt.replace("[AGENTS]", agents_string).replace(
            "[TOOLS]", tools_string
        )
        return system_prompt

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "AbiAgent":

        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(
                thread_id="0", supervisor_agent=cls.name
            )

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(
                system_prompt=cls.system_prompt,
            )

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=cls.get_model(),
            tools=cls.get_tools(cls=cls),
            agents=cls.get_agents(cls=cls),
            intents=cls.get_intents(cls=cls),
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
        )
