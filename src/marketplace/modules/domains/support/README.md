# Support Module

## Description

The Support Module provides comprehensive GitHub integration for issue management, enabling users to create feature requests, report bugs, and manage GitHub issues through an AI-powered interface.

Key Features:
- GitHub issue creation and management
- Feature request and bug report workflows
- GitHub REST API and GraphQL integration
- AI-powered support assistant
- Issue search and duplicate detection
- Project management integration

## TL;DR

- Start the Support agent:
```bash
make chat-support-agent
```
- Or use the generic chat command:
```bash
make chat Agent=SupportAgent
```

## Overview

### Structure

```
src.marketplace.modules.domains.support/
├── agents/                                        # AI agents
│   └── SupportAgent.py                           # Main support assistant agent
├── workflows/                                     # Business workflows
│   └── GitHubSupportWorkflows.py                 # GitHub issue management workflows
├── integrations/                                  # API integrations
│   ├── GithubIntegration.py                      # GitHub REST API integration
│   └── GithubGraphqlIntegration.py               # GitHub GraphQL API integration
└── README.md                                      # This documentation
```

### Core Components

- **SupportAgent**: AI agent for natural language interaction with GitHub support services
- **GitHubSupportWorkflows**: Workflow orchestration for issue management
- **GithubIntegration**: Complete GitHub REST API integration
- **GithubGraphqlIntegration**: GitHub GraphQL API integration for advanced features

## Agents

### Support Agent

An AI agent that provides natural language interface for GitHub issue management:

1. **Issue Analysis**: Identifies user intent (feature request vs bug report)
2. **Duplicate Detection**: Searches for existing similar issues
3. **Issue Creation**: Creates new feature requests or bug reports
4. **Issue Updates**: Updates existing issues with new information
5. **Project Integration**: Manages issues within GitHub projects

```python
from src.marketplace.modules.domains.support.agents.SupportAgent import create_agent

# Create agent
agent = create_agent()

# Use agent for support operations
# The agent provides natural language interface to GitHub issue management
```

## Workflows

### GitHub Support Workflows

Orchestrates GitHub issue management operations:

1. **List Issues**: Search and filter existing issues
2. **Get Issue Details**: Retrieve specific issue information
3. **Create Bug Reports**: Generate structured bug reports
4. **Create Feature Requests**: Generate feature request issues
5. **Issue Validation**: Validate input parameters before creation

```python
from src.marketplace.modules.domains.support.workflows.GitHubSupportWorkflows import (
    GitHubSupportWorkflows,
    GitHubSupportWorkflowsConfiguration
)

# Configure workflow
config = GitHubSupportWorkflowsConfiguration(
    github_integration_config=github_config,
    github_graphql_integration_config=graphql_config
)

workflow = GitHubSupportWorkflows(config)

# Use workflow methods
issues = workflow.list_issues(parameters)
```

## Integrations

### GitHub REST API Integration

Complete integration with GitHub's REST API:

1. **Repository Management**: Create, update, and delete repositories
2. **Issue Operations**: Full CRUD operations for issues and comments
3. **User Management**: Get user details and manage assignees
4. **Secret Management**: Handle repository secrets securely
5. **Activity Tracking**: Monitor repository activities

```python
from src.marketplace.modules.domains.support.integrations.GithubIntegration import (
    GithubIntegration,
    GithubIntegrationConfiguration
)

# Configure integration
config = GithubIntegrationConfiguration(
    access_token="your_github_token"
)

integration = GithubIntegration(config)

# Use integration methods
issues = integration.list_issues("owner/repo")
```

### GitHub GraphQL Integration

Advanced integration using GitHub's GraphQL API:

1. **Project Management**: Manage GitHub projects and boards
2. **Advanced Queries**: Complex data retrieval and filtering
3. **Item Management**: Add and manage items in projects
4. **Field Operations**: Handle custom project fields

```python
from src.marketplace.modules.domains.support.integrations.GithubGraphqlIntegration import (
    GithubGraphqlIntegration,
    GithubGraphqlIntegrationConfiguration
)

# Configure integration
config = GithubGraphqlIntegrationConfiguration(
    access_token="your_github_token"
)

integration = GithubGraphqlIntegration(config)

# Use integration methods
project_data = integration.get_project_node_id("org", 1)
```

## Usage Examples

### Support Agent Interaction

```bash
# Start Support agent
make chat-support-agent

# Example conversations:
# "I need a new feature to integrate with external API"
# "Report a bug: the login page is not working"
# "Show me existing issues about authentication"
# "Update issue #123 with additional information"
```

### Issue Management

```python
# List issues
issues = workflow.list_issues(ListIssuesParameters(
    repo_name="owner/repo",
    state="open",
    limit=10
))

# Create bug report
result = workflow.report_bug(ReportBugParameters(
    repo_name="owner/repo",
    issue_title="Login page not working",
    issue_body="Users cannot log in when using Chrome browser..."
))

# Create feature request
result = workflow.create_feature_request(FeatureRequestParameters(
    repo_name="owner/repo",
    issue_title="Add external API integration",
    issue_body="We need to integrate with external service..."
))
```

### Repository Operations

```python
# Get repository details
repo = integration.get_repository_details("owner/repo")

# Create issue
issue = integration.create_issue(
    repo_name="owner/repo",
    title="Bug Report",
    body="Description of the bug",
    labels=["bug"],
    assignees=["username"]
)

# List issues with filters
issues = integration.list_issues(
    repo_name="owner/repo",
    state="open",
    labels="bug,urgent",
    limit=20
)
```

### Project Management

```python
# Get project details
project = graphql_integration.get_project_node_id("organization", 1)

# Add issue to project
result = graphql_integration.add_issue_to_project(
    project_node_id=project_id,
    issue_node_id=issue_id,
    status_field_id=status_id,
    priority_field_id=priority_id
)
```

## Configuration

### Environment Variables

Required environment variables:

```bash
# GitHub access token for API authentication
GITHUB_ACCESS_TOKEN=your_github_access_token

# OpenAI API key for the agent
OPENAI_API_KEY=your_openai_api_key

# GitHub support repository (optional, has default)
GITHUB_SUPPORT_REPOSITORY=owner/repo
```

### API Configuration

The GitHub integrations use the following default configuration:

- **REST API URL**: `https://api.github.com`
- **GraphQL API URL**: `https://api.github.com/graphql`
- **Authentication**: Bearer token via access token
- **Content Type**: `application/json`

## Security Features

1. **Token Authentication**: Secure Bearer token authentication
2. **Secret Management**: Secure storage of GitHub tokens
3. **Input Validation**: Parameter validation before API calls
4. **Error Handling**: Graceful handling of authentication failures
5. **Permission Checks**: Verify user permissions before operations

## Error Handling

The module provides comprehensive error handling:

1. **Connection Errors**: Network and API connectivity issues
2. **Authentication Errors**: Invalid tokens and permissions
3. **Validation Errors**: Input parameter validation
4. **Resource Errors**: Missing repositories or issues
5. **Rate Limiting**: GitHub API rate limit handling

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Verify GITHUB_ACCESS_TOKEN is set correctly
2. **Repository Not Found**: Ensure repository exists and is accessible
3. **Permission Errors**: Check token permissions and repository access
4. **Rate Limiting**: Monitor GitHub API rate limits
5. **GraphQL Errors**: Verify GraphQL query syntax and permissions

## Dependencies

### Core Dependencies
- **abi**: Core ABI framework
- **langchain-openai**: OpenAI integration for agent functionality
- **requests**: HTTP client for API communication
- **pydantic**: Data validation and serialization

### Optional Dependencies
- **fastapi**: API router functionality
- **dataclasses**: Configuration management
