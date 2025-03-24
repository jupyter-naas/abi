.venv:
	@ docker compose run --rm --remove-orphans abi poetry install

dev-build:
	@ docker compose build

install:
	@ docker compose run --rm --remove-orphans abi poetry install
	@ docker compose run --rm --remove-orphans abi poetry update abi

abi-add: .venv
	@ docker compose run --rm abi bash -c 'cd lib && poetry add $(dep) && poetry lock'

add:
	@ docker compose run --rm abi bash -c 'poetry add $(dep) && poetry lock'

lock:
	@ docker compose run --rm --remove-orphans abi poetry lock

path=tests/
test: unit-tests integration-tests
	@echo "All tests completed successfully!"

# Add a separate target for tests with linting
test-with-lint: lint unit-tests integration-tests
	@echo "All tests and linting completed successfully!"

sh: .venv
	@ docker compose run --rm --remove-orphans -it abi bash
  
api: .venv
	@ docker compose run --rm --remove-orphans -p 9879:9879 abi poetry run api


dvc-login: .venv
	@ docker compose run --rm --remove-orphans  abi bash -c 'poetry run python scripts/setup_dvc.py | sh'

storage-pull: .venv
	@ docker compose run --rm --remove-orphans abi bash -c 'poetry run python scripts/storage_pull.py | sh'

storage-push: .venv
	@ docker compose run --rm --remove-orphans  abi bash -c 'poetry run python scripts/storage_push.py | sh'

clean:
	@echo "Cleaning up build artifacts..."
	rm -rf __pycache__ .pytest_cache build dist *.egg-info lib/.venv .venv
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
	docker compose down
	docker compose rm -f
	rm -rf src/core/modules/common/integrations/siteanalyzer/target

# Docker Build Commands
# -------------------
# These commands are used to build the Docker image for the ABI project

# Default build target that triggers the Linux x86_64 build
build: build.linux.x86_64

# Builds a Docker image for Linux x86_64 architecture
# Usage: make build.linux.x86_64
# 
# Parameters:
#   - Image name: abi
#   - Dockerfile: Dockerfile.linux.x86_64
#   - Platform: linux/amd64 (ensures consistent builds on x86_64/amd64 architecture)
build.linux.x86_64: .venv
	docker build . -t abi -f Dockerfile.linux.x86_64 --platform linux/amd64

# -------------------------------------------------------------------------------------------------

chat-supervisor-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent SupervisorAssistant'

chat-support-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent SupportAssistant'

chat-opendata-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent OpenDataAssistant'

chat-osint-investigator-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent OSINTInvestigatorAssistant'

chat-content-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent ContentAssistant'

chat-growth-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent GrowthAssistant'

chat-sales-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent SalesAssistant'

chat-operations-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent OperationsAssistant'

chat-finance-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent FinanceAssistant'

chat-powerpoint-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent PowerPointAssistant'

chat-trading-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent StockTradingAgent'
  
chat-arxiv-agent: .venv
	@ docker compose run abi bash -c 'poetry install && poetry run python -m src.core.apps.terminal_agent.main generic_run_agent ArXivAssistant'

.DEFAULT_GOAL := chat-supervisor-agent

.PHONY: all test unit-tests integration-tests lint clean

# Default target - runs tests when you type just 'make'
all: test

# Unit tests
unit-tests:
	@echo "Running unit tests..."
	python -m pytest tests/unit --verbose

# Integration tests
integration-tests:
	@echo "Running integration tests..."
	python -m pytest tests/integration --verbose

# Code linting
lint:
	@echo "Running basic linters..."
	flake8 src tests --select=F,E7 --ignore=E501,W291,W293
	black --check src tests

# Add after the lint command
fix-lint:
	@echo "Auto-fixing linting issues..."
	black src tests
	isort src tests

.PHONY: test chat-supervisor-agent chat-support-agent chat-content-agent chat-finance-agent chat-growth-agent chat-opendata-agent chat-operations-agent chat-sales-agent api sh lock add abi-add

# Build module - copies components to the module directory
build-module:
	@read -p "Enter module name (use snake_case, e.g. yahoo_financials): " MODULE_NAME && \
	if [[ $$MODULE_NAME =~ [A-Z[:space:]\-] ]]; then \
		echo "Error: Module name must be in snake_case format (lowercase with underscores, no spaces or hyphens)"; \
		exit 1; \
	fi && \
	MODULE_NAME_PASCAL=$$(echo $$MODULE_NAME | sed -r 's/(^|_)([a-z])/\U\2/g') && \
	mkdir -p src/custom/modules/$$MODULE_NAME/integrations && \
	mkdir -p src/custom/modules/$$MODULE_NAME/pipelines && \
	mkdir -p src/custom/modules/$$MODULE_NAME/workflows && \
	mkdir -p src/custom/modules/$$MODULE_NAME/assistants && \
	mkdir -p src/custom/modules/$$MODULE_NAME/ontologies && \
	mkdir -p src/custom/modules/$$MODULE_NAME/tests && \
	mkdir -p src/custom/modules/$$MODULE_NAME/apps && \
	mkdir -p src/custom/modules/$$MODULE_NAME/analytics && \
	touch src/custom/modules/$$MODULE_NAME/__init__.py && \
	echo "Copying integrations..." && \
	cp -r src/integrations/* src/custom/modules/$$MODULE_NAME/integrations/ 2>/dev/null || true && \
	echo "Copying pipelines..." && \
	cp -r src/data/pipelines/* src/custom/modules/$$MODULE_NAME/pipelines/ 2>/dev/null || true && \
	echo "Copying workflows..." && \
	cp -r src/workflows/* src/custom/modules/$$MODULE_NAME/workflows/ 2>/dev/null || true && \
	echo "Creating module README..." && \
	echo "# $$MODULE_NAME Module\n\nDescription of your module and its purpose.\n\n## Components\n\n- Integrations\n- Workflows\n- Pipelines\n- Ontologies\n- Assistants\n\n## Usage\n\nHow to use this module.\n" > src/custom/modules/$$MODULE_NAME/README.md && \
	echo "Creating example assistant..." && \
	echo "from langchain_openai import ChatOpenAI\nfrom abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState\nfrom src import secret, services\n\nNAME = \"$$MODULE_NAME_PASCAL Assistant\"\nDESCRIPTION = \"A brief description of what your assistant does.\"\nMODEL = \"o3-mini\"  # Or another appropriate model\nTEMPERATURE = 1\nAVATAR_URL = \"https://example.com/avatar.png\"\nSYSTEM_PROMPT = \"\"\"You are the $$MODULE_NAME_PASCAL Assistant. Your role is to help users with tasks related to $$MODULE_NAME.\n\nYou can perform the following tasks:\n- Task 1\n- Task 2\n- Task 3\n\nAlways be helpful, concise, and focus on solving the user's problem.\"\"\"\n\ndef create_agent(shared_state: AgentSharedState = None) -> Agent:\n    \"\"\"Creates a new instance of the $$MODULE_NAME_PASCAL Assistant.\"\"\"\n    # Configure the underlying chat model\n    llm = ChatOpenAI(\n        model=MODEL,\n        temperature=TEMPERATURE,\n        api_key=secret.get_openai_api_key()\n    )\n    \n    # Configure the agent\n    config = AgentConfiguration(\n        name=NAME,\n        description=DESCRIPTION,\n        model=MODEL,\n        temperature=TEMPERATURE,\n        system_prompt=SYSTEM_PROMPT,\n        avatar_url=AVATAR_URL,\n        shared_state=shared_state or AgentSharedState(),\n    )\n    \n    # Create and return the agent\n    agent = Agent(llm=llm, config=config)\n    \n    # Add tools to the agent (uncomment and modify as needed)\n    # workflow = YourWorkflow(YourWorkflowConfiguration())\n    # agent.add_tools(workflow.as_tools())\n    \n    return agent\n\n# For testing purposes\nif __name__ == \"__main__\":\n    agent = create_agent()\n    agent.run(\"Hello, I need help with $$MODULE_NAME\")\n" > src/custom/modules/$$MODULE_NAME/assistants/$${MODULE_NAME_PASCAL}Assistant.py && \
	echo "Creating example workflow..." && \
	echo "from pydantic import BaseModel, Field\nfrom typing import Optional, List, Dict, Any\nfrom fastapi import APIRouter\nfrom langchain_core.tools import StructuredTool\n\nclass $${MODULE_NAME_PASCAL}WorkflowConfiguration(BaseModel):\n    \"\"\"Configuration for the $$MODULE_NAME_PASCAL Workflow.\"\"\"\n    # Add configuration parameters here\n    api_key: Optional[str] = Field(None, description=\"API key for external service\")\n\nclass $${MODULE_NAME_PASCAL}WorkflowParameters(BaseModel):\n    \"\"\"Parameters for running the $$MODULE_NAME_PASCAL Workflow.\"\"\"\n    # Add input parameters here\n    query: str = Field(..., description=\"Query to process\")\n    max_results: int = Field(10, description=\"Maximum number of results to return\")\n\nclass $${MODULE_NAME_PASCAL}WorkflowResult(BaseModel):\n    \"\"\"Result of the $$MODULE_NAME_PASCAL Workflow.\"\"\"\n    # Define the structure of the workflow results\n    results: List[Dict[str, Any]] = Field(default_factory=list, description=\"List of results\")\n    count: int = Field(0, description=\"Number of results found\")\n\nclass $${MODULE_NAME_PASCAL}Workflow:\n    \"\"\"A workflow for $$MODULE_NAME operations.\"\"\"\n    \n    def __init__(self, configuration: $${MODULE_NAME_PASCAL}WorkflowConfiguration):\n        self.__configuration = configuration\n    \n    def as_tools(self) -> list[StructuredTool]:\n        \"\"\"Returns a list of LangChain tools for this workflow.\"\"\"\n        return [StructuredTool(\n            name=\"$${MODULE_NAME}_workflow\",\n            description=\"Runs the $$MODULE_NAME_PASCAL workflow with the given parameters\",\n            func=lambda **kwargs: self.run($${MODULE_NAME_PASCAL}WorkflowParameters(**kwargs)),\n            args_schema=$${MODULE_NAME_PASCAL}WorkflowParameters\n        )]\n    \n    def as_api(self, router: APIRouter) -> None:\n        \"\"\"Adds API endpoints for this workflow to the given router.\"\"\"\n        @router.post(\"/$${MODULE_NAME_PASCAL}Workflow\")\n        def run(parameters: $${MODULE_NAME_PASCAL}WorkflowParameters):\n            return self.run(parameters)\n    \n    def run(self, parameters: $${MODULE_NAME_PASCAL}WorkflowParameters) -> $${MODULE_NAME_PASCAL}WorkflowResult:\n        \"\"\"Runs the workflow with the given parameters.\"\"\"\n        # Implement your workflow logic here\n        # This is a placeholder implementation\n        \n        # Example placeholder implementation\n        results = [\n            {\"id\": 1, \"name\": \"Result 1\", \"value\": \"Sample data 1\"},\n            {\"id\": 2, \"name\": \"Result 2\", \"value\": \"Sample data 2\"},\n        ]\n        \n        # Take only as many results as requested\n        results = results[:parameters.max_results]\n        \n        return $${MODULE_NAME_PASCAL}WorkflowResult(\n            results=results,\n            count=len(results)\n        )\n\n# For testing purposes\nif __name__ == \"__main__\":\n    config = $${MODULE_NAME_PASCAL}WorkflowConfiguration()\n    workflow = $${MODULE_NAME_PASCAL}Workflow(config)\n    result = workflow.run($${MODULE_NAME_PASCAL}WorkflowParameters(query=\"test query\"))\n    print(result)\n" > src/custom/modules/$$MODULE_NAME/workflows/$${MODULE_NAME_PASCAL}Workflow.py && \
	echo "Creating example pipeline..." && \
	echo "from pydantic import BaseModel, Field\nfrom typing import Optional, List\nfrom fastapi import APIRouter\nfrom langchain_core.tools import StructuredTool\nfrom rdflib import Graph, Namespace, URIRef, Literal\nfrom rdflib.namespace import RDF, RDFS\nfrom abi.services.ontology_store import OntologyStoreService\nfrom abi.services.ontology_store.models.Graph import ABIGraph\n\nclass $${MODULE_NAME_PASCAL}PipelineConfiguration(BaseModel):\n    \"\"\"Configuration for the $$MODULE_NAME_PASCAL Pipeline.\"\"\"\n    # Add configuration parameters here\n    ontology_store: OntologyStoreService = Field(..., description=\"Ontology store service for persisting RDF data\")\n\nclass $${MODULE_NAME_PASCAL}PipelineParameters(BaseModel):\n    \"\"\"Parameters for running the $$MODULE_NAME_PASCAL Pipeline.\"\"\"\n    # Add input parameters here\n    entity_id: str = Field(..., description=\"ID of the entity to process\")\n    attributes: List[str] = Field(default_factory=list, description=\"Attributes to include\")\n\nclass $${MODULE_NAME_PASCAL}Pipeline:\n    \"\"\"A pipeline for transforming $$MODULE_NAME data into RDF.\"\"\"\n    \n    def __init__(self, configuration: $${MODULE_NAME_PASCAL}PipelineConfiguration):\n        self.__configuration = configuration\n    \n    def as_tools(self) -> list[StructuredTool]:\n        \"\"\"Returns a list of LangChain tools for this pipeline.\"\"\"\n        return [StructuredTool(\n            name=\"$${MODULE_NAME}_pipeline\",\n            description=\"Executes the $$MODULE_NAME_PASCAL pipeline with the given parameters\",\n            func=lambda **kwargs: self.run($${MODULE_NAME_PASCAL}PipelineParameters(**kwargs)),\n            args_schema=$${MODULE_NAME_PASCAL}PipelineParameters\n        )]\n    \n    def as_api(self, router: APIRouter) -> None:\n        \"\"\"Adds API endpoints for this pipeline to the given router.\"\"\"\n        @router.post(\"/$${MODULE_NAME_PASCAL}Pipeline\")\n        def run(parameters: $${MODULE_NAME_PASCAL}PipelineParameters):\n            return self.run(parameters).serialize(format=\"turtle\")\n    \n    def run(self, parameters: $${MODULE_NAME_PASCAL}PipelineParameters) -> Graph:\n        \"\"\"Runs the pipeline with the given parameters.\"\"\"\n        # Create a new RDF graph\n        graph = ABIGraph()\n        \n        # Define namespaces\n        YOUR = Namespace(f\"http://ontology.naas.ai/{$$MODULE_NAME}/\")\n        \n        # Bind namespaces\n        graph.bind(\"your\", YOUR)\n        \n        # Create entity URI\n        entity_uri = URIRef(f\"{YOUR}entity/{parameters.entity_id}\")\n        \n        # Add class assertion\n        graph.add((entity_uri, RDF.type, YOUR.YourClass))\n        \n        # Add example attributes\n        if parameters.attributes:\n            for attr in parameters.attributes:\n                graph.add((entity_uri, YOUR.hasAttribute, Literal(attr)))\n        else:\n            # Default attribute if none provided\n            graph.add((entity_uri, YOUR.hasAttribute, Literal(\"default attribute\")))\n        \n        # Optionally persist to ontology store\n        # self.__configuration.ontology_store.add_graph(\n        #    store_name=\"your_store\",\n        #    graph=graph\n        # )\n        \n        return graph\n\n# For testing purposes\nif __name__ == \"__main__\":\n    from abi.services.ontology_store import OntologyStoreService\n    \n    # Setup dependencies\n    ontology_store = OntologyStoreService()\n    \n    # Create pipeline configuration\n    config = $${MODULE_NAME_PASCAL}PipelineConfiguration(\n        ontology_store=ontology_store\n    )\n    \n    # Initialize and run pipeline\n    pipeline = $${MODULE_NAME_PASCAL}Pipeline(config)\n    result = pipeline.run($${MODULE_NAME_PASCAL}PipelineParameters(\n        entity_id=\"123\",\n        attributes=[\"attr1\", \"attr2\"]\n    ))\n    \n    # Print results in Turtle format\n    print(result.serialize(format=\"turtle\"))\n" > src/custom/modules/$$MODULE_NAME/pipelines/$${MODULE_NAME_PASCAL}Pipeline.py && \
	echo "Creating example integration..." && \
	echo "from pydantic import BaseModel, Field, SecretStr\nfrom typing import Optional, List, Dict, Any\nfrom langchain_core.tools import StructuredTool\n\nclass $${MODULE_NAME_PASCAL}IntegrationConfiguration(BaseModel):\n    \"\"\"Configuration for the $$MODULE_NAME_PASCAL Integration.\"\"\"\n    api_key: SecretStr = Field(..., description=\"API key for the service\")\n    base_url: str = Field(\"https://api.example.com\", description=\"Base URL for API calls\")\n\nclass $${MODULE_NAME_PASCAL}SearchParameters(BaseModel):\n    \"\"\"Parameters for searching.\"\"\"\n    query: str = Field(..., description=\"Search query\")\n    limit: int = Field(10, description=\"Maximum number of results\")\n\nclass $${MODULE_NAME_PASCAL}Integration:\n    \"\"\"Integration with the $$MODULE_NAME_PASCAL service.\"\"\"\n    \n    def __init__(self, configuration: $${MODULE_NAME_PASCAL}IntegrationConfiguration):\n        self.__configuration = configuration\n    \n    def as_tools(self) -> list[StructuredTool]:\n        \"\"\"Returns a list of LangChain tools for this integration.\"\"\"\n        return [\n            StructuredTool(\n                name=\"search_$${MODULE_NAME}\",\n                description=\"Search for information in the $$MODULE_NAME_PASCAL service\",\n                func=self.search,\n                args_schema=$${MODULE_NAME_PASCAL}SearchParameters\n            )\n        ]\n    \n    def search(self, parameters: $${MODULE_NAME_PASCAL}SearchParameters) -> List[Dict[str, Any]]:\n        \"\"\"Search for information in the $$MODULE_NAME_PASCAL service.\"\"\"\n        # This is a placeholder implementation\n        # In a real integration, you would make API calls to the service\n        \n        # Example placeholder implementation\n        results = [\n            {\"id\": \"result1\", \"title\": \"Sample Result 1\", \"description\": f\"This is a sample result for '{parameters.query}'\"},\n            {\"id\": \"result2\", \"title\": \"Sample Result 2\", \"description\": f\"Another sample result for '{parameters.query}'\"}\n        ]\n        \n        # Return limited results\n        return results[:parameters.limit]\n\n# For testing purposes\nif __name__ == \"__main__\":\n    config = $${MODULE_NAME_PASCAL}IntegrationConfiguration(\n        api_key=SecretStr(\"your-api-key-here\")\n    )\n    integration = $${MODULE_NAME_PASCAL}Integration(config)\n    results = integration.search($${MODULE_NAME_PASCAL}SearchParameters(query=\"test\"))\n    print(results)\n" > src/custom/modules/$$MODULE_NAME/integrations/$${MODULE_NAME_PASCAL}Integration.py && \
	echo "Creating example ontology..." && \
	echo "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n@prefix dc: <http://purl.org/dc/elements/1.1/> .\n@prefix bfo: <http://purl.obolibrary.org/obo/> .\n@prefix abi: <http://ontology.naas.ai/abi/> .\n@prefix $${MODULE_NAME}: <http://ontology.naas.ai/$${MODULE_NAME}/> .\n\n# Ontology metadata\n<http://ontology.naas.ai/$${MODULE_NAME}/$${MODULE_NAME_PASCAL}Ontology> rdf:type owl:Ontology ;\n    dc:title \"$$MODULE_NAME_PASCAL Ontology\" ;\n    dc:description \"An ontology for the $$MODULE_NAME_PASCAL module\" .\n\n# Classes\n$${MODULE_NAME}:$${MODULE_NAME_PASCAL}Entity rdf:type owl:Class ;\n    rdfs:label \"$$MODULE_NAME_PASCAL Entity\"@en ;\n    rdfs:subClassOf bfo:BFO_0000001 ;\n    skos:definition \"A primary entity in the $$MODULE_NAME_PASCAL domain\" .\n\n# Object Properties\n$${MODULE_NAME}:hasRelatedEntity rdf:type owl:ObjectProperty ;\n    rdfs:label \"has related entity\"@en ;\n    rdfs:domain $${MODULE_NAME}:$${MODULE_NAME_PASCAL}Entity ;\n    rdfs:range $${MODULE_NAME}:$${MODULE_NAME_PASCAL}Entity ;\n    skos:definition \"Relates a $$MODULE_NAME_PASCAL entity to another related entity\" .\n\n# Data Properties\n$${MODULE_NAME}:hasAttribute rdf:type owl:DatatypeProperty ;\n    rdfs:label \"has attribute\"@en ;\n    rdfs:domain $${MODULE_NAME}:$${MODULE_NAME_PASCAL}Entity ;\n    rdfs:range xsd:string ;\n    skos:definition \"An attribute of a $$MODULE_NAME_PASCAL entity\" .\n\n# Individuals (Examples)\n$${MODULE_NAME}:exampleEntity rdf:type $${MODULE_NAME}:$${MODULE_NAME_PASCAL}Entity ;\n    rdfs:label \"Example Entity\"@en ;\n    $${MODULE_NAME}:hasAttribute \"Example value\" .\n" > src/custom/modules/$$MODULE_NAME/ontologies/$${MODULE_NAME_PASCAL}Ontology.ttl && \
	echo "Creating example app..." && \
	echo "from fastapi import FastAPI, APIRouter\nfrom pydantic import BaseModel, Field\nfrom typing import List, Dict, Any\n\nclass $${MODULE_NAME_PASCAL}Response(BaseModel):\n    \"\"\"Response model for the $$MODULE_NAME_PASCAL app.\"\"\"\n    results: List[Dict[str, Any]] = Field(default_factory=list)\n    message: str = Field(\"Success\")\n\ndef create_$${MODULE_NAME}_app() -> FastAPI:\n    \"\"\"Creates a FastAPI app for the $$MODULE_NAME_PASCAL module.\"\"\"\n    app = FastAPI(\n        title=\"$$MODULE_NAME_PASCAL App\",\n        description=\"API for the $$MODULE_NAME_PASCAL module\",\n        version=\"0.1.0\"\n    )\n    \n    router = APIRouter(prefix=\"/$${MODULE_NAME}\", tags=[\"$${MODULE_NAME}\"])\n    \n    @router.get(\"/\", response_model=$${MODULE_NAME_PASCAL}Response)\n    async def root():\n        \"\"\"Root endpoint for the $$MODULE_NAME_PASCAL app.\"\"\"\n        return $${MODULE_NAME_PASCAL}Response(\n            results=[{\"status\": \"ok\"}],\n            message=\"$$MODULE_NAME_PASCAL App is running\"\n        )\n    \n    @router.get(\"/status\", response_model=$${MODULE_NAME_PASCAL}Response)\n    async def status():\n        \"\"\"Status endpoint for the $$MODULE_NAME_PASCAL app.\"\"\"\n        return $${MODULE_NAME_PASCAL}Response(\n            results=[{\"status\": \"operational\"}],\n            message=\"$$MODULE_NAME_PASCAL services are operational\"\n        )\n    \n    # Add more endpoints as needed\n    \n    app.include_router(router)\n    return app\n\n# For direct execution\nif __name__ == \"__main__\":\n    import uvicorn\n    app = create_$${MODULE_NAME}_app()\n    uvicorn.run(app, host=\"0.0.0.0\", port=8000)\n" > src/custom/modules/$$MODULE_NAME/apps/$${MODULE_NAME_PASCAL}App.py && \
	echo "Creating example analytics..." && \
	echo "import pandas as pd\nimport matplotlib.pyplot as plt\nfrom typing import Dict, List, Any, Optional\nimport io\nimport base64\n\nclass $${MODULE_NAME_PASCAL}Analytics:\n    \"\"\"Analytics for the $$MODULE_NAME_PASCAL module.\"\"\"\n    \n    def __init__(self):\n        \"\"\"Initialize the analytics component.\"\"\"\n        pass\n    \n    def analyze_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:\n        \"\"\"Analyze data and return results.\"\"\"\n        # Convert to DataFrame for easier analysis\n        df = pd.DataFrame(data)\n        \n        # Example analysis metrics (customize based on your actual data)\n        metrics = {\n            \"count\": len(df),\n            \"fields\": list(df.columns) if not df.empty else [],\n            \"summary\": df.describe().to_dict() if not df.empty else {}\n        }\n        \n        return metrics\n    \n    def generate_chart(self, data: List[Dict[str, Any]], x_field: str, y_field: str, \n                      chart_type: str = \"bar\", title: Optional[str] = None) -> str:\n        \"\"\"Generate a chart from the data and return as base64 encoded image.\"\"\"\n        # Convert to DataFrame\n        df = pd.DataFrame(data)\n        \n        if df.empty or x_field not in df.columns or y_field not in df.columns:\n            return \"\"\n        \n        # Create figure\n        plt.figure(figsize=(10, 6))\n        \n        # Generate the specified chart type\n        if chart_type == \"bar\":\n            df.plot(kind=\"bar\", x=x_field, y=y_field)\n        elif chart_type == \"line\":\n            df.plot(kind=\"line\", x=x_field, y=y_field)\n        elif chart_type == \"scatter\":\n            df.plot(kind=\"scatter\", x=x_field, y=y_field)\n        else:\n            df.plot(kind=\"bar\", x=x_field, y=y_field)  # Default to bar\n        \n        # Add title if provided\n        if title:\n            plt.title(title)\n        else:\n            plt.title(f\"{y_field} by {x_field}\")\n        \n        # Add labels\n        plt.xlabel(x_field)\n        plt.ylabel(y_field)\n        \n        # Save to bytes buffer\n        buffer = io.BytesIO()\n        plt.savefig(buffer, format=\"png\")\n        buffer.seek(0)\n        \n        # Convert to base64\n        image_base64 = base64.b64encode(buffer.getvalue()).decode(\"utf-8\")\n        plt.close()\n        \n        return f\"data:image/png;base64,{image_base64}\"\n\n# For testing purposes\nif __name__ == \"__main__\":\n    # Sample test data\n    test_data = [\n        {\"category\": \"A\", \"value\": 10},\n        {\"category\": \"B\", \"value\": 15},\n        {\"category\": \"C\", \"value\": 7},\n        {\"category\": \"D\", \"value\": 12}\n    ]\n    \n    analytics = $${MODULE_NAME_PASCAL}Analytics()\n    \n    # Test analysis\n    results = analytics.analyze_data(test_data)\n    print(\"Analysis results:\", results)\n    \n    # Test chart generation\n    chart = analytics.generate_chart(test_data, \"category\", \"value\", \"bar\", \"Sample Chart\")\n    print(\"Chart generated with length:\", len(chart))\n    \n    # To view the chart, you would typically embed it in HTML like:\n    # print(f\"<img src='{chart}' />\")\n" > src/custom/modules/$$MODULE_NAME/analytics/$${MODULE_NAME_PASCAL}Analytics.py && \
	echo "Creating sample test file..." && \
	echo "import unittest\nfrom unittest.mock import MagicMock, patch\n\nclass Test$${MODULE_NAME_PASCAL}Module(unittest.TestCase):\n    \"\"\"Test suite for the $$MODULE_NAME_PASCAL module.\"\"\"\n    \n    def setUp(self):\n        \"\"\"Set up test fixtures.\"\"\"\n        pass\n    \n    def tearDown(self):\n        \"\"\"Tear down test fixtures.\"\"\"\n        pass\n    \n    def test_assistant(self):\n        \"\"\"Test the $$MODULE_NAME_PASCAL Assistant.\"\"\"\n        try:\n            from ..assistants.$${MODULE_NAME_PASCAL}Assistant import create_agent\n            \n            # Test agent creation\n            agent = create_agent()\n            self.assertIsNotNone(agent)\n            \n            # Additional tests for the assistant would go here\n        except ImportError:\n            self.skipTest(\"Assistant not implemented yet\")\n    \n    def test_workflow(self):\n        \"\"\"Test the $$MODULE_NAME_PASCAL Workflow.\"\"\"\n        try:\n            from ..workflows.$${MODULE_NAME_PASCAL}Workflow import $${MODULE_NAME_PASCAL}Workflow, $${MODULE_NAME_PASCAL}WorkflowConfiguration, $${MODULE_NAME_PASCAL}WorkflowParameters\n            \n            # Test workflow initialization\n            config = $${MODULE_NAME_PASCAL}WorkflowConfiguration()\n            workflow = $${MODULE_NAME_PASCAL}Workflow(config)\n            self.assertIsNotNone(workflow)\n            \n            # Test workflow execution\n            params = $${MODULE_NAME_PASCAL}WorkflowParameters(query=\"test\")\n            result = workflow.run(params)\n            self.assertIsNotNone(result)\n            \n            # Test tool creation\n            tools = workflow.as_tools()\n            self.assertTrue(len(tools) > 0)\n        except ImportError:\n            self.skipTest(\"Workflow not implemented yet\")\n    \n    def test_pipeline(self):\n        \"\"\"Test the $$MODULE_NAME_PASCAL Pipeline.\"\"\"\n        try:\n            from ..pipelines.$${MODULE_NAME_PASCAL}Pipeline import $${MODULE_NAME_PASCAL}Pipeline, $${MODULE_NAME_PASCAL}PipelineConfiguration, $${MODULE_NAME_PASCAL}PipelineParameters\n            from abi.services.ontology_store import OntologyStoreService\n            \n            # Create a mock ontology store\n            mock_store = MagicMock(spec=OntologyStoreService)\n            \n            # Test pipeline initialization\n            config = $${MODULE_NAME_PASCAL}PipelineConfiguration(ontology_store=mock_store)\n            pipeline = $${MODULE_NAME_PASCAL}Pipeline(config)\n            self.assertIsNotNone(pipeline)\n            \n            # Test pipeline execution\n            params = $${MODULE_NAME_PASCAL}PipelineParameters(entity_id=\"123\")\n            result = pipeline.run(params)\n            self.assertIsNotNone(result)\n            \n            # Test if result is a graph\n            self.assertTrue(hasattr(result, 'serialize'))\n        except ImportError:\n            self.skipTest(\"Pipeline not implemented yet\")\n    \n    def test_integration(self):\n        \"\"\"Test the $$MODULE_NAME_PASCAL Integration.\"\"\"\n        try:\n            from ..integrations.$${MODULE_NAME_PASCAL}Integration import $${MODULE_NAME_PASCAL}Integration, $${MODULE_NAME_PASCAL}IntegrationConfiguration, $${MODULE_NAME_PASCAL}SearchParameters\n            from pydantic import SecretStr\n            \n            # Test integration initialization\n            config = $${MODULE_NAME_PASCAL}IntegrationConfiguration(api_key=SecretStr(\"test_key\"))\n            integration = $${MODULE_NAME_PASCAL}Integration(config)\n            self.assertIsNotNone(integration)\n            \n            # Test search function\n            params = $${MODULE_NAME_PASCAL}SearchParameters(query=\"test\")\n            results = integration.search(params)\n            self.assertIsNotNone(results)\n            self.assertTrue(isinstance(results, list))\n        except ImportError:\n            self.skipTest(\"Integration not implemented yet\")\n\nif __name__ == '__main__':\n    unittest.main()" > src/custom/modules/$$MODULE_NAME/tests/test_module.py && \
	echo "Module '$$MODULE_NAME' built successfully in src/custom/modules/$$MODULE_NAME/"
