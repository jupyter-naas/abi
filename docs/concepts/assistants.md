# Assistants

This document explains the concept of Assistants in the ABI framework, their purpose, capabilities, and how they integrate with the broader system.

## What are Assistants?

Assistants in ABI are AI-powered interfaces that enable natural language interaction with the system. They serve as the primary touchpoint for users, allowing them to interact with complex business data and processes using conversational language instead of technical commands.

## Key Features

- **Natural Language Understanding**: Process and understand user queries in natural language
- **Context Awareness**: Maintain conversation context across multiple interactions
- **Tool Integration**: Access and execute workflows, integrations, and pipelines
- **Knowledge Graph Access**: Query the ontology store for relevant information
- **Multi-turn Conversations**: Support for complex, multi-step conversations
- **Personalization**: Adapt responses based on user preferences and history

## Assistant Architecture

```
┌───────────────────────────────────────────────────────────┐
│                      Assistant                            │
│                                                           │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────┐  │
│  │  Language     │    │  Reasoning    │    │  Tool     │  │
│  │  Understanding│───►│  Engine       │───►│  Executor │  │
│  │               │    │               │    │           │  │
│  └───────────────┘    └───────────────┘    └───────────┘  │
│          ▲                    │                  │        │
│          │                    ▼                  ▼        │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────┐  │
│  │  User         │    │  Knowledge    │    │  Workflow │  │
│  │  Interface    │    │  Base         │    │  Runner   │  │
│  │               │    │               │    │           │  │
│  └───────────────┘    └───────────────┘    └───────────┘  │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## Types of Assistants

ABI supports multiple types of assistants, each tailored for specific use cases:

### Data Analyst Assistant

Specializes in data analysis and visualization tasks. Can query databases, generate reports, and create visualizations from data.

### Business Process Assistant

Focuses on executing and monitoring business workflows. Can initiate, track, and manage business processes.

### Research Assistant

Designed for information retrieval and synthesis. Can search through knowledge bases, summarize information, and answer complex questions.

### Domain-Specific Assistants

Customized for specific industry domains with specialized knowledge and capabilities relevant to that domain.

## Assistant Components

### Prompt Templates

Pre-defined templates that structure the assistant's understanding of tasks and guide its responses.

### Tools Registry

A collection of tools (functions) that the assistant can use to perform specific actions, such as querying data or executing workflows.

### Memory System

Stores conversation history and context to maintain coherent multi-turn conversations.

### Response Formatter

Ensures responses are formatted appropriately for the user interface, handling text, tables, visualizations, and other output types.

## Customizing Assistants

Assistants can be customized through:

- **Prompt Engineering**: Modifying prompt templates to guide assistant behavior
- **Tool Registration**: Adding custom tools to extend capabilities
- **Knowledge Integration**: Connecting to domain-specific knowledge sources
- **Response Templates**: Creating custom output formats

## Creating an Assistant

A simple example of creating an assistant:

```python
from abi.assistant import Assistant, AssistantConfiguration
from abi.tools import ToolRegistry

# Configure the assistant
config = AssistantConfiguration(
    name="Sales Analyst",
    description="Assistant for analyzing sales data",
    model="gpt-4",
    temperature=0.3
)

# Create a tool registry
tools = ToolRegistry()
tools.register(sales_query_tool)
tools.register(generate_sales_report)
tools.register(visualization_tool)

# Initialize the assistant
assistant = Assistant(config, tools)

# Use the assistant
response = assistant.process_message(
    "Show me sales trends for Q2 compared to last year"
)
```

## Integrating Assistants with Workflows

Assistants can trigger workflows based on user requests:

```python
# Assistant initiating a workflow
@assistant.tool("create_sales_report")
def create_sales_report(region: str, period: str):
    # Create the workflow configuration
    workflow_config = SalesReportWorkflowConfiguration(
        region=region,
        period=period
    )
    
    # Initialize and run the workflow
    workflow = SalesReportWorkflow(workflow_config)
    return workflow.run(SalesReportWorkflowParameters())
```

## Next Steps

- Learn how to [Create Assistants](../guides/creating-assistants.md)
- Understand [Workflows](workflows.md) that assistants can execute
- Explore the [Ontology](ontology.md) that assistants can query 