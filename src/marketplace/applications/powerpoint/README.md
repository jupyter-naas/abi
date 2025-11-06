# PowerPoint Module

## Overview

### Description

The PowerPoint Module provides comprehensive integration for creating, modifying, and managing PowerPoint presentations programmatically. This module enables AI agents to generate structured presentations from user briefs, using template-based slide structures and semantic knowledge graph storage.

This module enables:
- **Template-Based Presentation Creation**: Generate presentations from structured templates with slide duplication and content population
- **Interactive Presentation Building**: Conversational agent that guides users through presentation creation with validation
- **Knowledge Graph Integration**: Store presentations, slides, and shapes in semantic triple store for search and retrieval
- **Content Management**: Update slides, shapes, text, images, tables, and notes with source citations
- **Presentation Analysis**: Extract structure, shapes, and content from existing presentations
- **Cloud Storage Integration**: Upload presentations to Naas storage with public download URLs

### Requirements

**Python Libraries:**
- `python-pptx`: PowerPoint file manipulation
- `rdflib`: RDF graph operations for ontology storage
- `langchain_core`: AI agent framework integration

**Optional:**
- `NAAS_API_KEY`: For cloud storage and asset management (optional, for production)

### TL;DR

To get started with the PowerPoint module:

1. Ensure `python-pptx` is installed
2. (Optional) Configure `NAAS_API_KEY` for cloud storage
3. Start chatting with the PowerPoint agent:
```bash
make chat agent=PowerPointAgent
```

## Structure

```
src/marketplace/applications/powerpoint/

├── agents/                         
│   ├── PowerPointAgent_test.py               
│   └── PowerPointAgent.py          # Conversational presentation creation agent
├── integrations/                    
│   ├── PowerPointIntegration_test.py          
│   └── PowerPointIntegration.py    # Core PowerPoint file operations
├── pipelines/                     
│   ├── AddPowerPointPresentationPipeline_test.py          
│   └── AddPowerPointPresentationPipeline.py  # Knowledge graph integration
├── workflows/   
│   ├── CreatePresentationFromTemplateWorkflow_test.py      
│   └── CreatePresentationFromTemplateWorkflow.py  # End-to-end presentation creation
├── models/                         
│   └── default.py                  # Model configuration (airgap/cloud support)
├── ontologies/                     
│   ├── PowerPointOntology.ttl      # Presentation, Slide, Shape ontology
│   └── PowerPointSparqlQueries.ttl # SPARQL query templates
├── templates/
│   └── TemplateNaasPPT.pptx        # Default presentation template
├── sandbox/                        # Development and experimentation
│   ├── add_template_presentation.py
│   ├── duplicate_slides.py
│   └── ...
├── __init__.py                     # Module initialization
└── README.md                       # This documentation
```

## Core Components

### Agents

#### PowerPoint Agent
A conversational agent specialized in creating PowerPoint presentations from user briefs using template structures.

**Capabilities:**
- Analyzes user briefs to extract presentation requirements (number of slides, audience, objectives)
- Generates structured slide outlines based on template structure
- Creates detailed slide content with source citations
- Validates content with users through interactive conversation
- Generates final presentations from validated content
- Searches knowledge graph for existing presentations

**Key Features:**
- Template-based slide structure generation
- Interactive validation workflow
- Source citation management
- Markdown to JSON conversion for slide data
- JSON to PowerPoint conversion via workflow

**Usage:**
```bash
make chat agent=PowerPointAgent
```

**System Prompt Highlights:**
- Never invents facts; structures and adapts content from briefs
- Honors template structure as a guide
- Always cites data sources with URLs
- Validates with users before final generation

**Testing:**
```bash
uv run python -m pytest src/marketplace/applications/powerpoint/agents/PowerPointAgent_test.py
```

### Integrations

#### PowerPoint Integration
Core integration class providing comprehensive PowerPoint file manipulation capabilities.

**Key Methods:**
- `create_presentation()`: Create new presentations from templates
- `save_presentation()`: Save presentations to file system
- `list_slides()`: Extract slide structure and metadata
- `get_shapes_from_slide()`: Get all shapes from a specific slide
- `get_all_shapes_and_slides()`: Extract complete presentation structure
- `duplicate_slide()`: Copy slides from template to presentation
- `update_shape()`: Update text content in shapes
- `update_notes()`: Add source citations to slide notes
- `add_slide()`: Add new slides to presentations
- `add_shape()`: Add shapes to slides
- `add_text_box()`: Add text boxes with formatting
- `add_image()`: Add images to slides
- `add_table()`: Add tables to slides
- `replace_table()`: Replace table content
- `remove_all_slides()`: Clear all slides from presentation
- `set_slide_format()`: Configure slide dimensions and layout

**Configuration:**

```python
from src.marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegration,
    PowerPointIntegrationConfiguration
)

# Create configuration
config = PowerPointIntegrationConfiguration(
    template_path="path/to/template.pptx"
)

# Initialize integration
integration = PowerPointIntegration(config)
```

**Example Usage:**
```python
# Create presentation from template
presentation = integration.create_presentation("template.pptx")

# Get slide structure
slides = integration.list_slides(presentation, text=True)

# Update shape text
presentation = integration.update_shape(
    presentation, 
    slide_number=0, 
    shape_id=1, 
    text="New Title"
)

# Save presentation
integration.save_presentation(presentation, "output.pptx")
```

**Testing:**
```bash
uv run python -m pytest src/marketplace/applications/powerpoint/integrations/PowerPointIntegration_test.py
```

### Pipelines

#### Add PowerPoint Presentation Pipeline
Pipeline that extracts presentation metadata and structure, then stores it in the knowledge graph as semantic triples.

**Key Features:**
- Extracts presentation core properties (author, dates, metadata)
- Creates unique identifiers from presentation signatures
- Stores presentations, slides, and shapes as RDF triples
- Links presentations to templates
- Prevents duplicate storage using hash-based identification

**Data Model:**
- **Presentation**: Top-level entity with metadata (name, author, dates, storage path, download URL)
- **Slide**: Individual slides with slide numbers
- **Shape**: Shapes within slides (text, position, size, rotation, alt text)

**Ontology Namespace:** `http://ontology.naas.ai/abi/powerpoint/`

**Testing:**
```bash
uv run python -m pytest src/marketplace/applications/powerpoint/pipelines/AddPowerPointPresentationPipeline_test.py
```

### Workflows

#### Create Presentation From Template Workflow
End-to-end workflow that orchestrates presentation creation from JSON slide data.

**Process:**
1. Creates presentation from template
2. Clears existing slides
3. Duplicates template slides based on slide data
4. Updates shapes with content from JSON
5. Adds source citations to slide notes
6. Saves presentation to storage
7. Uploads to Naas cloud storage (optional)
8. Stores in knowledge graph via pipeline

**Input Parameters:**
- `presentation_name`: Name of the presentation (without .pptx)
- `slides_data`: List of slide dictionaries containing:
  - `slide_number`: Index of the slide
  - `template_slide_number`: Template slide to duplicate
  - `shapes`: List of shape dictionaries with `shape_id` and `text`
  - `sources`: List of source URLs
- `template_path`: Path to PowerPoint template file

**Output:**
- `presentation_name`: Generated presentation filename
- `storage_path`: Local storage path
- `download_url`: Public download URL (if Naas configured)
- `presentation_uri`: Knowledge graph URI
- `template_uri`: Template URI in knowledge graph

**Testing:**
```bash
uv run python -m pytest src/marketplace/applications/powerpoint/workflows/CreatePresentationFromTemplateWorkflow_test.py
```

### Models

#### Default Model
Model configuration that supports both airgap and cloud deployments.

**Configuration:**
- **Cloud Mode**: Uses `gpt-4.1` from ChatGPT module
- **Airgap Mode**: Uses `airgap_qwen` from ABI module

**Source:** `src/marketplace/applications/powerpoint/models/default.py`

### Ontologies

#### PowerPoint Ontology
Turtle file (`PowerPointOntology.ttl`) defining the semantic data model for presentations.

**Classes:**
- `ppt:Presentation`: Digital slide deck entity
- `ppt:Slide`: Individual slide component
- `ppt:Shape`: Graphical element within slides

**Properties:**
- `ppt:hasSlide` / `ppt:isSlideOf`: Presentation-Slide relationships
- `ppt:hasShape` / `ppt:isShapeOf`: Slide-Shape relationships
- `ppt:hasTemplate` / `ppt:isTemplateOf`: Presentation-Template relationships
- Data properties for metadata (author, dates, storage paths, URLs, positions, sizes)

**Namespace:** `http://ontology.naas.ai/abi/powerpoint/`

#### PowerPoint SPARQL Queries
Turtle file (`PowerPointSparqlQueries.ttl`) containing reusable SPARQL query templates for:
- Searching presentations by name
- Retrieving slides by URI
- Retrieving shapes by URI
- Extracting all text content from presentations

## Usage Examples

### Basic Presentation Creation

```python
from src.marketplace.applications.powerpoint.agents.PowerPointAgent import create_agent

# Create agent
agent = create_agent()

# Start conversation
response = agent.invoke("Create a 5-slide presentation about AI trends for a business audience")
```

### Using Integration Directly

```python
from src.marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegration,
    PowerPointIntegrationConfiguration
)

# Initialize integration
config = PowerPointIntegrationConfiguration(
    template_path="template.pptx"
)
integration = PowerPointIntegration(config)

# Create and modify presentation
presentation = integration.create_presentation()
integration.add_slide(presentation, layout_index=0)
integration.update_shape(presentation, slide_number=0, shape_id=1, text="Title")
integration.save_presentation(presentation, "output.pptx")
```

### Using Workflow

```python
from src.marketplace.applications.powerpoint.workflows.CreatePresentationFromTemplateWorkflow import (
    CreatePresentationFromTemplateWorkflow,
    CreatePresentationFromTemplateWorkflowConfiguration,
    CreatePresentationFromTemplateWorkflowParameters
)

# Configure workflow
config = CreatePresentationFromTemplateWorkflowConfiguration(...)
workflow = CreatePresentationFromTemplateWorkflow(config)

# Create presentation from JSON
result = workflow.create_presentation(
    CreatePresentationFromTemplateWorkflowParameters(
        presentation_name="MyPresentation",
        slides_data=[
            {
                "slide_number": 0,
                "template_slide_number": 0,
                "shapes": [{"shape_id": 1, "text": "Title"}],
                "sources": ["https://example.com"]
            }
        ],
        template_path="template.pptx"
    )
)
```

## Agent Workflow

The PowerPoint agent follows a structured conversation flow:

1. **Brief Analysis**: Extracts requirements (number of slides, audience, objectives)
2. **Template Structure Injection**: Loads template slide structure
3. **Slide Outline Generation**: Creates structured slide outline
4. **Content Generation**: Populates slides with detailed content and sources
5. **User Validation**: Interactive validation and refinement
6. **Final Generation**: Converts validated content to PowerPoint presentation
7. **Knowledge Graph Storage**: Stores presentation metadata for future retrieval

## Dependencies

### Python Libraries
- `python-pptx`: PowerPoint file manipulation and creation
- `rdflib`: RDF graph operations for semantic storage
- `langchain_core`: AI agent framework integration
- `pydantic`: Data validation and serialization
- `fastapi`: API router for agent endpoints (optional)

### Modules

- `src.core.abi.models.airgap_qwen`: Airgap model for local deployments
- `src.core.chatgpt.models.gpt_4_1`: Cloud model for cloud deployments
- `src.core.templatablesparqlquery`: SPARQL query tools for knowledge graph operations
- `src.marketplace.applications.naas.integrations.NaasIntegration`: Cloud storage integration (optional)
- `abi.services.agent.Agent`: Base agent framework
- `abi.pipeline`: Pipeline framework
- `abi.workflow`: Workflow framework

## Configuration

### Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `AI_MODE` | `cloud` \| `airgap` | `cloud` | Model deployment mode |
| `OPENAI_API_KEY` | API key | Required (cloud) | For cloud models |
| `NAAS_API_KEY` | API key | Optional | For cloud storage and asset management |

### Model Selection

The agent automatically selects models based on `AI_MODE`:

```python
# Cloud Mode (default)
AI_MODE=cloud  # Uses gpt-4.1

# Airgap Mode
AI_MODE=airgap  # Uses qwen3 via Docker Model Runner
```

## Template Structure

The module uses PowerPoint templates with structured slide layouts. Each template slide should have:
- **Shape Alt Text**: Descriptive text indicating the purpose of each shape (e.g., "Title", "Subtitle", "Content")
- **Consistent Layout**: Standardized slide layouts for predictable content placement
- **Shape IDs**: Unique identifiers for each shape to enable programmatic updates

**Default Template:** `src/marketplace/applications/powerpoint/templates/TemplateNaasPPT.pptx`

## Knowledge Graph Integration

Presentations are stored in the knowledge graph with:
- **Unique Identification**: Hash-based signatures prevent duplicates
- **Full Metadata**: Author, creation/modification dates, storage paths
- **Hierarchical Structure**: Presentation → Slides → Shapes relationships
- **Template Linking**: Connections between presentations and their source templates
- **Search Capabilities**: SPARQL queries for finding presentations, slides, and content

## Testing

### Run All Tests

```bash
# Run all PowerPoint module tests
pytest src/marketplace/applications/powerpoint/ -v

# Specific component tests
pytest src/marketplace/applications/powerpoint/agents/PowerPointAgent_test.py -v
pytest src/marketplace/applications/powerpoint/integrations/PowerPointIntegration_test.py -v
pytest src/marketplace/applications/powerpoint/pipelines/AddPowerPointPresentationPipeline_test.py -v
pytest src/marketplace/applications/powerpoint/workflows/CreatePresentationFromTemplateWorkflow_test.py -v
```

## Development

### Sandbox

The `sandbox/` directory contains experimental code and utilities:
- `add_template_presentation.py`: Template management utilities
- `duplicate_slides.py`: Slide duplication experiments
- Various agent and integration development versions

### Extension Points

**New Template Support:**
1. Add template file to `templates/` directory
2. Update agent default template path
3. Ensure template has proper shape alt text

**Custom Workflows:**
- Extend `CreatePresentationFromTemplateWorkflow` base class
- Add new workflow methods for specialized presentation types
- Register workflows in agent initialization

**Additional Integrations:**
- Extend `PowerPointIntegration` with new methods
- Add LangChain tool wrappers via `as_tools()`
- Integrate with additional storage backends

---

*AI-powered PowerPoint presentation creation with template-based structure and semantic knowledge graph storage*

