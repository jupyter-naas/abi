# AI Network Configuration System

The AI Network Configuration System provides centralized, configuration-driven control over your multi-agent AI ecosystem. All agents, intent mappings, and system behaviors are dynamically loaded from a single configuration file.

## Overview

Configure your AI Network through a YAML-based system that delivers:

- **Configuration-Driven Architecture**: All agents and intents defined in config.yaml
- **SLUG-Based Routing**: Consistent agent identification and routing system
- **Enhanced Intent Mapping**: Support for RAW, TOOL, and AGENT intent types
- **Dynamic Agent Loading**: Enable/disable agents without code changes
- **Zero Hardcoded Elements**: Complete flexibility through configuration

## Configuration Structure

The `ai_network` section in `config.yaml` uses a flat, SLUG-based structure where each agent is defined by its unique identifier (SLUG).

### Agent Definition
Each agent contains:
- **enabled**: Boolean flag for activation
- **description**: Brief agent description
- **strengths**: Core capabilities
- **use_when**: Recommended use cases

### ABI Intent Mapping
The ABI agent contains centralized intent mapping with three types:
- **raw_intents**: Direct text responses (key-value pairs)
- **tool_intents**: Route to specific tools/functions
- **agent_intents**: Route to specific agents

## Example Configuration

```yaml
ai_network:
  # ABI Orchestrator with centralized intent mapping
  abi:
    enabled: true
    description: "Multi-agent orchestrator"
    strengths: "Orchestration, strategic advisory"
    use_when: "Identity, strategy, coordination"
    intent_mapping:
      raw_intents:
        "what is your name": "My name is ABI"
        "who are you": "I am ABI, developed by NaasAI"
      tool_intents:
        open_knowledge_graph_explorer:
          - "show knowledge graph"
          - "sparql query"
        check_ai_network_config:
          - "list agents"
          - "agent status"
      agent_intents:
        chatgpt:
          - "use chatgpt"
          - "web search"
        claude:
          - "use claude"
          - "anthropic"

  # Foundation AI Models
  chatgpt:
    enabled: true
    description: "OpenAI ChatGPT"
    strengths: "General conversation, coding"
    use_when: "General tasks, coding help"

  claude:
    enabled: true
    description: "Anthropic Claude"
    strengths: "Analysis, writing"
    use_when: "Detailed analysis"

  # Disabled agents (ready for activation)
  llama:
    enabled: false
    description: "Meta Llama"
    strengths: "Local, private"
    use_when: "Private tasks"
```

## CLI Management

Use the integrated ABI CLI to manage your AI Network configuration:

### List All Modules
```bash
python src/cli.py network list
python src/cli.py network list --show-disabled  # Include disabled modules
```

### Enable/Disable Modules
```bash
# Enable a module
python src/cli.py network enable gemini core

# Disable a module  
python src/cli.py network disable claude core
```

### Validate Configuration
```bash
python src/cli.py network validate
```

### Show Current Configuration
```bash
python src/cli.py network show
```

### Additional CLI Commands
```bash
# System status and health checks
python src/cli.py system status

# List available agents
python src/cli.py agent list

# Start interactive chat (default behavior)
python src/cli.py chat
python src/cli.py  # Same as above

# Get help
python src/cli.py --help
python src/cli.py network --help
```

## Module Categories and Paths

| Category | File System Path | Description |
|----------|------------------|-------------|
| `core` | `src/core/modules/` | Foundation AI models |
| `marketplace` | `src/marketplace/modules/domains/modules/` | Business role specialists |
| `applications` | `src/marketplace/modules/applications/` | External integrations |
| `custom` | `src/custom/modules/` | User-defined modules |

## Configuration Management

### Declarative Configuration
```yaml
# In config.yaml
ai_network:
  core:
    modules:
      - name: "claude"
        enabled: true
        description: "Anthropic Claude models integration"
```

### CLI Management
```bash
python src/cli.py network enable claude core
python src/cli.py network disable claude core
python src/cli.py network list  # View current status
```

## Advanced Features

### Natural Configuration Flow
Modules load in the exact order they appear in your `config.yaml` file:

- **Categories** load in the order defined in the YAML structure
- **Modules** within each category load in their configuration sequence
- **No artificial priorities** or hardcoded loading rules
- **Simple reordering** - just move entries up/down in the config file

This approach provides predictable, intuitive module management without complex priority systems.

### Category-Level Control
Disable entire categories:

```yaml
marketplace:
  enabled: false  # Disables all domain expert modules
```

### Auto-Discovery
For custom modules, enable auto-discovery to automatically load any modules found:

```yaml
custom:
  enabled: true
  auto_discover: true  # Automatically finds modules in src/custom/modules
```

### Error Handling
Configure how the system handles module loading failures:

```yaml
loading:
  fail_on_error: true      # Stop if any module fails to load
  retry_attempts: 3        # Number of retry attempts
  timeout_seconds: 30      # Timeout for each module
```

## Programmatic Access

### Get Loaded Modules
```python
from src.__modules__ import get_modules

modules = get_modules()
print(f"Loaded {len(modules)} modules")
```

### Get Modules by Category
```python
from src.__modules__ import get_modules_by_category

core_modules = get_modules_by_category("core")
marketplace = get_modules_by_category("marketplace")
```

### Reload Modules (Development)
```python
from src.__modules__ import reload_modules

# Reload all modules with current configuration
modules = reload_modules()
```

### Configuration Access
```python
from src.utils.ConfigLoader import get_ai_network_config

config = get_ai_network_config()
enabled_modules = config.get_enabled_modules()
```

## Best Practices

1. **Start Small**: Enable only the modules you need to reduce startup time
2. **Use Priorities**: Set priorities to control loading order for dependencies
3. **Test Changes**: Use `validate` command before restarting the application
4. **Document Custom Modules**: Add clear descriptions for your custom modules
5. **Monitor Performance**: Check loading times with different module combinations

## Troubleshooting

### Module Not Loading
1. Check if the module is enabled: `python src/cli.py network list`
2. Validate configuration: `python src/cli.py network validate`
3. Check module directory exists in the correct path
4. Review application logs for specific error messages

### Configuration Errors
```bash
# Validate your configuration
python src/cli.py network validate

# Check system status
python src/cli.py system status
```

### Performance Issues
- Disable unused modules to reduce startup time
- Consider enabling `parallel_loading` (experimental)
- Monitor module loading times in logs

## Legacy Support

The system automatically detects legacy `.disabled` suffixes and provides migration guidance:

```
⚠️ Module 'arxiv' exists but is disabled via .disabled suffix
💡 Remove .disabled suffix or update config to enable: src/marketplace/modules/applications/arxiv.disabled
```

This ensures smooth transitions when upgrading existing installations.
