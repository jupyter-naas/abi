# PowerPointAgent

## What it is
A LangGraph-based agent that helps draft a slide deck in markdown, converts it to slide/shape JSON using a `.pptx` template’s structure, then generates a final PowerPoint from that template and returns a download link (when available).

## Public API

### Classes

- `PowerPointState(ABIAgentState)`
  - Agent state extension that adds:
    - `presentation_data: dict` — populated after markdown → JSON conversion.

- `PowerPointAgent(Agent)`
  - Main agent implementation for creating presentations from a template.

#### Class attributes
- `name = "PowerPoint"`
- `description = "An agent specialized in creating PowerPoint presentations."`
- `avatar_url` — PowerPoint logo URL
- `system_prompt` — includes `[TOOLS]` and `[TEMPLATE_STRUCTURE]` placeholders
- `suggestions: list[str] = []`

#### Constructors / factories
- `PowerPointAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> PowerPointAgent`
  - Creates a configured agent using `ABIModule` services and the default chat model from the model registry.
  - Sets defaults:
    - `datastore_path = "datastore/powerpoint/presentations"`
    - `template_path = "src/marketplace/applications/powerpoint/templates/TemplateNaasPPT.pptx"`
  - Injects the tool list into `system_prompt` (tools list is currently empty in code).

- `PowerPointAgent.__init__(...)`
  - Wires integrations/services:
    - `PowerPointIntegration` (reads template slides/shapes)
    - triple store service (via `ABIModule`)
    - object storage via `StorageUtils`
    - `CreatePresentationFromTemplateWorkflow` (creates PPTX + returns metadata)

#### Graph / node methods
- `build_graph(patcher: Callable | None = None)`
  - Builds and compiles a `StateGraph(PowerPointState)` with nodes:
    - `current_active_agent` (base `Agent`)
    - `continue_conversation`
    - `inject_template_structure`
    - `validate_presentation_draft`
    - `call_model` (base `Agent`)
    - `call_tools` (base `Agent`)
    - `convert_markdown_to_json`
    - `convert_json_to_ppt`

- `continue_conversation(state: MessagesState) -> Command`
  - Routes to `inject_template_structure`.

- `inject_template_structure(state: PowerPointState) -> Command`
  - If `[TEMPLATE_STRUCTURE]` is present in `state["system_prompt"]`:
    - Extracts slides/shapes from the template (`get_all_shapes_and_slides()`).
    - Serializes the structure as RDF/Turtle inside a fenced code block.
    - Replaces the placeholder in the system prompt.
  - Routes to `validate_presentation_draft`.

- `validate_presentation_draft(state: PowerPointState) -> Command`
  - If there is a last human message and the last AI message contains a ```markdown block:
    - Calls the chat model with a strict system prompt to output only `"true"` or `"false"`.
    - `"true"` → routes to `convert_markdown_to_json`
    - otherwise → routes to `call_model`
  - If conditions aren’t met → routes to `call_model`.

#### Conversion methods
- `convert_markdown_to_shapes(markdown_blocks: str, template_shapes: list[dict]) -> str`
  - Prompts the model to map markdown slide content onto the provided template shapes by updating only each shape’s `"text"` field.
  - Returns the model response text (expected to be JSON only).

- `convert_markdown_to_json(state: PowerPointState) -> Command`
  - Reads the last AI message content and:
    - Extracts `presentation_title` from `**PresentationTitle: ...**` (defaults to `"Presentation"`).
    - Extracts markdown between ```markdown ... ``` (required).
    - Splits slides by `"###"` and requires each slide to include `TemplateSlideUri: ppt:SlideN`.
    - For each slide:
      - loads template shapes for that template slide number
      - converts slide markdown → shapes JSON using `convert_markdown_to_shapes(...)`
      - extracts `Sources:` lines into a list
    - Saves:
      - `markdown_blocks.txt`
      - `presentation_data.json`
  - On missing markdown or missing template slide URI: ends the graph with an error AI message.
  - Otherwise routes to `convert_json_to_ppt` and updates `presentation_data`.

- `convert_json_to_ppt(state: PowerPointState) -> Command`
  - Calls `CreatePresentationFromTemplateWorkflow.create_presentation(...)` using:
    - `presentation_name = <title-without-spaces>.pptx`
    - `slides_data` and `template_path`
  - Sends a final AI message containing:
    - a public download link if `download_url` exists, otherwise
    - a bug report template with `presentation_uri` and storage path
  - Ends the graph.

#### Lifecycle
- `duplicate(queue: Queue | None = None, agent_shared_state: AgentSharedState | None = None) -> Agent`
  - Creates a new agent instance with the same configuration and duplicated sub-agents, using a new/shared state and event queue.

## Configuration/Dependencies

- Requires `ABIModule.get_instance()` environment to be initialized, including:
  - `engine.services.model_registry` (for `New()`)
  - `engine.services.triple_store`
  - `engine.services.object_storage`
  - `configuration.workspace_id`, `configuration.storage_name`, `configuration.naas_api_key`

- Key internal dependencies:
  - `PowerPointIntegration(template_path=...)`
  - `StorageUtils(object_storage_service)`
  - `CreatePresentationFromTemplateWorkflow(...)`
  - LangGraph (`StateGraph`, `Command`, checkpointing)

## Usage

```python
from naas_abi_marketplace.applications.powerpoint.agents.PowerPointAgent import PowerPointAgent

agent = PowerPointAgent.New()
agent.build_graph()

# Execution of the compiled graph depends on the naas_abi_core Agent runtime.
# You must provide messages via the base Agent’s execution mechanism in your environment.
```

## Caveats

- The markdown-to-PPT pipeline requires the last AI draft to include:
  - a fenced ```markdown block
  - for each slide: `TemplateSlideUri: ppt:SlideN` (mandatory)
- `validate_presentation_draft` expects the model to reply with exactly `"true"` or `"false"` (any other output routes back to `call_model`).
- `convert_markdown_to_shapes` expects JSON-only output; failures in parsing/logical mapping can result in missing/empty shapes.
- Shapes with `shape_type` not in `[14, 17]` and empty text are omitted from the injected template structure.
