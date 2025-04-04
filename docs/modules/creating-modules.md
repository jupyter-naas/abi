# Creating a Module: Step-by-Step Guide

This guide walks you through the process of creating a new module in the ABI system from planning to deployment.

## What is a Module?

A module in ABI is a self-contained component that encapsulates related functionality. Modules are designed to be pluggable and can include:

- **Agents**: AI agents that provide specific capabilities
- **Workflows**: Sequences of operations for specific tasks
- **Pipelines**: Data processing flows
- **Ontologies**: Domain-specific or application-specific ontologies
- **Integrations**: Connectors to external services and APIs
- **Analytics**: Data analysis and insights
- **Apps**: User interfaces and applications

## Planning Your Module

Before creating a module, plan its structure and purpose:

- **Define the purpose**: What problem will your module solve?
- **Identify components**: Which components (agents, workflows, etc.) will you need?
- **Consider dependencies**: What external services or libraries will your module require?
- **Plan the interface**: How will users interact with your module?

## Creating the Module Structure

### Option A: Using the Makefile Command (Recommended)

```bash
make build-module
```

When prompted, enter your module name using `snake_case` format.

### Option B: Manual Creation

1. Create a directory for your module in the appropriate location:

```bash
mkdir -p src/custom/modules/your_module_name
```

2. Create the component directories:

```bash
cd src/custom/modules/your_module_name
mkdir -p agents workflows pipelines integrations apps tests analytics
```

3. Create an `__init__.py` file to make the directory a Python package:

```bash
touch __init__.py
```

## Implementing Module Components

### A. Integrations

Integrations connect ABI to external services:

1. Create a configuration class in `integrations/YourIntegration.py`:

```python
from dataclasses import dataclass
from abi.components.Integration import Integration, IntegrationConfiguration

@dataclass
class YourIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for YourIntegration.
    
    Attributes:
        api_key (str): API key for the service
        base_url (str): Base URL for API requests
    """
    api_key: str
    base_url: str = "https://api.example.com"

class YourIntegration(Integration):
    """Integration with YourService API."""
    
    def __init__(self, configuration: YourIntegrationConfiguration):
        self.__configuration = configuration
        
    def example_method(self, parameter: str) -> dict:
        """Example method description."""
        # Implementation using functional programming principles
        return self._make_request(f"/endpoint/{parameter}")
        
def as_tools(configuration: YourIntegrationConfiguration):
    """Convert YourIntegration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = YourIntegration(configuration)

    class ExampleToolSchema(BaseModel):
        parameter: str = Field(..., description="Description of parameter")

    return [
        StructuredTool(
            name="your_example_tool",
            description="Description of what this tool does",
            func=integration.example_method,
            args_schema=ExampleToolSchema
        )
    ]
```

### B. Pipelines

Pipelines transform data into semantic triples:

1. Create a pipeline in `pipelines/YourPipeline.py`:

```python
from dataclasses import dataclass
from typing import Dict, Any
from pydantic import Field
from abi.components.Pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from langchain_core.tools import StructuredTool

from ..integrations.YourIntegration import YourIntegration, YourIntegrationConfiguration

@dataclass
class YourPipelineConfiguration(PipelineConfiguration):
    """Configuration for YourPipeline."""
    integration: YourIntegration
    triple_store: Any  # ITripleStoreService
    triple_store_name: str = "your_store"

class YourPipelineParameters(PipelineParameters):
    """Parameters for YourPipeline execution."""
    query_params: Dict[str, str] = Field(..., description="Query parameters for the integration")

class YourPipeline(Pipeline):
    """Pipeline for transforming integration data into RDF triples."""
    
    def __init__(self, configuration: YourPipelineConfiguration):
        self.__configuration = configuration
        
    def run(self, parameters: YourPipelineParameters) -> Dict[str, Any]:
        """Run the pipeline to fetch and transform data.
        
        Steps:
        1. Fetch data from integration
        2. Transform to RDF triples
        3. Store in triple store
        """
        # Fetch data
        data = self.__configuration.integration.fetch_data(parameters.query_params)
        
        # Transform to RDF
        graph = self.__transform_to_rdf(data)
        
        # Store in triple store
        self.__configuration.triple_store.store_graph(
            graph, 
            self.__configuration.triple_store_name
        )
        
        return {"status": "success", "triples_count": len(graph)}
        
    def __transform_to_rdf(self, data: Dict[str, Any]) -> Graph:
        """Transform integration data to RDF triples."""
        # Implementation using functional approach
        graph = Graph()
        # Add namespace prefixes
        ABI = Namespace("http://ontology.naas.ai/abi/")
        graph.bind("abi", ABI)
        
        # Create triples from data
        # This is where you map your API data to your ontology
        entity_uri = URIRef(f"{ABI}entity/{data['id']}")
        graph.add((entity_uri, RDF.type, ABI.YourEntity))
        graph.add((entity_uri, ABI.hasAttribute, Literal(data['attribute'])))
        
        return graph
        
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline."""
        return [StructuredTool(
            name="your_pipeline",
            description="Executes the pipeline with the given parameters",
            func=lambda **kwargs: self.run(YourPipelineParameters(**kwargs)),
            args_schema=YourPipelineParameters
        )]
```

### C. Workflows

Workflows implement business logic:

1. Create a workflow in `workflows/YourWorkflow.py`:

```python
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from pydantic import Field
from abi.components.Workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from langchain_core.tools import StructuredTool
from fastapi import APIRouter

from ..integrations.YourIntegration import YourIntegration, YourIntegrationConfiguration
from ..pipelines.YourPipeline import YourPipeline, YourPipelineConfiguration

@dataclass
class YourWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for YourWorkflow."""
    integration_config: YourIntegrationConfiguration
    triple_store: Any  # ITripleStoreService
    triple_store_name: str = "your_store"

class YourWorkflowParameters(WorkflowParameters):
    """Parameters for YourWorkflow execution."""
    query: str = Field(..., description="Search query for the data")
    limit: Optional[int] = Field(10, description="Maximum number of results")

class YourWorkflow(Workflow):
    """Workflow that orchestrates the entire data processing pipeline."""
    
    def __init__(self, configuration: YourWorkflowConfiguration):
        self.__configuration = configuration
        self.__integration = YourIntegration(self.__configuration.integration_config)
        self.__pipeline = YourPipeline(YourPipelineConfiguration(
            integration=self.__integration,
            triple_store=self.__configuration.triple_store,
            triple_store_name=self.__configuration.triple_store_name
        ))

    def run(self, parameters: YourWorkflowParameters) -> Dict[str, Any]:
        """Execute the complete workflow.
        
        Steps:
        1. Get unstructured data from integration
        2. Send data to pipeline
        3. Execute SPARQL to retrieve and reformat data
        """
        # 1. Get unstructured data from integration
        query_params = {
            "query": parameters.query,
            "limit": str(parameters.limit)
        }
        
        # 2. Process data through pipeline
        pipeline_result = self.__pipeline.run(parameters=YourPipelineParameters(
            query_params=query_params
        ))
        
        # 3. Execute SPARQL to retrieve data in desired format
        sparql_query = f"""
            PREFIX abi: <http://ontology.naas.ai/abi/>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            
            SELECT ?entity ?attribute
            WHERE {{
                ?entity rdf:type abi:YourEntity ;
                        abi:hasAttribute ?attribute .
            }}
            LIMIT {parameters.limit}
        """
        
        query_result = self.__configuration.triple_store.query(
            store_name=self.__configuration.triple_store_name,
            query=sparql_query
        )
        
        # Transform SPARQL results back to original format
        formatted_results = [
            {
                "id": str(row.entity).split("/")[-1],
                "attribute": str(row.attribute)
            }
            for row in query_result
        ]
        
        return {
            "results": formatted_results,
            "count": len(formatted_results),
            "pipeline_status": pipeline_result["status"]
        }
        
    def as_tools(self) -> List[StructuredTool]:
        """Expose the workflow as a LangChain tool."""
        return [StructuredTool(
            name="search_your_data",
            description="Search for data in your system",
            func=lambda **kwargs: self.run(YourWorkflowParameters(**kwargs)),
            args_schema=YourWorkflowParameters
        )]
        
    def as_api(self, router: APIRouter) -> None:
        """Add API endpoints for this workflow."""
        @router.post("/search")
        def search_data(parameters: YourWorkflowParameters):
            return self.run(parameters)
```

### D. Agents

Agents provide LLM agent interfaces:

1. Create an assistant in `agents/YourAssistant.py`:

```python
from fastapi import APIRouter
from lib.abi.services.agent.Agent import Agent

# Define assistant metadata
NAME = "Your Assistant Name"
DESCRIPTION = "A detailed description of what your assistant does."
AVATAR_URL = "https://example.com/avatar.png"  # Optional

# Define system prompt
SYSTEM_PROMPT = """
You are a specialized assistant that helps with specific tasks.
Your main responsibilities are:
1. Task one
2. Task two
3. Task three

Follow these guidelines:
- Guideline one
- Guideline two
- Guideline three
"""

# Suggested user messages
SUGGESTIONS = [
    "How do I do task one?",
    "Help me with task two",
    "I need assistance with task three"
]

def create_agent() -> Agent:
    """Creates and returns a configured assistant agent."""
    # Import necessary components
    from ..workflows.YourWorkflow import YourWorkflow, YourWorkflowConfiguration
    from ..integrations.YourIntegration import YourIntegrationConfiguration
    
    # Initialize components with configurations
    integration_config = YourIntegrationConfiguration(
        api_key="dummy"  # Real key will be provided via environment/secrets
    )
    
    workflow = YourWorkflow(
        YourWorkflowConfiguration(integration_config=integration_config)
    )
    
    # Create agent with tools
    agent = Agent(
        name=NAME,
        system_prompt=SYSTEM_PROMPT,
        tools=workflow.as_tools()
    )
    
    return agent

class YourAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "your_assistant", 
        name: str = NAME, 
        description: str = "API endpoints to call your assistant completion.", 
        description_stream: str = "API endpoints to call your assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)
```

### E. Ontology (Optional)

Create an ontology file in `ontologies/YourOntology.ttl` to model your domain:

```ttl
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix dc11: <http://purl.org/dc/elements/1.1/> .
@prefix dc: <http://purl.org/dc/terms/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix cco: <https://www.commoncoreontologies.org/> .
@prefix abi: <http://ontology.naas.ai/abi/> .
@prefix your: <http://ontology.naas.ai/your_module/> .

<http://ontology.naas.ai/your_module/YourOntology> rdf:type owl:Ontology ;
    owl:imports <https://www.commoncoreontologies.org/CommonCoreOntology> ;
    dc11:contributor "Your Name" ;
    dc:description "Domain ontology for your domain."@en ;
    dc:title "Your Domain Ontology" .

#################################################################
#    Classes
#################################################################

your:YourEntity a owl:Class ;
    rdfs:label "Your Entity"@en ;
    rdfs:subClassOf bfo:BFO_0000001 ; # or appropriate BFO class
    skos:definition "Definition of your entity based on integration data" .

#################################################################
#    Object Properties
#################################################################

your:hasRelatedEntity a owl:ObjectProperty ;
    rdfs:label "has related entity"@en ;
    rdfs:domain your:YourEntity ;
    rdfs:range your:RelatedEntity .

#################################################################
#    Data Properties
#################################################################

your:hasAttribute a owl:DatatypeProperty ;
    rdfs:label "has attribute"@en ;
    rdfs:domain your:YourEntity ;
    rdfs:range xsd:string .
```

## Setting Up Triggers (Optional)

Create a `triggers.py` file at the root of your module to define ontology triggers:

```python
from abi.services.triple_store.TripleStorePorts import OntologyEvent
from rdflib import Namespace

# Define your namespace
ex = Namespace("http://example.org/")

# Define triggers list
triggers = [
    (
        (None, ex.hasStatus, ex.New),  # Triple pattern to match
        OntologyEvent.TRIPLE_ADDED,    # Event type
        lambda triple: print(f"New status detected: {triple}")  # Callback function
    )
]
```

## Testing Your Module

1. Create tests in the `tests` directory:

```python
# tests/test_integration.py
import unittest
from ..integrations.YourIntegration import YourIntegration, YourIntegrationConfiguration

class TestYourIntegration(unittest.TestCase):
    def setUp(self):
        self.integration = YourIntegration(
            YourIntegrationConfiguration(
                api_key="test_key"
            )
        )
    
    def test_example_method(self):
        # Implement test using functional programming principles
        result = self.integration.example_method("test")
        self.assertIsInstance(result, dict)
```

2. Run the tests:

```bash
make test
```

## Publishing Your Module

### For Personal Use

Your module is automatically loaded when placed in:
- `src/core/modules/` for core functionality
- `src/custom/modules/` for custom extensions

### For Marketplace

To share your module through the marketplace:

1. Package your module by copying it to the marketplace directory:

```bash
mkdir -p src/marketplace/your_module_name
cp -r src/custom/modules/your_module_name/* src/marketplace/your_module_name/
```

2. Add a comprehensive README.md file in your module directory explaining:
   - Purpose and features
   - Installation instructions
   - Usage examples
   - Configuration requirements
   - Dependencies

## Best Practices

1. **Follow functional programming principles**
   - Use pure functions when possible
   - Minimize side effects
   - Use immutable data structures
   - Leverage higher-order functions

2. **Keep components focused**
   - Each component should have a single responsibility
   - Use composition over inheritance

3. **Document thoroughly**
   - Add docstrings to all classes and functions
   - Include examples and parameter descriptions

4. **Handle errors gracefully**
   - Use appropriate exception types
   - Provide helpful error messages

5. **Use descriptive naming**
   - Use snake_case for your module name and Python components
   - Make names clear and descriptive

6. **Maintain separation of concerns**
   - Keep integrations separate from business logic
   - Workflows should orchestrate, not implement details

7. **Test comprehensively**
   - Unit tests for each component
   - Integration tests for workflows

## Disabling/Enabling Modules

To disable a module without removing it:

```bash
# Disable
mv src/custom/modules/your_module_name src/custom/modules/your_module_name_disabled

# Enable
mv src/custom/modules/your_module_name_disabled src/custom/modules/your_module_name
```

## Getting Help

For questions or support, reach out via:
- [ABI Documentation](docs/)
- [Community Forum](https://join.slack.com/t/naas-club/shared_invite/zt-2xmz8c3j8-OH3UAqvwsYkTR3BLRHGXeQ)
- [Support Email](mailto:support@naas.ai)