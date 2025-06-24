# Intent Agent Architecture

The IntentAgent is a specialized agent that extends the base Agent class with advanced intent mapping and routing capabilities. It analyzes user messages to identify and map them to predefined intents, then routes conversations accordingly using sophisticated filtering and validation mechanisms.

## Design Philosophy

The IntentAgent addresses the challenge of routing user messages to appropriate handlers by:

1. **Intent Recognition**: Using vector similarity search to map user messages to predefined intents
2. **Logical Filtering**: Employing LLM-based analysis to filter out logically irrelevant intents
3. **Entity Validation**: Ensuring consistency between entities in user messages and mapped intents
4. **Smart Routing**: Directing conversation flow based on intent types and targets
5. **Contextual Processing**: Injecting intent information into system prompts for context-aware responses

## Key Components

### IntentState
Extends the base MessagesState to include intent mapping information:
```python
class IntentState(MessagesState):
    intent_mapping: dict[str, Any]  # Contains mapped intents and metadata
```

### Intent Types
The agent handles different types of intents:
- **RAW**: Direct text responses returned immediately
- **AGENT**: Routes to specific sub-agents
- **TOOL**: Routes to tool execution (implementation varies)

### Core Processing Pipeline

The IntentAgent processes conversations through a multi-stage pipeline:

1. **Intent Mapping**: Analyzes user messages using vector similarity search
2. **Intent Filtering**: Uses LLM analysis to remove logically irrelevant matches
3. **Entity Checking**: Validates entity consistency between user input and intents
4. **Intent Routing**: Determines next actions based on mapping results
5. **Context Injection**: Updates system prompts with intent information

## Conversation Flow

```mermaid
graph TD
    A[START] --> B["map_intents()"]
    B --> C["filter_out_intents()"]
    C --> D["entity_check()"]
    D --> E["intent_mapping_router()"]
    
    E --> F{Intent Analysis}
    F -->|No intents found| G["call_model()"]
    F -->|Single RAW intent| H[END with RAW response]
    F -->|Single AGENT intent| I["Route to specific agent"]
    F -->|Multiple intents or other types| J["inject_intents_in_system_prompt()"]
    F -->|@ mention detected| K["Direct agent routing"]
    
    G --> L[END]
    J --> M["call_model() with context"]
    M --> L
    I --> N["Sub-agent processing"]
    N --> M
    K --> N
    
    subgraph "Intent Processing Pipeline"
        B
        C
        D
        E
    end
    
    subgraph "Response Generation"
        G
        J
        M
    end
    
    subgraph "Special Routing"
        H
        I
        K
        N
    end
```