# ABI

**An API-driven organizational AI system backend offering assistants, ontology, integrations, workflows, and analytics in a unified framework.**

<img src="./assets/abi-flywheel.png" width="100%" height="100%">

## Table of Content

- [ABI](#abi)
  - [Table of Content](#table-of-content)
  - [Overview](#overview)
    - [Key Features](#key-features)
    - [License](#license)
  - [Setup Project](#setup-project)
    - [Sneak peek 👀](#sneak-peek-)
    - [Getting Started](#getting-started)
    - [Managing Dependencies](#managing-dependencies)
      - [Add a new Python dependency to `src` project](#add-a-new-python-dependency-to-src-project)
      - [Add a new Python dependency to `lib/abi` project](#add-a-new-python-dependency-to-libabi-project)
  - [Build New Components](#build-new-components)
    - [Create Integration](#create-integration)
    - [Create Pipeline](#create-pipeline)
    - [Create Workflow](#create-workflow)
    - [Create Assistant (Single Agent)](#create-assistant-single-agent)
      - [Create Assistant File](#create-assistant-file)
      - [Add Integrations, Workflows and Pipelines as tools](#add-integrations-workflows-and-pipelines-as-tools)
      - [Chat with Assistant in Terminal](#chat-with-assistant-in-terminal)
  - [Standard Operating Procedure](#standard-operating-procedure)
    - [Start with user intent](#start-with-user-intent)
    - [Map Business Problem to Ontology](#map-business-problem-to-ontology)
    - [Build Components](#build-components)
    - [Setup Assistant](#setup-assistant)
    - [Validate your solution](#validate-your-solution)
    - [Deploy to production](#deploy-to-production)
    - [Learn more](#learn-more)
  - [Deploying the API](#deploying-the-api)
    - [Prerequisites](#prerequisites)
    - [Setup GitHub Repository Secrets](#setup-github-repository-secrets)
    - [Customize Deployment Configuration](#customize-deployment-configuration)
    - [Deployment Process](#deployment-process)
    - [Monitoring Deployment](#monitoring-deployment)
  - [Cursor users](#cursor-users)
  - [Contributing](#contributing)
  - [Support](#support)

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

## Setup Project

### Sneak peek 👀

![ABI Terminal](https://naasai-public.s3.eu-west-3.amazonaws.com/abi2.gif)


### Getting Started

1. **Prerequisites**
   - Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)

2. **Get the Repository**
   
   Choose one of the following options:

   a. **Clone the Repository** (for personal use)
   ```bash
   git clone https://github.com/jupyter-naas/abi.git
   cd abi
   ```

   b. **Fork the Repository** (to contribute changes)
   ```bash
   # 1. Fork via GitHub UI
   # 2. Clone your fork
   git clone https://github.com/YOUR-USERNAME/abi.git
   cd abi
   ```

   c. **Create a Private Fork** (for private development)
   ```bash
   # 1. Create private repository via GitHub UI
   # 2. Clone your private repository
   git clone https://github.com/YOUR-USERNAME/abi-private.git
   cd abi-private
   git remote add upstream https://github.com/jupyter-naas/abi.git
   git pull --rebase upstream main
   git push
   ```

3. **Set Up Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   cp config.yaml.example config.yaml
   # Edit config.yaml with your configuration
   ```

4. **Create Docker Container & Start Chatting**
   ```bash
   # Start default agent (chat-supervisor-agent) which can access to all domain agents and tools
   make

   # Or start a specific foundation agent:
   make chat-support-agent     # Support agent

   # Or start a specific domain agent:
   make chat-content-agent      # Content agent
   make chat-finance-agent      # Finance agent  
   make chat-growth-agent       # Growth agent
   make chat-opendata-agent     # Open Data agent
   make chat-operations-agent   # Operations agent
   make chat-sales-agent        # Sales agent

   # Or start a specific custom agent:
   make chat-airtable-agent     # Airtable agent
   make chat-agicap-agent       # Agicap agent
   make chat-aws-s3-agent       # AWS S3 agent
   make chat-brevo-agent        # Brevo agent
   make chat-clockify-agent     # Clockify agent
   make chat-discord-agent      # Discord agent
   make chat-github-agent       # Github agent
   make chat-gladia-agent       # Gladia agent
   make chat-gmail-agent        # Gmail agent
   make chat-google-analytics-agent # Google Analytics agent
   make chat-google-calendar-agent # Google Calendar agent
   make chat-google-drive-agent # Google Drive agent
   make chat-google-sheets-agent # Google Sheets agent
   make chat-harvest-agent       # Harvest agent
   make chat-hubspot-agent       # Hubspot agent
   make chat-linkedin-agent      # LinkedIn agent
   make chat-mercury-agent       # Mercury agent
   make chat-naas-agent         # Naas agent
   make chat-news-api-agent     # News API agent
   make chat-notion-agent       # Notion agent
   make chat-onedrive-agent     # OneDrive agent
   make chat-pennylane-agent    # Pennylane agent
   make chat-pipedrive-agent    # Pipedrive agent
   make chat-postgres-agent     # Postgres agent
   make chat-qonto-agent        # Qonto agent
   make chat-sendgrid-agent     # Sendgrid agent
   make chat-serper-agent       # Serper agent
   make chat-slack-agent        # Slack agent
   make chat-stripe-agent       # Stripe agent
   make chat-supabase-agent     # Supabase agent
   make chat-yahoo-finance-agent # Yahoo Finance agent
   make chat-youtube-agent      # YouTube agent
   make chat-zerobounce-agent   # Zerobounce agent
   ```

   You will only have a access to tools registered in .env file.
   To change default agent please update: `.DEFAULT_GOAL := chat-supervisor-agent` in Makefile

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

## Build New Components

### Create Integration

To create a new integration, follow these steps:

1. **Create Integration File**
   Create a new file in `src/integrations/YourIntegration.py` using template: `src/integrations/__IntegrationTemplate__.py`.

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

### Create Pipeline

Pipelines in ABI are used to process and transform data. Here's how to create a new pipeline:

1. **Create Pipeline File**
   Create a new file in `src/data/pipelines/YourPipeline.py` using template: `src/data/pipelines/__PipelineTemplate__.py`.
   
3. **Implement Pipeline Logic**
   - Add your data processing logic in the `run()` method
   - Use the integration to fetch data
   - Transform data into RDF graph format
   - Store results in the ontology store if needed

4. **Test Pipeline**
   Create tests in `tests/pipelines/` to verify your pipeline:
   - Test data transformation
   - Test integration with ontology store
   - Test error handling

For examples, see existing pipelines in the `src/data/pipelines/` directory.

### Create Workflow

To create a new workflow in ABI, follow these steps:

1. **Create Workflow File**
   Create a new file in `src/workflows/YourWorkflow.py` using template: `src/workflows/__WorkflowTemplate__.py`.

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

### Create Assistant (Single Agent)

To create a new assistant, follow these steps:

#### Create Assistant File
Create a new file in `src/assistants/custom/YourAssistant.py` using template: `src/assistants/custom/__TemplateAssistant__.py`.

#### Add Integrations, Workflows and Pipelines as tools
- Import necessary integrations, pipelines and workflows
- Configure integrations with required credentials
- Add tools using the `as_tools()` method (Class.as_tools(Configuration))

#### Chat with Assistant in Terminal
- Create function to run new assistant in `src/apps/terminal_agent/main.py` following the pattern of existing assistants
- Set function in pyproject.toml: `chat-<assistant-name>-agent = "src.apps.terminal_agent.main:run_<assistant-name>-agent"`
- Add new function in Makefile: `make chat-<assistant-name>-agent`
- Run new assistant: `make chat-<assistant-name>-agent`

## Standard Operating Procedure

This standard procedure explain how to answer to user intent using the ABI framework.

### Start with user intent

Begin by identifying the user's business problem and core question they want answered. 
Understanding this clearly will help guide the solution design.
For example, **"What are my top priorities?"**

### Map Business Problem to Ontology

Map your business problem to ontological concepts:

1. Identify Domain Concepts
   - Use `src/ontologies/domain-level` ontology
   - Example for "What are my top priorities?":
     - Task (core concept)
     - Properties: assignee, creator, due date, status, priority, labels

2. Map to Application Concepts 
   - Use `src/ontologies/application-level` ontology
   - Map domain concepts to your tools:
     - Tasks → GitHub Issues, CRM Tasks, Marketing Campaigns
   - Create subclasses that inherit from domain classes:
     - abi:GitHubIssue ⊂ abi:Task
     - abi:GithubUser ⊂ abi:User
     - abi:GithubProject ⊂ abi:Project

3. Write SPARQL Query
   - Create query from `src/ontologies/ConsolidatedOntology.ttl`
   - Use schema to retrieve data from all relevant subclasses
   - Ensures solution remains tool-agnostic and reusable

### Build Components

Once you have your ontological concepts, build your solution in three steps:

1. **Integration**
   Create or update integrations in `src/integrations` to connect with required data sources.
   Please checkout `src/integrations/GithubIntegration` or `src/integrations/GithubGraphqlIntegration` for more details.

2. **Pipeline**
   Create a pipeline to map data from integrations to ontological concepts. Keep mapping logic modular by:
   - Building small pipelines for specific data transformations
   - Combining smaller pipelines into larger ones as needed
   You will be able to use function to easily create mapping to ontology. 
   Please checkout `src/data/pipelines/GithubIssuePipeline` for more details.

3. **Workflow**
   Create a workflow that uses pipeline results via SPARQL queries. 
   Workflows should focus on business logic rather than data transformation.
   Please checkout `src/workflows/operations_assistant/GetTopPrioritiesWorkflow` for more details.

NB: Each component (Integration, Pipeline, Workflow) can be used as both an AI assistant tool and a REST API endpoint.

### Setup Assistant
1. [Create or use an existing assistant](#create-assistant-single-agent) in `src/assistants`.
2. Setup the workflow that answer to the user intent as a tool in the assistant. We recommend to put the user intent as description of your workflow so the assistant can understand it better.
3. You can also add your pipelines and integrations function as tools if you want to trigger them from the assistant.

### Validate your solution
1. Setup your assistant to validate your solution with your terminal. See [Chat with Assistant](#chat-with-assistant-in-terminal) for detailed instructions.
2. Ask the user intent and see if the solution is working as expected.
3. If not, you can update your assistant configuration, workflow, pipeline and integration and test again.

### Deploy to production
Merge your branch into main.
- Your assistant will be deployed to production and you will be able to use it with API but also in Naas platform.
- Your workflows, pipelines and integrations will also be deployed as API.
- Your pipelines will schedule according to your configuration.

### Learn more

- lib/abi: [lib/abi/README.md](lib/README.md)
- src: [src/README.md](src/README.md)

## Deploying the API

### Prerequisites

1. Create a GitHub Classic Personal Access Token:
   - Go to GitHub Settings > Developer Settings > Personal Access Tokens > Tokens (classic)
   - Generate a new token with the following permissions:
     - `repo` (Full control of private repositories)
     - `read:packages` and `write:packages` (For container registry access)
     - `read:packages` and `write:packages` (For container registry access)
   - Copy the token value

2. Get required API keys:
   - OpenAI API key from [OpenAI Platform](https://platform.openai.com/api-keys)
   - NAAS Credentials JWT Token from your NAAS account

### Setup GitHub Repository Secrets

1. Navigate to your repository's Settings > Secrets and variables > Actions
2. Add the following secrets:
   - `ACCESS_TOKEN`: Your GitHub Classic Personal Access Token
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `NAAS_CREDENTIALS_JWT_TOKEN`: Your NAAS Credentials JWT Token

### Customize Deployment Configuration

1. Open `.github/workflows/deploy_api.yml`
2. Update the space name to match your project:
   ```yaml
   naas-python space create --name=your-api-name # Replace 'abi-api' with your desired name
   ```

### Deployment Process

The API deployment is automated through GitHub Actions and triggers when:
1. A new container is built (via the "Build ABI Container" workflow)
2. The deployment workflow creates/updates a NAAS space with the latest container image
3. The API will be accessible through the NAAS platform once deployment is complete

### Monitoring Deployment

1. Go to your repository's Actions tab
2. Look for the "ABI API" workflow
3. Check the latest workflow run for deployment status and logs

## Cursor users

For Cursor users there is the [.cursorrules](.cursorrules) file already configured to help you create new Integrations, Pipelines and Workflows.

More will be added as we add more components to the framework.

## Contributing

1. Fork the repository.
2. Create a new branch with your feature or fix.
3. Open a pull request to the main branch.

## Support
For any questions or support requests, please reach out via support@naas.ai or on our [community forum](https://join.slack.com/t/naas-club/shared_invite/zt-2wjo50ks0-KhYxmgW6PZVe72Aj3tGi9Q) on Slack.

