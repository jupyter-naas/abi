# Integrations

This document explains the concept of Integrations in the ABI framework, their purpose, implementation, and how they connect ABI to external systems.

## What are Integrations?

Integrations are modular components that connect ABI to external systems, services, and data sources. They provide standardized interfaces for interacting with various platforms, handling authentication, data retrieval, and transformation between ABI and external services.

## Key Features

- **Unified Interface**: Common patterns for interacting with diverse external systems
- **Authentication Management**: Handle various authentication methods (OAuth, API keys, etc.)
- **Error Handling**: Standardized error handling and retry mechanisms
- **Rate Limiting**: Respect API rate limits of external services
- **Data Transformation**: Convert between external data formats and ABI's internal representations
- **Caching**: Optimize performance through intelligent caching of responses

## Integration Architecture

```
┌───────────────────────────────────────────────────────────┐
│                      Integration                          │
│                                                           │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────┐  │
│  │  Auth         │    │  Request      │    │  Response │  │
│  │  Manager      │───►│  Builder      │───►│  Parser   │  │
│  │               │    │               │    │           │  │
│  └───────────────┘    └───────────────┘    └───────────┘  │
│                              │                  ▲         │
│                              ▼                  │         │
│                       ┌───────────────┐         │         │
│                       │  HTTP/API     │         │         │
│                       │  Client       │─────────┘         │
│                       │               │                   │
│                       └───────────────┘                   │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## Types of Integrations

ABI supports various types of integrations:

### API Integrations

Connect to REST, GraphQL, or SOAP APIs of external services like Salesforce, Jira, or Google Workspace.

### Database Integrations

Connect to relational databases (MySQL, PostgreSQL), NoSQL databases (MongoDB), or data warehouses (Snowflake, BigQuery).

### File System Integrations

Interact with local file systems, cloud storage (S3, GCS), or document management systems.

### Messaging System Integrations

Connect to messaging platforms like Slack, Microsoft Teams, or email systems.

### Custom Protocol Integrations

Support for specialized protocols or legacy systems with custom communication methods.

## Integration Components

### Configuration

Defines connection parameters, credentials, and behavior settings:

```python
@dataclass
class SalesforceIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Salesforce integration.
    
    Attributes:
        client_id (str): OAuth client ID
        client_secret (str): OAuth client secret
        username (str): Salesforce username
        password (str): Salesforce password
        security_token (str): Salesforce security token
        instance_url (str): Salesforce instance URL
    """
    client_id: str
    client_secret: str
    username: str
    password: str
    security_token: str
    instance_url: str
```

### Authentication

Handles authentication with the external system:

```python
def authenticate(self):
    """Authenticate with Salesforce and obtain access token."""
    auth_url = f"{self.__configuration.instance_url}/services/oauth2/token"
    payload = {
        'grant_type': 'password',
        'client_id': self.__configuration.client_id,
        'client_secret': self.__configuration.client_secret,
        'username': self.__configuration.username,
        'password': f"{self.__configuration.password}{self.__configuration.security_token}"
    }
    response = requests.post(auth_url, data=payload)
    response.raise_for_status()
    
    auth_data = response.json()
    self.__access_token = auth_data['access_token']
    self.__instance_url = auth_data['instance_url']
```

### API Methods

Methods for interacting with specific endpoints or features of the external system:

```python
def query(self, soql_query: str) -> List[Dict]:
    """Execute a SOQL query against Salesforce.
    
    Args:
        soql_query (str): The SOQL query to execute
        
    Returns:
        List[Dict]: List of records matching the query
    """
    endpoint = f"{self.__instance_url}/services/data/v54.0/query"
    headers = {
        'Authorization': f'Bearer {self.__access_token}',
        'Content-Type': 'application/json'
    }
    params = {'q': soql_query}
    
    response = requests.get(endpoint, headers=headers, params=params)
    response.raise_for_status()
    
    result = response.json()
    return result['records']
```

## Creating an Integration

A simplified example of creating a custom integration:

```python
from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
import requests

@dataclass
class JiraIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Jira integration.
    
    Attributes:
        base_url (str): Jira instance URL
        username (str): Jira username or email
        api_token (str): Jira API token
    """
    base_url: str
    username: str
    api_token: str

class JiraIntegration(Integration):
    """Integration for Jira issue tracking system.
    
    This class provides methods to interact with Jira's REST API endpoints.
    """
    
    __configuration: JiraIntegrationConfiguration
    
    def __init__(self, configuration: JiraIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__session = requests.Session()
        self.__session.auth = (configuration.username, configuration.api_token)
        self.__session.headers.update({"Accept": "application/json"})
    
    def get_issue(self, issue_key: str) -> dict:
        """Retrieve a Jira issue by its key.
        
        Args:
            issue_key (str): The Jira issue key (e.g., 'PROJECT-123')
            
        Returns:
            dict: The issue data
        """
        url = f"{self.__configuration.base_url}/rest/api/2/issue/{issue_key}"
        response = self.__session.get(url)
        response.raise_for_status()
        return response.json()
```

## Using Integrations in Pipelines and Workflows

Integrations are typically used within pipelines and workflows:

```python
# Using an integration in a pipeline
class JiraTicketPipeline(Pipeline):
    __configuration: JiraTicketPipelineConfiguration
    
    def __init__(self, configuration: JiraTicketPipelineConfiguration):
        self.__configuration = configuration
        self.__jira = configuration.jira_integration
    
    def run(self, parameters: JiraTicketPipelineParameters) -> Graph:
        # Use the integration to fetch data
        issue_data = self.__jira.get_issue(parameters.issue_key)
        
        # Process the data and create a graph
        graph = ABIGraph()
        # ... process and add to graph
        
        return graph
```

## Next Steps

- Learn how to [Build Integrations](../guides/building-integrations.md)
- Understand how [Pipelines](pipelines.md) use integrations for data processing
- Explore how [Workflows](workflows.md) orchestrate integrations for business processes 