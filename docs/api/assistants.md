# Assistants API

The Assistants API provides endpoints and interfaces for creating, managing, and interacting with AI assistants in the ABI framework. Assistants can be configured with different capabilities, tools, and knowledge sources to serve various business needs.

## REST API

### Assistant Management

#### Create Assistant

Creates a new assistant with the specified configuration.

```
POST /api/v1/assistants
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "Customer Support Assistant",
  "description": "Handles customer inquiries and provides product information",
  "model": "gpt-4-1106-preview",
  "instructions": "You are a helpful customer support agent for Acme Inc. Answer product questions accurately and politely.",
  "tools": [
    {
      "type": "workflow",
      "workflow_id": "wf_customer_inquiry"
    },
    {
      "type": "knowledge_base",
      "knowledge_base_id": "kb_product_info"
    },
    {
      "type": "function",
      "function": {
        "name": "get_customer_data",
        "description": "Get customer data by email or ID",
        "parameters": {
          "type": "object",
          "properties": {
            "customer_id": {
              "type": "string",
              "description": "The customer ID"
            },
            "email": {
              "type": "string",
              "description": "The customer email"
            }
          },
          "required": ["customer_id"]
        }
      }
    }
  ],
  "metadata": {
    "department": "support",
    "priority": "high"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "ast_123456789",
    "name": "Customer Support Assistant",
    "description": "Handles customer inquiries and provides product information",
    "model": "gpt-4-1106-preview",
    "instructions": "You are a helpful customer support agent for Acme Inc. Answer product questions accurately and politely.",
    "tools": [
      {
        "type": "workflow",
        "workflow_id": "wf_customer_inquiry"
      },
      {
        "type": "knowledge_base",
        "knowledge_base_id": "kb_product_info"
      },
      {
        "type": "function",
        "function": {
          "name": "get_customer_data",
          "description": "Get customer data by email or ID",
          "parameters": {
            "type": "object",
            "properties": {
              "customer_id": {
                "type": "string",
                "description": "The customer ID"
              },
              "email": {
                "type": "string",
                "description": "The customer email"
              }
            },
            "required": ["customer_id"]
          }
        }
      }
    ],
    "metadata": {
      "department": "support",
      "priority": "high"
    },
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-01T12:00:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### Get Assistant

Returns details of a specific assistant.

```
GET /api/v1/assistants/{assistant_id}
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
    "id": "ast_123456789",
    "name": "Customer Support Assistant",
    "description": "Handles customer inquiries and provides product information",
    "model": "gpt-4-1106-preview",
    "instructions": "You are a helpful customer support agent for Acme Inc. Answer product questions accurately and politely.",
    "tools": [
      {
        "type": "workflow",
        "workflow_id": "wf_customer_inquiry"
      },
      {
        "type": "knowledge_base",
        "knowledge_base_id": "kb_product_info"
      },
      {
        "type": "function",
        "function": {
          "name": "get_customer_data",
          "description": "Get customer data by email or ID",
          "parameters": {
            "type": "object",
            "properties": {
              "customer_id": {
                "type": "string",
                "description": "The customer ID"
              },
              "email": {
                "type": "string",
                "description": "The customer email"
              }
            },
            "required": ["customer_id"]
          }
        }
      }
    ],
    "metadata": {
      "department": "support",
      "priority": "high"
    },
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-01T12:00:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### List Assistants

Returns a list of assistants with pagination.

```
GET /api/v1/assistants
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
name=Support
department=support
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "ast_123456789",
        "name": "Customer Support Assistant",
        "description": "Handles customer inquiries and provides product information",
        "model": "gpt-4-1106-preview",
        "metadata": {
          "department": "support",
          "priority": "high"
        },
        "created_at": "2023-05-01T12:00:00Z",
        "updated_at": "2023-05-01T12:00:00Z"
      },
      {
        "id": "ast_987654321",
        "name": "Sales Support Assistant",
        "description": "Assists with sales inquiries and provides pricing information",
        "model": "gpt-4-1106-preview",
        "metadata": {
          "department": "sales",
          "priority": "medium"
        },
        "created_at": "2023-04-15T10:00:00Z",
        "updated_at": "2023-04-15T10:00:00Z"
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

#### Update Assistant

Updates an existing assistant.

```
PUT /api/v1/assistants/{assistant_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "Enhanced Customer Support Assistant",
  "description": "Handles customer inquiries, provides product information, and can process returns",
  "instructions": "You are a helpful customer support agent for Acme Inc. Answer product questions accurately and politely. You can also help customers process returns.",
  "tools": [
    {
      "type": "workflow",
      "workflow_id": "wf_customer_inquiry"
    },
    {
      "type": "workflow",
      "workflow_id": "wf_process_return"
    },
    {
      "type": "knowledge_base",
      "knowledge_base_id": "kb_product_info"
    }
  ],
  "metadata": {
    "department": "support",
    "priority": "high",
    "version": "2.0"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "ast_123456789",
    "name": "Enhanced Customer Support Assistant",
    "description": "Handles customer inquiries, provides product information, and can process returns",
    "model": "gpt-4-1106-preview",
    "instructions": "You are a helpful customer support agent for Acme Inc. Answer product questions accurately and politely. You can also help customers process returns.",
    "tools": [
      {
        "type": "workflow",
        "workflow_id": "wf_customer_inquiry"
      },
      {
        "type": "workflow",
        "workflow_id": "wf_process_return"
      },
      {
        "type": "knowledge_base",
        "knowledge_base_id": "kb_product_info"
      }
    ],
    "metadata": {
      "department": "support",
      "priority": "high",
      "version": "2.0"
    },
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-02T09:30:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### Delete Assistant

Deletes an assistant.

```
DELETE /api/v1/assistants/{assistant_id}
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
    "id": "ast_123456789",
    "deleted": true
  }
}
```

### Conversations

#### Create Conversation

Creates a new conversation with an assistant.

```
POST /api/v1/assistants/{assistant_id}/conversations
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "metadata": {
    "user_id": "u_123456",
    "session_id": "sess_789012",
    "source": "web_app"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "conv_987654321",
    "assistant_id": "ast_123456789",
    "metadata": {
      "user_id": "u_123456",
      "session_id": "sess_789012",
      "source": "web_app"
    },
    "created_at": "2023-05-02T10:00:00Z",
    "updated_at": "2023-05-02T10:00:00Z"
  }
}
```

#### Get Conversation

Retrieves a conversation by ID.

```
GET /api/v1/conversations/{conversation_id}
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
    "id": "conv_987654321",
    "assistant_id": "ast_123456789",
    "metadata": {
      "user_id": "u_123456",
      "session_id": "sess_789012",
      "source": "web_app"
    },
    "message_count": 4,
    "created_at": "2023-05-02T10:00:00Z",
    "updated_at": "2023-05-02T10:15:30Z"
  }
}
```

#### List Conversations

Lists conversations with pagination.

```
GET /api/v1/conversations
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

```
assistant_id=ast_123456789
user_id=u_123456
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
        "id": "conv_987654321",
        "assistant_id": "ast_123456789",
        "metadata": {
          "user_id": "u_123456",
          "session_id": "sess_789012",
          "source": "web_app"
        },
        "message_count": 4,
        "created_at": "2023-05-02T10:00:00Z",
        "updated_at": "2023-05-02T10:15:30Z"
      },
      {
        "id": "conv_123456789",
        "assistant_id": "ast_123456789",
        "metadata": {
          "user_id": "u_123456",
          "session_id": "sess_345678",
          "source": "mobile_app"
        },
        "message_count": 2,
        "created_at": "2023-05-01T15:30:00Z",
        "updated_at": "2023-05-01T15:35:20Z"
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

### Messages

#### Send Message

Sends a message to an assistant in a conversation.

```
POST /api/v1/conversations/{conversation_id}/messages
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "role": "user",
  "content": "I need help with my recent order #12345. I haven't received it yet.",
  "attachments": [
    {
      "type": "image",
      "file_id": "file_abcdef123456",
      "description": "Screenshot of my order confirmation"
    }
  ]
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "msg_123456789",
    "conversation_id": "conv_987654321",
    "role": "user",
    "content": "I need help with my recent order #12345. I haven't received it yet.",
    "attachments": [
      {
        "type": "image",
        "file_id": "file_abcdef123456",
        "description": "Screenshot of my order confirmation"
      }
    ],
    "created_at": "2023-05-02T10:10:00Z"
  }
}
```

#### Get Messages

Retrieves messages from a conversation with pagination.

```
GET /api/v1/conversations/{conversation_id}/messages
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

```
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
        "id": "msg_123456789",
        "conversation_id": "conv_987654321",
        "role": "user",
        "content": "I need help with my recent order #12345. I haven't received it yet.",
        "attachments": [
          {
            "type": "image",
            "file_id": "file_abcdef123456",
            "description": "Screenshot of my order confirmation"
          }
        ],
        "created_at": "2023-05-02T10:10:00Z"
      },
      {
        "id": "msg_987654321",
        "conversation_id": "conv_987654321",
        "role": "assistant",
        "content": "I'm sorry to hear you haven't received your order #12345. Let me look up the status for you.",
        "tool_calls": [
          {
            "id": "call_12345",
            "type": "workflow",
            "workflow_id": "wf_customer_inquiry",
            "parameters": {
              "order_id": "12345"
            }
          }
        ],
        "created_at": "2023-05-02T10:10:30Z"
      },
      {
        "id": "msg_456789123",
        "conversation_id": "conv_987654321",
        "role": "tool",
        "tool_call_id": "call_12345",
        "content": "{\"status\":\"shipped\",\"carrier\":\"FedEx\",\"tracking_number\":\"FX123456789\",\"estimated_delivery\":\"2023-05-03\"}",
        "created_at": "2023-05-02T10:10:35Z"
      },
      {
        "id": "msg_789123456",
        "conversation_id": "conv_987654321",
        "role": "assistant",
        "content": "I've checked your order #12345 and it's currently in transit. It was shipped via FedEx with tracking number FX123456789 and is estimated to be delivered by May 3, 2023. Would you like me to send you the tracking link?",
        "created_at": "2023-05-02T10:10:40Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total_items": 4,
      "total_pages": 1
    }
  }
}
```

### Run Assistant

#### Run Assistant (Streaming)

Runs an assistant with streaming response.

```
POST /api/v1/assistants/{assistant_id}/run
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "messages": [
    {
      "role": "user",
      "content": "I need help with my recent order #12345. I haven't received it yet."
    }
  ],
  "stream": true,
  "metadata": {
    "user_id": "u_123456",
    "session_id": "sess_789012"
  }
}
```

**Response:**

A stream of Server-Sent Events (SSE) with the following format:

```
event: message_start
data: {"conversation_id":"conv_987654321","message_id":"msg_987654321","role":"assistant"}

event: message_content
data: {"message_id":"msg_987654321","content":"I'm sorry to hear you haven't received your order #12345. "}

event: message_content
data: {"message_id":"msg_987654321","content":"Let me look up the status for you."}

event: tool_call_start
data: {"message_id":"msg_987654321","tool_call_id":"call_12345","type":"workflow","workflow_id":"wf_customer_inquiry"}

event: tool_call_parameters
data: {"tool_call_id":"call_12345","parameters":{"order_id":"12345"}}

event: tool_call_end
data: {"tool_call_id":"call_12345"}

event: tool_output
data: {"message_id":"msg_456789123","tool_call_id":"call_12345","content":"{\"status\":\"shipped\",\"carrier\":\"FedEx\",\"tracking_number\":\"FX123456789\",\"estimated_delivery\":\"2023-05-03\"}"}

event: message_content
data: {"message_id":"msg_987654321","content":"I've checked your order #12345 and it's currently in transit. "}

event: message_content
data: {"message_id":"msg_987654321","content":"It was shipped via FedEx with tracking number FX123456789 and is estimated to be delivered by May 3, 2023. "}

event: message_content
data: {"message_id":"msg_987654321","content":"Would you like me to send you the tracking link?"}

event: message_end
data: {"message_id":"msg_987654321"}

event: done
data: {"conversation_id":"conv_987654321"}
```

#### Run Assistant (Non-Streaming)

Runs an assistant without streaming.

```
POST /api/v1/assistants/{assistant_id}/run
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "messages": [
    {
      "role": "user",
      "content": "I need help with my recent order #12345. I haven't received it yet."
    }
  ],
  "stream": false,
  "metadata": {
    "user_id": "u_123456",
    "session_id": "sess_789012"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "conversation_id": "conv_987654321",
    "messages": [
      {
        "id": "msg_123456789",
        "role": "user",
        "content": "I need help with my recent order #12345. I haven't received it yet.",
        "created_at": "2023-05-02T10:10:00Z"
      },
      {
        "id": "msg_987654321",
        "role": "assistant",
        "content": "I'm sorry to hear you haven't received your order #12345. Let me look up the status for you.",
        "tool_calls": [
          {
            "id": "call_12345",
            "type": "workflow",
            "workflow_id": "wf_customer_inquiry",
            "parameters": {
              "order_id": "12345"
            }
          }
        ],
        "created_at": "2023-05-02T10:10:30Z"
      },
      {
        "id": "msg_456789123",
        "role": "tool",
        "tool_call_id": "call_12345",
        "content": "{\"status\":\"shipped\",\"carrier\":\"FedEx\",\"tracking_number\":\"FX123456789\",\"estimated_delivery\":\"2023-05-03\"}",
        "created_at": "2023-05-02T10:10:35Z"
      },
      {
        "id": "msg_789123456",
        "role": "assistant",
        "content": "I've checked your order #12345 and it's currently in transit. It was shipped via FedEx with tracking number FX123456789 and is estimated to be delivered by May 3, 2023. Would you like me to send you the tracking link?",
        "created_at": "2023-05-02T10:10:40Z"
      }
    ]
  }
}
```

## Python API

### Assistant Management

```python
from abi.assistants import AssistantManager, AssistantConfig, ToolConfig

# Initialize the assistant manager
assistant_manager = AssistantManager(access_token=access_token)

# Create an assistant
assistant_config = AssistantConfig(
    name="Customer Support Assistant",
    description="Handles customer inquiries and provides product information",
    model="gpt-4-1106-preview",
    instructions="You are a helpful customer support agent for Acme Inc. Answer product questions accurately and politely.",
    tools=[
        ToolConfig.workflow(workflow_id="wf_customer_inquiry"),
        ToolConfig.knowledge_base(knowledge_base_id="kb_product_info"),
        ToolConfig.function(
            name="get_customer_data",
            description="Get customer data by email or ID",
            parameters={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer ID"
                    },
                    "email": {
                        "type": "string",
                        "description": "The customer email"
                    }
                },
                "required": ["customer_id"]
            }
        )
    ],
    metadata={
        "department": "support",
        "priority": "high"
    }
)

assistant = assistant_manager.create_assistant(assistant_config)
print(f"Created assistant with ID: {assistant.id}")

# Get assistant by ID
assistant = assistant_manager.get_assistant(assistant.id)

# List assistants
assistants = assistant_manager.list_assistants(
    page=1,
    page_size=10,
    department="support"
)

for ast in assistants.items:
    print(f"{ast.id}: {ast.name}")

# Update an assistant
assistant.name = "Enhanced Customer Support Assistant"
assistant.description = "Handles customer inquiries, provides product information, and can process returns"
assistant.tools.append(ToolConfig.workflow(workflow_id="wf_process_return"))
assistant.metadata["version"] = "2.0"

updated_assistant = assistant_manager.update_assistant(assistant)

# Delete an assistant
assistant_manager.delete_assistant(assistant.id)
```

### Conversations

```python
from abi.assistants import ConversationManager

# Initialize the conversation manager
conversation_manager = ConversationManager(access_token=access_token)

# Create a conversation
conversation = conversation_manager.create_conversation(
    assistant_id="ast_123456789",
    metadata={
        "user_id": "u_123456",
        "session_id": "sess_789012",
        "source": "web_app"
    }
)

print(f"Created conversation with ID: {conversation.id}")

# Get a conversation
conversation = conversation_manager.get_conversation(conversation.id)

# List conversations
conversations = conversation_manager.list_conversations(
    assistant_id="ast_123456789",
    user_id="u_123456",
    page=1,
    page_size=10
)

for conv in conversations.items:
    print(f"{conv.id}: Messages: {conv.message_count}")
```

### Messages

```python
from abi.assistants import MessageManager, Message, Attachment

# Initialize the message manager
message_manager = MessageManager(access_token=access_token)

# Send a message
message = message_manager.send_message(
    conversation_id="conv_987654321",
    content="I need help with my recent order #12345. I haven't received it yet.",
    role="user",
    attachments=[
        Attachment(
            type="image",
            file_id="file_abcdef123456",
            description="Screenshot of my order confirmation"
        )
    ]
)

print(f"Sent message with ID: {message.id}")

# Get messages
messages = message_manager.get_messages(
    conversation_id="conv_987654321",
    page=1,
    page_size=10
)

for msg in messages.items:
    print(f"{msg.role}: {msg.content}")
```

### Running Assistants

```python
from abi.assistants import AssistantRunner
import json

# Initialize the assistant runner
runner = AssistantRunner(access_token=access_token)

# Run assistant with streaming
async def run_streaming():
    async for event in runner.run_streaming(
        assistant_id="ast_123456789",
        messages=[
            {"role": "user", "content": "I need help with my recent order #12345. I haven't received it yet."}
        ],
        metadata={
            "user_id": "u_123456",
            "session_id": "sess_789012"
        }
    ):
        if event.type == "message_content":
            print(f"Assistant: {event.data['content']}", end="")
        elif event.type == "tool_output":
            print(f"\nTool output: {json.loads(event.data['content'])}")
        elif event.type == "done":
            print(f"\nConversation ID: {event.data['conversation_id']}")

# Run in an async context
import asyncio
asyncio.run(run_streaming())

# Run assistant without streaming
response = runner.run(
    assistant_id="ast_123456789",
    messages=[
        {"role": "user", "content": "I need help with my recent order #12345. I haven't received it yet."}
    ],
    metadata={
        "user_id": "u_123456",
        "session_id": "sess_789012"
    }
)

print(f"Conversation ID: {response.conversation_id}")
for message in response.messages:
    print(f"{message.role}: {message.content}")
```

## Assistant Configuration

### Models

ABI supports various language models:

| Model ID | Description | 
|----------|-------------|
| gpt-4-1106-preview | OpenAI GPT-4 Turbo |
| gpt-3.5-turbo | OpenAI GPT-3.5 Turbo |
| claude-3-opus | Anthropic Claude 3 Opus |
| claude-3-sonnet | Anthropic Claude 3 Sonnet |
| llama-2-70b | Meta Llama 2 70B |
| mistral-large | Mistral Large |

### Tools

Assistants can be configured with different types of tools:

1. **Workflow Tools**:
   ```json
   {
     "type": "workflow",
     "workflow_id": "wf_customer_inquiry"
   }
   ```

2. **Knowledge Base Tools**:
   ```json
   {
     "type": "knowledge_base",
     "knowledge_base_id": "kb_product_info"
   }
   ```

3. **Function Tools**:
   ```json
   {
     "type": "function",
     "function": {
       "name": "get_weather",
       "description": "Get the current weather in a location",
       "parameters": {
         "type": "object",
         "properties": {
           "location": {
             "type": "string",
             "description": "The city and state, e.g. San Francisco, CA"
           },
           "unit": {
             "type": "string",
             "enum": ["celsius", "fahrenheit"],
             "description": "The unit of temperature"
           }
         },
         "required": ["location"]
       }
     }
   }
   ```

4. **Ontology Tools**:
   ```json
   {
     "type": "ontology",
     "ontology_id": "ont_business_data"
   }
   ```

5. **Integration Tools**:
   ```json
   {
     "type": "integration",
     "integration_id": "int_salesforce",
     "operations": ["read_contacts", "update_contacts"]
   }
   ```

### Instructions

Assistant instructions can define persona, capabilities, and behavior. Good instructions:

1. Define the assistant's role and personality
2. Specify the domain expertise
3. Include formatting preferences
4. Set guidelines for handling sensitive information
5. Establish interaction patterns

Example instructions:

```
You are a customer support agent for Acme Inc. You help customers with product inquiries, 
order status, and technical issues.

Your personality is:
- Friendly and helpful
- Professional but approachable
- Patient with frustrated customers

Domain expertise:
- Acme product catalog and features
- Order processing and shipping
- Technical troubleshooting

When responding:
- Be concise but thorough
- Use bullet points for multiple steps
- Confirm customer understanding before proceeding

Privacy guidelines:
- Do not display full order numbers (use last 4 digits)
- Never show complete credit card numbers
- Verify identity before providing account details

For complex issues, use the appropriate tool to escalate to a human agent.
```

## Webhooks

You can configure webhooks to receive events from assistants:

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
  "url": "https://example.com/webhooks/assistant",
  "events": ["message.created", "conversation.created", "tool.called"],
  "secret": "whsec_abcdefghijklmnopqrstuvwxyz",
  "description": "Production webhook for assistant events"
}
```

## Best Practices

1. **Assistant Design**:
   - Create focused assistants for specific use cases
   - Provide clear and detailed instructions
   - Configure only the tools needed for the task

2. **Conversation Management**:
   - Store metadata to track context
   - Implement proper conversation timeouts
   - Archive old conversations periodically

3. **Message Handling**:
   - Validate user inputs
   - Handle attachments securely
   - Implement rate limiting for message sending

4. **Tool Usage**:
   - Monitor tool execution performance
   - Implement fallbacks for tool failures
   - Log tool calls for debugging

5. **Security**:
   - Validate all inputs
   - Implement content filtering
   - Use scoped API keys

## Error Handling

Common errors when working with assistants:

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| 400 | INVALID_ASSISTANT_CONFIG | Invalid assistant configuration |
| 400 | INVALID_MESSAGE_FORMAT | Message format is invalid |
| 404 | ASSISTANT_NOT_FOUND | Assistant not found |
| 404 | CONVERSATION_NOT_FOUND | Conversation not found |
| 429 | RATE_LIMIT_EXCEEDED | Rate limit exceeded |
| 500 | MODEL_ERROR | Error from the language model |
| 500 | TOOL_EXECUTION_ERROR | Error executing a tool |

## Next Steps

- Learn about [Workflows API](workflows.md) to build the workflows used by assistants
- Explore the [Knowledge Base API](knowledge-bases.md) to create knowledge sources
- Check the [Ontology API](ontology.md) to define semantic knowledge 