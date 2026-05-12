from queue import Queue
from typing import Callable, Literal, Optional, Union

import pydash as pd
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import BaseTool, Tool
from langchain_core.tools import tool as lc_tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from naas_abi_core.models.Model import ChatModel
from naas_abi_core.utils.Logger import logger

from .Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from .beta.IntentMapper import Intent, IntentType
from .IntentAgent import IntentAgent, IntentState

BorderlineBehavior = Literal["refuse", "suggest"]


class CoordinatorAgent(IntentAgent):
    """A strict supervisor agent that ONLY delegates and NEVER answers directly.

    Extends IntentAgent. Where IntentAgent falls through to `call_model` (a
    free-form LLM response) on a no-match or low-confidence path, this class
    short-circuits to a deterministic refusal node bound to END. The "I don't
    know unless an agent can handle it" rule is therefore structural in the
    LangGraph topology, not prompted.

    Key differences vs IntentAgent
    ------------------------------
    - No-match paths route to `coordinator_refusal` -> END instead of `call_model`.
    - TOOL intents can be optionally rejected (by default the coordinator only
      delegates to AGENT intents, since TOOLs would still need an LLM to phrase
      the answer to the user).
    - Borderline matches (filtered out by entity/relevance check, or below
      threshold) can either refuse outright or suggest the top candidates,
      controlled by `borderline_behavior`.
    - `duplicate()` rebuilds the SUBCLASS instance, so the new graph topology
      survives concurrent duplication.

    Attributes
    ----------
    allow_tool_intents : bool
        If False (default), TOOL intents are treated as no-match. Set True only
        if you want the supervisor to call leaf tools directly with templated
        output (note: this still goes through `call_model` to format the
        result, which reintroduces some LLM freedom).
    borderline_behavior : BorderlineBehavior
        "refuse"  -> behave the same as no-match.
        "suggest" -> return a templated message listing the top candidates and
                     ask the user to pick one.
    refusal_message_template : str
        Template for the refusal message. Available placeholders:
        {agent_list}  - bullet list of "name: description" lines.
        {agent_count} - number of available agents.
    suggestion_message_template : str
        Template for the borderline suggestion message. Placeholders:
        {agent_list} - bullet list of top candidates with confidence scores.
    """

    allow_tool_intents: bool = False
    borderline_behavior: BorderlineBehavior = "suggest"

    refusal_message_template: str = (
        "I cannot handle this request directly — I only delegate to "
        "specialised agents, and none of mine match what you're asking.\n\n"
        "I have {agent_count} agent(s) available:\n{agent_list}\n\n"
        "Try rephrasing, or address one of them directly with `@<agent_name>`."
    )

    suggestion_message_template: str = (
        "I couldn't route your request automatically. "
        "Based on what you asked, here are the most relevant agents:\n\n"
        "{agent_list}\n\n"
        "Reply with the number to use that agent, or address one directly with `@<agent_name>`."
    )

    # Suggestion tier: scores in [borderline_floor, threshold) trigger the
    # "did you mean?" path when borderline_behavior == "suggest".
    borderline_floor: float = 0.55

    def __init__(
        self,
        name: str,
        description: str,
        chat_model: BaseChatModel | ChatModel,
        embedding_model: Embeddings | None = None,
        tools: list[Union[Tool, BaseTool, "Agent"]] = [],
        agents: list["Agent"] = [],
        intents: list[Intent] = [],
        memory: BaseCheckpointSaver | None = None,
        state: AgentSharedState = AgentSharedState(),
        configuration: AgentConfiguration = AgentConfiguration(),
        event_queue: Queue | None = None,
        threshold: float = 0.85,
        threshold_neighbor: float = 0.05,
        direct_intent_score: float = 0.90,
        enable_default_intents: bool = True,
        enable_default_tools: bool = True,
        markdown_pretty_display: bool = True,
        # Coordinator-specific knobs (overridable per instance)
        allow_tool_intents: Optional[bool] = None,
        borderline_behavior: Optional[BorderlineBehavior] = None,
        borderline_floor: Optional[float] = None,
    ):
        if allow_tool_intents is not None:
            self.allow_tool_intents = allow_tool_intents
        if borderline_behavior is not None:
            self.borderline_behavior = borderline_behavior
        if borderline_floor is not None:
            self.borderline_floor = borderline_floor

        super().__init__(
            name=name,
            description=description,
            chat_model=chat_model,
            embedding_model=embedding_model,
            tools=tools,
            agents=agents,
            intents=intents,
            memory=memory,
            state=state,
            configuration=configuration,
            event_queue=event_queue,
            threshold=threshold,
            threshold_neighbor=threshold_neighbor,
            direct_intent_score=direct_intent_score,
            enable_default_intents=enable_default_intents,
            enable_default_tools=enable_default_tools,
            markdown_pretty_display=markdown_pretty_display,
        )

    # ------------------------------------------------------------------ #
    # Templated response helpers                                         #
    # ------------------------------------------------------------------ #

    def _format_agent_list(self) -> str:
        if not self._agents:
            return "(no agents are currently available)"
        return "\n".join(f"- **{a.name}**: {a.description}" for a in self._agents)

    def _format_candidate_list(
        self, candidate_intents: list[dict], max_candidates: int = 3
    ) -> str:
        # candidate_intents is the same shape as IntentAgent's mapping items:
        # {"intent": Intent, "score": float, "text": str, ...}
        seen: set[str] = set()
        lines: list[str] = []
        idx = 1
        for c in candidate_intents:
            if idx > max_candidates:
                break
            target = c["intent"].intent_target
            if target in seen:
                continue
            seen.add(target)
            score_pct = f"{c['score']:.1%}"
            agent = next((a for a in self._agents if a.name == target), None)
            desc = (
                agent.description
                if agent and hasattr(agent, "description") and agent.description
                else c["intent"].intent_value
            )
            lines.append(f"{idx}. **{target}** (relevance: {score_pct})\n   {desc}")
            idx += 1
        return "\n".join(lines) if lines else "(no close matches)"

    def _refusal_message(self) -> str:
        return self.refusal_message_template.format(
            agent_list=self._format_agent_list(),
            agent_count=len(self._agents),
        )

    def _suggestion_message(self, candidates: list[dict]) -> str:
        return self.suggestion_message_template.format(
            agent_list=self._format_candidate_list(candidates),
        )

    # ------------------------------------------------------------------ #
    # LLM-based agent recommender                                       #
    # ------------------------------------------------------------------ #

    def agent_recommender(self, state: IntentState) -> Command:
        """Uses the LLM to pick the best agent when vector search finds no confident match.

        Flow:
        1. Vector pre-filter: get top candidates (unconstrained by threshold).
        2. LLM meaning search: present ALL registered agents and ask the model to
           pick one with a confidence score.
        3. If confidence >= 0.8 and the agent exists → route directly.
        4. Otherwise → coordinator_refusal with vector candidates for suggestions.
        """
        logger.debug("🎯 Agent Recommender node")

        last_human_message = self.get_last_human_message(state)
        if last_human_message is None or not isinstance(
            last_human_message.content, str
        ):
            return Command(goto="coordinator_refusal")

        if not self._agents:
            return Command(goto="coordinator_refusal")

        # Step 1 — vector pre-filter for fallback suggestions.
        # The intent vector index is built lazily on first use, so we gate
        # this on whether intents exist (not on `vector_store is not None`).
        raw_candidates: list[dict] = []
        if self._intent_mapper.intents:
            raw_candidates = [
                r
                for r in self._intent_mapper.map_intent(
                    last_human_message.content, k=20
                )
                if r["intent"].intent_type == IntentType.AGENT
            ]

        # Step 2 — LLM meaning search over all registered agents
        agent_roster = "\n".join(f"- {a.name}: {a.description}" for a in self._agents)

        @lc_tool
        def select_best_agent(agent_name: str, confidence: float) -> str:  # noqa: ARG001
            """Select the single best agent for the user's request.

            Args:
                agent_name: Exact agent name from the list, or empty string if none fits.
                confidence: Your confidence (0.0–1.0) that this agent handles the request.
                    Be strict: assign 0.8+ only when the agent's capabilities clearly cover
                    the request.
            """
            return agent_name

        system_prompt = (
            "You are a strict routing assistant. Your ONLY job is to determine whether "
            "one of the listed agents can ACTUALLY fulfill the user's request based on "
            "its stated capabilities — not just because the topic is vaguely related.\n\n"
            f"Available agents:\n{agent_roster}\n\n"
            "Rules:\n"
            "- Assign confidence 0.8+ ONLY when the agent's description explicitly covers "
            "the requested action (e.g. 'creates Notion pages' for a Notion request).\n"
            "- Topic similarity alone is NOT enough. An agent named 'ChatGPT' or 'Assistant' "
            "does NOT automatically handle all requests — check its description.\n"
            "- If no agent clearly covers the request, use agent_name='' and confidence=0.0.\n"
            "- Prefer refusal over a wrong routing.\n\n"
            "Call `select_best_agent` exactly once with:\n"
            "- agent_name: the exact name from the list, or empty string if none fits\n"
            "- confidence: 0.0–1.0 (only 0.8+ when the agent description clearly matches)"
        )

        messages = [SystemMessage(content=system_prompt), last_human_message]

        try:
            response = self._chat_model.bind_tools([select_best_agent]).invoke(messages)
        except Exception as e:
            logger.warning(f"Agent recommender LLM call failed: {e}")
            return Command(
                goto="coordinator_refusal",
                update={"intent_mapping": {"intents": raw_candidates}},
            )

        agent_name = ""
        confidence = 0.0
        try:
            assert (
                isinstance(response.additional_kwargs.get("tool_calls", []), list)
                and len(response.additional_kwargs.get("tool_calls", [])) > 0
            )
            args = response.additional_kwargs.get("tool_calls", [])[0]["args"]
            agent_name = str(args.get("agent_name", "")).strip()
            confidence = float(args.get("confidence", 0.0))
        except Exception as e:
            logger.warning(f"Failed to parse agent recommender response: {e}")
            return Command(
                goto="coordinator_refusal",
                update={"intent_mapping": {"intents": raw_candidates}},
            )

        logger.debug(
            f"🎯 Agent recommender selected '{agent_name}' (confidence: {confidence:.1%})"
        )

        # Step 3 — high confidence: route directly
        if confidence >= 0.8 and self._is_known_agent(agent_name):
            logger.debug(f"✅ Routing directly to '{agent_name}'")
            self.state.set_current_active_agent(agent_name)
            return Command(goto=agent_name)

        # Step 4 — low confidence: fall back to suggestions
        logger.debug(
            f"❌ Confidence too low ({confidence:.1%}), falling back to suggestions"
        )
        return Command(
            goto="coordinator_refusal",
            update={"intent_mapping": {"intents": raw_candidates}},
        )

    # ------------------------------------------------------------------ #
    # New terminal node: deterministic refusal                           #
    # ------------------------------------------------------------------ #

    def coordinator_refusal(self, state: IntentState) -> Command:
        """Terminal node. Falls back to a support agent if one is registered and
        no agent has already given up this turn; otherwise returns a templated refusal.
        """
        logger.debug("🛑 Coordinator refusal node")

        # # Fall back to support agent when available and not already tried this turn.
        # support_agent = self._find_support_agent()
        # if support_agent and not self._state.tried_support_fallback:
        #     logger.debug(f"🆘 Falling back to support agent '{support_agent.name}'")
        #     self._state.set_tried_support_fallback(True)
        #     self._notify_agent_routing(support_agent.name)
        #     self.state.set_current_active_agent(support_agent.name)
        #     return Command(goto=support_agent.name)

        candidates: list[dict] = []
        if "intent_mapping" in state:
            candidates = state["intent_mapping"].get("intents", []) or []

        allowed_types = {IntentType.AGENT}
        if self.allow_tool_intents:
            allowed_types.add(IntentType.TOOL)
        actionable = [c for c in candidates if c["intent"].intent_type in allowed_types]

        if self.borderline_behavior == "suggest" and actionable:
            content = self._suggestion_message(actionable)
        else:
            content = self._refusal_message()

        ai_message = AIMessage(
            content=content,
            additional_kwargs={"owner": self.name, "coordinator_refusal": True},
        )
        self._notify_ai_message(ai_message, self.name)
        return Command(goto=END, update={"messages": [ai_message]})

    # ------------------------------------------------------------------ #
    # Override: should_filter — empty case must NOT fall through to LLM  #
    # ------------------------------------------------------------------ #

    def should_filter(self, intents: list) -> str:
        if len(intents) == 1 and intents[0]["score"] > self._direct_intent_score:
            return "intent_mapping_router"
        if len(intents) == 0:
            logger.debug("❌ No intents found, going to agent_recommender")
            return "agent_recommender"
        return "filter_out_intents"

    # ------------------------------------------------------------------ #
    # Override: intent_mapping_router — close every LLM leak path        #
    # ------------------------------------------------------------------ #

    def intent_mapping_router(self, state: IntentState) -> Command:
        logger.debug("🔀 Coordinator Intent Mapping Router")

        if "intent_mapping" not in state:
            return Command(goto="coordinator_refusal")

        intents = state["intent_mapping"]["intents"]

        # No intents -> refuse
        if len(intents) == 0:
            logger.debug("❌ No intents, refusing")
            return Command(goto="coordinator_refusal")

        # Single intent
        if len(intents) == 1:
            intent: Intent = intents[0]["intent"]

            # RAW intents are deterministic templated answers — fine for a
            # coordinator (e.g. "Hi" -> "Hello, I'm Abi. I delegate to: ...").
            if intent.intent_type == IntentType.RAW:
                logger.debug(
                    f"📝 RAW intent, templated response: {intent.intent_target}"
                )
                ai_message = AIMessage(
                    content=intent.intent_target,
                    additional_kwargs={"owner": self.name},
                )
                self._notify_ai_message(ai_message, self.name)
                return Command(goto=END, update={"messages": [ai_message]})

            # AGENT intents are the happy path.
            if intent.intent_type == IntentType.AGENT:
                logger.debug(f"🤖 AGENT intent, delegating to {intent.intent_target}")
                # Guard: intent_target must be a real registered agent.
                if not self._is_known_agent(intent.intent_target):
                    logger.warning(
                        f"AGENT intent target '{intent.intent_target}' "
                        f"is not in registered agents; refusing."
                    )
                    return Command(goto="coordinator_refusal")
                if intent.intent_target != "call_model":
                    self.state.set_current_active_agent(intent.intent_target)
                return Command(goto=intent.intent_target)

            # TOOL intents: only allowed if explicitly enabled. Even then they
            # currently flow through call_model to format the response, which
            # is the LLM-free-form node we are trying to avoid. So by default
            # we refuse.
            if intent.intent_type == IntentType.TOOL:
                if self.allow_tool_intents:
                    logger.debug("🔧 TOOL intent allowed, injecting in prompt")
                    return Command(goto="inject_intents_in_system_prompt")
                logger.debug("🔧 TOOL intent rejected by coordinator policy")
                return Command(goto="coordinator_refusal")

            logger.warning(f"Unknown intent type: {intent.intent_type}")
            return Command(goto="coordinator_refusal")

        # Multiple intents
        actionable = [
            i
            for i in intents
            if i["intent"].intent_type
            in (
                {IntentType.AGENT, IntentType.TOOL}
                if self.allow_tool_intents
                else {IntentType.AGENT}
            )
        ]
        if len(actionable) > 1:
            # Reuse parent's human-validation node (it produces a templated
            # numbered list — no LLM free-form generation).
            return Command(goto="request_human_validation")
        if len(actionable) == 1:
            # Re-route as if it were a single intent.
            single_state: dict = {"intent_mapping": {"intents": [actionable[0]]}}
            # Recursive single-intent dispatch via the same logic.
            return self.intent_mapping_router({**state, **single_state})

        # No actionable intents (only RAW matched, or all filtered out) —
        # try meaning-based agent selection before giving up.
        return Command(goto="agent_recommender")

    # ------------------------------------------------------------------ #
    # Override: map_intents — close the early-return-to-call_model leak  #
    # ------------------------------------------------------------------ #

    def map_intents(self, state: IntentState) -> Command:
        # A sub-agent just called request_help — it cannot handle the request.
        # Route to refusal immediately so we don't re-route to the same agent.
        if self._state.requesting_help:
            logger.debug("🛑 Sub-agent requested help — routing to coordinator_refusal")
            self._state.set_requesting_help(False)
            return Command(
                goto="coordinator_refusal",
                update={"intent_mapping": {"intents": []}},
            )

        # Handle numeric selection from a prior coordinator suggestion message.
        # The parent's numeric handler only recognises MULTIPLES_INTENTS_MESSAGE;
        # coordinator suggestions use coordinator_refusal=True as a sentinel instead.
        last_ai_message = pd.find(
            state["messages"][::-1], lambda m: isinstance(m, AIMessage)
        )
        last_human_message = self.get_last_human_message(state)

        if (
            last_human_message is not None
            and isinstance(last_human_message.content, str)
            and last_human_message.content.strip().isdigit()
            and last_ai_message is not None
            and last_ai_message.additional_kwargs.get("coordinator_refusal") is True
            and last_ai_message.additional_kwargs.get("owner") == self.name
        ):
            choice_num = int(last_human_message.content.strip())
            lines = (
                last_ai_message.content.split("\n")
                if isinstance(last_ai_message.content, str)
                else []
            )
            matching = [
                line for line in lines if line.strip().startswith(f"{choice_num}.")
            ]
            if matching and "**" in matching[0]:
                intent_name = matching[0].split("**")[1]
                if self._is_known_agent(intent_name):
                    logger.debug(f"📌 Coordinator numeric selection: '{intent_name}'")
                    self.state.set_current_active_agent(intent_name)
                    return Command(
                        goto=intent_name,
                        update={"intent_mapping": {"intents": []}},
                    )

        cmd: Command = super().map_intents(state)
        # Parent may emit goto="call_model" via should_filter when zero matches
        # remain after both vector and prompt mapping. Rewrite to agent_recommender
        # so the LLM can still find the right agent from meaning.
        if getattr(cmd, "goto", None) == "call_model":
            logger.debug(
                "Rewriting parent map_intents goto=call_model -> agent_recommender"
            )
            return Command(
                goto="agent_recommender",
                update=cmd.update,
            )
        return cmd

    # ------------------------------------------------------------------ #
    # Override: build_graph — wire the new node and remove call_model    #
    # leak edges                                                         #
    # ------------------------------------------------------------------ #

    def build_graph(self, patcher: Optional[Callable] = None):
        graph = StateGraph(IntentState)

        graph.add_node(self.render_system_prompt)
        graph.add_edge(START, "render_system_prompt")

        graph.add_node(self.current_active_agent)
        graph.add_edge("render_system_prompt", "current_active_agent")

        graph.add_node(self.continue_conversation)

        # Intent pipeline
        graph.add_node(self.map_intents)
        graph.add_node(self.filter_out_intents)
        graph.add_node(self.entity_check)
        graph.add_node(self.intent_mapping_router)
        graph.add_edge("entity_check", "intent_mapping_router")

        # Validation prompt for ambiguous multi-agent matches
        graph.add_node(self.request_human_validation)
        graph.add_edge("request_human_validation", END)

        # LLM-based agent recommender (vector pre-filter + meaning search)
        graph.add_node(self.agent_recommender)

        # Coordinator refusal terminal node (reached when recommender isn't confident)
        graph.add_node(self.coordinator_refusal)
        graph.add_edge("coordinator_refusal", END)

        # We still need call_model and call_tools available as nodes because:
        # (a) the @mention path in `current_active_agent` may set a current
        #     active agent and goto it (sub-agents are bound via their .graph)
        # (b) if allow_tool_intents=True, inject_intents_in_system_prompt ->
        #     call_model is the only way to actually invoke the tool.
        # We DO NOT add an edge from the routing pipeline to call_model.
        # The router's goto-rewrites guarantee call_model is only reached for
        # the @mention / active-agent path or the explicitly-allowed TOOL path.
        graph.add_node(self.inject_intents_in_system_prompt)
        graph.add_edge("inject_intents_in_system_prompt", "call_model")
        graph.add_node(self.call_model)
        graph.add_edge("call_model", END)
        graph.add_node(self.call_tools)

        # Sub-agent subgraphs
        for agent in self._agents:
            agent = self.validate_agent_name(agent)
            logger.debug(
                f"Adding sub-agent '{agent._name}' to coordinator graph '{self._name}'"
            )
            graph.add_node(agent._name, agent.graph)

        if patcher is not None:
            graph = patcher(graph)

        self.graph = graph.compile(checkpointer=self._checkpointer)

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    def _is_known_agent(self, name: str) -> bool:
        if name == "call_model":  # special parent sentinel — disallow
            return False
        return any(a.name == name for a in self._agents)

    def _find_support_agent(self) -> "Agent | None":
        """Return the first registered agent whose name contains 'support' (case-insensitive)."""
        for agent in self._agents:
            if "support" in agent.name.lower():
                return agent
        return None

    # ------------------------------------------------------------------ #
    # Override: duplicate — must rebuild THIS subclass, not IntentAgent  #
    # ------------------------------------------------------------------ #

    def duplicate(
        self,
        queue: Queue | None = None,
        agent_shared_state: AgentSharedState | None = None,
    ) -> "CoordinatorAgent":
        shared_state = agent_shared_state or AgentSharedState()
        if queue is None:
            queue = Queue()

        agents: list[Union["IntentAgent", "Agent"]] = [
            agent.duplicate(queue, shared_state) for agent in self._original_agents
        ]

        # Use type(self)(...) so further subclasses (e.g. AbiAgent) duplicate
        # themselves correctly without overriding duplicate again.
        return type(self)(
            name=self._name,
            description=self._description,
            chat_model=self._chat_model,
            tools=self._original_tools,
            agents=agents,
            intents=self._intents,
            memory=self._checkpointer,
            state=shared_state,
            configuration=self._configuration,
            event_queue=queue,
            embedding_model=self._embedding_model,
            threshold=self._threshold,
            threshold_neighbor=self._threshold_neighbor,
            direct_intent_score=self._direct_intent_score,
            enable_default_intents=self._enable_default_intents,
            enable_default_tools=self._enable_default_tools,
            markdown_pretty_display=self._markdown_pretty_display,
            allow_tool_intents=self.allow_tool_intents,
            borderline_behavior=self.borderline_behavior,
            borderline_floor=self.borderline_floor,
        )
