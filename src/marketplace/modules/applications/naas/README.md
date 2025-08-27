# Naas Module

## Description

The Naas Module provides comprehensive integration with Naas.ai services, enabling workspace management, plugin operations, ontology handling, user management, secret storage, and asset management through a unified API interface.

Key Features:
- Complete Naas workspace lifecycle management
- Plugin creation and management within workspaces
- Ontology creation and management with multiple levels
- User invitation and role management
- Secure secret storage and retrieval
- Asset upload and storage management
- Image URL to asset pipeline for automatic asset creation

## TL;DR

- Start the Naas agent:
```bash
make chat-naas-agent
```
- Or use the generic chat command:
```bash
make chat Agent=NaasAgent
```

## Overview

### Structure

```
src/marketplace/modules/applications/naas/
├── agents/                                        # AI agents
│   └── NaasAgent.py                              # Main Naas management agent
├── integrations/                                  # API integrations
│   └── NaasIntegration.py                        # Complete Naas API integration
├── pipelines/                                     # Data processing pipelines
│   ├── ImageURLtoAssetPipeline.py                # Image URL to asset conversion
│   └── ImageURLtoAssetPipeline_test.py           # Pipeline tests
├── README.md                                      # This documentation
└── naas_agent.md                                  # Detailed agent capabilities
```

### Core Components

- **NaasAgent**: AI agent for natural language interaction with Naas services
- **NaasIntegration**: Complete API integration with all Naas endpoints
- **ImageURLtoAssetPipeline**: Automated pipeline for converting image URLs to Naas assets

## Agents

### Naas Agent

An AI agent that provides natural language interface for Naas workspace management:

1. **Workspace Management**: Create, retrieve, update, and delete workspaces
2. **Plugin Operations**: Manage plugins within workspaces
3. **Ontology Handling**: Create and manage ontologies with different levels
4. **User Management**: Invite users and manage roles/permissions
5. **Secret Management**: Secure storage and retrieval of sensitive data
6. **Storage Operations**: Manage storage spaces and assets

```python
from src.marketplace.modules.applications.naas.agents.NaasAgent import create_agent

# Create agent
agent = create_agent()

# Use agent for Naas operations
# The agent provides natural language interface to all Naas services
```

## Integrations

### Naas Integration

Complete API integration providing access to all Naas services:

1. **Workspace API**: Full CRUD operations for workspaces
2. **Plugin API**: Plugin management within workspaces
3. **Ontology API**: Ontology creation and management
4. **User API**: User invitation and role management
5. **Secret API**: Secure secret storage operations
6. **Storage API**: Asset and storage management

```python
from src.marketplace.modules.applications.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration
)

# Configure integration
config = NaasIntegrationConfiguration(
    api_key="your_naas_api_key"
)

integration = NaasIntegration(config)

# Use integration methods
workspaces = integration.get_workspaces()
```

## Pipelines

### Image URL to Asset Pipeline

Automated pipeline for converting image URLs to Naas assets:

1. **URL Processing**: Downloads images from external URLs
2. **Asset Creation**: Uploads images to Naas storage
3. **Triple Store Integration**: Updates ontology with asset references
4. **Duplicate Prevention**: Avoids processing existing assets
5. **Error Handling**: Graceful handling of download/upload failures

```python
from src.marketplace.modules.applications.naas.pipelines.ImageURLtoAssetPipeline import (
    ImageURLtoAssetPipeline,
    ImageURLtoAssetPipelineConfiguration,
    ImageURLtoAssetPipelineParameters
)

# Configure pipeline
config = ImageURLtoAssetPipelineConfiguration(
    triple_store=triple_store_service,
    naas_integration_config=naas_config
)

pipeline = ImageURLtoAssetPipeline(config)

# Process image URL
parameters = ImageURLtoAssetPipelineParameters(
    image_url="https://example.com/image.jpg",
    subject_uri="http://example.org/subject",
    predicate_uri="http://example.org/hasImage"
)

result = pipeline.run(parameters)
```

## Usage Examples

### Workspace Management

```bash
# Start Naas agent
make chat-naas-agent

# Example conversations:
# "Create a new workspace called 'Data Science Projects'"
# "Show me all my workspaces"
# "Update workspace ABC123 with name 'Client Projects'"
# "Delete workspace ABC123"
```

### Plugin Operations

```python
# Create plugin
plugin_data = {
    "name": "Chatbot Plugin",
    "type": "chatbot",
    "configuration": {...}
}
result = integration.create_plugin(workspace_id, plugin_data)

# List plugins
plugins = integration.get_plugins(workspace_id)
```

### Ontology Management

```python
# Create ontology
ontology = integration.create_ontology(
    workspace_id=workspace_id,
    label="Finance Terms",
    source="Financial domain vocabulary",
    level="DOMAIN",
    description="Financial terminology ontology"
)

# List ontologies
ontologies = integration.get_ontologies(workspace_id)
```

### User Management

```python
# Invite user
result = integration.invite_workspace_user(
    workspace_id=workspace_id,
    email="user@example.com",
    role="member"
)

# List users
users = integration.get_workspace_users(workspace_id)
```

### Secret Management

```python
# Create secret
secret = integration.create_secret(
    name="API_KEY",
    value="secret_value_123"
)

# List secrets
secrets = integration.list_secrets()
```

### Asset Management

```python
# Upload asset
asset = integration.upload_asset(
    data=image_bytes,
    workspace_id=workspace_id,
    storage_name="images",
    prefix="avatars/",
    object_name="user_avatar.jpg"
)

# List storage objects
objects = integration.list_workspace_storage_objects(
    workspace_id=workspace_id,
    storage_name="images",
    prefix="avatars/"
)
```

## Testing

### Run Tests

```bash
# Test image URL to asset pipeline
uv run python -m pytest src.marketplace.modules.applications.naas.pipelines/ImageURLtoAssetPipeline_test.py
```

## Configuration

### Environment Variables

Required environment variables:

```bash
# Naas API key for authentication
NAAS_API_KEY=your_naas_api_key

# OpenAI API key for the agent
OPENAI_API_KEY=your_openai_api_key
```

### API Configuration

The Naas integration uses the following default configuration:

- **Base URL**: `https://api.naas.ai`
- **Authentication**: Bearer token via API key
- **Content Type**: `application/json`

## Security Features

1. **API Key Authentication**: Secure Bearer token authentication
2. **JWT Token Handling**: User ID extraction from JWT tokens
3. **Secret Management**: Secure storage of sensitive data
4. **Asset Visibility Control**: Configurable asset visibility settings
5. **Role-Based Access**: User role and permission management

## Error Handling

The module provides comprehensive error handling:

1. **Connection Errors**: Network and API connectivity issues
2. **Authentication Errors**: Invalid API keys and permissions
3. **Validation Errors**: Input parameter validation
4. **Resource Errors**: Missing workspaces, plugins, or assets
5. **Upload Errors**: File upload and storage issues

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Verify NAAS_API_KEY is set correctly
2. **Workspace Not Found**: Ensure workspace ID exists and is accessible
3. **Permission Errors**: Check user role and workspace permissions
4. **Upload Failures**: Verify storage exists and has proper credentials
5. **Pipeline Errors**: Check image URL accessibility and storage configuration


## Dependencies

### Core Dependencies
- **abi**: Core ABI framework
- **langchain-openai**: OpenAI integration for agent functionality
- **requests**: HTTP client for API communication
- **pydantic**: Data validation and serialization

### Optional Dependencies
- **jwt**: JWT token handling
- **rdflib**: RDF graph operations for pipeline
- **pydash**: Utility functions for data manipulation
