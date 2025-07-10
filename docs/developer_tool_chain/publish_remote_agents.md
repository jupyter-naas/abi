# Publish Remote Agents

This guide explains how to publish ABI agents as remote plugins on the Naas platform. This feature is only available if you have access to the Naas platform.

## Prerequisites

Before publishing remote agents, ensure you have:

1. **Naas Platform Access**: Access to the Naas platform with appropriate permissions
2. **GitHub Repository**: A GitHub repository where your ABI project is hosted
3. **Required API Keys and Tokens**: All necessary authentication credentials

## Required Configuration

### Environment Variables

You need to set up the following environment variables in your `.env` file:

```bash
# Naas Platform Configuration
NAAS_API_KEY=your_naas_api_key_here
ABI_API_KEY=your_abi_api_key_here

# GitHub Configuration  
GITHUB_ACCESS_TOKEN=your_github_personal_access_token_here
```

### Configuration File

Update your `config.yaml` file with the following settings:

```yaml
config:
  workspace_id: "your_naas_workspace_id"
  github_project_repository: "your_github_username/your_repository_name"
  space_name: "your_naas_space_name"
  # ... other configuration options
```

## How to Publish Remote Agents

### Method 1: Using Make Command (Recommended)

The easiest way to publish remote agents is using the provided Make command:

```bash
make publish-remote-agents
```
This command performs the following actions:
1. Reads configuration settings from your environment and config files
2. Publishes a predefined set of agents:
   - `Supervisor` (set as default)
   - `Ontology` 
   - `Naas`
   - `Multi_Models`
   - `Support`
3. Configures the published agents with appropriate settings

To customize which agents are published, you can modify the `agents_to_publish` list directly in the script.
Use the agent name to add more agents to publish.

### Method 2: Running the Script Directly

You can also run the script directly with custom parameters:

```bash
uv run python scripts/publish_remote_agents.py
```

### Method 3: Programmatic Usage

For advanced usage, you can import and use the function directly:

```python
from scripts.publish_remote_agents import publish_remote_agent

publish_remote_agent(
    naas_api_key="your_naas_api_key",
    api_base_url="https://your-space.default.space.naas.ai",
    abi_api_key="your_abi_api_key",
    workspace_id="your_workspace_id",
    github_access_token="your_github_token",
    github_repository="your_username/your_repo",
    default_agent="Supervisor",
    agents_to_publish=["Supervisor", "Ontology", "Naas"]
)
```

## Configuration Parameters

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `naas_api_key` | Your Naas platform API key | Yes | - |
| `api_base_url` | Base URL for your ABI API (format: `https://{space_name}.default.space.naas.ai`) | Yes | - |
| `abi_api_key` | API key for ABI authentication | Yes | - |
| `workspace_id` | Naas workspace ID where plugins will be published | Yes | - |
| `github_access_token` | GitHub personal access token | Yes | - |
| `github_repository` | GitHub repository name (format: `username/repository`) | Yes | - |
| `default_agent` | Name of the agent to set as default | No | "Supervisor" |
| `agents_to_publish` | List of agent names to publish | No | ["Supervisor", "Ontology", "Naas", "Multi_Models", "Support"] |

## What the Script Does

The `publish_remote_agents.py` script performs the following process:

### 1. Initialization
- **Naas Integration Setup**: Initializes connection to the Naas platform using your API key
- **GitHub Integration Setup**: Sets up GitHub integration for repository secret management
- **Retrieves Existing Plugins**: Fetches current plugins from your Naas workspace

### 2. GitHub Secret Management
- **Updates ABI API Key**: Creates or updates the `ABI_API_KEY` secret in your GitHub repository
- This secret is used by the remote agents to authenticate with your ABI API

### 3. Agent Discovery and Processing
For each agent specified in `agents_to_publish`:

- **Loads Agent Modules**: Dynamically loads all available ABI agent modules
- **Extracts Agent Metadata**: Gathers agent information including:
  - Name and description
  - System prompt from agent configuration
  - Avatar URL and suggestions from the module
  - API route name for remote access

### 4. Plugin Data Preparation
Creates a plugin configuration object with:
- **Basic Information**: ID, name, slug, description
- **AI Configuration**: Model (gpt-4o), temperature (0), prompt type
- **Remote Configuration**: API endpoint URL with authentication token
- **UI Elements**: Avatar, suggestions for user interaction

### 5. Plugin Publication
For each agent:
- **Checks Existing Plugins**: Searches for existing plugins with the same ID
- **Updates or Creates**: 
  - If plugin exists: Updates the existing plugin
  - If plugin doesn't exist: Creates a new plugin
- **Logs Results**: Provides feedback on successful publication

### 6. Default Agent Setting
- Sets the specified `default_agent` as the default plugin in the workspace
- This agent will be pre-selected when users access your workspace

## Expected Output

When running the script successfully, you should see output similar to:

```
==> Getting existing plugins from workspace: your_workspace_id
==> Existing plugins: 5
==> Updating "ABI_API_KEY" secret in Github repository: your_username/your_repo
==> Publishing agent: Supervisor
Plugin 'Supervisor' updated in workspace 'your_workspace_id'
==> Publishing agent: Ontology
Plugin 'Ontology' created in workspace 'your_workspace_id'
...
```

## Troubleshooting

### Common Issues

1. **Missing Environment Variables**
   ```
   ValueError: NAAS_API_KEY, API_BASE_URL, ABI_API_KEY, WORKSPACE_ID, GITHUB_ACCESS_TOKEN, and GITHUB_REPOSITORY must be set
   ```
   **Solution**: Ensure all required environment variables are set in your `.env` file

2. **Invalid Route Name**
   ```
   ValueError: Route name not found for agent AgentName
   ```
   **Solution**: Ensure the agent has a properly configured `as_api` method with a `route_name` parameter

3. **Authentication Errors**
   - Check that your API keys and tokens are valid and have the necessary permissions
   - Verify your Naas workspace ID is correct
   - Ensure your GitHub access token has repository access

### Verification

After publishing, you can verify the agents are available by:
1. Logging into your Naas workspace
2. Checking the plugins section
3. Testing the remote agents through the Naas interface

## Security Considerations

- **API Keys**: Never commit API keys to version control
- **GitHub Tokens**: Use GitHub personal access tokens with minimal required permissions
- **Workspace Access**: Ensure only authorized users have access to your Naas workspace
- **Secret Management**: The script automatically manages GitHub repository secrets for secure API access