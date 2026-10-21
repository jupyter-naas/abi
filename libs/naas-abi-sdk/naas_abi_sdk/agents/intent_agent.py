"""SDK IntentAgent: core ``IntentAgent`` routing, async and core-free.

Same graph and prompts as core: map intents by embedding similarity, filter
ambiguous ones with the model, check named entities, then answer RAW intents
directly, inject TOOL intents into the system prompt, or ask the user to pick.
Differences: v1 has no local sub-agents (an AGENT intent other than
``call_model`` falls back to the model), and the entity check uses spaCy only
when it is installed (otherwise intents are treated as entity-free).
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from naas_abi_sdk.agents._messages import logger, validate_name
from naas_abi_sdk.agents.agent import ABIAgentState, Agent
from naas_abi_sdk.agents.intent_mapper import IntentMapper
from naas_abi_sdk.agents.intents import DEFAULT_INTENTS, Intent, IntentScope, IntentType

MULTIPLES_INTENTS_MESSAGE = "I found multiple intents that could handle your request"

_nlp: Any = None


def get_nlp() -> Any | None:
    """spaCy ``en_core_web_sm`` when installed; None otherwise (no download)."""
    global _nlp
    if _nlp is None:
        try:
            import spacy

            _nlp = spacy.load("en_core_web_sm")
        except Exception:  # noqa: BLE001 - optional dependency
            _nlp = False
    return _nlp or None


class IntentState(ABIAgentState):
    intent_mapping: dict[str, Any]


class IntentAgent(Agent):
    def __init__(
        self,
        name: str,
        description: str,
        chat_model: Any,
        embedding_model: Any | None = None,
        tools: list[Any] | None = None,
        agents: list[Any] | None = None,
        intents: list[Intent] | None = None,
        memory: Any = None,
        state: Any = None,
        configuration: Any = None,
        threshold: float = 0.85,
        threshold_neighbor: float = 0.05,
        direct_intent_score: float = 0.90,
        enable_default_intents: bool = True,
        enable_default_tools: bool = True,
        markdown_pretty_display: bool = True,
    ):
        prepared: list[Intent] = []
        for intent in intents or []:
            if intent.intent_type in (IntentType.TOOL, IntentType.AGENT):
                intent.intent_target = validate_name(intent.intent_target)
                intent.intent_scope = IntentScope.DIRECT
            prepared.append(intent)
        if enable_default_intents:
            values = {intent.intent_value for intent in intents or []}
            prepared += [i for i in DEFAULT_INTENTS if i.intent_value not in values]
        self._enable_default_intents = enable_default_intents
        self._intents = prepared
        # SDK RemoteModel (model registry over NATS) wraps the Embeddings in .model.
        if embedding_model is not None and not hasattr(embedding_model, "aembed_query"):
            embedding_model = getattr(embedding_model, "model", embedding_model)
        self._embedding_model = embedding_model
        self._intent_mapper = IntentMapper(
            self._intents, embedding_model=self._embedding_model
        )
        self._threshold = threshold
        self._threshold_neighbor = threshold_neighbor
        self._direct_intent_score = direct_intent_score
        super().__init__(
            name=name,
            description=description,
            chat_model=chat_model,
            tools=tools,
            agents=agents,
            memory=memory,
            state=state,
            configuration=configuration,
            enable_default_tools=enable_default_tools,
            markdown_pretty_display=markdown_pretty_display,
        )

    @property
    def intents(self) -> list[Intent]:
        return self._intents

    def build_graph(self) -> None:
        graph = StateGraph(IntentState)
        graph.add_node("render_system_prompt", self.render_system_prompt)
        graph.add_edge(START, "render_system_prompt")
        graph.add_node("current_active_agent", self.current_active_agent)
        graph.add_edge("render_system_prompt", "current_active_agent")
        graph.add_node("continue_conversation", self.continue_conversation)
        graph.add_node("map_intents", self.map_intents)
        graph.add_node("filter_out_intents", self.filter_out_intents)
        graph.add_node("entity_check", self.entity_check)
        graph.add_node("intent_mapping_router", self.intent_mapping_router)
        graph.add_edge("entity_check", "intent_mapping_router")
        graph.add_node("request_human_validation", self.request_human_validation)
        graph.add_edge("request_human_validation", END)
        graph.add_node(
            "inject_intents_in_system_prompt", self.inject_intents_in_system_prompt
        )
        graph.add_edge("inject_intents_in_system_prompt", "call_model")
        graph.add_node("call_model", self.call_model)
        graph.add_edge("call_model", END)
        graph.add_node("call_tools", self.call_tools)
        self.graph = graph.compile(checkpointer=self._checkpointer)

    async def continue_conversation(self, state: Any) -> Command:
        return Command(goto="map_intents")

    def _last_human(self, state: Any) -> HumanMessage | None:
        """Core ``get_last_human_message`` (owner-aware)."""
        messages = state["messages"]
        last_ai = next(
            (m for m in reversed(messages) if isinstance(m, AIMessage)), None
        )
        humans = [m for m in reversed(messages) if isinstance(m, HumanMessage)]
        owner = (
            (getattr(last_ai, "additional_kwargs", None) or {}).get("owner")
            if last_ai
            else None
        )
        if last_ai is not None and owner is not None and owner != self.name:
            return humans[1] if len(humans) > 1 else None
        return humans[0] if humans else None

    async def map_intents(self, state: IntentState) -> Command:
        last_ai = next(
            (m for m in reversed(state["messages"]) if isinstance(m, AIMessage)), None
        )
        last_human = self._last_human(state)
        assert last_human is not None and isinstance(last_human.content, str)

        if (
            last_human.content.strip().isdigit()
            and last_ai is not None
            and MULTIPLES_INTENTS_MESSAGE in last_ai.content
            and last_ai.additional_kwargs.get("owner") == self.name
        ):
            choice = int(last_human.content.strip())
            lines = [
                line
                for line in last_ai.content.split("\n")
                if line.strip().startswith(f"{choice}.")
            ]
            if lines:
                update: dict = {"intent_mapping": {"intents": []}}
                # v1 has no local sub-agents: core's "agent not found" path.
                return Command(goto="call_model", update=update)

        try:
            intents = [
                m
                for m in await self._intent_mapper.map_intent(last_human.content, k=10)
                if m["score"] > self._threshold
            ]
            if not intents:
                _, prompted = await self._intent_mapper.map_prompt(
                    last_human.content, k=10
                )
                intents = [m for m in prompted if m["score"] > self._threshold]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Intent mapping unavailable for '%s', falling back to model routing: %s",
                self.name,
                exc,
            )
            intents = []

        if not intents:
            return Command(
                update={"intent_mapping": {"intents": []}}, goto=self.should_filter([])
            )

        max_score = intents[0]["score"]
        max_score_2 = intents[1]["score"] if len(intents) > 1 else 0
        if max_score >= self._direct_intent_score and max_score > max_score_2:
            return Command(
                goto="intent_mapping_router",
                update={"intent_mapping": {"intents": [intents[0]]}},
            )

        close = [
            i for i in intents if max_score - i["score"] < self._threshold_neighbor
        ]
        seen: set[Any] = set()
        final: list[dict] = []
        for intent in close:
            target = intent["intent"].intent_target
            if target not in seen:
                seen.add(target)
                final.append(intent)
        return Command(
            goto=self.should_filter(final),
            update={"intent_mapping": {"intents": final}},
        )

    def should_filter(self, intents: list) -> str:
        if len(intents) == 1 and intents[0]["score"] > self._direct_intent_score:
            return "intent_mapping_router"
        if not intents:
            return "call_model"
        return "filter_out_intents"

    async def filter_out_intents(self, state: IntentState) -> Command:
        last_human = self._last_human(state)
        assert last_human is not None
        mapped = state["intent_mapping"]["intents"]

        @tool
        def filter_intents(bool_list: list[bool]) -> list[Intent]:
            """
            This tool is used to filter out the intents that are not related to the last user message. True will keep the intent, false will remove it.
            """
            return []

        intents = [intent["text"] for intent in mapped]
        messages: list = [
            SystemMessage(content=_filter_prompt(intents, last_human.content))
        ]
        messages += [m for m in state["messages"] if not isinstance(m, SystemMessage)]
        try:
            response = await self._chat_model.bind_tools([filter_intents]).ainvoke(
                messages
            )
        except Exception:  # noqa: BLE001
            logger.warning("Error filtering intents going to 'entity_check'")
            return Command(goto="entity_check")

        filtered: list = []
        try:
            bool_list = response.tool_calls[0]["args"]["bool_list"]
            assert isinstance(bool_list, list)
            filtered = [mapped[i] for i in range(len(bool_list)) if bool_list[i]]
        except Exception as e:  # noqa: BLE001
            logger.error("Error filtering out intents: %s", e)
            filtered = mapped
        if len(filtered) == 1 and filtered[0]["score"] > self._threshold:
            return Command(
                goto="intent_mapping_router",
                update={"intent_mapping": {"intents": filtered}},
            )
        return Command(
            goto="entity_check", update={"intent_mapping": {"intents": filtered}}
        )

    def _extract_entities(self, text: str) -> list[str]:
        nlp = get_nlp()
        if nlp is None:
            return []
        return [ent.text.lower() for ent in nlp(text).ents]

    async def entity_check(self, state: IntentState) -> Command:
        last_human = self._last_human(state)
        assert last_human is not None and isinstance(last_human.content, str)
        kept = []
        for intent in state["intent_mapping"]["intents"]:
            entities = self._extract_entities(intent["intent"].intent_value)
            if not entities:
                kept.append(intent)
                continue
            human_entities = self._extract_entities(last_human.content)
            all_present = (
                bool(human_entities)
                and len(human_entities) >= len(entities)
                and all(e in entities for e in human_entities)
            )
            if all_present:
                kept.append(intent)
                continue
            messages: list[BaseMessage] = [
                SystemMessage(content=_entity_prompt(entities, last_human.content))
            ]
            messages += [m for m in state["messages"] if isinstance(m, HumanMessage)]
            response = await self._chat_model.ainvoke(messages)
            if response.content == "true":
                kept.append(intent)
        return Command(update={"intent_mapping": {"intents": kept}})

    async def request_human_validation(self, state: IntentState) -> Command:
        if "intent_mapping" not in state or not state["intent_mapping"]["intents"]:
            return Command(goto="call_model")
        agent_intents = [
            i
            for i in state["intent_mapping"]["intents"]
            if i["intent"].intent_type in (IntentType.AGENT, IntentType.TOOL)
        ]
        if len(agent_intents) <= 1:
            return Command(goto="inject_intents_in_system_prompt")
        agents_info: list[dict] = []
        seen: set[Any] = set()
        for intent in agent_intents:
            name = intent["intent"].intent_target
            if name not in seen:
                agents_info.append(
                    {
                        "name": name,
                        "score": intent["score"],
                        "intent_text": intent["intent"].intent_value,
                    }
                )
                seen.add(name)
        agents_info.sort(key=lambda x: (-x["score"], x["name"]))
        message = "I found multiple intents that could handle your request:\n\n"
        for i, info in enumerate(agents_info, 1):
            message += f"{i}. **{info['name']}** (confidence: {info['score']:.1%})\n"
            message += f"   Intent: {info['intent_text']}\n\n"
        message += "Please choose an intent by number (e.g., '1' or '2')\n"
        ai_message = AIMessage(content=message, additional_kwargs={"owner": self.name})
        self._notify_ai_message(ai_message, self.name)
        return Command(goto=END, update={"messages": [ai_message]})

    async def intent_mapping_router(self, state: IntentState) -> Command:
        if "intent_mapping" in state:
            intents = state["intent_mapping"]["intents"]
            if not intents:
                return Command(goto="call_model")
            if len(intents) == 1:
                intent: Intent = intents[0]["intent"]
                if intent.intent_type == IntentType.RAW:
                    ai_message = AIMessage(content=intent.intent_target)
                    self._notify_ai_message(ai_message, self.name)
                    return Command(goto=END, update={"messages": [ai_message]})
                if intent.intent_type == IntentType.AGENT:
                    if intent.intent_target != "call_model":
                        logger.warning(
                            "Agent intent '%s' has no local sub-agent in the SDK; calling the model",
                            intent.intent_target,
                        )
                    return Command(goto="call_model")
                return Command(goto="inject_intents_in_system_prompt")
            not_raw = [
                i
                for i in intents
                if i["intent"].intent_type in (IntentType.AGENT, IntentType.TOOL)
            ]
            if len(not_raw) > 1:
                return Command(goto="request_human_validation")
            return Command(goto="inject_intents_in_system_prompt")
        return Command(goto="call_model")

    async def inject_intents_in_system_prompt(
        self, state: IntentState
    ) -> Command | None:
        if "intent_mapping" not in state or not state["intent_mapping"]["intents"]:
            return None
        intents_str = ""
        for intent in state["intent_mapping"]["intents"]:
            intents_str += (
                f"-Mapped intent: `{intent['intent'].intent_value}`, "
                f"tool to call: `{intent['intent'].intent_target}`\n"
            )
        if "<intents_rules>" not in state["system_prompt"]:
            updated = f"""{state["system_prompt"]}

<intents_rules>
Everytime a user is sending a message, a system is trying to map the prompt/message to an intent or a list of intents using a vector search.
The following is the list of mapped intents. This list will change over time as new messages comes in.
You must analyze if the user message and the mapped intents are related to each other.
If it's the case, you must take them into account, otherwise you must ignore the ones that are not related.
If you endup with a single intent which is of type RAW, you must output the intent_target and nothing else as there will be tests asserting the correctness of the output.
If you endup with a single intent which is of type TOOL, you must call this tool.

<intents>\n{intents_str}\n</intents>

</intents_rules>
"""
        else:
            updated = re.sub(
                r"(<intents>)(.*?)(</intents>)",
                lambda m: f"{m.group(1)}\n{intents_str}\n{m.group(3)}",
                state["system_prompt"],
                flags=re.DOTALL,
            )
        return Command(update={"system_prompt": updated})

    def _populate_duplicate_shell(self, clone: Agent) -> None:
        """Intent fields are copied with ``__dict__``; the mapper (and its index) is shared."""


def _filter_prompt(intents: list[str], last_message: Any) -> str:
    return f"""You are a logical assistant. You are given a list of possible intents retrieved via vector search from the last user message. These matches may not always be logically relevant because the search is based only on surface similarity, without full understanding of the request.

Your task is to filter out any intent that is not logically compatible with the last user message.

You must examine whether the user’s message and the mapped intent match **in meaning and logical structure**. You should exclude intents where:
- The intent contains named entities (like people or organizations) that are not mentioned in the user message.
- The intent refers to actions or goals not implied by the user message.
- The intent is more specific than the user message in a way that changes the meaning (e.g., user asks for a general phone number but the intent asks for the phone number of a specific person).
- The intent cannot logically follow from the user message, even if some keywords are similar.
- The intent may be topically similar but not what the user is asking for.

You will be shown:
- The list of mapped intents
- The last user message

You must call the tool `filter_intents` once and only once with a list of booleans. Each boolean corresponds to whether the mapped intent at that index is logically relevant to the user message.

Be strict — include only intents that directly and logically correspond to the user's actual request.

Example:
- User says: "Give me the personal email address"
- Intent: "Give me the personal email address of John Doe" → This should be **excluded** (not logically equivalent, adds information not present in prompt)

Now, analyze and apply this reasoning to the intents.

Mapped intents:
```mapped_intents
{intents}
```
Last user message: "{last_message}"
        """


def _entity_prompt(entities: list[str], last_message: str) -> str:
    return f"""
You are a precise and logical assistant. You will be given:
- An **intent** (which includes one or more named entities)
- A list of **entities** extracted from that intent
- The **last user message**
- The **chat history**

Your task is to determine whether the last user message (and optionally the conversation history) clearly **refers to or requests information about** the entities in the intent.

You must answer **"true"** if:
- The user's message explicitly or implicitly refers to **all** the key entities in the intent (such as a specific person, object, or organization).
- The user's request logically aligns with the target entities (e.g., same person, role, or context).

Answer **"false"** if:
- The user’s message does **not mention** or clearly imply the entities.
- The intent introduces **entities that were not referenced** in the user's message or recent chat history.
- There is insufficient information to link the user's request to those specific entities.

⚠️ Very Important:
- You must output **"true"** or **"false"** only. No explanations. No other words.
- Your answer will be parsed by a test function and must strictly match one of those two strings.

### Example:
Intent: "What is the color of the dress of Lucie?"
Entities: ["Lucie", "dress"]
Last user message: "What is the color of the dress of Lucie?"
Chat history: ["What is the color of the dress of Lucie?", "The color of the dress of Lucie is blue"]
Output: "true"

Now analyze the following:

Entities: {entities}
Last user message: "{last_message}"
"""
