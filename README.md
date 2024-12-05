# ABI

**An API-driven organizational AI system backend offering assistants, ontology, integrations, workflows, and analytics in a unified framework.**

<img src="./assets/images/abi-flywheel.png" width="100%" height="100%">

## Overview

The **ABI** (Augmented Business Intelligence) project is a Python-based backend framework designed to serve as the core infrastructure for building an Organizational AI System. This system empowers businesses to integrate, manage, and scale AI-driven operations with a focus on ontology, assistant-driven workflows, and analytics. Designed for flexibility and scalability, ABI provides a customizable framework suitable for organizations aiming to create intelligent, automated systems tailored to their needs.

### Key Features

- **Assistants**: Configurable AI assistants to handle specific organizational tasks and interact with users.
- **Ontology Management**: Define and manage data relationships, structures, and semantic elements.
- **Integrations**: Seamlessly connect to external data sources and APIs for unified data access.
- **Pipelines**: Define data processing pipelines to handle and transform data efficiently into the ontological layer.
- **Workflows**: Automate complex business processes and manage end-to-end workflows.
- **Analytics**: Access insights through integrated analytics and real-time data processing.
- **Data**: Handle diverse datasets and manage schema, versioning, deduplication, and change data capture.

### License
ABI Framework is open-source and available for non-production use under the [AGPL license](https://opensource.org/licenses/AGPL). For production deployments, a commercial license is required. Please contact us at support@naas.ai for details on licensing options.

## Sneak peek 👀

![ABI Terminal](https://naasai-public.s3.eu-west-3.amazonaws.com/abi2.gif)

## Setup Project

### Getting Started

1. **Prerequisites**
   - Docker Desktop 

2. **Get the Repository**
   
   Choose one of the following options:

   a. **Clone the Repository** (for personal use)
   ```bash
   git clone https://github.com/jupyter-naas/abi-framework.git
   cd abi-framework
   ```

   b. **Fork the Repository** (to contribute changes)
   ```bash
   # 1. Fork via GitHub UI
   # 2. Clone your fork
   git clone https://github.com/YOUR-USERNAME/abi-framework.git
   cd abi-framework
   ```

   c. **Create a Private Fork** (for private development)
   ```bash
   # 1. Create private repository via GitHub UI
   # 2. Clone your private repository
   git clone https://github.com/YOUR-USERNAME/abi-framework-private.git
   cd abi-framework-private
   git remote add upstream https://github.com/jupyter-naas/abi-framework.git
   git pull --rebase upstream main
   git push
   ```

3. **Set Up Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Create Docker Container & Start Chatting**
   ```bash
   make chat
   ```


### Managing Dependencies

#### Add a new Python dependency to `src` project

```bash
make add dep=<library-name>
```

This will automatically:
- Add the dependency to your `pyproject.toml`
- Update the `poetry.lock` file
- Install the package in your virtual environment

#### Add a new Python dependency to `lib/abi` project

```bash
make abi-add dep=<library-name>
```

## Creating a new Integration

To create a new integration, follow these steps:

1. **Create Integration File**
   Create a new file in `src/integrations/YourIntegration.py` with the following structure:

   ```python
   from lib.abi.integration.integration import Integration, IntegrationConfiguration
   from dataclasses import dataclass

   @dataclass
   class YourIntegrationConfiguration(IntegrationConfiguration):
       """Configuration for YourIntegration.
       
       Attributes:
           attribute_1 (str): Description of attribute_1
           attribute_2 (int): Description of attribute_2
       """
       attribute_1: str
       attribute_2: int

   class YourIntegration(Integration):
       """YourIntegration class for interacting with YourService.
       
       This class provides methods to interact with YourService's API endpoints.
       It handles authentication and request management.
       
       Attributes:
           __configuration (YourIntegrationConfiguration): Configuration instance
               containing necessary credentials and settings.
       
       Example:
           >>> config = YourIntegrationConfiguration(
           ...     attribute_1="value1",
           ...     attribute_2=42
           ... )
           >>> integration = YourIntegration(config)
       """

       __configuration: YourIntegrationConfiguration

       def __init__(self, configuration: YourIntegrationConfiguration):
           super().__init__(configuration)
           self.__configuration = configuration
   ```

2. **Add Required Methods**
   Implement the necessary methods for your integration. Common patterns include:
   - Authentication methods
   - API endpoint wrappers
   - Data transformation utilities

3. **Add Configuration**
   If your integration requires API keys or other configuration:
   - Add the required variables to `.env.example`
   - Update your local `.env` file with actual values

4. **Test Integration**
   Create tests in `tests/integrations/` to verify your integration works as expected.

For more detailed examples, check the existing integrations in the `src/integrations/` directory.

## Creating a new Pipeline

Pipelines in ABI are used to process and transform data. Here's how to create a new pipeline:

1. **Create Pipeline File**
   Create a new file in `src/data/pipelines/` with your pipeline name. Use this template:

   ```python
   from abi.pipeline import Pipeline, PipelineConfiguration
   from dataclasses import dataclass
   from src.data.integrations import YourIntegration
   from abi.utils.Graph import ABIGraph
   from rdflib import Graph
   from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService

   @dataclass
   class YourPipelineConfiguration(PipelineConfiguration):
       """Configuration for YourPipeline.
       
       Attributes:
           attribute_1 (str): Description of attribute_1
           attribute_2 (int): Description of attribute_2
           ontology_store_name (str): Name of the ontology store to use
       """
       attribute_1: str
       attribute_2: int
       ontology_store_name: str = "yourstorename"

   class YourPipeline(Pipeline):
       def __init__(self, integration: YourIntegration, ontology_store: IOntologyStoreService, configuration: YourPipelineConfiguration):
           super().__init__([integration], configuration)
           
           self.__integration = integration
           self.__configuration = configuration
           self.__ontology_store = ontology_store
           
       def run(self) -> Graph:        
           graph = ABIGraph()
           
           # Add your pipeline logic here
           
           return graph

   def as_tools(ontology_store: IOntologyStoreService):
       from langchain_core.tools import StructuredTool
       from pydantic import BaseModel, Field
       
       class YourPipelineSchema(BaseModel):
           attribute_1: str = Field(..., description="Description of attribute_1")
           attribute_2: int = Field(..., description="Description of attribute_2")
           ontology_store_name: str = Field(default="yourstorename", description="Name of the ontology store to use")
       
       def run_pipeline(attribute_1: str, attribute_2: int, ontology_store_name: str = "yourstorename") -> Graph:
           configuration = YourPipelineConfiguration(
               attribute_1=attribute_1,
               attribute_2=attribute_2,
               ontology_store_name=ontology_store_name
           )
           integration = YourIntegration(YourIntegrationConfiguration(attribute_1=attribute_1, attribute_2=attribute_2))
           pipeline = YourPipeline(integration, ontology_store, configuration)
           return pipeline.run()
       
       return [
           StructuredTool(
               name="your_pipeline_tool",
               description="Run the pipeline to process and transform data",
               func=run_pipeline,
               args_schema=YourPipelineSchema
           )
       ]

   def api():
       import fastapi
       import uvicorn
       from rdflib import Graph
       
       app = fastapi.FastAPI()
       
       @app.post("/pipeline")
       def run_pipeline_endpoint(
           attribute_1: str,
           attribute_2: int,
           ontology_store_name: str = "yourstorename"
       ) -> Graph:
           configuration = YourPipelineConfiguration(
               attribute_1=attribute_1,
               attribute_2=attribute_2,
               ontology_store_name=ontology_store_name
           )
           integration = YourIntegration(YourIntegrationConfiguration(attribute_1=attribute_1, attribute_2=attribute_2))
           pipeline = YourPipeline(integration, ontology_store, configuration)
           return pipeline.run()
       
       uvicorn.run(app, host="0.0.0.0", port=9876)

   def cli():
       import click
       
       @click.command()
       @click.option('--attribute-1', required=True, help='Description of attribute_1')
       @click.option('--attribute-2', type=int, required=True, help='Description of attribute_2')
       @click.option('--ontology-store-name', default="yourstorename", help='Name of the ontology store to use')
       def run_pipeline_cli(attribute_1: str, attribute_2: int, ontology_store_name: str):
           """Run the pipeline from command line."""
           configuration = YourPipelineConfiguration(
               attribute_1=attribute_1,
               attribute_2=attribute_2,
               ontology_store_name=ontology_store_name
           )
           integration = YourIntegration(YourIntegrationConfiguration(attribute_1=attribute_1, attribute_2=attribute_2))
           pipeline = YourPipeline(integration, ontology_store, configuration)
           result = pipeline.run()
           click.echo(result.serialize(format='turtle'))

       if __name__ == '__main__':
           run_pipeline_cli()
   ```

2. **Implement Pipeline Logic**
   - Add your data processing logic in the `run()` method
   - Use the integration to fetch data
   - Transform data into RDF graph format
   - Store results in the ontology store if needed

3. **Test Pipeline**
   Create tests in `tests/pipelines/` to verify your pipeline:
   - Test data transformation
   - Test integration with ontology store
   - Test error handling

For examples, see existing pipelines in the `src/data/pipelines/` directory.

## Creating a new Workflow

To create a new workflow in ABI, follow these steps:

1. **Create Workflow File**
   Create a new file in `src/workflows/YourWorkflow.py` with this structure:

   ```python
   from abi.workflow import Workflow, WorkflowConfiguration
   from src.integrations import YourIntegration, YourIntegrationConfiguration
   from src import secret
   from dataclasses import dataclass
   from pydantic import BaseModel, Field

   @dataclass
   class YourWorkflowConfiguration(WorkflowConfiguration):
       attribute_1: str
       attribute_2: int

   class YourWorkflow(Workflow):
       __configuration: YourWorkflowConfiguration
       
       def __init__(self, configuration: YourWorkflowConfiguration):
           super().__init__(configuration)
           self.__configuration = configuration
           
           self.__your_integration = YourIntegration(
               YourIntegrationConfiguration(
                   attribute_1=self.__configuration.attribute_1,
                   attribute_2=self.__configuration.attribute_2
               )
           )

       def run(self) -> str:
           # Implement your workflow logic here
           return "Your result"

   def api():
       import fastapi
       import uvicorn
       
       app = fastapi.FastAPI()
       
       @app.get("/your_endpoint")
       def your_endpoint():
           configuration = YourWorkflowConfiguration()
           workflow = YourWorkflow(configuration)
           return workflow.run()
       
       uvicorn.run(app, host="0.0.0.0", port=9877)

   def main():
       configuration = YourWorkflowConfiguration(
           attribute_1="attribute_1",
           attribute_2=1
       )
       workflow = YourWorkflow(configuration)
       result = workflow.run()
       print(result)

   def as_tool():
       from langchain_core.tools import StructuredTool
       
       def your_tool_function():
           configuration = YourWorkflowConfiguration(
               attribute_1="attribute_1",
               attribute_2=1
           )
           workflow = YourWorkflow(configuration)
           return workflow.run()
       
       class YourToolSchema(BaseModel):
           attribute_1: str = Field(..., description="The attribute_1 of the tool.")
           attribute_2: int = Field(..., description="The attribute_2 of the tool.")
       
       return StructuredTool(
           name="your_tool_name",
           description="Your tool description.",
           func=your_tool_function,
           args_schema=YourToolSchema
       )

   if __name__ == "__main__":
       main()
   ```

2. **Implement Workflow Logic**
   - Add your business logic in the `run()` method
   - Use integrations to interact with external services
   - Process and transform data as needed
   - Return results in the required format

3. **Test Workflow**
   Create tests in `tests/workflows/` to verify your workflow:
   - Test business logic
   - Test integration with external services
   - Test error handling
   - Test API endpoints

4. **Use the Workflow**
   The workflow can be used in multiple ways:
   - As a standalone script: `python -m src.workflows.YourWorkflow`
   - As an API endpoint: Import and use the `api()` function
   - As a LangChain tool: Import and use the `as_tool()` function

For examples, see existing workflows in the `src/workflows/` directory.

### Learn more

- lib/abi: [lib/abi/README.md](lib/README.md)
- src: [src/README.md](src/README.md)

### Upcoming Changes

#### Standardization of Pipeline and Workflow Interfaces

We are working on standardizing the interfaces for Pipelines and Workflows to provide a more consistent developer experience. The following changes are planned:

1. **Unified Tool Interfaces**
   - Both Pipelines and Workflows will expose standardized `as_tools()` methods
   - Consistent schema definitions and argument handling
   - Unified error handling patterns

2. **Standardized API Endpoints**
   - Common `as_api()` implementation patterns
   - Consistent endpoint structures and response formats
   - Unified error handling and status codes

3. **CLI Interface Standardization**
   - Unified `as_cli()` command structure
   - Consistent parameter handling
   - Standardized output formatting

These changes will make it easier to:
- Create new Pipelines and Workflows
- Maintain consistent interfaces across components
- Integrate components into larger systems
- Test and validate component behavior

The standardization will be rolled out gradually to maintain backward compatibility while improving the developer experience.

## Cursor users

For Cursor users there is the [.cursorrules](.cursorrules) file already configured to help you create new Integrations, Pipelines and Workflows.

More will be added as we add more components to the framework.


## Contributing

1. Fork the repository.
2. Create a new branch with your feature or fix.
3. Open a pull request to the main branch.

## Support
For any questions or support requests, please reach out via support@naas.ai or on our [community forum](https://join.slack.com/t/naas-club/shared_invite/zt-1970s5rie-dXXkigAdEJYc~LPdQIEaLA) on Slack.