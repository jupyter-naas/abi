from typing import Union, Callable, Optional, Any, Dict
from queue import Queue
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import Tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from .Agent import Agent, AgentSharedState, AgentConfiguration, create_checkpointer
from .beta.IntentMapper import IntentMapper, Intent, IntentType, IntentScope
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langgraph.graph.message import MessagesState
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.tools import tool
from abi import logger
import pydash as pd
import spacy


nlp = spacy.load("en_core_web_sm")
MULTIPLES_INTENTS_MESSAGE = "I found multiple intents that could handle your request"
DEFAULT_INTENTS: list = [
    Intent(intent_value="what's your name?", intent_type=IntentType.AGENT, intent_target="call_model", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="what do you do?", intent_type=IntentType.AGENT, intent_target="call_model", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="comment tu t'appelles?", intent_type=IntentType.AGENT, intent_target="call_model", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="que fais-tu?", intent_type=IntentType.AGENT, intent_target="call_model", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Hello", intent_type=IntentType.RAW, intent_target="Hello, what can I do for you?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Hi", intent_type=IntentType.RAW, intent_target="Hello, what can I do for you?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Hey", intent_type=IntentType.RAW, intent_target="Hello, what can I do for you?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Salut", intent_type=IntentType.RAW, intent_target="Bonjour, que puis-je faire pour vous?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Bonjour", intent_type=IntentType.RAW, intent_target="Bonjour, que puis-je faire pour vous?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Coucou", intent_type=IntentType.RAW, intent_target="Bonjour, que puis-je faire pour vous?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Hi there", intent_type=IntentType.RAW, intent_target="Hello, what can I do for you?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Hello there", intent_type=IntentType.RAW, intent_target="Hello, what can I do for you?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Hello, how are you?", intent_type=IntentType.RAW, intent_target="Hello, I am doing well thank you, how can I help you today?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Hi, how are you?", intent_type=IntentType.RAW, intent_target="Hello, I am doing well thank you, how can I help you today?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Bonjour, comment vas-tu?", intent_type=IntentType.RAW, intent_target="Bonjour, je vais bien merci, comment puis-je vous aider aujourd'hui?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Salut, ça va?", intent_type=IntentType.RAW, intent_target="Bonjour, je vais bien merci, comment puis-je vous aider aujourd'hui?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Thank you", intent_type=IntentType.RAW, intent_target="You're welcome, can I help you with anything else?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Thank you very much", intent_type=IntentType.RAW, intent_target="You're welcome, can I help you with anything else?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Thank you so much", intent_type=IntentType.RAW, intent_target="You're welcome, can I help you with anything else?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Merci", intent_type=IntentType.RAW, intent_target="Je vous en prie, puis-je vous aider avec autre chose?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Merci beaucoup", intent_type=IntentType.RAW, intent_target="Je vous en prie, puis-je vous aider avec autre chose?", intent_scope=IntentScope.DIRECT),
    Intent(intent_value="Merci bien", intent_type=IntentType.RAW, intent_target="Je vous en prie, puis-je vous aider avec autre chose?", intent_scope=IntentScope.DIRECT),
]


class IntentState(MessagesState):
    """State class for intent-based conversations.
    
    Extends MessagesState to include intent mapping information that tracks
    the current intent analysis results throughout the conversation flow.
    
    Attributes:
        intent_mapping (dict[str, Any]): Dictionary containing mapped intents
            and their associated metadata from the intent analysis process.
    """
    intent_mapping: Dict[str, Any]


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
        # Add default intents while avoiding duplicates
        intent_values = {(intent.intent_value, intent.intent_type, intent.intent_target) for intent in intents}
        for default_intent in DEFAULT_INTENTS:
            if (default_intent.intent_value, default_intent.intent_type, default_intent.intent_target) not in intent_values:
                intents.append(default_intent)

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

    @property
    def intents(self) -> list[Intent]:
        return self._intents
    

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

        graph.add_node(self.current_active_agent)
        graph.add_edge(START, "current_active_agent")
        
        graph.add_node(self.continue_conversation)
        
        graph.add_node(self.map_intents)
        
        graph.add_node(self.filter_out_intents)
        
        graph.add_node(self.entity_check)
        
        graph.add_node(self.intent_mapping_router)
        graph.add_edge("entity_check", "intent_mapping_router")
        
        graph.add_node(self.request_human_validation)
        graph.add_edge("request_human_validation", END)
        
        graph.add_node(self.inject_intents_in_system_prompt)
        graph.add_edge("inject_intents_in_system_prompt", "call_model")
        
        graph.add_node(self.call_model)
        graph.add_edge("call_model", END)

        graph.add_node(self.call_tools)

        for agent in self._agents:
            graph.add_node(agent.name, agent.graph)

        if patcher is not None:
            graph = patcher(graph)
        
        self.graph = graph.compile(checkpointer=self._checkpointer)  
    

    def continue_conversation(self, state: IntentState) -> Command:
        return Command(goto="map_intents")


    def map_intents(self, state: IntentState) -> Command:
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
        # Reset intents rules in system prompt
        # self._system_prompt = self._configuration.system_prompt

        # Get the last messages
        last_ai_message : Any | None = pd.find(state["messages"][::-1], lambda m: isinstance(m, AIMessage))
        last_human_message = self.get_last_human_message(state)

        # Assertions to ensure the last human message is valid
        assert last_human_message is not None
        assert isinstance(last_human_message, HumanMessage)
        assert isinstance(last_human_message.content, str)

        logger.debug("🔍 Map intents")
        logger.debug(f"==> Last human message: {last_human_message.content if last_human_message is not None else None}")
        
        # Handle multiples intents routing via numeric response to a validation request (e.g., "1", "2", etc.)
        if isinstance(last_human_message.content, str) and last_human_message.content.strip().isdigit() and last_ai_message is not None and MULTIPLES_INTENTS_MESSAGE in last_ai_message.content and last_ai_message.additional_kwargs.get("owner") == self.name:
            choice_num = int(last_human_message.content.strip())
            
            logger.debug("🔀 Handle multiples intents routing via numeric response to a validation request (e.g., '1', '2', etc.)")

            # Extract agent names from the validation message
            lines = last_ai_message.content.split('\n')
            intent_lines = [line for line in lines if line.strip().startswith(f"{choice_num}.")]
            if intent_lines:
                command_update: dict = {
                    "intent_mapping": {"intents": []}
                }
                logger.debug(f"Command update: {command_update}")

                # Extract agent name from the line like "1. **AgentName** (confidence: 89.7%)"
                intent_line = intent_lines[0]
                if "**" in intent_line:
                    intent_name = intent_line.split("**")[1]
                    agent = pd.find(self._agents, lambda a: a.name == intent_name)
                    if agent is not None:
                        logger.debug(f"✅ Calling agent: {intent_name}")
                        return Command(goto=intent_name, update=command_update)
                    else:
                        logger.debug("❌ Agent not found, going to call_model")
                        return Command(goto="call_model", update=command_update) 

        # Map intents using vector similarity search
        intents = pd.filter_(self._intent_mapper.map_intent(last_human_message.content, k=10), lambda matches: matches['score'] > self._threshold)
        if len(intents) == 0:
            _, prompted_intents = self._intent_mapper.map_prompt(last_human_message.content, k=10)
            intents = pd.filter_(prompted_intents, lambda matches: matches['score'] > self._threshold)
            
            # If we have no intents, we return an empty intent mapping
            if len(intents) == 0:
                return Command(update={
                    "intent_mapping": {
                        "intents": []
                    }
                }, goto=self.should_filter([]))

        # Keep intents that are close to the best intent.
        max_score = intents[0]['score']
        if max_score >= 0.99:
            logger.debug(f"🎯 Intent mapping score above 99% ({round(max_score*100, 2)}%), routing to intent_mapping_router")
            return Command(goto="intent_mapping_router", update={"intent_mapping": {"intents": [intents[0]]}})
        
        close_intents = pd.filter_(intents, lambda intent: max_score - intent['score'] < self._threshold_neighbor)
        
        assert isinstance(close_intents, list)
        
        # Filter out intents with duplicate targets, keeping the highest scoring one
        seen_targets = set()
        final_intents = []
        for intent in close_intents:
            target = intent['intent'].intent_target
            if target not in seen_targets:
                seen_targets.add(target)
                final_intents.append(intent)

        logger.debug(f"{len(final_intents)} intents mapped: {final_intents}")
        state['intent_mapping'] = {"intents": final_intents}
        return Command(goto=self.should_filter(final_intents), update={"intent_mapping": {"intents": final_intents}})
    

    def should_filter(self, intents: list) -> str:
        """Determine if intent mapping should be filtered.
        
        Checks if the intent mapping should be filtered based on the threshold
        and neighbor values.
        """
        
        if len(intents) == 1 and intents[0]['score'] > self._threshold:
            return "intent_mapping_router"
        if len(intents) == 0:
            logger.debug("❌ No intents found, going to call_model")
            return "call_model"
        
        return "filter_out_intents"
    
    
    def filter_out_intents(self, state: IntentState) -> Command:
        """Filter out logically irrelevant intents using LLM analysis.
        
        Uses the chat model to analyze mapped intents and filter out those that
        are not logically compatible with the user's message. This addresses
        cases where vector similarity alone may match irrelevant intents.
        
        Args:
            state (dict[str, Any]): Current conversation state with mapped intents
            
        Returns:
            Command: Command to update state with filtered intents
            if no filtering is needed
        """
        logger.debug("🔍 Filter out irrelevant intents")
        last_human_message = self.get_last_human_message(state)
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
        
        try:
            response = self._chat_model.bind_tools([filter_intents]).invoke(messages)
        except Exception:
            logger.warning("Error filtering intents going to 'entity_check'")
            return Command(goto="entity_check")
        
        assert isinstance(response, AIMessage)
        
        filtered_intents: list = []
        
        try:
            assert isinstance(response.tool_calls, list), response.tool_calls
            assert len(response.tool_calls) > 0, response.tool_calls
            assert isinstance(response.tool_calls[0]['args'], dict), response.tool_calls
            assert 'bool_list' in response.tool_calls[0]['args'], response.tool_calls
            assert isinstance(response.tool_calls[0]['args']['bool_list'], list), response.tool_calls
            
            bool_list = response.tool_calls[0]['args']['bool_list']
            for i in range(len(bool_list)):
                if bool_list[i]:
                    filtered_intents.append(mapped_intents[i])
        except Exception as e:
            logger.error(f"Error filtering out intents: {e}")
            filtered_intents = mapped_intents

        logger.debug(f"{len(filtered_intents)} intents filtered: {filtered_intents}")
        state['intent_mapping'] = {"intents": filtered_intents}
        if len(filtered_intents) == 1 and filtered_intents[0]['score'] > self._threshold:
            return Command(goto="intent_mapping_router", update={"intent_mapping": {"intents": filtered_intents}})
        return Command(goto="entity_check", update={"intent_mapping": {"intents": filtered_intents}})


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
    

    def entity_check(self, state: IntentState) -> Command:
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
        logger.debug("🔍 Entity Check")

        last_human_message = self.get_last_human_message(state)
        
        assert last_human_message is not None
        assert isinstance(last_human_message, HumanMessage)
        assert isinstance(last_human_message.content, str)
        assert "intent_mapping" in state

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
                if isinstance(message, HumanMessage):
                    messages.append(message)
            
            response = self._chat_model.invoke(messages)
            if response.content == "true":
                filtered_intents.append(intent)

        logger.debug(f"{len(filtered_intents)} intents filtered after entity check: {filtered_intents}")
        
        return Command(update={"intent_mapping": {"intents": filtered_intents}})


    def request_human_validation(self, state: IntentState) -> Command:
        """Request human validation when multiple agents are above threshold.
        
        When multiple agent intents are identified with scores above the threshold,
        this method asks the human user to choose which agent they want to use.
        It presents the available options and waits for user input.
        
        Args:
            state (IntentState): Current conversation state with multiple agent intents
            
        Returns:
            Command: Command to end conversation with validation request message
        """
        logger.debug("👀 Request Human Validation")
        
        if "intent_mapping" not in state or len(state["intent_mapping"]["intents"]) == 0:
            return Command(goto="call_model")
        
        agent_intents = [
            intent for intent in state["intent_mapping"]["intents"] if intent['intent'].intent_type in [IntentType.AGENT, IntentType.TOOL]
        ]
        
        if len(agent_intents) <= 1:
            return Command(goto="inject_intents_in_system_prompt")
        
        # Create a list of unique agents with their scores
        agents_info = []
        seen_agents = set()
        
        for intent in agent_intents:
            agent_name = intent['intent'].intent_target
            if agent_name not in seen_agents:
                agents_info.append({
                    'name': agent_name,
                    'score': intent['score'],
                    'intent_text': intent['intent'].intent_value
                })
                seen_agents.add(agent_name)
        
        # Sort by score (descending) and then by agent name (ascending)
        agents_info.sort(key=lambda x: (-x['score'], x['name']))
        
        # Create the validation message
        # validation_message = f"Validation Request: '{initial_human_message.content}'\n\n"
        validation_message = "I found multiple intents that could handle your request:\n\n"
        
        for i, agent_info in enumerate(agents_info, 1):
            validation_message += f"{i}. **{agent_info['name']}** (confidence: {agent_info['score']:.1%})\n"
            validation_message += f"   Intent: {agent_info['intent_text']}\n\n"
        
        validation_message += "Please choose an intent by number (e.g., '1' or '2')\n"
        
        ai_message = AIMessage(content=validation_message, additional_kwargs={"owner": self.name})
        self._notify_ai_message(ai_message, self.name)
        
        return Command(goto=END, update={"messages": [ai_message]})


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
        logger.debug("🔀 Intent Mapping Router")

        if "intent_mapping" in state:
            intent_mapping = state["intent_mapping"]
            # If there are no intents, we check if there's an active agent for context preservation
            if len(intent_mapping["intents"]) == 0:
                logger.debug("❌ No intents found, calling model for active agent")
                return Command(goto="call_model")
            
            # If there's a single intent is mapped, we check the intent type to return the appropriate Command
            if len(intent_mapping["intents"]) == 1:
                logger.debug("✅ Single intent found, routing to appropriate handler")
                intent : Intent = intent_mapping["intents"][0]['intent']
                if intent.intent_type == IntentType.RAW:
                    logger.debug(f"📝 Raw intent found, routing to '{intent.intent_target}'")
                    
                    ai_message = AIMessage(content=intent.intent_target)
                    self._notify_ai_message(ai_message, self.name)

                    return Command(goto=END, update={
                        "messages": [ai_message]
                    })
                elif intent.intent_type == IntentType.AGENT:
                    logger.debug(f"🤖 Agent intent found, routing to {intent.intent_target}")
                    return Command(goto=intent.intent_target)
                else:
                    logger.debug("🔧 Tool intent found, routing to inject intents in system prompt")
                    return Command(goto="inject_intents_in_system_prompt")
                
            # If there are multiple intents, we check intents type to return the appropriate Command
            elif len(intent_mapping["intents"]) > 1:
                logger.debug("✅ Multiple intents found, routing to request human validation or inject intents in system prompt")
                # Check if we have multiple agent intents above threshold
                not_raw_intents = [
                    intent for intent in intent_mapping["intents"] if intent['intent'].intent_type in [IntentType.AGENT, IntentType.TOOL]
                ]
                
                if len(not_raw_intents) > 1:
                    # We have multiple agent/tools intents - ask human for validation
                    return Command(goto="request_human_validation")
                else:
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
        logger.debug("💉 Inject Intents in System Prompt")

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


    def duplicate(self, queue: Queue | None = None, agent_shared_state: AgentSharedState | None = None) -> "Agent":
        """Create a new instance of the agent with the same configuration.

        This method creates a deep copy of the agent with the same configuration
        but with its own independent state. This is useful when you need to run
        multiple instances of the same agent concurrently.

        Returns:
            Agent: A new Agent instance with the same configuration
        """
        shared_state = agent_shared_state or AgentSharedState()
        
        if queue is None:
            queue = Queue()

        # We duplicated each agent and add them as tools.
        # This will be recursively done for each sub agents.
        agents: list[IntentAgent] = [agent.duplicate(queue, shared_state) for agent in self._original_agents]

        new_agent = IntentAgent(
            name=self._name,
            description=self._description,
            chat_model=self._chat_model,
            tools=self._original_tools,
            agents=agents,
            intents=self._intents,
            memory=self._checkpointer,
            state=shared_state,  # Create new state instance
            configuration=self._configuration,
            event_queue=queue,
        )

        return new_agent   
