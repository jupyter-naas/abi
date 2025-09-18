"""Intent-based Agent Implementation.

This module provides an IntentAgent that extends the base Agent class with intent
mapping capabilities. The IntentAgent can analyze user messages, map them to predefined
intents, and route conversations accordingly. It includes functionality for intent
filtering, entity extraction, and intent-based conversation flow control.

The module integrates with langgraph for state management and conversation flow,
and uses spaCy for natural language processing tasks like entity extraction.

Classes:
    IntentState: State class for intent mapping in conversations
    IntentAgent: Agent with intent mapping and routing capabilities

Dependencies:
    - langchain_core: For chat models, tools, and messages
    - langgraph: For state graphs and checkpoints
    - spaCy: For natural language processing
    - abi: Internal logging and utilities
"""

from typing import Union, Callable, Optional, Any
from queue import Queue

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import Tool
from langgraph.checkpoint.base import BaseCheckpointSaver

from .Agent import Agent, AgentSharedState, AgentConfiguration, create_checkpointer
from .beta.IntentMapper import IntentMapper, Intent, IntentType
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langgraph.graph.message import MessagesState
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.tools import tool
from abi import logger
import pydash as pd
import spacy
import rich




nlp = spacy.load("en_core_web_sm")


class IntentState(MessagesState):
    """State class for intent-based conversations.
    
    Extends MessagesState to include intent mapping information that tracks
    the current intent analysis results throughout the conversation flow.
    
    Attributes:
        intent_mapping (dict[str, Any]): Dictionary containing mapped intents
            and their associated metadata from the intent analysis process.
    """
    intent_mapping: dict[str, Any]

class IntentAgent(Agent):
    """Agent with intent mapping and routing capabilities.
    
    IntentAgent extends the base Agent class to provide intent-based conversation
    routing. It analyzes user messages to identify and map them to predefined
    intents, then routes the conversation flow accordingly. The agent includes
    sophisticated filtering mechanisms for intent accuracy and entity validation.
    
    The agent operates through several stages:
    1. Intent mapping - Maps user messages to potential intents
    2. Intent filtering - Filters out irrelevant intents
    3. Entity checking - Validates entity consistency
    4. Intent routing - Routes to appropriate handlers
    
    Attributes:
        _intents (list[Intent]): List of available intents for mapping
        _intent_mapper (IntentMapper): Mapper instance for intent analysis
    """
    _intents: list[Intent]
    _intent_mapper: IntentMapper
    
    def __init__(
        self,
        name: str,
        description: str,
        chat_model: BaseChatModel,
        tools: list[Union[Tool, "Agent"]] = [],
        agents: list["Agent"] = [],
        intents: list[Intent] = [],
        memory: BaseCheckpointSaver | None = None,
        state: AgentSharedState = AgentSharedState(),
        configuration: AgentConfiguration = AgentConfiguration(),
        event_queue: Queue | None = None,
        threshold: float = 0.85,
        threshold_neighbor: float = 0.05,
    ):
        """Initialize the IntentAgent.
        
        Sets up the agent with intent mapping capabilities by initializing
        the intent mapper before calling the parent constructor.
        
        Args:
            name (str): Unique name identifier for the agent
            description (str): Human-readable description of the agent's purpose
            chat_model (BaseChatModel): Language model for generating responses
            tools (list[Union[Tool, "Agent"]], optional): Available tools and sub-agents.
                Defaults to [].
            agents (list["Agent"], optional): List of sub-agents this agent can route to.
                Defaults to [].
            intents (list[Intent], optional): List of intents for mapping user messages.
                Defaults to [].
            memory (BaseCheckpointSaver | None, optional): Checkpoint saver for conversation state.
                If None, will use PostgreSQL if POSTGRES_URL env var is set, otherwise in-memory.
                Defaults to None.
            state (AgentSharedState, optional): Shared state configuration.
                Defaults to AgentSharedState().
            configuration (AgentConfiguration, optional): Agent configuration settings.
                Defaults to AgentConfiguration().
            event_queue (Queue | None, optional): Queue for handling events.
                Defaults to None.
            threshold (float, optional): Minimum score threshold for intent matching.
                Defaults to 0.85.
            threshold_neighbor (float, optional): Maximum score difference for similar intents.
                Defaults to 0.05.
        """
        # We set class specific properties before calling the super constructor because it will call the build_graph method.
        self._intents = intents
        self._intent_mapper = IntentMapper(self._intents)
        self._threshold = threshold
        self._threshold_neighbor = threshold_neighbor

        # Handle memory configuration (same pattern as base Agent class)
        if memory is None:
            memory = create_checkpointer()

        super().__init__(
            name=name,
            description=description,
            chat_model=chat_model,
            tools=tools,
            agents=agents,
            memory=memory,
            state=state,
            configuration=configuration,
            event_queue=event_queue,
        )
    
    def map_intents(self, state: MessagesState) -> Command | dict:
        """Map user messages to available intents.
        
        Analyzes the last human message to identify matching intents using
        vector similarity search. Handles special cases like @ mentions for
        direct agent routing. Performs initial intent filtering based on
        confidence scores.
        
        Args:
            state (MessagesState): Current conversation state containing messages
            
        Returns:
            Command | dict: Either a Command to route to a specific agent (for @ mentions)
            or a state update dictionary containing mapped intents
            
        Raises:
            AssertionError: If no human message is found in the conversation state
        """
        last_human_message : Any | None = pd.find(state["messages"][::-1], lambda m: isinstance(m, HumanMessage))
    
        # This should never happen.
        assert last_human_message is not None
        assert isinstance(last_human_message, HumanMessage)
    
        if isinstance(last_human_message.content, str) and last_human_message.content.startswith("@"):
            at_mention = last_human_message.content.split(" ")[0].split("@")[1]
            
            # Check if we have an agent with this name.
            agent = pd.find(self._agents, lambda a: a.name == at_mention)
            
            if agent is not None:
                # We found an agent with this name.
                return Command(goto=agent.name)

        assert isinstance(last_human_message.content, str)
        intents = pd.filter_(self._intent_mapper.map_intent(last_human_message.content, k=10), lambda matches: matches['score'] > self._threshold)
        if len(intents) == 0:
            _, prompted_intents = self._intent_mapper.map_prompt(last_human_message.content, k=10)
            intents = pd.filter_(prompted_intents, lambda matches: matches['score'] > self._threshold)
            
            if len(intents) == 0:
                return {
                    "intent_mapping": {
                        "intents": []
                    }
                }

        
        # We keep intents that are close to the best intent.
        max_score = intents[0]['score']
        close_intents = pd.filter_(intents, lambda intent: max_score - intent['score'] < self._threshold_neighbor)
        
        assert isinstance(close_intents, list)
        
        # If we have multiple intents, we want to count the number of different intent targets. If we have only one target, we can use it because it
        # means that we have multiple intents mapping to the same target.
        unique_targets = pd.uniq(pd.map_(close_intents, lambda intent: intent['intent'].intent_target))
        
        final_intents = []
        if len(unique_targets) == 1:
            final_intents = [close_intents[0]]
        else:
            final_intents = close_intents

        logger.debug(f"final_intents: {final_intents}")

        return {
            "intent_mapping": {
                "intents": final_intents
            }
        }
    
    def return_raw_intent(self, state: dict[str, Any]) -> Command:
        """Return raw intent target as the final response.
        
        Used when a single RAW type intent is identified and should be returned
        directly as the agent's response without further processing.
        
        Args:
            state (dict[str, Any]): Current conversation state
            
        Returns:
            Command: Command to end conversation with the intent target as response
        """
        logger.debug(f"return_raw_intent state: {state}")
        intent : Intent = state["intent_mapping"]["intents"][0]['intent']
        
        ai_message = AIMessage(content=intent.intent_target)
        
        self._notify_ai_message(ai_message, self.name)
        
        return Command(goto=END, update={"messages": [ai_message]})
    
    def filter_out_intents(self, state: IntentState):
        """Filter out logically irrelevant intents using LLM analysis.
        
        Uses the chat model to analyze mapped intents and filter out those that
        are not logically compatible with the user's message. This addresses
        cases where vector similarity alone may match irrelevant intents.
        
        Args:
            state (dict[str, Any]): Current conversation state with mapped intents
            
        Returns:
            Command | None: Command to update state with filtered intents, or None
            if no filtering is needed
        """
        if "intent_mapping" not in state or len(state["intent_mapping"]["intents"]) <= 1:
            return

        if len(state["intent_mapping"]["intents"]) == 1 and state["intent_mapping"]["intents"][0]['score'] > self._threshold:
            return
        
        logger.debug(f"filter_out_intents state: {state}")
        last_human_message : Any = pd.find(state["messages"][::-1], lambda m: isinstance(m, HumanMessage))
        assert last_human_message is not None
        
        mapped_intents = state["intent_mapping"]["intents"]
        
        @tool
        def filter_intents(bool_list: list[bool]) -> list[Intent]:
            """
            This tool is used to filter out the intents that are not related to the last user message. True will keep the intent, false will remove it.
            """
            return []
        
        intents = [intent['text'] for intent in mapped_intents]
        
        system_prompt = f"""You are a logical assistant. You are given a list of possible intents retrieved via vector search from the last user message. These matches may not always be logically relevant because the search is based only on surface similarity, without full understanding of the request.

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
Last user message: "{last_human_message.content}"
        """
        
        # messages = [SystemMessage(content=system_prompt), last_human_message]
        messages: list = [SystemMessage(content=system_prompt)]
        for message in state["messages"]:
            if not isinstance(message, SystemMessage):
                messages.append(message)
        
        response = self._chat_model.bind_tools([filter_intents]).invoke(messages)
        assert isinstance(response, AIMessage)
        
        logger.debug(f"filter_out_intents response: {response}")
        
        filtered_intents : list[Intent] = []
        
        assert isinstance(response.tool_calls, list), response.tool_calls
        assert len(response.tool_calls) > 0, response.tool_calls
        assert isinstance(response.tool_calls[0]['args'], dict), response.tool_calls
        assert 'bool_list' in response.tool_calls[0]['args'], response.tool_calls
        assert isinstance(response.tool_calls[0]['args']['bool_list'], list), response.tool_calls
        
        bool_list = response.tool_calls[0]['args']['bool_list']
        for i in range(len(bool_list)):
            if bool_list[i]:
                filtered_intents.append(mapped_intents[i])
        
        return Command(update={"intent_mapping": {"intents": filtered_intents}})
    
    def _extract_entities(self, text: str) -> list[str]:
        """Extract named entities from text using spaCy.
        
        Uses the spaCy NLP model to identify and extract named entities
        from the provided text, returning them in lowercase for consistent
        comparison.
        
        Args:
            text (str): Input text to extract entities from
            
        Returns:
            list[str]: List of extracted entity texts in lowercase
        """
        doc = nlp(text)
        return [ent.text.lower() for ent in doc.ents]
    
    def entity_check(self, state: IntentState):
        """Validate entity consistency between user message and intents.
        
        Performs entity checking to ensure that intents containing named entities
        are only kept if those entities are present or implied in the user's
        message. Uses both rule-based and LLM-based validation approaches.
        
        Args:
            state (dict[str, Any]): Current conversation state with mapped intents
            
        Returns:
            Command | None: Command to update state with entity-validated intents,
            or None if no intent mapping exists
        """
        if "intent_mapping" not in state:
                return
            
        last_human_message : Any | None = pd.find(state["messages"][::-1], lambda m: isinstance(m, HumanMessage))
        
        assert last_human_message is not None
        assert isinstance(last_human_message, HumanMessage)
        assert isinstance(last_human_message.content, str)
        
        mapped_intents = state["intent_mapping"]["intents"]
        
        filtered_intents = []
        
        for intent in mapped_intents:
            entities = self._extract_entities(intent['intent'].intent_value)
            
            if len(entities) == 0:
                filtered_intents.append(intent)
                continue
            
            last_human_message_entities = self._extract_entities(last_human_message.content)
            all_entities_present = False
            if len(last_human_message_entities) > 0 and len(last_human_message_entities) >= len(entities):
                all_entities_present = True
                for entity in last_human_message_entities:
                    if entity not in entities:
                        all_entities_present = False
                        break
            
            if all_entities_present:
                filtered_intents.append(intent)
                continue
            
            messages: list[BaseMessage] = [SystemMessage(content=f"""
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
Last user message: "{last_human_message.content}"
""")]
            
            for message in state["messages"]:
                # if not isinstance(message, SystemMessage):
                if isinstance(message, HumanMessage):
                    messages.append(message)
            
            response = self._chat_model.invoke(messages)
            
            rich.print(messages)
            rich.print(response.content)
            rich.print(response.content == "true")
            if response.content == "true":
                filtered_intents.append(intent)
        
        return Command(update={"intent_mapping": {"intents": filtered_intents}})

    def intent_mapping_router(self, state: IntentState) -> Command:
        """Route conversation flow based on intent mapping results.
        
        Analyzes the current intent mapping state and determines the next step
        in the conversation flow. Routes to different handlers based on the
        number and type of mapped intents.
        
        Args:
            state (dict[str, Any]): Current conversation state with intent mapping
            
        Returns:
            Command: Command specifying the next node to execute in the graph
        """
        logger.debug(f"intent_mapping_router state: {state}")
        if "intent_mapping" in state:
            intent_mapping = state["intent_mapping"]
            if len(intent_mapping["intents"]) == 0:
                # Check if there's an active agent for context preservation
                if (hasattr(self, '_state') and 
                    hasattr(self._state, 'current_active_agent') and 
                    self._state.current_active_agent):
                    active_agent_name = self._state.current_active_agent
                    # Find the active agent in our agents list
                    active_agent = pd.find(self._agents, lambda a: a.name == active_agent_name)
                    if active_agent is not None:
                        # Route to the active agent for conversation continuation
                        return Command(goto=active_agent_name)
                
                return Command(goto="call_model")
            elif len(intent_mapping["intents"]) == 1:
                intent : Intent = intent_mapping["intents"][0]['intent']
                
                # # Handle deserialized intent targets
                # if isinstance(intent.intent_target, dict) and '_type' in intent.intent_target:
                #     target_info = intent.intent_target
                #     if target_info['_type'] == 'agent':
                #         # Find agent by name
                #         for agent in self._agents:
                #             if agent.name == target_info['name']:
                #                 intent.intent_target = agent
                #                 break
                #     elif target_info['_type'] == 'raw':
                #         intent.intent_target = target_info['value']
                
                if intent.intent_type == IntentType.RAW:
                    return Command(goto=END, update={
                        "messages": [AIMessage(content=intent.intent_target)]
                    })
                elif intent.intent_type == IntentType.TOOL:
                    # Create a tool call message to trigger the specific tool
                    tool_call_message = AIMessage(
                        content="",
                        tool_calls=[{
                            "name": intent.intent_target,
                            "args": {},
                            "id": f"call_{intent.intent_target}",
                            "type": "tool_call"
                        }]
                    )
                    return Command(goto="call_tools", update={
                        "messages": [tool_call_message]
                    })
                elif intent.intent_type == IntentType.AGENT:
                    return Command(goto=intent.intent_target)
                else:
                    return Command(goto="inject_intents_in_system_prompt")
            if len(intent_mapping["intents"]) >= 1:
                return Command(goto="inject_intents_in_system_prompt")
        
        return Command(goto="call_model")
    
    def inject_intents_in_system_prompt(self, state: IntentState):
        """Inject mapped intents into the system prompt.
        
        Updates the agent's system prompt to include information about
        mapped intents, providing context for the language model to
        make intent-aware responses.
        
        Args:
            state (dict[str, Any]): Current conversation state with intent mapping
            
        Returns:
            None: Updates the agent's system prompt in place
        """
        # We reset the system prompt to the original one.
        self._system_prompt = self._configuration.system_prompt
        
        if "intent_mapping" in state and len(state["intent_mapping"]["intents"]) > 0:
            intents = state["intent_mapping"]["intents"]
            updated_system_prompt = f"""{self._configuration.system_prompt}
            
            ---
            INTENT RULES:
            Everytime a user is sending a message, a system is trying to map the prompt/message to an intent or a list of intents using a vector search.
            The following is the list of mapped intents. This list will change over time as new messages comes in.
            You must analyze if the user message and the mapped intents are related to each other. If it's the case, you must take them into account, otherwise you must ignore the ones that are not related.
            If you endup with a single intent which is of type RAW, you must output the intent_target and nothing else as there will be tests asserting the correctness of the output.
            
            

            """
            
            for intent in intents:
                updated_system_prompt += f"""
                - {intent['intent']}
                """

            updated_system_prompt += "\n\nEND INTENT RULES"
            self._system_prompt = updated_system_prompt
    
    def should_filter(self, state: dict[str, Any]) -> str:
        """Determine if intent mapping should be filtered.
        
        Checks if the intent mapping should be filtered based on the threshold
        and neighbor values.
        """
        
        if "intent_mapping" in state:
            if len(state["intent_mapping"]["intents"]) == 1 and state["intent_mapping"]["intents"][0]['score'] > self._threshold:
                return "intent_mapping_router"
        
        return "filter_out_intents"
        
    
    def build_graph(self, patcher: Optional[Callable] = None):
        """Build the conversation flow graph for the IntentAgent.
        
        Constructs a StateGraph that defines the conversation flow with intent
        mapping capabilities. The graph includes nodes for intent mapping,
        filtering, entity checking, routing, and integration with sub-agents.
        
        Args:
            patcher (Optional[Callable], optional): Optional function to modify
                the graph before compilation. Defaults to None.
                
        Returns:
            None: Sets the compiled graph on the agent instance
        """
        graph = StateGraph(IntentState)
        
        graph.add_node(self.map_intents)
        graph.add_edge(START, "map_intents")
        
        graph.add_conditional_edges("map_intents", self.should_filter)
        
        graph.add_node(self.filter_out_intents)
        # graph.add_edge("map_intents", "filter_out_intents")
        
        graph.add_node(self.entity_check)
        graph.add_edge("filter_out_intents", "entity_check")
        
        graph.add_node(self.intent_mapping_router)
        # graph.add_conditional_edges("intent_mapping", self.intent_mapping_router)
        graph.add_edge("entity_check", "intent_mapping_router")
        # graph.add_edge("intent_mapping_router", END)
        
        graph.add_node(self.inject_intents_in_system_prompt)
        graph.add_edge("inject_intents_in_system_prompt", "call_model")
        
        # graph.add_node(self.return_raw_intent)
        # graph.add_edge("return_raw_intent", END)
        
        graph.add_node(self.call_model)
        graph.add_node(self.call_tools)
        
        graph.add_edge("call_model", END)
        
        
        for agent in self._agents:
            # graph.add_node(agent.graph, metadata={"name": agent.name})
            graph.add_node(agent.name, agent.graph)
            # This makes sure that after calling an agent in a graph, we call the main model of the graph.
            # graph.add_edge(agent.name, "call_model")
        
        
        if patcher is not None:
            graph = patcher(graph)
        
        self.graph = graph.compile(checkpointer=self._checkpointer)     

    @property
    def intents(self) -> list[Intent]:
        return self._intents
        
        