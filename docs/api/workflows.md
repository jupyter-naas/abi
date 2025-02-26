# Workflows API

The Workflows API provides endpoints and interfaces for creating, managing, and executing business workflows in the ABI framework. Workflows orchestrate complex business processes and can be invoked by assistants, API calls, or scheduled events.

## REST API

### Workflow Management

#### Create Workflow

Creates a new workflow with the specified configuration.

```
POST /api/v1/workflows
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "Customer Feedback Analysis",
  "description": "Analyzes customer feedback and generates insights",
  "type": "feedback_analysis",
  "configuration": {
    "nlp_service": "default",
    "sentiment_analysis": true,
    "topic_extraction": true,
    "language": "en",
    "response_threshold": 0.7
  },
  "integrations": [
    {
      "id": "int_zendesk",
      "required": true
    },
    {
      "id": "int_salesforce",
      "required": false
    }
  ],
  "metadata": {
    "department": "customer_success",
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
    "id": "wf_123456789",
    "name": "Customer Feedback Analysis",
    "description": "Analyzes customer feedback and generates insights",
    "type": "feedback_analysis",
    "configuration": {
      "nlp_service": "default",
      "sentiment_analysis": true,
      "topic_extraction": true,
      "language": "en",
      "response_threshold": 0.7
    },
    "integrations": [
      {
        "id": "int_zendesk",
        "required": true,
        "status": "pending"
      },
      {
        "id": "int_salesforce",
        "required": false,
        "status": "pending"
      }
    ],
    "metadata": {
      "department": "customer_success",
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

#### Get Workflow

Returns details of a specific workflow.

```
GET /api/v1/workflows/{workflow_id}
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
    "id": "wf_123456789",
    "name": "Customer Feedback Analysis",
    "description": "Analyzes customer feedback and generates insights",
    "type": "feedback_analysis",
    "configuration": {
      "nlp_service": "default",
      "sentiment_analysis": true,
      "topic_extraction": true,
      "language": "en",
      "response_threshold": 0.7
    },
    "integrations": [
      {
        "id": "int_zendesk",
        "required": true,
        "status": "connected"
      },
      {
        "id": "int_salesforce",
        "required": false,
        "status": "connected"
      }
    ],
    "metadata": {
      "department": "customer_success",
      "priority": "medium",
      "version": "1.0"
    },
    "status": "active",
    "stats": {
      "runs_total": 128,
      "runs_success": 124,
      "runs_failed": 4,
      "average_duration_ms": 2450
    },
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-01T14:30:00Z",
    "activated_at": "2023-05-01T14:30:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### List Workflows

Returns a list of workflows with pagination.

```
GET /api/v1/workflows
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
type=feedback_analysis
department=customer_success
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "wf_123456789",
        "name": "Customer Feedback Analysis",
        "description": "Analyzes customer feedback and generates insights",
        "type": "feedback_analysis",
        "status": "active",
        "metadata": {
          "department": "customer_success",
          "priority": "medium",
          "version": "1.0"
        },
        "created_at": "2023-05-01T12:00:00Z",
        "updated_at": "2023-05-01T14:30:00Z"
      },
      {
        "id": "wf_987654321",
        "name": "Customer Onboarding",
        "description": "Manages customer onboarding process",
        "type": "onboarding",
        "status": "active",
        "metadata": {
          "department": "customer_success",
          "priority": "high",
          "version": "2.1"
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

#### Update Workflow

Updates an existing workflow.

```
PUT /api/v1/workflows/{workflow_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "Enhanced Customer Feedback Analysis",
  "description": "Analyzes customer feedback and generates detailed insights with recommendations",
  "configuration": {
    "nlp_service": "advanced",
    "sentiment_analysis": true,
    "topic_extraction": true,
    "language": "en",
    "response_threshold": 0.8,
    "generate_recommendations": true
  },
  "metadata": {
    "department": "customer_success",
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
    "id": "wf_123456789",
    "name": "Enhanced Customer Feedback Analysis",
    "description": "Analyzes customer feedback and generates detailed insights with recommendations",
    "type": "feedback_analysis",
    "configuration": {
      "nlp_service": "advanced",
      "sentiment_analysis": true,
      "topic_extraction": true,
      "language": "en",
      "response_threshold": 0.8,
      "generate_recommendations": true
    },
    "integrations": [
      {
        "id": "int_zendesk",
        "required": true,
        "status": "connected"
      },
      {
        "id": "int_salesforce",
        "required": false,
        "status": "connected"
      }
    ],
    "metadata": {
      "department": "customer_success",
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

#### Activate Workflow

Activates an inactive workflow.

```
POST /api/v1/workflows/{workflow_id}/activate
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
    "id": "wf_123456789",
    "status": "active",
    "activated_at": "2023-05-01T14:30:00Z",
    "updated_at": "2023-05-01T14:30:00Z"
  }
}
```

#### Deactivate Workflow

Deactivates an active workflow.

```
POST /api/v1/workflows/{workflow_id}/deactivate
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
    "id": "wf_123456789",
    "status": "inactive",
    "deactivated_at": "2023-05-02T16:20:00Z",
    "updated_at": "2023-05-02T16:20:00Z"
  }
}
```

#### Delete Workflow

Deletes a workflow.

```
DELETE /api/v1/workflows/{workflow_id}
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
    "id": "wf_123456789",
    "deleted": true
  }
}
```

### Workflow Execution

#### Execute Workflow

Executes a workflow with the provided parameters.

```
POST /api/v1/workflows/{workflow_id}/execute
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "parameters": {
    "feedback_id": "f_12345",
    "customer_id": "c_67890",
    "feedback_text": "I really love your product, but the latest update made the user interface more complicated. It's still a great service overall though!",
    "source": "email",
    "include_recommendations": true
  },
  "execution_options": {
    "timeout_seconds": 30,
    "wait_for_completion": true
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "execution_id": "exec_123456789",
    "workflow_id": "wf_123456789",
    "status": "completed",
    "started_at": "2023-05-02T10:10:00Z",
    "completed_at": "2023-05-02T10:10:02Z",
    "duration_ms": 2152,
    "parameters": {
      "feedback_id": "f_12345",
      "customer_id": "c_67890",
      "feedback_text": "I really love your product, but the latest update made the user interface more complicated. It's still a great service overall though!",
      "source": "email",
      "include_recommendations": true
    },
    "result": {
      "sentiment": "mixed",
      "sentiment_score": 0.65,
      "feedback_components": [
        {
          "topic": "product_overall",
          "sentiment": "positive",
          "score": 0.85
        },
        {
          "topic": "user_interface",
          "sentiment": "negative",
          "score": 0.70
        }
      ],
      "primary_topics": ["user_interface", "product_satisfaction"],
      "recommendations": [
        "Consider simplifying the user interface in the next update",
        "Highlight the positive overall experience in your response"
      ]
    }
  }
}
```

#### Execute Workflow (Async)

Executes a workflow asynchronously and returns immediately.

```
POST /api/v1/workflows/{workflow_id}/execute_async
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "parameters": {
    "feedback_id": "f_12345",
    "customer_id": "c_67890",
    "feedback_text": "I really love your product, but the latest update made the user interface more complicated. It's still a great service overall though!",
    "source": "email",
    "include_recommendations": true
  },
  "callback_url": "https://example.com/webhooks/workflow_completed"
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "execution_id": "exec_123456789",
    "workflow_id": "wf_123456789",
    "status": "running",
    "started_at": "2023-05-02T10:10:00Z",
    "parameters": {
      "feedback_id": "f_12345",
      "customer_id": "c_67890",
      "feedback_text": "I really love your product, but the latest update made the user interface more complicated. It's still a great service overall though!",
      "source": "email",
      "include_recommendations": true
    },
    "callback_url": "https://example.com/webhooks/workflow_completed"
  }
}
```

#### Get Execution Status

Returns the status of a workflow execution.

```
GET /api/v1/workflow_executions/{execution_id}
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
    "execution_id": "exec_123456789",
    "workflow_id": "wf_123456789",
    "workflow_name": "Enhanced Customer Feedback Analysis",
    "status": "completed",
    "started_at": "2023-05-02T10:10:00Z",
    "completed_at": "2023-05-02T10:10:02Z",
    "duration_ms": 2152,
    "parameters": {
      "feedback_id": "f_12345",
      "customer_id": "c_67890",
      "feedback_text": "I really love your product, but the latest update made the user interface more complicated. It's still a great service overall though!",
      "source": "email",
      "include_recommendations": true
    },
    "result": {
      "sentiment": "mixed",
      "sentiment_score": 0.65,
      "feedback_components": [
        {
          "topic": "product_overall",
          "sentiment": "positive",
          "score": 0.85
        },
        {
          "topic": "user_interface",
          "sentiment": "negative",
          "score": 0.70
        }
      ],
      "primary_topics": ["user_interface", "product_satisfaction"],
      "recommendations": [
        "Consider simplifying the user interface in the next update",
        "Highlight the positive overall experience in your response"
      ]
    },
    "steps": [
      {
        "name": "extract_sentiment",
        "status": "completed",
        "started_at": "2023-05-02T10:10:00Z",
        "completed_at": "2023-05-02T10:10:00Z",
        "duration_ms": 250
      },
      {
        "name": "identify_topics",
        "status": "completed",
        "started_at": "2023-05-02T10:10:00Z",
        "completed_at": "2023-05-02T10:10:01Z",
        "duration_ms": 810
      },
      {
        "name": "generate_recommendations",
        "status": "completed",
        "started_at": "2023-05-02T10:10:01Z",
        "completed_at": "2023-05-02T10:10:02Z",
        "duration_ms": 1090
      }
    ]
  }
}
```

#### List Executions

Returns a list of workflow executions with pagination.

```
GET /api/v1/workflow_executions
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

```
workflow_id=wf_123456789
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
        "execution_id": "exec_123456789",
        "workflow_id": "wf_123456789",
        "workflow_name": "Enhanced Customer Feedback Analysis",
        "status": "completed",
        "started_at": "2023-05-02T10:10:00Z",
        "completed_at": "2023-05-02T10:10:02Z",
        "duration_ms": 2152
      },
      {
        "execution_id": "exec_987654321",
        "workflow_id": "wf_123456789",
        "workflow_name": "Enhanced Customer Feedback Analysis",
        "status": "completed",
        "started_at": "2023-05-01T15:30:00Z",
        "completed_at": "2023-05-01T15:30:03Z",
        "duration_ms": 2876
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

### Workflow Scheduling

#### Schedule Workflow

Creates a schedule to execute a workflow on a recurring basis.

```
POST /api/v1/workflows/{workflow_id}/schedules
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "Daily Feedback Analysis",
  "description": "Runs feedback analysis every night at midnight",
  "schedule_type": "cron",
  "cron_expression": "0 0 * * *",
  "parameters": {
    "source": "daily_report",
    "include_recommendations": true
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
    "id": "sched_123456789",
    "workflow_id": "wf_123456789",
    "name": "Daily Feedback Analysis",
    "description": "Runs feedback analysis every night at midnight",
    "schedule_type": "cron",
    "cron_expression": "0 0 * * *",
    "parameters": {
      "source": "daily_report",
      "include_recommendations": true
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

Returns details of a workflow schedule.

```
GET /api/v1/workflow_schedules/{schedule_id}
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
    "id": "sched_123456789",
    "workflow_id": "wf_123456789",
    "workflow_name": "Enhanced Customer Feedback Analysis",
    "name": "Daily Feedback Analysis",
    "description": "Runs feedback analysis every night at midnight",
    "schedule_type": "cron",
    "cron_expression": "0 0 * * *",
    "parameters": {
      "source": "daily_report",
      "include_recommendations": true
    },
    "enabled": true,
    "timezone": "UTC",
    "next_execution": "2023-05-03T00:00:00Z",
    "last_execution": {
      "execution_id": "exec_123456789",
      "status": "completed",
      "started_at": "2023-05-02T00:00:00Z",
      "completed_at": "2023-05-02T00:00:02Z"
    },
    "created_at": "2023-05-01T14:30:00Z",
    "updated_at": "2023-05-02T00:00:03Z",
    "created_by": "usr_987654321"
  }
}
```

#### List Schedules

Returns a list of workflow schedules with pagination.

```
GET /api/v1/workflow_schedules
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

```
workflow_id=wf_123456789
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
        "id": "sched_123456789",
        "workflow_id": "wf_123456789",
        "workflow_name": "Enhanced Customer Feedback Analysis",
        "name": "Daily Feedback Analysis",
        "description": "Runs feedback analysis every night at midnight",
        "schedule_type": "cron",
        "cron_expression": "0 0 * * *",
        "enabled": true,
        "next_execution": "2023-05-03T00:00:00Z",
        "created_at": "2023-05-01T14:30:00Z",
        "updated_at": "2023-05-02T00:00:03Z"
      },
      {
        "id": "sched_987654321",
        "workflow_id": "wf_123456789",
        "workflow_name": "Enhanced Customer Feedback Analysis",
        "name": "Weekly Analysis Report",
        "description": "Generates comprehensive analysis every Sunday",
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

Updates an existing workflow schedule.

```
PUT /api/v1/workflow_schedules/{schedule_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "Daily Feedback Analysis",
  "description": "Runs feedback analysis every night at 2 AM",
  "cron_expression": "0 2 * * *",
  "parameters": {
    "source": "daily_report",
    "include_recommendations": true,
    "generate_report": true
  },
  "enabled": true
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "sched_123456789",
    "workflow_id": "wf_123456789",
    "name": "Daily Feedback Analysis",
    "description": "Runs feedback analysis every night at 2 AM",
    "schedule_type": "cron",
    "cron_expression": "0 2 * * *",
    "parameters": {
      "source": "daily_report",
      "include_recommendations": true,
      "generate_report": true
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

Deletes a workflow schedule.

```
DELETE /api/v1/workflow_schedules/{schedule_id}
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
    "id": "sched_123456789",
    "deleted": true
  }
}
```

## Python API

### Workflow Management

```python
from abi.workflows import WorkflowManager, WorkflowConfig

# Initialize the workflow manager
workflow_manager = WorkflowManager(access_token=access_token)

# Create a workflow
workflow_config = WorkflowConfig(
    name="Customer Feedback Analysis",
    description="Analyzes customer feedback and generates insights",
    type="feedback_analysis",
    configuration={
        "nlp_service": "default",
        "sentiment_analysis": True,
        "topic_extraction": True,
        "language": "en",
        "response_threshold": 0.7
    },
    integrations=[
        {"id": "int_zendesk", "required": True},
        {"id": "int_salesforce", "required": False}
    ],
    metadata={
        "department": "customer_success",
        "priority": "medium",
        "version": "1.0"
    }
)

workflow = workflow_manager.create_workflow(workflow_config)
print(f"Created workflow with ID: {workflow.id}")

# Get workflow by ID
workflow = workflow_manager.get_workflow(workflow.id)

# List workflows
workflows = workflow_manager.list_workflows(
    status="active",
    department="customer_success",
    page=1,
    page_size=10
)

for wf in workflows.items:
    print(f"{wf.id}: {wf.name} - Status: {wf.status}")

# Update a workflow
workflow.name = "Enhanced Customer Feedback Analysis"
workflow.description = "Analyzes customer feedback and generates detailed insights with recommendations"
workflow.configuration["nlp_service"] = "advanced"
workflow.configuration["generate_recommendations"] = True
workflow.metadata["priority"] = "high"
workflow.metadata["version"] = "1.1"

updated_workflow = workflow_manager.update_workflow(workflow)

# Activate/deactivate a workflow
workflow_manager.activate_workflow(workflow.id)
workflow_manager.deactivate_workflow(workflow.id)

# Delete a workflow
workflow_manager.delete_workflow(workflow.id)
```

### Workflow Execution

```python
from abi.workflows import WorkflowExecutor

# Initialize the workflow executor
executor = WorkflowExecutor(access_token=access_token)

# Execute a workflow (synchronous)
execution_result = executor.execute_workflow(
    workflow_id="wf_123456789",
    parameters={
        "feedback_id": "f_12345",
        "customer_id": "c_67890",
        "feedback_text": "I really love your product, but the latest update made the user interface more complicated. It's still a great service overall though!",
        "source": "email",
        "include_recommendations": True
    },
    execution_options={
        "timeout_seconds": 30,
        "wait_for_completion": True
    }
)

print(f"Execution ID: {execution_result.execution_id}")
print(f"Status: {execution_result.status}")
print(f"Result: {execution_result.result}")

# Execute a workflow asynchronously
execution = executor.execute_workflow_async(
    workflow_id="wf_123456789",
    parameters={
        "feedback_id": "f_12345",
        "customer_id": "c_67890",
        "feedback_text": "I really love your product, but the latest update made the user interface more complicated. It's still a great service overall though!",
        "source": "email",
        "include_recommendations": True
    },
    callback_url="https://example.com/webhooks/workflow_completed"
)

print(f"Async execution started with ID: {execution.execution_id}")

# Get execution status
execution_status = executor.get_execution_status(execution.execution_id)
print(f"Execution status: {execution_status.status}")

# List executions
executions = executor.list_executions(
    workflow_id="wf_123456789",
    status="completed",
    start_date="2023-05-01T00:00:00Z",
    end_date="2023-05-02T23:59:59Z",
    page=1,
    page_size=10
)

for exec in executions.items:
    print(f"{exec.execution_id}: Started at {exec.started_at}, Status: {exec.status}")
```

### Workflow Scheduling

```python
from abi.workflows import WorkflowScheduler

# Initialize the workflow scheduler
scheduler = WorkflowScheduler(access_token=access_token)

# Create a schedule
schedule = scheduler.create_schedule(
    workflow_id="wf_123456789",
    name="Daily Feedback Analysis",
    description="Runs feedback analysis every night at midnight",
    schedule_type="cron",
    cron_expression="0 0 * * *",
    parameters={
        "source": "daily_report",
        "include_recommendations": True
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
    workflow_id="wf_123456789",
    enabled=True,
    page=1,
    page_size=10
)

for sched in schedules.items:
    print(f"{sched.id}: {sched.name} - Next run: {sched.next_execution}")

# Update a schedule
schedule.cron_expression = "0 2 * * *"
schedule.description = "Runs feedback analysis every night at 2 AM"
schedule.parameters["generate_report"] = True

updated_schedule = scheduler.update_schedule(schedule)

# Delete a schedule
scheduler.delete_schedule(schedule.id)
```

## Workflow Configuration

### Workflow Types

ABI supports various workflow types:

| Type | Description | 
|------|-------------|
| feedback_analysis | Analyzes customer feedback |
| data_processing | Processes and transforms data |
| notification | Sends notifications based on events |
| approval | Manages approval processes |
| integration | Synchronizes data between systems |
| reporting | Generates reports |
| custom | Custom workflow implementation |

### Configuration Options

Workflows can be configured with various options depending on the workflow type:

```python
# Feedback Analysis Configuration
config = {
    "nlp_service": "default",  # default, advanced, custom
    "sentiment_analysis": True,
    "topic_extraction": True,
    "language": "en",
    "response_threshold": 0.7,
    "generate_recommendations": True
}

# Data Processing Configuration
config = {
    "source_integration": "int_salesforce",
    "target_integration": "int_zendesk",
    "batch_size": 100,
    "transformation_rules": {
        "customer_id": "contact_id",
        "feedback": "description"
    },
    "field_mappings": [
        {"source": "email", "target": "contact_email"},
        {"source": "name", "target": "contact_name"}
    ]
}

# Notification Configuration
config = {
    "channels": ["email", "slack"],
    "templates": {
        "email": "template_123",
        "slack": "template_456"
    },
    "recipients": {
        "email": ["user@example.com"],
        "slack": ["#channel", "@user"]
    },
    "priority_rules": [
        {"condition": "severity == 'high'", "priority": "urgent"},
        {"condition": "severity == 'medium'", "priority": "normal"}
    ]
}
```

### Schedule Types

Schedules can be defined using different patterns:

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

## Error Handling

Common errors when working with workflows:

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| 400 | INVALID_WORKFLOW_CONFIG | Invalid workflow configuration |
| 400 | INVALID_PARAMETERS | Invalid workflow parameters |
| 400 | INVALID_SCHEDULE | Invalid schedule configuration |
| 404 | WORKFLOW_NOT_FOUND | Workflow not found |
| 404 | EXECUTION_NOT_FOUND | Execution not found |
| 404 | SCHEDULE_NOT_FOUND | Schedule not found |
| 409 | INTEGRATION_MISSING | Required integration not configured |
| 422 | PARAMETER_VALIDATION_ERROR | Parameter validation failed |
| 429 | RATE_LIMIT_EXCEEDED | Rate limit exceeded |
| 500 | WORKFLOW_EXECUTION_ERROR | Error during workflow execution |
| 504 | EXECUTION_TIMEOUT | Workflow execution timed out |

## Event Webhooks

You can configure webhooks to receive events from workflows:

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
  "url": "https://example.com/webhooks/workflows",
  "events": ["workflow.created", "workflow.executed", "execution.completed"],
  "secret": "whsec_abcdefghijklmnopqrstuvwxyz",
  "description": "Production webhook for workflow events"
}
```

### Webhook Event Types

| Event Type | Description |
|------------|-------------|
| workflow.created | Fired when a new workflow is created |
| workflow.updated | Fired when a workflow is updated |
| workflow.activated | Fired when a workflow is activated |
| workflow.deactivated | Fired when a workflow is deactivated |
| workflow.deleted | Fired when a workflow is deleted |
| workflow.executed | Fired when a workflow execution starts |
| execution.step_completed | Fired when a workflow execution step completes |
| execution.completed | Fired when a workflow execution completes |
| execution.failed | Fired when a workflow execution fails |
| schedule.created | Fired when a schedule is created |
| schedule.updated | Fired when a schedule is updated |
| schedule.deleted | Fired when a schedule is deleted |
| schedule.triggered | Fired when a schedule triggers a workflow execution |

## Best Practices

1. **Workflow Design**:
   - Create focused workflows for specific business processes
   - Keep workflows modular and reusable
   - Document workflow parameters thoroughly

2. **Performance Optimization**:
   - Include timeout parameters in long-running workflows
   - Use asynchronous execution for non-interactive workflows
   - Process data in batches when possible

3. **Error Handling**:
   - Implement proper error handling in custom workflows
   - Use try/catch blocks around integration calls
   - Provide descriptive error messages

4. **Security**:
   - Validate all inputs before processing
   - Apply the principle of least privilege when granting permissions
   - Use secure webhook endpoints with verification

5. **Monitoring**:
   - Track workflow execution statistics
   - Set up alerts for failed workflows
   - Regularly review workflow performance metrics

## Next Steps

- Learn about [Pipelines API](pipelines.md) to process and transform data
- Explore the [Integrations API](integrations.md) to connect external systems
- Check the [Assistants API](assistants.md) to expose workflows via conversational interfaces 