# AI Network Configuration System

The AI Network Configuration System replaces the old "disabled" prefix approach with a centralized, YAML-based configuration system that provides fine-grained control over module loading.

## Overview

Instead of renaming directories with `.disabled` suffixes, you now configure which modules to load directly in `config.yaml` under the `ai_network` section. This provides:

- **Centralized Control**: All module configuration in one place
- **Priority-Based Loading**: Control the order modules are loaded
- **Category Organization**: Modules organized by type (core models, domain experts, applications, custom)
- **Rich Metadata**: Descriptions and priorities for each module
- **CLI Management**: Command-line tools for easy configuration

## Configuration Structure

The `ai_network` section in `config.yaml` contains four main categories:

### Core Models
Foundation language models (ChatGPT, Claude, Gemini, etc.)

### Domain Experts  
Specialized business role agents (Software Engineer, Accountant, etc.)

### Applications
External service integrations (GitHub, ArXiv, etc.)

### Custom Modules
User-defined modules in `src/custom/modules`

## Example Configuration

```yaml
ai_network:
  # Core AI Models - Foundation language models
  core_models:
    enabled: true
    modules:
      - name: "abi"
        enabled: true
        priority: 1
        description: "Core ABI system with ontology management"
      - name: "chatgpt"
        enabled: true
        priority: 2
        description: "OpenAI GPT models integration"
      - name: "claude"
        enabled: false
        priority: 3
        description: "Anthropic Claude models integration"

  # Domain Expert Agents - Specialized business roles
  domain_experts:
    enabled: true
    modules:
      - name: "software-engineer"
        enabled: true
        priority: 1
        description: "Software development and architecture expert"
      - name: "data-engineer"
        enabled: false
        priority: 2
        description: "Data pipeline and infrastructure expert"

  # Application Integrations - External service integrations
  applications:
    enabled: true
    modules:
      - name: "github"
        enabled: true
        priority: 1
        description: "GitHub repository and project management integration"

  # Custom Modules - User-defined modules
  custom_modules:
    enabled: true
    auto_discover: true # Automatically discover modules in src/custom/modules
    modules: []

  # Module Loading Settings
  loading:
    fail_on_error: true # Stop loading if a module fails
    parallel_loading: false # Load modules in parallel (experimental)
    timeout_seconds: 30 # Timeout for module loading
    retry_attempts: 3 # Number of retry attempts for failed modules
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
python src/cli.py network enable gemini core_models

# Disable a module  
python src/cli.py network disable claude core_models
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
| `core_models` | `src/core/modules/` | Foundation AI models |
| `domain_experts` | `src/marketplace/modules/domains/modules/` | Business role specialists |
| `applications` | `src/marketplace/modules/applications/` | External integrations |
| `custom_modules` | `src/custom/modules/` | User-defined modules |

## Migration from Disabled Prefix System

### Old System (Deprecated)
```bash
# Disable a module
mv src/core/modules/claude src/core/modules/claude.disabled

# Enable a module
mv src/core/modules/claude.disabled src/core/modules/claude
```

### New System
```yaml
# In config.yaml
ai_network:
  core_models:
    modules:
      - name: "claude"
        enabled: false  # Disabled
        # enabled: true   # Enabled
```

Or use the CLI:
```bash
python src/cli.py network disable claude core_models
python src/cli.py network enable claude core_models
```

## Advanced Features

### Priority-Based Loading
Modules are loaded in priority order (lower number = higher priority):

```yaml
modules:
  - name: "abi"
    priority: 1  # Loads first
  - name: "chatgpt"  
    priority: 2  # Loads second
```

### Category-Level Control
Disable entire categories:

```yaml
domain_experts:
  enabled: false  # Disables all domain expert modules
```

### Auto-Discovery
For custom modules, enable auto-discovery to automatically load any modules found:

```yaml
custom_modules:
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

core_modules = get_modules_by_category("core_models")
domain_experts = get_modules_by_category("domain_experts")
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

## Backward Compatibility

The system still recognizes `.disabled` suffixes and will warn you about them:

```
⚠️ Module 'arxiv' exists but is disabled via .disabled suffix
💡 Remove .disabled suffix or update config to enable: src/marketplace/modules/applications/arxiv.disabled
```

This allows for gradual migration from the old system to the new configuration approach.
