# PowerPointAgent

## What it is
A LangGraph/LangChain-based agent that turns a user brief into a PowerPoint presentation using a `.pptx` template’s slide/shape structure. It:
- Injects the template structure into the system prompt (as RDF/Turtle),
- Guides the user to produce/confirm a markdown slide draft,
- Converts approved markdown into shape-populated JSON,
- Generates a final `.pptx` via a workflow that creates a presentation from the template and returns a download link.

## Public API

### Constants
- `NAME`: `"PowerPoint"`
- `DESCRIPTION`: `"An agent specialized in creating PowerPoint presentations."`
- `AVATAR_URL`: PowerPoint logo URL
- `SYSTEM_PROMPT`: System prompt template containing `[TOOLS]` and `[TEMPLATE_STRUCTURE]` placeholders.
- `SUGGESTIONS`: Empty list (currently unused)

### Classes

#### `PowerPointState(ABIAgentState)`
Agent state extension used in the graph.
- `presentation_data: dict`: populated after markdown→JSON conversion.

#### `PowerPointAgent(Agent)`
Main agent implementation.

**Constructor**
```python
PowerPointAgent(
    name: str,
    description: str,
    chat_model: BaseChatModel | ChatModel,
    datastore_path: str,
    template_path: str,
    workspace_id: str,
    storage_name: str,
    tools: list[Tool | BaseTool | Agent] = [],
    agents: list[Agent] = [],
    memory: BaseCheckpointSaver = MemorySaver(),
    state: AgentSharedState = AgentSharedState(),
    configuration: AgentConfiguration = AgentConfiguration(),
    event_queue: Queue | None = None,
)
```
Purpose:
- Initializes PowerPoint integration, storage utilities, triple store access, Naas configuration, and the workflow used to create a presentation from a template.

**Graph construction**
- `build_graph(patcher: Optional[Callable] = None)`
  - Builds a `StateGraph(PowerPointState)` and registers nodes used in the conversation flow:
    - `current_active_agent` (inherited node name from base `Agent`)
    - `continue_conversation`
    - `inject_template_structure`
    - `validate_presentation_draft`
    - `call_model` (base `Agent`)
    - `call_tools` (base `Agent`)
    - `convert_markdown_to_json`
    - `convert_json_to_ppt`
  - Compiles with the agent checkpointer.

**Conversation/flow nodes**
- `continue_conversation(state: MessagesState) -> Command`
  - Routes to `inject_template_structure`.

- `inject_template_structure(state: PowerPointState) -> Command`
  - If the system prompt contains `[TEMPLATE_STRUCTURE]`, it:
    - Reads slides/shapes from the template via `PowerPointIntegration.get_all_shapes_and_slides()`,
    - Builds an RDF graph (Turtle) describing presentation/slides/shapes,
    - Injects it into the system prompt.
  - Routes to `validate_presentation_draft`.

- `validate_presentation_draft(state: PowerPointState) -> Command`
  - If last AI message contains a markdown code block and there is a last user message, it asks the model (via a strict true/false system prompt) whether the user approved proceeding.
  - On `"true"` → routes to `convert_markdown_to_json`
  - Otherwise → routes to `call_model`

**Markdown/JSON/PPT conversion**
- `convert_markdown_to_shapes(markdown_blocks: str, template_shapes: list[dict]) -> str`
  - Prompts the model to map markdown slide text into the given template shape JSON by updating only `"text"` fields and returning JSON only.

- `convert_markdown_to_json(state: PowerPointState) -> Command`
  - Parses the last AI message to extract:
    - `presentation_title` from `**PresentationTitle: ...**` (defaults to `"Presentation"`),
    - markdown content within a ```markdown fenced block,
    - per-slide `TemplateSlideUri: ppt:SlideN` (required),
    - optional `Sources:` list.
  - For each slide:
    - loads template shapes for the referenced slide number,
    - uses `convert_markdown_to_shapes(...)` then `extract_json_from_completion(...)` to produce `shapes`.
  - Saves artifacts to storage:
    - `markdown_blocks.txt`
    - `presentation_data.json`
  - Updates state with `presentation_data` and routes to `convert_json_to_ppt`.

- `convert_json_to_ppt(state: PowerPointState) -> Command`
  - Calls `CreatePresentationFromTemplateWorkflow.create_presentation(...)` with:
    - `presentation_name` derived from title (spaces removed) + `.pptx`,
    - `slides_data`,
    - `template_path`.
  - Emits a final AI message containing either:
    - a public `download_url`, or
    - a bug report template if `download_url` is missing.
  - Ends the graph.

**Lifecycle**
- `duplicate(queue: Queue | None = None, agent_shared_state: AgentSharedState | None = None) -> Agent`
  - Clones the agent with the same configuration and duplicated sub-agents, using an independent shared state and (optionally) a shared event queue.

### Factory function

#### `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Agent`
Creates and returns a fully configured `PowerPointAgent` with:
- A specific imported model: `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model`
- Default paths:
  - `datastore_path = "datastore/powerpoint/presentations"`
  - `template_path = "src/marketplace/applications/powerpoint/templates/TemplateNaasPPT.pptx"`
- Workspace/storage settings read from `ABIModule.get_instance().configuration`
- In-memory checkpointing via `MemorySaver()`

## Configuration/Dependencies

### Runtime services and integrations
The agent depends on the `ABIModule` singleton and its engine services:
- Triple store: `ABIModule.get_instance().engine.services.triple_store`
- Object storage: `ABIModule.get_instance().engine.services.object_storage`

Integrations/configuration objects used:
- `PowerPointIntegrationConfiguration(template_path=...)`
- `PowerPointIntegration(...)` (reads template shapes/slides)
- `NaasIntegrationConfiguration(api_key=...)` (uses `naas_api_key` from module configuration)
- `AddPowerPointPresentationPipelineConfiguration(...)`
- `CreatePresentationFromTemplateWorkflow(...)` (creates final PPT and registers into a knowledge graph; returns `download_url` and `presentation_uri`)

### Key third-party libraries
- `langchain_core` (chat model + messages + tools)
- `langgraph` (graph orchestration + checkpointing)
- `rdflib` (template structure serialization as Turtle)
- `pydash` (message searching)
- `naas_abi_core` (Agent framework, logging, JSON utilities, storage utilities)

## Usage

Minimal example (factory):
```python
from naas_abi_marketplace.applications.powerpoint.agents.PowerPointAgent import create_agent

agent = create_agent()
agent.build_graph()

# Execution depends on the naas_abi_core Agent runtime and how it drives langgraph graphs.
# Typically, you would pass user messages into the agent's execution entrypoint provided by the base Agent.
```

Creating directly:
```python
from langgraph.checkpoint.memory import MemorySaver
from naas_abi_core.services.agent.Agent import AgentConfiguration, AgentSharedState
from naas_abi_marketplace.applications.powerpoint.agents.PowerPointAgent import PowerPointAgent

# chat_model and ABIModule-backed services must be available in your environment.
agent = PowerPointAgent(
    name="PowerPoint",
    description="An agent specialized in creating PowerPoint presentations.",
    chat_model=...,  # BaseChatModel | ChatModel
    datastore_path="datastore/powerpoint/presentations",
    template_path="path/to/template.pptx",
    workspace_id="...",
    storage_name="...",
    memory=MemorySaver(),
    state=AgentSharedState(thread_id="0"),
    configuration=AgentConfiguration(),
)
agent.build_graph()
```

## Caveats
- The markdown-to-PPT pipeline requires the AI draft to include:
  - a `**PresentationTitle: ...**` line (optional; defaults to `"Presentation"`),
  - a fenced ````markdown ... ``` block,
  - for each slide: `TemplateSlideUri: ppt:SlideN` (mandatory).
- If no `TemplateSlideUri` is found for a slide, the agent stops and returns an error message.
- The agent relies on model outputs being strictly parseable:
  - `validate_presentation_draft` expects the model to respond with exactly `"true"` or `"false"`.
  - `convert_markdown_to_shapes` expects JSON-only output; parsing is done via `extract_json_from_completion`.
- Slide numbering in produced JSON uses enumeration order of parsed markdown blocks (starting at 0), which may not match the human-readable “Slide X” label in markdown.
