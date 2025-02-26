# API Reference Overview

This section provides detailed reference documentation for the ABI API. The ABI framework exposes both a REST API for external integrations and a Python API for internal development.

## API Architecture

The ABI API follows a layered architecture:

1. **REST API Layer**: External HTTP endpoints using FastAPI
2. **Python API Layer**: Internal programmatic interfaces
3. **Service Layer**: Core business logic implementations
4. **Repository Layer**: Data access and persistence

![API Architecture Diagram](../assets/images/api-architecture.png)

## API Categories

The ABI API is organized into the following major categories:

### Core API
- **Assistant Management**: Create, configure, and interact with AI assistants
- **Workflow Management**: Manage and execute business workflows
- **Pipeline Management**: Control data processing pipelines
- **Integration Management**: Configure and use external integrations
- **Ontology Management**: Access and query the knowledge graph

### System API
- **Authentication & Authorization**: User and API key management
- **Configuration**: System configuration settings
- **Logging & Monitoring**: System health and performance metrics
- **Storage Management**: File and data storage operations

## REST API Conventions

The ABI REST API follows these conventions:

### Base URL

All API endpoints are relative to the base URL:

```
https://{hostname}/api/v1
```

For local development, this would typically be:

```
http://localhost:8000/api/v1
```

### Authentication

ABI API endpoints use API keys for authentication. Include your API key in the request header:

```
Authorization: Bearer {your_api_key}
```

### Request Format

API requests accept JSON payloads with snake_case property names:

```json
{
  "property_name": "value",
  "another_property": 123
}
```

### Response Format

API responses return JSON with a standard format:

```json
{
  "status": "success",
  "data": {
    // Response data here
  },
  "message": null,
  "errors": null
}
```

For error responses:

```json
{
  "status": "error",
  "data": null,
  "message": "Error description",
  "errors": [
    {
      "code": "ERROR_CODE",
      "detail": "Detailed error information"
    }
  ]
}
```

### HTTP Methods

The API uses standard HTTP methods:

- `GET`: Retrieve resources
- `POST`: Create resources
- `PUT`: Update resources (complete replacement)
- `PATCH`: Partial update of resources
- `DELETE`: Remove resources

### Status Codes

ABI API uses standard HTTP status codes:

- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `204 No Content`: Successful request with no response body
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication failure
- `403 Forbidden`: Permission denied
- `404 Not Found`: Resource not found
- `409 Conflict`: Request conflicts with current state
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server-side error

### Pagination

List endpoints support pagination with these query parameters:

- `page`: Page number (starting from 1)
- `page_size`: Number of items per page
- `sort_by`: Field to sort by
- `sort_order`: 'asc' or 'desc'

Paginated responses include metadata:

```json
{
  "status": "success",
  "data": {
    "items": [...],
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total_items": 42,
      "total_pages": 5
    }
  }
}
```

### Filtering

List endpoints support filtering with query parameters:

```
GET /api/v1/resources?field_name=value&created_after=2023-01-01T00:00:00Z
```

### Rate Limiting

API requests are subject to rate limiting. The current limits are included in response headers:

```
X-Rate-Limit-Limit: 100
X-Rate-Limit-Remaining: 99
X-Rate-Limit-Reset: 1620000000
```

## Python API Conventions

The ABI Python API follows these conventions:

### Module Structure

```
abi/
  assistants/
  workflows/
  pipelines/
  integrations/
  ontology/
  services/
  utils/
```

### Class Naming

Classes use PascalCase:

```python
class AssistantManager:
    ...

class WorkflowExecutor:
    ...
```

### Method Naming

Methods use snake_case:

```python
def create_assistant(self, config):
    ...

def execute_workflow(self, parameters):
    ...
```

### Exception Handling

API operations raise specific exception types:

```python
from abi.exceptions import ResourceNotFoundError, ValidationError, AuthenticationError

try:
    result = api.get_resource(resource_id)
except ResourceNotFoundError:
    # Handle not found
except ValidationError as e:
    # Handle validation errors
    print(e.errors)
except AuthenticationError:
    # Handle authentication issues
```

### Asynchronous Support

The Python API supports both synchronous and asynchronous operation:

```python
# Synchronous
result = api.execute_workflow(params)

# Asynchronous
result = await api.execute_workflow_async(params)
```

## API Versioning

ABI API is versioned to ensure backward compatibility:

- REST API: Version in URL path (`/api/v1/...`)
- Python API: Version in import path (`from abi.v1 import ...`)

Breaking changes are only introduced in major version increments.

## API Reference Sections

Explore detailed documentation for each API category:

- [Authentication](authentication.md)
- [Assistants API](assistants.md)
- [Workflows API](workflows.md)
- [Pipelines API](pipelines.md)
- [Integrations API](integrations.md)
- [Ontology API](ontology.md)
- [System API](system.md)

## Getting Help

If you encounter issues with the API:

1. Check the appropriate reference documentation
2. Look for error messages in the API response
3. Consult the [troubleshooting guide](../deployment/troubleshooting.md)
4. Check for known issues in the [issue tracker](https://github.com/organization/abi/issues)
5. Contact support at support@example.com 