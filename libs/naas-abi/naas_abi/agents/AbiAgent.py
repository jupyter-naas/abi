
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
3. For organization/workspace/user admin requests (list orgs, create workspaces, invite or remove members, update roles or your own profile), use the Nexus admin tools directly. Do not invent success.
        4. For Slides edits (deck.html), use the Slides tools surgically. Never dump or rewrite the full deck for a small text change. When a deck is open in the Slides UI, you are already editing that presentation: do not ask which deck. For a new seed brief that needs facts, call web_search first, then write the open HTML.
        5. If no match is found, tell the user you do not have the capabilities to handle its request and propose alternatives based on your available agents and tools.
</tasks>

<slides_guidelines>
- You edit the open presentation HTML only (Coder workspace files via sidecar when available; Forgejo for version history). Preview is that HTML. PPTX is an export reconstructed from the live .slide DOM at 1280x720. Do not edit buildPptx, FOOTER_TXT, or other script strings.
- Never ask which deck, slug, file, or template when open-deck context is present. Omit slug on tool calls; tools default to the open deck.
- A new deck is already a seed. The user's first message is the brief for that open deck.html. Do not ask which file to edit. Default to 6-8 slides after research unless they specified length.
- Research loop (required, not optional) for news, current events, "what is going on", country or company briefings, or any factual deck:
  1. Call web_search first. Run 2 to 4 queries (latest developments, context, key actors, dates). Include the current year. Stop searching after 4 queries.
  2. Optionally one second-pass query to contradict or confirm named sources, still within the 4-query budget.
  3. Outline 6-8 sections against the open template.
  4. Then write or replace HTML in the open deck.html with real claims, dates, and named sources. Do not keep searching instead of writing.
- Do not write slides from training data alone when the brief is time-sensitive. Slides write tools will reject the edit until web_search has run.
- Do not leave template filler (Presentation Title, Agenda: Context / Approach / Plan, lorem). Keep the seed template CSS and structure (Minimal Light, Pitch Dark, or Executive). Replace section titles and body copy only. Do not invent a new design system.
- Cite sources in speaker-visible lines or footer/source lines if the template allows, without wrecking layout.
- Tiny copy edits (title typo, color tweak) may skip search. A first-message create/brief may not.
- Prefer replace_in_slides_deck for copy edits (matches plain text and HTML entities like &amp; so cover &lt;h1&gt; and body copy update in Preview and PPTX).
- For cover / title / slide 1 edits: call replace_in_slides_deck with section_index=0 and occurrence=0. Never use occurrence=1 for the title (that hits &lt;title&gt;/menubar before the cover &lt;h1&gt; Preview shows). Confirm cover_h1_updated is true in the tool result.
- Use list_slides_sections then read_slides_section for targeted inspection.
- Use write_slides_section to replace one &lt;section&gt; only. Keep .deck / .slide 1280x720, cover h1, and theme CSS variables.
- Avoid read_slides_deck with include_assets=true. Default reads redact embedded data-URLs on purpose.
- Avoid write_slides_deck unless creating or restructuring the whole presentation.
</slides_guidelines>

<tools>
[TOOLS]
</tools>

<agents>
[AGENTS]
</agents>

<operating_guidelines>
- Maintain a clear, concise, and professional tone in all interactions.
- Format all responses as clean, well-structured Markdown (use headings, bullet lists, lines breaks and code blocks when helpful).
- Always include all relevant output and context from your tools and agents in your responses.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- If you need to ask the user a question, display the question after two markdown line breaks: "\\n\\n".
- Never invent, suggest, or imply the existence of any other agent, tool, module, or capability.
- Never claim to have performed an action (routing, provisioning, activation, notification) unless a real tool or agent call was made and returned a result.
- Never fabricate timelines, confirmations, or follow-up steps.
- Do not simulate conversations with imaginary sub-agents or services.
- Keep responses concise and factual.
</constraints>
"""
    suggestions: list[dict] = [
        {
            "label": "What can you do?",
            "value": "What can you do?",
            "description": "Get an overview of all available agents and their capabilities",
        },
        {
            "label": "Find the right agent",
            "value": "Find the best agent for my task",
            "description": "Let Abi recommend the right agent for your request",
        },
        {
            "label": "Explore my knowledge graph",
            "value": "",
            "description": "Browse entities and relationships in your data",
            "disabled": True,
        },
        {
            "label": "Browse Marketplace",
            "value": "",
            "description": "Discover and enable modules from the marketplace",
            "cta": "/marketplace",
        },
    ]
    # @staticmethod
    # def build_suggestions(cls: type) -> list[dict[str, str]]:
    #     from naas_abi import ABIModule

    #     suggestions: list[dict[str, str]] = []
    #     seen_agent_names: set[str] = set()
    #     for module in ABIModule.get_instance().engine.modules.values():
    #         for agent_cls in module.agents:
    #             if agent_cls is None:
    #                 continue
    #             if issubclass(agent_cls, Agent):
    #                 agent_name = str(agent_cls.name)
    #                 if agent_name in seen_agent_names:
    #                     continue
    #                 seen_agent_names.add(agent_name)
    #                 suggestions.append(
    #                     {
    #                         "label": agent_name,
    #                         "value": f"Chat with {agent_name}",
    #                     }
    #                 )
    #     return suggestions

    # suggestions: list[dict[str, str]] = build_suggestions(cls=AbiAgent)

    @staticmethod
    def get_tools() -> list:
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

        from naas_abi.agents.tools.nexus_admin_tools import nexus_admin_tools

        tools += nexus_admin_tools()

        try:
            from naas_abi.agents.tools.slides_tools import slides_tools

            tools += slides_tools()
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("slides tools unavailable: %s", exc)

        try:
            from naas_abi.agents.slides_policy import attach_slides_research_note
            from zen.tools.WebTools import make_web_fetch_tool, make_web_search_tool

            tools += [
                attach_slides_research_note(make_web_search_tool()),
                make_web_fetch_tool(),
            ]
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("web search tools unavailable: %s", exc)

        # NOTE: coding-workspace filesystem tools (write_file/read_file/list_dir)
        # are injected generically for every agent via default_tools, so the
        # supervisor and all sub-agents can act on the caller's workspace.
        return tools

    @classmethod
    def get_agents(cls) -> tuple[list, AgentSharedState]:
        from queue import Queue

        from naas_abi import ABIModule

        agent_queue: Queue = Queue()
        agent_shared_state = AgentSharedState(thread_id="0", supervisor_agent=cls.name)

        candidate_classes: list[type[Agent]] = []
        seen_candidate_class_names: set[str] = set()

        def _register_candidate(agent_cls: type[Agent]) -> None:
            if agent_cls is cls:
                return
            candidate_name = f"{agent_cls.__module__}.{agent_cls.__name__}"
            if candidate_name in seen_candidate_class_names:
                return
            seen_candidate_class_names.add(candidate_name)
            candidate_classes.append(agent_cls)

        abi_module = ABIModule.get_instance()

        for agent_cls in abi_module.agents:
            if agent_cls is None:
                continue
            if issubclass(agent_cls, Agent):
                _register_candidate(agent_cls)

        for module in abi_module.engine.modules.values():
            for agent_cls in module.agents:
                if agent_cls is None:
                    continue
                if issubclass(agent_cls, Agent):
                    _register_candidate(agent_cls)

        # NOTE: this used to run in a ThreadPoolExecutor with the default
        # max_workers (up to 32 threads). Agent construction is pure-Python
        # (pydantic models, langchain tool wiring, supervisor attachment) and
        # therefore GIL-bound — concurrent threads couldn't overlap useful
        # work and just thrashed on lock waits. cProfile showed ~3s out of
        # 3.76s spent in `_thread.lock.acquire` / `as_completed`. Running
        # serially removes that overhead entirely.
        agents: list = []
        for agent_cls in candidate_classes:
            if not issubclass(agent_cls, Agent):
                continue
            agent = agent_cls.New().duplicate(
                queue=agent_queue, agent_shared_state=agent_shared_state
            )
            if agent is not None:
                agents.append(agent)

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
    def get_chat_model_id(cls) -> str:
        from naas_abi import ABIModule

        return str(ABIModule.get_instance().configuration.abi_agent_model)

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
        model_id: str | None = None,
    ) -> "AbiAgent":
        from naas_abi import ABIModule
        from naas_abi.agents.slides_policy import bind_slides_reasoning

        abi_module = ABIModule.get_instance()
        resolved_model = model_id or abi_module.configuration.abi_agent_model
        chat_model = abi_module.engine.services.model_registry.get_chat_model(
            resolved_model,
            provider=abi_module.configuration.abi_agent_provider,
        )
        chat_model = bind_slides_reasoning(chat_model, resolved_model)

        tools = cls.get_tools()

        agents, agent_shared_state = cls.get_agents()
        intents = cls.get_intents(agents=agents)

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
            chat_model=chat_model,
            tools=tools,
            agents=agents,
            intents=intents,
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
        )
