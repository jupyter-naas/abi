from typing import Optional

from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.agent.Agent import Agent
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
    description: str = "Abi is a orchestrator Agent developed by NaasAI."
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    system_prompt: str = """<role>You are Abi, the orchestrator Agent developed by NaasAI.
</role>

<objective>
Handle user requests by delegating to the available agents or tools.
</objective>

<context>
You will receive messages from users or from agents you supervise. 
Respond only based on what your available agents and tools can actually deliver.
</context>

<tasks>
1. Match the user request to the best available agent or tool.
2. If a match is found, delegate to that agent or tool with full context and report the result back verbatim.
3. If no match is found, tell the user you do not have the capibilities to handle its request and propose him alternatives based on your available agents and tools.
</tasks>

<tools>
[TOOLS]
</tools>

<agents>
[AGENTS]
</agents>

<operating_guidelines>
- Maintain a clear, concise, and professional tone in all interactions.
- Always include all relevant output and context from your tools and agents in your responses.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- Never invent, suggest, or imply the existence of any other agent, tool, module, or capability.
- Never claim to have performed an action (routing, provisioning, activation, notification) unless a real tool or agent call was made and returned a result.
- Never fabricate timelines, confirmations, or follow-up steps.
- Do not simulate conversations with imaginary sub-agents or services.
- Keep responses concise and factual.
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
    def get_agents(cls) -> tuple[list, AgentSharedState]:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from queue import Queue

        from naas_abi import ABIModule

        agent_queue: Queue = Queue()
        agent_shared_state = AgentSharedState(thread_id="0", supervisor_agent=cls.name)

        candidate_classes: list = []
        for module in ABIModule.get_instance().engine.modules.values():
            for agent_cls in module.agents:
                if agent_cls is None:
                    continue
                if agent_cls is cls:
                    continue
                if issubclass(agent_cls, Agent):
                    candidate_classes.append(agent_cls)

        def _load_agent(agent_cls: type) -> Agent | None:
            if issubclass(agent_cls, IntentAgent) or issubclass(agent_cls, Agent):
                return agent_cls.New().duplicate(
                    queue=agent_queue, agent_shared_state=agent_shared_state
                )
            return None

        agents: list = []
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(_load_agent, c): c for c in candidate_classes}
            for future in as_completed(futures):
                agents.append(future.result())

        return agents, agent_shared_state

    @staticmethod
    def get_intents(agents: list) -> list:
        # Define intents
        intents: list = []

        # TODO: Create generic method in Agent.py to get agent intents + Use agent intents in supervisor agent
        for agent in agents:
            # Primary routing intent using the agent name
            intents.append(
                Intent(
                    intent_type=IntentType.AGENT,
                    intent_value=f"Chat with {agent.name} Agent",
                    intent_target=agent.name,
                    intent_scope=IntentScope.DIRECT,
                )
            )

            # Additional routing intents to catch natural agent-name mentions
            # (e.g. "search on grok", "use grok", "ask grok") without requiring an LLM call.
            for verb in ("use", "ask", "search on", "talk to", "route to"):
                intents.append(
                    Intent(
                        intent_type=IntentType.AGENT,
                        intent_value=f"{verb} {agent.name}",
                        intent_target=agent.name,
                        intent_scope=IntentScope.DIRECT,
                    )
                )

            # Description-based intent for broader semantic coverage
            if hasattr(agent, "description") and agent.description:
                intents.append(
                    Intent(
                        intent_type=IntentType.AGENT,
                        intent_value=agent.description,
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

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "AbiAgent":
        from naas_abi_core import logger

        tools = cls.get_tools(cls=cls)

        agents, agent_shared_state = cls.get_agents(cls=cls)
        logger.debug(f"Agents: {agents}")

        intents = cls.get_intents(agents=agents)
        logger.debug(f"Intents: {intents}")

        if agent_configuration is None:
            tools_section = (
                "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
                or ""
            )
            agents_section = (
                "\n".join([f"- {agent.name}: {agent.description}" for agent in agents])
                or ""
            )
            agent_configuration = AgentConfiguration(
                system_prompt=cls.system_prompt.replace(
                    "[TOOLS]", tools_section
                ).replace("[AGENTS]", agents_section)
            )

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=cls.get_model(),
            tools=tools,
            agents=agents,
            intents=intents,
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
        )
