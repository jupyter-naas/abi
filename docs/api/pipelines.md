# Pipelines API

The Pipelines API provides endpoints and interfaces for creating, managing, and executing data processing pipelines in the ABI framework. Pipelines extract data from external systems, transform it, and load it into the ontology store.

## REST API

### Pipeline Management

#### Create Pipeline

Creates a new pipeline with the specified configuration.

```
POST /api/v1/pipelines
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "GitHub Repository Pipeline",
  "description": "Extracts data from GitHub repositories and loads it into the ontology",
  "type": "github_repository",
  "configuration": {
    "ontology_store_name": "github_data",
    "include_issues": true,
    "include_pull_requests": true,
    "include_contributors": true,
    "max_items_per_category": 100
  },
  "integrations": [
    {
      "id": "int_github",
      "required": true
    }
  ],
  "metadata": {
    "department": "engineering",
    "priority": "medium",
    "version": "1.0"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "pl_123456789",
    "name": "GitHub Repository Pipeline",
    "description": "Extracts data from GitHub repositories and loads it into the ontology",
    "type": "github_repository",
    "configuration": {
      "ontology_store_name": "github_data",
      "include_issues": true,
      "include_pull_requests": true,
      "include_contributors": true,
      "max_items_per_category": 100
    },
    "integrations": [
      {
        "id": "int_github",
        "required": true,
        "status": "pending"
      }
    ],
    "metadata": {
      "department": "engineering",
      "priority": "medium",
      "version": "1.0"
    },
    "status": "inactive",
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-01T12:00:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### Get Pipeline

Returns details of a specific pipeline.

```
GET /api/v1/pipelines/{pipeline_id}
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
    "id": "pl_123456789",
    "name": "GitHub Repository Pipeline",
    "description": "Extracts data from GitHub repositories and loads it into the ontology",
    "type": "github_repository",
    "configuration": {
      "ontology_store_name": "github_data",
      "include_issues": true,
      "include_pull_requests": true,
      "include_contributors": true,
      "max_items_per_category": 100
    },
    "integrations": [
      {
        "id": "int_github",
        "required": true,
        "status": "connected"
      }
    ],
    "metadata": {
      "department": "engineering",
      "priority": "medium",
      "version": "1.0"
    },
    "status": "active",
    "stats": {
      "runs_total": 78,
      "runs_success": 75,
      "runs_failed": 3,
      "entities_created": 4256,
      "average_duration_ms": 3450
    },
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-01T14:30:00Z",
    "activated_at": "2023-05-01T14:30:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### List Pipelines

Returns a list of pipelines with pagination.

```
GET /api/v1/pipelines
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
type=github_repository
department=engineering
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "pl_123456789",
        "name": "GitHub Repository Pipeline",
        "description": "Extracts data from GitHub repositories and loads it into the ontology",
        "type": "github_repository",
        "status": "active",
        "metadata": {
          "department": "engineering",
          "priority": "medium",
          "version": "1.0"
        },
        "created_at": "2023-05-01T12:00:00Z",
        "updated_at": "2023-05-01T14:30:00Z"
      },
      {
        "id": "pl_987654321",
        "name": "JIRA Issues Pipeline",
        "description": "Extracts JIRA issues and loads them into the ontology",
        "type": "jira_issues",
        "status": "active",
        "metadata": {
          "department": "engineering",
          "priority": "high",
          "version": "1.2"
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

#### Update Pipeline

Updates an existing pipeline.

```
PUT /api/v1/pipelines/{pipeline_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "Enhanced GitHub Repository Pipeline",
  "description": "Extracts comprehensive data from GitHub repositories and loads it into the ontology",
  "configuration": {
    "ontology_store_name": "github_data",
    "include_issues": true,
    "include_pull_requests": true,
    "include_contributors": true,
    "include_commit_history": true,
    "max_items_per_category": 200
  },
  "metadata": {
    "department": "engineering",
    "priority": "high",
    "version": "1.1"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "pl_123456789",
    "name": "Enhanced GitHub Repository Pipeline",
    "description": "Extracts comprehensive data from GitHub repositories and loads it into the ontology",
    "type": "github_repository",
    "configuration": {
      "ontology_store_name": "github_data",
      "include_issues": true,
      "include_pull_requests": true,
      "include_contributors": true,
      "include_commit_history": true,
      "max_items_per_category": 200
    },
    "integrations": [
      {
        "id": "int_github",
        "required": true,
        "status": "connected"
      }
    ],
    "metadata": {
      "department": "engineering",
      "priority": "high",
      "version": "1.1"
    },
    "status": "active",
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-02T09:30:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### Activate Pipeline

Activates an inactive pipeline.

```
POST /api/v1/pipelines/{pipeline_id}/activate
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
    "id": "pl_123456789",
    "status": "active",
    "activated_at": "2023-05-01T14:30:00Z",
    "updated_at": "2023-05-01T14:30:00Z"
  }
}
```

#### Deactivate Pipeline

Deactivates an active pipeline.

```
POST /api/v1/pipelines/{pipeline_id}/deactivate
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
    "id": "pl_123456789",
    "status": "inactive",
    "deactivated_at": "2023-05-02T16:20:00Z",
    "updated_at": "2023-05-02T16:20:00Z"
  }
}
```

#### Delete Pipeline

Deletes a pipeline.

```
DELETE /api/v1/pipelines/{pipeline_id}
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
    "id": "pl_123456789",
    "deleted": true
  }
}
```

### Pipeline Execution

#### Run Pipeline

Executes a pipeline with the provided parameters.

```
POST /api/v1/pipelines/{pipeline_id}/run
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
    "include_closed_issues": true,
    "max_items": 150,
    "since_date": "2023-01-01T00:00:00Z"
  },
  "execution_options": {
    "timeout_seconds": 120,
    "wait_for_completion": true,
    "incremental": true
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "execution_id": "plex_123456789",
    "pipeline_id": "pl_123456789",
    "status": "completed",
    "started_at": "2023-05-02T10:10:00Z",
    "completed_at": "2023-05-02T10:10:45Z",
    "duration_ms": 45123,
    "parameters": {
      "repository": "owner/repo",
      "include_closed_issues": true,
      "max_items": 150,
      "since_date": "2023-01-01T00:00:00Z"
    },
    "result": {
      "entities_created": 256,
      "relationships_created": 528,
      "entities_updated": 42,
      "entities_by_type": {
        "Repository": 1,
        "User": 18,
        "Issue": 87,
        "PullRequest": 65,
        "Commit": 85
      },
      "ontology_store": "github_data",
      "graph_size": 784
    }
  }
}
```

#### Run Pipeline (Async)

Executes a pipeline asynchronously and returns immediately.

```
POST /api/v1/pipelines/{pipeline_id}/run_async
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
    "include_closed_issues": true,
    "max_items": 150,
    "since_date": "2023-01-01T00:00:00Z"
  },
  "callback_url": "https://example.com/webhooks/pipeline_completed"
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "execution_id": "plex_123456789",
    "pipeline_id": "pl_123456789",
    "status": "running",
    "started_at": "2023-05-02T10:10:00Z",
    "parameters": {
      "repository": "owner/repo",
      "include_closed_issues": true,
      "max_items": 150,
      "since_date": "2023-01-01T00:00:00Z"
    },
    "callback_url": "https://example.com/webhooks/pipeline_completed"
  }
}
```

#### Get Execution Status

Returns the status of a pipeline execution.

```
GET /api/v1/pipeline_executions/{execution_id}
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
    "execution_id": "plex_123456789",
    "pipeline_id": "pl_123456789",
    "pipeline_name": "Enhanced GitHub Repository Pipeline",
    "status": "completed",
    "started_at": "2023-05-02T10:10:00Z",
    "completed_at": "2023-05-02T10:10:45Z",
    "duration_ms": 45123,
    "parameters": {
      "repository": "owner/repo",
      "include_closed_issues": true,
      "max_items": 150,
      "since_date": "2023-01-01T00:00:00Z"
    },
    "result": {
      "entities_created": 256,
      "relationships_created": 528,
      "entities_updated": 42,
      "entities_by_type": {
        "Repository": 1,
        "User": 18,
        "Issue": 87,
        "PullRequest": 65,
        "Commit": 85
      },
      "ontology_store": "github_data",
      "graph_size": 784
    },
    "steps": [
      {
        "name": "extract_repository",
        "status": "completed",
        "started_at": "2023-05-02T10:10:00Z",
        "completed_at": "2023-05-02T10:10:02Z",
        "duration_ms": 2000,
        "entities_created": 1
      },
      {
        "name": "extract_issues",
        "status": "completed",
        "started_at": "2023-05-02T10:10:02Z",
        "completed_at": "2023-05-02T10:10:15Z",
        "duration_ms": 13000,
        "entities_created": 105
      },
      {
        "name": "extract_pull_requests",
        "status": "completed",
        "started_at": "2023-05-02T10:10:15Z",
        "completed_at": "2023-05-02T10:10:30Z",
        "duration_ms": 15000,
        "entities_created": 65
      },
      {
        "name": "extract_commits",
        "status": "completed",
        "started_at": "2023-05-02T10:10:30Z",
        "completed_at": "2023-05-02T10:10:45Z",
        "duration_ms": 15000,
        "entities_created": 85
      }
    ]
  }
}
```

#### List Executions

Returns a list of pipeline executions with pagination.

```
GET /api/v1/pipeline_executions
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

```
pipeline_id=pl_123456789
status=completed
start_date=2023-05-01T00:00:00Z
end_date=2023-05-02T23:59:59Z
page=1
page_size=10
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "execution_id": "plex_123456789",
        "pipeline_id": "pl_123456789",
        "pipeline_name": "Enhanced GitHub Repository Pipeline",
        "status": "completed",
        "started_at": "2023-05-02T10:10:00Z",
        "completed_at": "2023-05-02T10:10:45Z",
        "duration_ms": 45123,
        "entities_created": 256
      },
      {
        "execution_id": "plex_987654321",
        "pipeline_id": "pl_123456789",
        "pipeline_name": "Enhanced GitHub Repository Pipeline",
        "status": "completed",
        "started_at": "2023-05-01T15:30:00Z",
        "completed_at": "2023-05-01T15:30:42Z",
        "duration_ms": 42000,
        "entities_created": 230
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

### Pipeline Scheduling

#### Schedule Pipeline

Creates a schedule to execute a pipeline on a recurring basis.

```
POST /api/v1/pipelines/{pipeline_id}/schedules
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "Daily GitHub Update",
  "description": "Updates GitHub data every night at midnight",
  "schedule_type": "cron",
  "cron_expression": "0 0 * * *",
  "parameters": {
    "repository": "owner/repo",
    "include_closed_issues": true,
    "max_items": 150,
    "incremental": true
  },
  "enabled": true,
  "timezone": "UTC"
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "plsched_123456789",
    "pipeline_id": "pl_123456789",
    "name": "Daily GitHub Update",
    "description": "Updates GitHub data every night at midnight",
    "schedule_type": "cron",
    "cron_expression": "0 0 * * *",
    "parameters": {
      "repository": "owner/repo",
      "include_closed_issues": true,
      "max_items": 150,
      "incremental": true
    },
    "enabled": true,
    "timezone": "UTC",
    "next_execution": "2023-05-03T00:00:00Z",
    "created_at": "2023-05-02T14:30:00Z",
    "updated_at": "2023-05-02T14:30:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### Get Schedule

Returns details of a pipeline schedule.

```
GET /api/v1/pipeline_schedules/{schedule_id}
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
    "id": "plsched_123456789",
    "pipeline_id": "pl_123456789",
    "pipeline_name": "Enhanced GitHub Repository Pipeline",
    "name": "Daily GitHub Update",
    "description": "Updates GitHub data every night at midnight",
    "schedule_type": "cron",
    "cron_expression": "0 0 * * *",
    "parameters": {
      "repository": "owner/repo",
      "include_closed_issues": true,
      "max_items": 150,
      "incremental": true
    },
    "enabled": true,
    "timezone": "UTC",
    "next_execution": "2023-05-03T00:00:00Z",
    "last_execution": {
      "execution_id": "plex_123456789",
      "status": "completed",
      "started_at": "2023-05-02T00:00:00Z",
      "completed_at": "2023-05-02T00:00:45Z",
      "entities_created": 256
    },
    "created_at": "2023-05-01T14:30:00Z",
    "updated_at": "2023-05-02T00:00:46Z",
    "created_by": "usr_987654321"
  }
}
```

#### List Schedules

Returns a list of pipeline schedules with pagination.

```
GET /api/v1/pipeline_schedules
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

```
pipeline_id=pl_123456789
enabled=true
page=1
page_size=10
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "plsched_123456789",
        "pipeline_id": "pl_123456789",
        "pipeline_name": "Enhanced GitHub Repository Pipeline",
        "name": "Daily GitHub Update",
        "description": "Updates GitHub data every night at midnight",
        "schedule_type": "cron",
        "cron_expression": "0 0 * * *",
        "enabled": true,
        "next_execution": "2023-05-03T00:00:00Z",
        "created_at": "2023-05-01T14:30:00Z",
        "updated_at": "2023-05-02T00:00:46Z"
      },
      {
        "id": "plsched_987654321",
        "pipeline_id": "pl_123456789",
        "pipeline_name": "Enhanced GitHub Repository Pipeline",
        "name": "Weekly Full Sync",
        "description": "Performs a full sync every Sunday",
        "schedule_type": "cron",
        "cron_expression": "0 0 * * 0",
        "enabled": true,
        "next_execution": "2023-05-07T00:00:00Z",
        "created_at": "2023-05-01T14:35:00Z",
        "updated_at": "2023-05-01T14:35:00Z"
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

#### Update Schedule

Updates an existing pipeline schedule.

```
PUT /api/v1/pipeline_schedules/{schedule_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "Daily GitHub Update",
  "description": "Updates GitHub data every night at 2 AM",
  "cron_expression": "0 2 * * *",
  "parameters": {
    "repository": "owner/repo",
    "include_closed_issues": true,
    "include_commit_history": true,
    "max_items": 200,
    "incremental": true
  },
  "enabled": true
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "plsched_123456789",
    "pipeline_id": "pl_123456789",
    "name": "Daily GitHub Update",
    "description": "Updates GitHub data every night at 2 AM",
    "schedule_type": "cron",
    "cron_expression": "0 2 * * *",
    "parameters": {
      "repository": "owner/repo",
      "include_closed_issues": true,
      "include_commit_history": true,
      "max_items": 200,
      "incremental": true
    },
    "enabled": true,
    "timezone": "UTC",
    "next_execution": "2023-05-03T02:00:00Z",
    "created_at": "2023-05-01T14:30:00Z",
    "updated_at": "2023-05-02T15:45:00Z"
  }
}
```

#### Delete Schedule

Deletes a pipeline schedule.

```
DELETE /api/v1/pipeline_schedules/{schedule_id}
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
    "id": "plsched_123456789",
    "deleted": true
  }
}
```

## Python API

### Pipeline Management

```python
from abi.pipelines import PipelineManager, PipelineConfig

# Initialize the pipeline manager
pipeline_manager = PipelineManager(access_token=access_token)

# Create a pipeline
pipeline_config = PipelineConfig(
    name="GitHub Repository Pipeline",
    description="Extracts data from GitHub repositories and loads it into the ontology",
    type="github_repository",
    configuration={
        "ontology_store_name": "github_data",
        "include_issues": True,
        "include_pull_requests": True,
        "include_contributors": True,
        "max_items_per_category": 100
    },
    integrations=[
        {"id": "int_github", "required": True}
    ],
    metadata={
        "department": "engineering",
        "priority": "medium",
        "version": "1.0"
    }
)

pipeline = pipeline_manager.create_pipeline(pipeline_config)
print(f"Created pipeline with ID: {pipeline.id}")

# Get pipeline by ID
pipeline = pipeline_manager.get_pipeline(pipeline.id)

# List pipelines
pipelines = pipeline_manager.list_pipelines(
    status="active",
    department="engineering",
    page=1,
    page_size=10
)

for pl in pipelines.items:
    print(f"{pl.id}: {pl.name} - Status: {pl.status}")

# Update a pipeline
pipeline.name = "Enhanced GitHub Repository Pipeline"
pipeline.description = "Extracts comprehensive data from GitHub repositories and loads it into the ontology"
pipeline.configuration["include_commit_history"] = True
pipeline.configuration["max_items_per_category"] = 200
pipeline.metadata["priority"] = "high"
pipeline.metadata["version"] = "1.1"

updated_pipeline = pipeline_manager.update_pipeline(pipeline)

# Activate/deactivate a pipeline
pipeline_manager.activate_pipeline(pipeline.id)
pipeline_manager.deactivate_pipeline(pipeline.id)

# Delete a pipeline
pipeline_manager.delete_pipeline(pipeline.id)
```

### Pipeline Execution

```python
from abi.pipelines import PipelineExecutor

# Initialize the pipeline executor
executor = PipelineExecutor(access_token=access_token)

# Execute a pipeline (synchronous)
execution_result = executor.run_pipeline(
    pipeline_id="pl_123456789",
    parameters={
        "repository": "owner/repo",
        "include_closed_issues": True,
        "max_items": 150,
        "since_date": "2023-01-01T00:00:00Z"
    },
    execution_options={
        "timeout_seconds": 120,
        "wait_for_completion": True,
        "incremental": True
    }
)

print(f"Execution ID: {execution_result.execution_id}")
print(f"Status: {execution_result.status}")
print(f"Entities created: {execution_result.result.entities_created}")

# Execute a pipeline asynchronously
execution = executor.run_pipeline_async(
    pipeline_id="pl_123456789",
    parameters={
        "repository": "owner/repo",
        "include_closed_issues": True,
        "max_items": 150,
        "since_date": "2023-01-01T00:00:00Z"
    },
    callback_url="https://example.com/webhooks/pipeline_completed"
)

print(f"Async execution started with ID: {execution.execution_id}")

# Get execution status
execution_status = executor.get_execution_status(execution.execution_id)
print(f"Execution status: {execution_status.status}")

# List executions
executions = executor.list_executions(
    pipeline_id="pl_123456789",
    status="completed",
    start_date="2023-05-01T00:00:00Z",
    end_date="2023-05-02T23:59:59Z",
    page=1,
    page_size=10
)

for exec in executions.items:
    print(f"{exec.execution_id}: Entities created: {exec.entities_created}")
```

### Pipeline Scheduling

```python
from abi.pipelines import PipelineScheduler

# Initialize the pipeline scheduler
scheduler = PipelineScheduler(access_token=access_token)

# Create a schedule
schedule = scheduler.create_schedule(
    pipeline_id="pl_123456789",
    name="Daily GitHub Update",
    description="Updates GitHub data every night at midnight",
    schedule_type="cron",
    cron_expression="0 0 * * *",
    parameters={
        "repository": "owner/repo",
        "include_closed_issues": True,
        "max_items": 150,
        "incremental": True
    },
    enabled=True,
    timezone="UTC"
)

print(f"Created schedule with ID: {schedule.id}")
print(f"Next execution: {schedule.next_execution}")

# Get a schedule
schedule = scheduler.get_schedule(schedule.id)

# List schedules
schedules = scheduler.list_schedules(
    pipeline_id="pl_123456789",
    enabled=True,
    page=1,
    page_size=10
)

for sched in schedules.items:
    print(f"{sched.id}: {sched.name} - Next run: {sched.next_execution}")

# Update a schedule
schedule.cron_expression = "0 2 * * *"
schedule.description = "Updates GitHub data every night at 2 AM"
schedule.parameters["include_commit_history"] = True
schedule.parameters["max_items"] = 200

updated_schedule = scheduler.update_schedule(schedule)

# Delete a schedule
scheduler.delete_schedule(schedule.id)
```

## Pipeline Configuration

### Pipeline Types

ABI supports various pipeline types:

| Type | Description | 
|------|-------------|
| github_repository | Extracts data from GitHub repositories |
| jira_issues | Extracts issues from JIRA |
| salesforce | Extracts data from Salesforce CRM |
| slack_messages | Extracts messages from Slack channels |
| zendesk_tickets | Extracts tickets from Zendesk |
| csv_import | Imports data from CSV files |
| database_extract | Extracts data from databases |
| custom | Custom pipeline implementation |

### Configuration Options

Pipelines can be configured with various options depending on the pipeline type:

```python
# GitHub Repository Pipeline Configuration
config = {
    "ontology_store_name": "github_data",
    "include_issues": True,
    "include_pull_requests": True,
    "include_contributors": True,
    "include_commit_history": True,
    "max_items_per_category": 100,
    "issue_states": ["open", "closed"],
    "commit_depth": 100
}

# JIRA Issues Pipeline Configuration
config = {
    "ontology_store_name": "jira_data",
    "project_keys": ["ABI", "DOCS"],
    "issue_types": ["Bug", "Story", "Task"],
    "include_comments": True,
    "include_attachments": False,
    "include_worklogs": True,
    "max_results": 1000,
    "jql_filter": "created >= -30d"
}

# Salesforce Pipeline Configuration
config = {
    "ontology_store_name": "salesforce_data",
    "objects": ["Account", "Contact", "Opportunity"],
    "fields": {
        "Account": ["Id", "Name", "Industry", "BillingCity"],
        "Contact": ["Id", "FirstName", "LastName", "Email"],
        "Opportunity": ["Id", "Name", "Amount", "StageName", "CloseDate"]
    },
    "where_clauses": {
        "Opportunity": "CloseDate >= LAST_N_DAYS:90"
    },
    "relationships": [
        {"from": "Contact", "to": "Account", "using": "AccountId"},
        {"from": "Opportunity", "to": "Account", "using": "AccountId"}
    ]
}
```

### Schedule Types

Schedules can be defined using different patterns (same as workflows):

1. **Cron Expression**:
   ```python
   schedule = {
       "schedule_type": "cron",
       "cron_expression": "0 0 * * *"  # Every day at midnight
   }
   ```

2. **Interval**:
   ```python
   schedule = {
       "schedule_type": "interval",
       "interval_value": 30,
       "interval_unit": "minutes"  # seconds, minutes, hours, days
   }
   ```

3. **Fixed Time**:
   ```python
   schedule = {
       "schedule_type": "fixed_time",
       "execution_time": "2023-06-01T12:00:00Z"  # One-time execution
   }
   ```

## Ontology Mapping

Pipelines map external data to entities and relationships in the ontology using mapping configurations:

```python
# GitHub mapping configuration
mapping = {
    "Repository": {
        "source": "repository",
        "properties": {
            "id": "id",
            "name": "name",
            "full_name": "full_name",
            "description": "description",
            "url": "html_url",
            "created_at": "created_at"
        }
    },
    "User": {
        "source": "user",
        "properties": {
            "id": "id",
            "login": "login",
            "type": "type",
            "url": "html_url"
        }
    },
    "Issue": {
        "source": "issue",
        "properties": {
            "id": "id",
            "number": "number",
            "title": "title",
            "state": "state",
            "created_at": "created_at",
            "updated_at": "updated_at"
        }
    },
    "relationships": [
        {
            "from": "Issue",
            "to": "Repository",
            "type": "belongsTo",
            "source_path": "repository_url"
        },
        {
            "from": "Issue",
            "to": "User",
            "type": "createdBy",
            "source_path": "user"
        }
    ]
}
```

## Error Handling

Common errors when working with pipelines:

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| 400 | INVALID_PIPELINE_CONFIG | Invalid pipeline configuration |
| 400 | INVALID_PARAMETERS | Invalid pipeline parameters |
| 400 | INVALID_SCHEDULE | Invalid schedule configuration |
| 404 | PIPELINE_NOT_FOUND | Pipeline not found |
| 404 | EXECUTION_NOT_FOUND | Execution not found |
| 404 | SCHEDULE_NOT_FOUND | Schedule not found |
| 409 | INTEGRATION_MISSING | Required integration not configured |
| 422 | DATA_VALIDATION_ERROR | Data validation failed |
| 429 | RATE_LIMIT_EXCEEDED | Rate limit exceeded |
| 500 | PIPELINE_EXECUTION_ERROR | Error during pipeline execution |
| 500 | EXTRACTION_ERROR | Error extracting data from source |
| 500 | TRANSFORMATION_ERROR | Error transforming data |
| 500 | LOADING_ERROR | Error loading data into ontology |
| 504 | EXECUTION_TIMEOUT | Pipeline execution timed out |

## Event Webhooks

You can configure webhooks to receive events from pipelines:

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
  "url": "https://example.com/webhooks/pipelines",
  "events": ["pipeline.created", "pipeline.executed", "execution.completed"],
  "secret": "whsec_abcdefghijklmnopqrstuvwxyz",
  "description": "Production webhook for pipeline events"
}
```

### Webhook Event Types

| Event Type | Description |
|------------|-------------|
| pipeline.created | Fired when a new pipeline is created |
| pipeline.updated | Fired when a pipeline is updated |
| pipeline.activated | Fired when a pipeline is activated |
| pipeline.deactivated | Fired when a pipeline is deactivated |
| pipeline.deleted | Fired when a pipeline is deleted |
| pipeline.executed | Fired when a pipeline execution starts |
| execution.step_completed | Fired when a pipeline execution step completes |
| execution.completed | Fired when a pipeline execution completes |
| execution.failed | Fired when a pipeline execution fails |
| schedule.created | Fired when a schedule is created |
| schedule.updated | Fired when a schedule is updated |
| schedule.deleted | Fired when a schedule is deleted |
| schedule.triggered | Fired when a schedule triggers a pipeline execution |

## Best Practices

1. **Pipeline Design**:
   - Create focused pipelines for specific data sources
   - Use clear and consistent entity mappings
   - Include only necessary data for your use cases

2. **Performance Optimization**:
   - Use incremental processing for large datasets
   - Implement data filtering at the source
   - Process data in batches
   - Include only needed fields

3. **Data Quality**:
   - Validate data before loading into the ontology
   - Handle missing or null values appropriately
   - Implement data transformation to ensure consistency
   - Add data provenance information

4. **Error Handling**:
   - Implement proper error handling for external API calls
   - Create fallback mechanisms for temporary failures
   - Log detailed error information for debugging

5. **Scheduling**:
   - Schedule pipelines during off-peak hours
   - Stagger schedules to avoid resource contention
   - Use incremental updates for frequent runs
   - Schedule full refreshes periodically

## Next Steps

- Learn about [Integrations API](integrations.md) to set up data source connections
- Explore the [Ontology API](ontology.md) to manage the knowledge graph structure
- Check the [Workflows API](workflows.md) to create business processes that use pipeline data 