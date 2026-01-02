TAGS_METADATA = [
    {
        "name": "Overview",
        "description": """
### Project Overview
The **ABI** (Artificial Business Intelligence) project is a Python-based backend framework designed to serve as the core infrastructure for building an Organizational AI System. 
This system empowers businesses to integrate, manage, and scale AI-driven operations with a focus on ontology, assistant-driven workflows, and analytics.\n
Designed for flexibility and scalability, ABI provides a customizable framework suitable for organizations aiming to create intelligent, automated systems tailored to their needs.

### API Overview
The ABI API allows users and applications to interact with ABI's capabilities for business process automation and intelligence.\n
This document describes the current version of the ABI API, which provides access to agents, pipelines, workflows, integrations, ontology management and analytics features.
        """,
    },
    {
        "name": "Authentication",
        "description": """
Authentication uses a Bearer token that can be provided either in the Authorization header (e.g. 'Authorization: Bearer `<token>`') or as a query parameter (e.g. '?token=`<token>`'). 
The token must match the `ABI_API_KEY` environment variable.
Contact your administrator to get the token.

*Authentication with Authorization header:*

```python
import requests

url = "https://<your-registry-name>.default.space.naas.ai/agents/abi/completion"

headers = {
    "Authorization": f"Bearer {token}"
}

response = requests.post(url, headers=headers)
print(response.json())
```

*Authentication with query parameter:*

```python
import requests

url = "https://<your-registry-name>.default.space.naas.ai/agents/abi/completion?token=<token>"

response = requests.post(url)
print(response.json())
```
        """,
    },
    {
        "name": "Agents",
        "description": """
API endpoints for interacting with ABI's agents.

### Core Agents:
- Abi: Manages and coordinates other agents
- Ontology: Manages and coordinates other agents
- Naas: Manages and coordinates other agents
- Support: Provides help and guidance for using ABI

### Marketplace Agents:
- Custom agents with deep expertise in specific domains
- Can be configured and trained for specialized tasks
- Extensible through custom tools and knowledge bases

Each agent can be accessed through dedicated endpoints that allow:
- Completion requests for generating responses
- Chat interactions for ongoing conversations
- Tool execution for specific tasks
- Configuration updates for customizing behavior

Agents leverage various tools including integrations, pipelines and workflows to accomplish tasks. They can be extended with custom tools and knowledge to enhance their capabilities.

        """,
    },
    {
        "name": "Pipelines",
        "description": """
API endpoints for interacting with ABI's pipelines.
        """,
    },
    {
        "name": "Workflows",
        "description": """
API endpoints for interacting with ABI's workflows.
        """,
    },
]

API_LANDING_HTML = """
<!DOCTYPE html>
<html>
    <head>
        <title>[TITLE]</title>
        <link rel="icon" type="image/x-icon" href="/static/favicon.ico">
        <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
                background-color: #000000;
                color: white;
            }
            .logo {
                width: 200px;
                margin-bottom: 20px;
            }
            h1 {
                font-size: 48px;
                margin-bottom: 40px;
            }
            .buttons {
                display: flex;
                gap: 20px;
            }
            a {
                padding: 12px 24px;
                font-size: 18px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                text-decoration: none;
                color: white;
                background-color: #007bff;
                transition: background-color 0.2s;
            }
            a:hover {
                background-color: #0056b3;
            }
        </style>
    </head>
    <body>
        <img src="/static/[LOGO_NAME]" alt="Logo" class="logo">
        <h1>Welcome to [TITLE]!</h1>
        <p>[TITLE] is a tool that allows you to interact with ABI's capabilities for business process automation and intelligence.</p>
        <div class="buttons">
            <a href="/redoc">Go to Documentation</a>
        </div>
    </body>
</html>
"""
