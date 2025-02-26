# Integrations API

The Integrations API provides endpoints and interfaces for creating, managing, and using connections to external systems and services in the ABI framework. Integrations enable data exchange between ABI and various external platforms, APIs, and data sources.

## REST API

### Integration Management

#### Create Integration

Creates a new integration with the specified configuration.

```
POST /api/v1/integrations
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "GitHub Integration",
  "description": "Integration with GitHub API for repository data access",
  "type": "github",
  "configuration": {
    "api_url": "https://api.github.com",
    "auth_method": "oauth",
    "request_timeout": 30,
    "rate_limit_per_hour": 5000
  },
  "credentials": {
    "access_token": "ghp_abcdefghijklmnopqrstuvwxyz",
    "token_type": "bearer"
  },
  "metadata": {
    "department": "engineering",
    "owner": "data-team",
    "version": "1.0"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "int_123456789",
    "name": "GitHub Integration",
    "description": "Integration with GitHub API for repository data access",
    "type": "github",
    "configuration": {
      "api_url": "https://api.github.com",
      "auth_method": "oauth",
      "request_timeout": 30,
      "rate_limit_per_hour": 5000
    },
    "credentials": {
      "access_token": "••••••••••••••••••••••••••",
      "token_type": "bearer"
    },
    "metadata": {
      "department": "engineering",
      "owner": "data-team",
      "version": "1.0"
    },
    "status": "configured",
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-01T12:00:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### Get Integration

Returns details of a specific integration.

```
GET /api/v1/integrations/{integration_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "int_123456789",
    "name": "GitHub Integration",
    "description": "Integration with GitHub API for repository data access",
    "type": "github",
    "configuration": {
      "api_url": "https://api.github.com",
      "auth_method": "oauth",
      "request_timeout": 30,
      "rate_limit_per_hour": 5000
    },
    "credentials": {
      "access_token": "••••••••••••••••••••••••••",
      "token_type": "bearer"
    },
    "metadata": {
      "department": "engineering",
      "owner": "data-team",
      "version": "1.0"
    },
    "status": "active",
    "stats": {
      "last_used": "2023-05-02T10:15:30Z",
      "total_calls": 1024,
      "success_rate": 99.5,
      "average_response_time_ms": 245
    },
    "health": {
      "status": "healthy",
      "last_check": "2023-05-02T10:30:00Z",
      "message": "All systems operational"
    },
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-01T14:30:00Z",
    "activated_at": "2023-05-01T14:30:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### List Integrations

Returns a list of integrations with pagination.

```
GET /api/v1/integrations
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

```
page=1
page_size=10
sort_by=created_at
sort_order=desc
status=active
type=github
department=engineering
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "int_123456789",
        "name": "GitHub Integration",
        "description": "Integration with GitHub API for repository data access",
        "type": "github",
        "status": "active",
        "metadata": {
          "department": "engineering",
          "owner": "data-team",
          "version": "1.0"
        },
        "health": {
          "status": "healthy",
          "last_check": "2023-05-02T10:30:00Z"
        },
        "created_at": "2023-05-01T12:00:00Z",
        "updated_at": "2023-05-01T14:30:00Z"
      },
      {
        "id": "int_987654321",
        "name": "JIRA Integration",
        "description": "Integration with JIRA API for issue tracking",
        "type": "jira",
        "status": "active",
        "metadata": {
          "department": "engineering",
          "owner": "data-team",
          "version": "1.1"
        },
        "health": {
          "status": "healthy",
          "last_check": "2023-05-02T10:30:00Z"
        },
        "created_at": "2023-04-15T10:00:00Z",
        "updated_at": "2023-04-20T15:45:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total_items": 2,
      "total_pages": 1
    }
  }
}
```

#### Update Integration

Updates an existing integration.

```
PUT /api/v1/integrations/{integration_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "GitHub Enterprise Integration",
  "description": "Integration with GitHub Enterprise API for repository data access",
  "configuration": {
    "api_url": "https://github.enterprise.example.com/api/v3",
    "auth_method": "oauth",
    "request_timeout": 60,
    "rate_limit_per_hour": 10000
  },
  "metadata": {
    "department": "engineering",
    "owner": "data-team",
    "version": "1.1"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "int_123456789",
    "name": "GitHub Enterprise Integration",
    "description": "Integration with GitHub Enterprise API for repository data access",
    "type": "github",
    "configuration": {
      "api_url": "https://github.enterprise.example.com/api/v3",
      "auth_method": "oauth",
      "request_timeout": 60,
      "rate_limit_per_hour": 10000
    },
    "credentials": {
      "access_token": "••••••••••••••••••••••••••",
      "token_type": "bearer"
    },
    "metadata": {
      "department": "engineering",
      "owner": "data-team",
      "version": "1.1"
    },
    "status": "active",
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-02T09:30:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### Update Credentials

Updates the credentials for an integration.

```
PUT /api/v1/integrations/{integration_id}/credentials
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "credentials": {
    "access_token": "ghp_newabcdefghijklmnopqrstuvwxyz",
    "token_type": "bearer"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "int_123456789",
    "credentials": {
      "access_token": "••••••••••••••••••••••••••",
      "token_type": "bearer"
    },
    "updated_at": "2023-05-02T09:45:00Z"
  }
}
```

#### Activate Integration

Activates a configured integration.

```
POST /api/v1/integrations/{integration_id}/activate
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "int_123456789",
    "status": "active",
    "activated_at": "2023-05-01T14:30:00Z",
    "updated_at": "2023-05-01T14:30:00Z"
  }
}
```

#### Deactivate Integration

Deactivates an active integration.

```
POST /api/v1/integrations/{integration_id}/deactivate
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "int_123456789",
    "status": "inactive",
    "deactivated_at": "2023-05-02T16:20:00Z",
    "updated_at": "2023-05-02T16:20:00Z"
  }
}
```

#### Test Integration

Tests the connection to the external system.

```
POST /api/v1/integrations/{integration_id}/test
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "int_123456789",
    "connection_test": {
      "success": true,
      "latency_ms": 127,
      "message": "Successfully connected to GitHub API",
      "timestamp": "2023-05-02T16:25:00Z"
    }
  }
}
```

#### Delete Integration

Deletes an integration.

```
DELETE /api/v1/integrations/{integration_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "int_123456789",
    "deleted": true
  }
}
```

### Integration Operations

#### Execute Operation

Executes an operation on the integration.

```
POST /api/v1/integrations/{integration_id}/operations/{operation}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "parameters": {
    "repository": "owner/repo",
    "since": "2023-01-01T00:00:00Z",
    "per_page": 100
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "operation_id": "op_123456789",
    "integration_id": "int_123456789",
    "operation": "get_issues",
    "status": "completed",
    "started_at": "2023-05-02T16:30:00Z",
    "completed_at": "2023-05-02T16:30:01Z",
    "duration_ms": 1024,
    "result": {
      "total_count": 42,
      "items": [
        {
          "id": 1234567890,
          "number": 123,
          "title": "Fix bug in login process",
          "state": "open",
          "created_at": "2023-03-15T10:30:00Z",
          "updated_at": "2023-04-01T14:20:00Z",
          "author": {
            "id": 9876543,
            "login": "username"
          }
        },
        // More items...
      ]
    }
  }
}
```

#### List Available Operations

Returns a list of available operations for an integration.

```
GET /api/v1/integrations/{integration_id}/operations
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "operations": [
      {
        "id": "get_repository",
        "name": "Get Repository",
        "description": "Retrieves information about a GitHub repository",
        "parameters": [
          {
            "name": "owner",
            "type": "string",
            "description": "Repository owner",
            "required": true
          },
          {
            "name": "repo",
            "type": "string",
            "description": "Repository name",
            "required": true
          }
        ],
        "result_schema": {
          "type": "object",
          "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
            "full_name": {"type": "string"},
            "description": {"type": "string"},
            "html_url": {"type": "string"}
          }
        }
      },
      {
        "id": "get_issues",
        "name": "Get Issues",
        "description": "Retrieves issues for a GitHub repository",
        "parameters": [
          {
            "name": "repository",
            "type": "string",
            "description": "Repository in format 'owner/repo'",
            "required": true
          },
          {
            "name": "since",
            "type": "string",
            "format": "date-time",
            "description": "Only issues updated at or after this time",
            "required": false
          },
          {
            "name": "per_page",
            "type": "integer",
            "description": "Results per page (max 100)",
            "required": false,
            "default": 30
          }
        ],
        "result_schema": {
          "type": "object",
          "properties": {
            "total_count": {"type": "integer"},
            "items": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {"type": "integer"},
                  "number": {"type": "integer"},
                  "title": {"type": "string"},
                  "state": {"type": "string"},
                  "created_at": {"type": "string", "format": "date-time"},
                  "updated_at": {"type": "string", "format": "date-time"}
                }
              }
            }
          }
        }
      }
    ]
  }
}
```

#### Get Operation Status

Returns the status of an operation.

```
GET /api/v1/integrations/{integration_id}/operations/{operation}/{operation_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "operation_id": "op_123456789",
    "integration_id": "int_123456789",
    "operation": "get_issues",
    "status": "completed",
    "started_at": "2023-05-02T16:30:00Z",
    "completed_at": "2023-05-02T16:30:01Z",
    "duration_ms": 1024,
    "parameters": {
      "repository": "owner/repo",
      "since": "2023-01-01T00:00:00Z",
      "per_page": 100
    },
    "result": {
      "total_count": 42,
      "items": [
        {
          "id": 1234567890,
          "number": 123,
          "title": "Fix bug in login process",
          "state": "open",
          "created_at": "2023-03-15T10:30:00Z",
          "updated_at": "2023-04-01T14:20:00Z",
          "author": {
            "id": 9876543,
            "login": "username"
          }
        },
        // More items...
      ]
    }
  }
}
```

### Integration Health

#### Get Health Status

Returns the health status of an integration.

```
GET /api/v1/integrations/{integration_id}/health
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "integration_id": "int_123456789",
    "health": {
      "status": "healthy",
      "last_check": "2023-05-02T16:30:00Z",
      "message": "All systems operational",
      "checks": [
        {
          "name": "connection",
          "status": "passed",
          "latency_ms": 127,
          "message": "Successfully connected to GitHub API"
        },
        {
          "name": "authentication",
          "status": "passed",
          "message": "Successfully authenticated"
        },
        {
          "name": "rate_limit",
          "status": "passed",
          "message": "Rate limit: 4978/5000 remaining"
        },
        {
          "name": "permissions",
          "status": "passed",
          "message": "All required permissions granted"
        }
      ],
      "metrics": {
        "success_rate_24h": 99.8,
        "average_latency_ms": 245,
        "error_rate": 0.2,
        "total_calls_24h": 1245
      }
    }
  }
}
```

#### Check Integration Health

Triggers a health check for an integration.

```
POST /api/v1/integrations/{integration_id}/health/check
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "integration_id": "int_123456789",
    "health_check": {
      "status": "healthy",
      "timestamp": "2023-05-02T16:35:00Z",
      "message": "All systems operational",
      "checks": [
        {
          "name": "connection",
          "status": "passed",
          "latency_ms": 125,
          "message": "Successfully connected to GitHub API"
        },
        {
          "name": "authentication",
          "status": "passed",
          "message": "Successfully authenticated"
        },
        {
          "name": "rate_limit",
          "status": "passed",
          "message": "Rate limit: 4975/5000 remaining"
        },
        {
          "name": "permissions",
          "status": "passed",
          "message": "All required permissions granted"
        }
      ]
    }
  }
}
```

## Python API

### Integration Management

```python
from abi.integrations import IntegrationManager, IntegrationConfig

# Initialize the integration manager
integration_manager = IntegrationManager(access_token=access_token)

# Create an integration
integration_config = IntegrationConfig(
    name="GitHub Integration",
    description="Integration with GitHub API for repository data access",
    type="github",
    configuration={
        "api_url": "https://api.github.com",
        "auth_method": "oauth",
        "request_timeout": 30,
        "rate_limit_per_hour": 5000
    },
    credentials={
        "access_token": "ghp_abcdefghijklmnopqrstuvwxyz",
        "token_type": "bearer"
    },
    metadata={
        "department": "engineering",
        "owner": "data-team",
        "version": "1.0"
    }
)

integration = integration_manager.create_integration(integration_config)
print(f"Created integration with ID: {integration.id}")

# Get integration by ID
integration = integration_manager.get_integration(integration.id)

# List integrations
integrations = integration_manager.list_integrations(
    status="active",
    type="github",
    department="engineering",
    page=1,
    page_size=10
)

for intg in integrations.items:
    print(f"{intg.id}: {intg.name} - Status: {intg.status}")

# Update an integration
integration.name = "GitHub Enterprise Integration"
integration.description = "Integration with GitHub Enterprise API for repository data access"
integration.configuration["api_url"] = "https://github.enterprise.example.com/api/v3"
integration.configuration["request_timeout"] = 60
integration.metadata["version"] = "1.1"

updated_integration = integration_manager.update_integration(integration)

# Update credentials
integration_manager.update_credentials(
    integration_id=integration.id,
    credentials={
        "access_token": "ghp_newabcdefghijklmnopqrstuvwxyz",
        "token_type": "bearer"
    }
)

# Activate/deactivate an integration
integration_manager.activate_integration(integration.id)
integration_manager.deactivate_integration(integration.id)

# Test an integration
test_result = integration_manager.test_integration(integration.id)
print(f"Test result: {test_result.success} - {test_result.message}")

# Delete an integration
integration_manager.delete_integration(integration.id)
```

### Integration Operations

```python
from abi.integrations import IntegrationClient

# Initialize the integration client
client = IntegrationClient(access_token=access_token)

# Get a specific integration client
github = client.get_integration_client("int_123456789")

# List available operations
operations = github.list_operations()
for op in operations:
    print(f"{op.id}: {op.name} - {op.description}")

# Execute an operation
result = github.execute_operation(
    operation="get_issues",
    parameters={
        "repository": "owner/repo",
        "since": "2023-01-01T00:00:00Z",
        "per_page": 100
    }
)

print(f"Operation ID: {result.operation_id}")
print(f"Status: {result.status}")
print(f"Total issues: {result.result['total_count']}")

# Get operation status
operation_status = github.get_operation_status(
    operation="get_issues",
    operation_id="op_123456789"
)

print(f"Operation status: {operation_status.status}")
```

### Using Direct Integration Interfaces

```python
from abi.integrations import GitHubIntegration, GitHubIntegrationConfiguration

# Initialize with configuration
github_config = GitHubIntegrationConfiguration(
    api_url="https://api.github.com",
    access_token="ghp_abcdefghijklmnopqrstuvwxyz",
    request_timeout=30
)

github = GitHubIntegration(github_config)

# Use type-specific methods directly
repository = github.get_repository("owner", "repo")
print(f"Repository: {repository['name']}")

issues = github.get_issues(
    owner="owner",
    repo="repo",
    state="open",
    since="2023-01-01T00:00:00Z"
)
print(f"Found {len(issues)} open issues")

# Create an issue
new_issue = github.create_issue(
    owner="owner",
    repo="repo",
    title="Fix authentication bug",
    body="The login process fails when using special characters in the password",
    labels=["bug", "priority:high"]
)
print(f"Created issue #{new_issue['number']}")
```

### Integration Health Monitoring

```python
from abi.integrations import IntegrationHealthMonitor

# Initialize the health monitor
health_monitor = IntegrationHealthMonitor(access_token=access_token)

# Get health status
health = health_monitor.get_health_status("int_123456789")
print(f"Health status: {health.status} - {health.message}")
print(f"Success rate (24h): {health.metrics.success_rate_24h}%")

# Perform a health check
check_result = health_monitor.check_health("int_123456789")
for check in check_result.checks:
    print(f"{check.name}: {check.status} - {check.message}")
```

## Integration Types

ABI supports various integration types:

| Type | Description | 
|------|-------------|
| github | Integration with GitHub repositories |
| jira | Integration with JIRA issue tracking |
| slack | Integration with Slack messaging platform |
| salesforce | Integration with Salesforce CRM |
| zendesk | Integration with Zendesk support platform |
| google_workspace | Integration with Google Workspace |
| microsoft_365 | Integration with Microsoft 365 |
| hubspot | Integration with HubSpot CRM |
| custom | Custom integration implementation |

## Integration Configuration

### Authentication Methods

Integrations support various authentication methods:

1. **API Key**:
   ```python
   config = {
       "auth_method": "api_key",
       "credentials": {
           "api_key": "your-api-key",
           "header_name": "X-API-Key"  # Optional, defaults to "Authorization"
       }
   }
   ```

2. **OAuth**:
   ```python
   config = {
       "auth_method": "oauth",
       "credentials": {
           "access_token": "your-access-token",
           "token_type": "bearer",
           "refresh_token": "your-refresh-token",  # Optional
           "expires_at": "2023-12-31T23:59:59Z"    # Optional
       }
   }
   ```

3. **Basic Auth**:
   ```python
   config = {
       "auth_method": "basic",
       "credentials": {
           "username": "your-username",
           "password": "your-password"
       }
   }
   ```

4. **JWT**:
   ```python
   config = {
       "auth_method": "jwt",
       "credentials": {
           "jwt_token": "your-jwt-token"
       }
   }
   ```

### Rate Limiting

Configure rate limiting for integrations:

```python
config = {
    "rate_limiting": {
        "requests_per_second": 10,
        "requests_per_minute": 500,
        "requests_per_hour": 5000,
        "max_concurrent_requests": 20,
        "retry_after_seconds": 5,
        "max_retries": 3
    }
}
```

### Request Configuration

Configure request behavior:

```python
config = {
    "request": {
        "timeout_seconds": 30,
        "connect_timeout_seconds": 10,
        "read_timeout_seconds": 30,
        "max_redirects": 5,
        "verify_ssl": true,
        "user_agent": "ABI Integration Client/1.0",
        "default_headers": {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    }
}
```

## Error Handling

Common errors when working with integrations:

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| 400 | INVALID_INTEGRATION_CONFIG | Invalid integration configuration |
| 400 | INVALID_CREDENTIALS | Invalid credentials format |
| 400 | INVALID_OPERATION | Invalid operation or parameters |
| 401 | AUTHENTICATION_FAILED | Authentication failed with the external system |
| 403 | PERMISSION_DENIED | Permission denied by the external system |
| 404 | INTEGRATION_NOT_FOUND | Integration not found |
| 404 | OPERATION_NOT_FOUND | Operation not found |
| 409 | RATE_LIMIT_EXCEEDED | Rate limit exceeded on the external system |
| 422 | PARAMETER_VALIDATION_ERROR | Parameter validation failed |
| 500 | INTEGRATION_ERROR | Error in the integration |
| 502 | EXTERNAL_SERVICE_ERROR | Error from the external service |
| 504 | EXTERNAL_SERVICE_TIMEOUT | Timeout from the external service |

## Event Webhooks

You can configure webhooks to receive events from integrations:

```
POST /api/v1/webhooks
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "url": "https://example.com/webhooks/integrations",
  "events": ["integration.created", "integration.health_changed", "operation.completed"],
  "secret": "whsec_abcdefghijklmnopqrstuvwxyz",
  "description": "Production webhook for integration events"
}
```

### Webhook Event Types

| Event Type | Description |
|------------|-------------|
| integration.created | Fired when a new integration is created |
| integration.updated | Fired when an integration is updated |
| integration.credentials_updated | Fired when integration credentials are updated |
| integration.activated | Fired when an integration is activated |
| integration.deactivated | Fired when an integration is deactivated |
| integration.deleted | Fired when an integration is deleted |
| integration.health_changed | Fired when integration health status changes |
| operation.started | Fired when an operation starts |
| operation.completed | Fired when an operation completes |
| operation.failed | Fired when an operation fails |

## Best Practices

1. **Credential Management**:
   - Store sensitive credentials securely
   - Rotate credentials regularly
   - Use OAuth where available instead of basic auth
   - Set up monitoring for credential expiration

2. **Rate Limit Management**:
   - Respect API rate limits of external services
   - Implement backoff strategies for rate limiting
   - Batch requests when possible
   - Schedule non-urgent operations during off-peak hours

3. **Error Handling**:
   - Implement proper error handling for API calls
   - Set up retries with backoff for transient errors
   - Log detailed error information for debugging
   - Notify administrators of persistent integration issues

4. **Performance Optimization**:
   - Use connection pooling for efficiency
   - Implement caching for frequently accessed data
   - Minimize payload sizes in requests and responses
   - Set appropriate timeouts for operations

5. **Monitoring and Alerting**:
   - Set up health checks for all integrations
   - Monitor success rates and error rates
   - Alert on integration health changes
   - Track usage patterns and performance metrics

## Next Steps

- Learn about [Pipelines API](pipelines.md) to process data from integrations
- Explore the [Workflows API](workflows.md) to create business processes using integrations
- Check the [Assistants API](assistants.md) to create interfaces that leverage integrations 