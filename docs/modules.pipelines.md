# Pipelines

## Overview

Pipelines in ABI are specialized components designed to ingest data from external sources, transform it into semantic triples, and populate the knowledge graph (ontology). They serve as the critical bridge between raw data from various sources and the unified semantic representation in the ABI system.

Pipelines are part of ABI's layered architecture, sitting between integrations (which handle communication with external services) and workflows (which orchestrate business logic):

```
┌─────────────────┐
│    Workflows    │ ← Business logic layer
├─────────────────┤
│    Pipelines    │ ← Data transformation layer
├─────────────────┤
│  Integrations   │ ← External service communication layer
└─────────────────┘
```

## Purpose and Benefits

Pipelines serve several key purposes in the ABI ecosystem:

1. **Data Ingestion**: They fetch raw data from external sources through integrations.

2. **Semantic Transformation**: They convert raw data into semantic triples that conform to the ontology.

3. **Knowledge Graph Population**: They store the transformed data in the ontology store, building a unified semantic layer.

4. **Technology Abstraction**: They abstract away the specifics of data sources, allowing the system to treat data uniformly regardless of origin.

5. **Unified Representation**: They enable data from disparate sources (GitHub, GitLab, LinkedIn, databases, etc.) to be represented in a single, consistent semantic model.

## How Pipelines Work

A pipeline typically follows this process flow:

1. **Configuration**: The pipeline is initialized with configuration parameters that specify how it should operate.

2. **Data Retrieval**: The pipeline uses one or more integrations to fetch raw data from external sources.

3. **Transformation**: The pipeline transforms the raw data into semantic triples that conform to the ontology.

4. **Storage**: The pipeline stores the transformed data in the ontology store.

5. **Return**: The pipeline returns the graph of triples it has created.

### Key Characteristics

- **Technology Agnostic**: Pipelines should not implement direct communication with external services; they should use integrations for this purpose.

- **Semantic Focus**: Pipelines focus on transforming data into the correct semantic representation.

- **Independence**: Pipelines should not call or trigger workflows (though workflows will often trigger pipelines).

- **Reusability**: A well-designed pipeline can be used by multiple workflows.

## Pipeline Architecture

Pipelines in ABI implement the `Pipeline` abstract class, which extends the `Expose` interface. This design allows pipelines to be exposed as both tools for LLM agents and as API endpoints.

### Key Components

1. **PipelineConfiguration**: A dataclass that holds configuration parameters for the pipeline.

2. **PipelineParameters**: A Pydantic model that defines the runtime parameters for pipeline execution.

3. **Pipeline Class**: The main class that implements the pipeline logic, including the `run()` method that executes the pipeline.

### The Expose Interface

Pipelines implement the `Expose` interface, which provides two key methods:

1. **`as_tools()`**: Returns a list of LangChain StructuredTools that can be used by an LLM agent.
2. **`as_api()`**: Registers API routes for the pipeline's functionality on a FastAPI router.

This design allows pipelines to be easily exposed as both tools for LLM agents and as API endpoints.

## Use Cases

### Unified Data Representation

One of the primary use cases for pipelines is to create a unified semantic representation of data from multiple sources. For example:

- A **GitHub pipeline** ingests repositories, issues, pull requests, and contributors
- A **GitLab pipeline** ingests similar data from GitLab
- A **Bitbucket pipeline** ingests similar data from Bitbucket

All three pipelines transform their respective data into the same ontological representation, allowing the system to treat issues, repositories, and contributors uniformly regardless of their source.

### Data Enrichment

Pipelines can also be used to enrich existing data in the ontology. For example:

- A **LinkedIn pipeline** might add professional information about contributors identified in the GitHub pipeline
- A **JIRA pipeline** might add additional task and project management information related to issues

### Real-time Data Processing

Pipelines can be triggered by events to process data in real-time:

- A webhook from GitHub could trigger a pipeline to update the ontology when a new issue is created
- A scheduled job could trigger a pipeline to refresh data from a source at regular intervals

## Creating a New Pipeline

To create a new pipeline in ABI, follow these steps:

1. Create a new file in `src/custom/modules/<module_name>/pipelines/YourPipelineName.py` using the template below
2. Implement the necessary methods to transform data from the integration into semantic triples
3. Add configuration parameters as needed
4. Implement the `as_tools()` and `as_api()` methods to expose the pipeline

### Pipeline Template

```python
from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from src.data.integrations import YourIntegration
from abi.utils.Graph import ABIGraph
from rdflib import Graph
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from src import secret
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class YourPipelineConfiguration(PipelineConfiguration):
    """Configuration for YourPipeline.
    
    Attributes:
        integration (YourIntegration): The integration instance to use
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use. Defaults to "yourstorename"
    """
    integration: YourIntegration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "yourstorename"

class YourPipelineParameters(PipelineParameters):
    """Parameters for YourPipeline execution.
    
    Attributes:
        parameter_1 (str): Description of parameter_1
        parameter_2 (int): Description of parameter_2
    """
    parameter_1: str
    parameter_2: int

class YourPipeline(Pipeline):
    __configuration: YourPipelineConfiguration
    
    def __init__(self, configuration: YourPipelineConfiguration):
        self.__configuration = configuration
        
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline.
        
        Returns:
            list[StructuredTool]: List containing the pipeline tool
        """
        return [StructuredTool(
            name="your_pipeline",
            description="Executes the pipeline with the given parameters",
            func=lambda **kwargs: self.run(YourPipelineParameters(**kwargs)),
            args_schema=YourPipelineParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this pipeline to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/YourPipeline")
        def run(parameters: YourPipelineParameters):
            return self.run(parameters).serialize(format="turtle")

    def run(self, parameters: YourPipelineParameters) -> Graph:        
        graph = ABIGraph()
        
        # Use the integration to fetch data
        raw_data = self.__configuration.integration.fetch_data(parameters.parameter_1, parameters.parameter_2)
        
        # Transform the raw data into semantic triples
        for item in raw_data:
            # Example: Create a node for each item
            subject = f"http://example.org/resource/{item['id']}"
            
            # Add properties to the node
            graph.add((subject, "http://example.org/property/name", item['name']))
            graph.add((subject, "http://example.org/property/description", item['description']))
            
            # Add relationships to other nodes
            for related_item in item['related_items']:
                related_subject = f"http://example.org/resource/{related_item['id']}"
                graph.add((subject, "http://example.org/property/relatedTo", related_subject))
        
        # Store the graph in the ontology store
        self.__configuration.ontology_store.insert(self.__configuration.ontology_store_name, graph)
        
        return graph
```

## Pipeline Implementation Guidelines

When implementing a pipeline, follow these guidelines:

1. **Use Integrations for External Communication**: Never implement direct communication with external services in a pipeline. Always use integrations for this purpose.

2. **Focus on Semantic Transformation**: The primary responsibility of a pipeline is to transform raw data into semantic triples that conform to the ontology.

3. **Maintain Independence**: Pipelines should not call or trigger workflows. Workflows will call pipelines as needed.

4. **Handle Errors Gracefully**: Implement proper error handling to ensure that the pipeline can recover from failures.

5. **Document Thoroughly**: Document the pipeline's purpose, configuration parameters, and runtime parameters thoroughly.

6. **Test Comprehensively**: Create tests to verify that the pipeline correctly transforms data and handles edge cases.

## Best Practices

When creating pipelines, follow these best practices:

1. **Single Responsibility**: A pipeline should focus on transforming data from a specific source or set of related sources.

2. **Reusability**: Design pipelines to be reusable by multiple workflows.

3. **Configuration Management**: Use the configuration class to manage dependencies and settings.

4. **Parameter Validation**: Validate runtime parameters to ensure they are valid before processing data.

5. **Efficient Transformation**: Optimize the transformation process to handle large datasets efficiently.

6. **Incremental Processing**: Where possible, design pipelines to process data incrementally rather than in bulk.

7. **Idempotence**: Ensure that running the same pipeline with the same parameters multiple times produces the same result.

## Conclusion

Pipelines are a critical component of ABI's architecture, serving as the bridge between raw data from external sources and the unified semantic representation in the ontology. By following the guidelines and best practices outlined in this document, you can create effective pipelines that enable ABI to build a rich semantic layer on top of various data sources.
