# Publish Remote Agents

This guide explains how to publish ABI agents as remote plugins on the Naas platform. This feature is only available if you have access to the Naas platform.

## Automatic Publishing (Recommended)

The system now supports automatic publishing of remote agents to your workspace. When enabled, agents will be automatically published to the specified workspace using `config.workspace_id` whenever the API is deployed.

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
  auto_publish:
    enabled: true # Enable automatic publishing of agents to workspace
    exclude_agents: [] # Agents to exclude from auto-publishing (empty list means publish all enabled agents)
    default_agent: "Abi" # Which agent to set as default in workspace
  github_repository: "your_github_username/your_repository_name"
  space_name: "your_naas_space_name"
  # ... other configuration options
```

#### Auto-Publish Configuration Options

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `enabled` | Enable/disable automatic publishing | `true` | `true` |
| `exclude_agents` | List of agent names to exclude from publishing | `[]` | `["TestAgent", "DebugAgent"]` |
| `default_agent` | Agent to set as default in the workspace | `"Abi"` | `"MyCustomAgent"` |

## How to Publish Remote Agents

### Method 1: Automatic Publishing (Recommended)

When `auto_publish.enabled` is set to `true` in your `config.yaml`, agents will be automatically published to your workspace after each API deployment via GitHub Actions.

**Benefits:**
- ✅ Simplifies deployment workflow  
- ✅ Ensures agents are up-to-date
- ✅ Reduces manual intervention
- ✅ Publishes all enabled agents automatically
- ✅ Excludes only specified agents via `exclude_agents`

**How it works:**
1. GitHub Actions workflow triggers after successful API deployment
2. Checks if auto-publish is enabled in configuration
3. Verifies API accessibility
4. Publishes all enabled agents except those in `exclude_agents`
5. Sets the `default_agent` as the workspace default

### Method 2: Manual Publishing with Make Command

You can also manually publish agents using:

```bash
make publish-remote-agents
```

**Dry-Run Mode (Preview Changes):**
To preview what agents would be published without making actual changes:

```bash
make publish-remote-agents-dry-run
```

Or directly:
```bash
uv run python scripts/publish_remote_agents.py --dry-run
# Alternative flags: --dryrun, -n
```

**Dry-run benefits:**
- ✅ Preview all agents that would be published
- ✅ See detailed plugin configuration data
- ✅ Test configuration without API keys
- ✅ Identify excluded agents
- ✅ Verify API URLs and workspace settings
- ✅ No actual changes made to workspace or GitHub

**Legacy behavior (when `auto_publish.enabled: false`):**
- Publishes only specific agents: `Abi`, `Ontology`, `Naas`, `Multi_Models`, `Support`
- Requires manual execution

**New behavior (when `auto_publish.enabled: true`):**  
- Publishes all enabled agents except those in `exclude_agents`
- Uses configuration from `config.yaml`

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
    default_agent="Abi",
agents_to_publish=["Abi", "Ontology", "Naas"]
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
| `default_agent` | Name of the agent to set as default | No | "Abi" |
| `agents_to_publish` | List of agent names to publish (legacy mode) | No | ["Abi", "Ontology", "Naas", "Multi_Models", "Support"] |
| `exclude_agents` | List of agent names to exclude from publishing | No | [] |
| `auto_publish_enabled` | Enable automatic publishing mode | No | false |

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

**Auto-publish mode (when `auto_publish.enabled: true`):**
- **Loads All Agent Modules**: Dynamically loads all available ABI agent modules
- **Filters by Exclusion**: Publishes all agents except those listed in `exclude_agents`
- **Extracts Agent Metadata**: Gathers agent information for all valid agents

**Legacy mode (when `auto_publish.enabled: false`):**
- **Loads Specific Agents**: Only processes agents listed in `agents_to_publish`
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

## GitHub Actions Workflow

The automatic publishing is handled by the `.github/workflows/auto-publish-agents.yml` workflow:

### Workflow Triggers
- **After API Deployment**: Automatically runs after the "ABI API" workflow completes successfully
- **Manual Trigger**: Can be manually triggered via GitHub Actions UI with force publish option

### Workflow Steps
1. **Checkout Code**: Gets the latest code from the repository
2. **Setup Environment**: Installs Python 3.10 and uv package manager
3. **Install Dependencies**: Installs all project dependencies
4. **Check Configuration**: Verifies auto-publish is enabled and gets API URL
5. **Verify API Access**: Waits up to 5 minutes for the API to be accessible
6. **Publish Agents**: Runs the publishing script with proper configuration
7. **Notify Results**: Reports success or failure

### Required Secrets
The workflow requires these GitHub repository secrets:
- `NAAS_API_KEY`: Your Naas platform API key
- `ABI_API_KEY`: Your ABI API authentication key  
- `GITHUB_TOKEN`: Automatically provided by GitHub Actions

### Workflow Configuration
The workflow is configured to trigger after the "ABI API" deployment workflow:
```yaml
workflows: ["ABI API"] # Matches the actual API deployment workflow name
```

## Expected Output

When running the script successfully, you should see output similar to:

**Auto-publish mode:**
```
🚀 Auto-publish enabled: True
🚫 Excluded agents: None
⭐ Default agent: Abi
🔍 Getting existing plugins from workspace: your_workspace_id
==> Getting agents from module: src/core/abi
==> Publishing agent: Abi
✅ Plugin 'Abi' updated in workspace 'your_workspace_id'
==> Publishing agent: Ontology
✅ Plugin 'Ontology' created in workspace 'your_workspace_id'
==> Skipping excluded agent: TestAgent
...
```

**Legacy mode:**
```
🚀 Auto-publish enabled: False
📝 Publishing specific agents: ['Abi', 'Ontology', 'Naas', 'Multi_Models', 'Support']
⭐ Default agent: Abi
🔍 Getting existing plugins from workspace: your_workspace_id
==> Publishing agent: Abi
✅ Plugin 'Abi' updated in workspace 'your_workspace_id'
...
```

**Dry-run mode:**
```
🧪 DRY RUN MODE - No changes will be made
==================================================
🚀 Auto-publish enabled: True
🚫 Excluded agents: ['TestAgent']
⭐ Default agent: Abi
🌐 API Base URL: https://abi-api.default.space.naas.ai
🏢 Workspace ID: your_workspace_id
🧪 DRY RUN MODE: No actual changes will be made
🧪 [DRY RUN] Would fetch existing plugins from workspace
🧪 [DRY RUN] Would update "ABI_API_KEY" secret in Github repository: your_repo
==> Getting agents from module: src/core/abi
🧪 [DRY RUN] Would publish agent: Abi
🧪 [DRY RUN] Plugin data for 'Abi':
    - ID: abi
    - Name: Abi
    - Type: CORE
    - Default: True
    - Remote URL: https://abi-api.default.space.naas.ai/agents/abi/stream-completion?token=dummy_abi_api_key
    - Avatar: https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png
    - Description: I'm Abi, your Artificial Business Intelligence assistant...
    - Suggestions: 4 items
🧪 [DRY RUN] Would check if plugin 'abi' already exists
🧪 [DRY RUN] Would create/update plugin in workspace 'your_workspace_id'
🧪 [DRY RUN] Would skip excluded agent: TestAgent
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