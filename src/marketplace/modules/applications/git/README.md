# Git Module

## Overview

### Description

The Git Module provides AI-powered tools for Git workflow automation, specifically focused on pull request management and description generation. It integrates with the ABI framework to automate common Git development tasks.

This module enables:
- Automated pull request description generation
- Git diff analysis and branch information extraction
- Clipboard integration for easy PR description sharing
- Integration with ABI framework's agent system
- Git workflow automation and repository management

### Requirements

No external API keys required - the module uses local Git operations and OpenAI integration from the ABI framework.

### TL;DR

To get started with the Git module:

1. Ensure you're in a Git repository with an origin/main remote
2. Make changes and commit them to a feature branch

Start generating pull request descriptions using this command:
```bash
make pull-request-description
```

### Structure

```
src/core/modules/git/

├── agents/                                       
│   └── PullRequestDescriptionAgent.py              
└── README.md                       
```

## Core Components
Concise list of available components with capabilities.

### Agents

#### Pull Request Description Agent

An AI agent that automatically generates pull request descriptions from git diffs. Analyzes branch changes, extracts branch name and diff information, creates structured PR descriptions with issue references, and handles file storage with clipboard integration.

**Capabilities:**
- Git diff analysis against origin/main
- Automated PR description generation
- Branch name and issue number extraction
- File storage and clipboard integration

**Command:**
```bash
make pull-request-description
```

**Use Cases:**
- Automated pull request documentation
- Git workflow automation
- Developer productivity enhancement
- Consistent PR description formatting

#### Testing
Run tests for the Pull Request Description Agent:
```bash
uv run python -m pytest src/core/modules/git/agents/PullRequestDescriptionAgent_test.py
```

### Integrations

#### Git Integration

The Git Integration provides tools for Git operations, diff analysis, and file storage capabilities.

**Functions:**
- `git_diff()`: Retrieves current branch name and diff against origin/main
- `store_pull_request_description(description)`: Saves description to storage
- `store_pull_request_description_to_clipboard()`: Copies description to clipboard

##### Configuration

```python
# Git integration is automatically configured
# No additional setup required - uses local Git commands
```

#### Run
Execute Git integration functions through the agent:
```bash
make pull-request-description
```

### Models
Currently no specific models are implemented. The module uses the OpenAI integration from the ABI framework.

### Ontologies

#### Git Ontology

Currently no specific ontology is implemented for the Git module.

#### Git Sparql Queries

Currently no SPARQL queries are implemented for the Git module.

### Pipelines
Currently no specific pipelines are implemented. The module operates through direct agent execution.

### Workflows
Currently no specific workflows are implemented. The module operates through the Pull Request Description Agent workflow.

## Usage Examples

### Generate Pull Request Description

```bash
# Generate PR description from current branch
make pull-request-description

# The agent will:
# 1. Analyze git diff against origin/main
# 2. Extract branch name and changes
# 3. Generate structured description
# 4. Save to pull_request_description.md
# 5. Copy to clipboard
```

### Manual Agent Usage

```bash
# Start the agent interactively
make chat Agent=PullRequestDescriptionAgent

# The agent will prompt for confirmation and execute the workflow
```

## Output Format

Generated pull request descriptions follow this structure:

```markdown
This pull request resolves #<branch_name_number>

[Generated description based on git diff analysis]
```

Where `<branch_name_number>` is extracted from the branch name (e.g., "123-feature" becomes "#123").

## Integration

### Makefile Integration
The git module integrates with the project Makefile:

```makefile
pull-request-description: deps
	@ echo "Generate the description of the pull request please." | uv run python -m src.core.apps.terminal_agent.main generic_run_agent PullRequestDescriptionAgent
```

### Git Hooks
The project includes pre-commit hooks that run quality checks:
- Automatically runs `make check` before commits
- Ensures code quality and consistency

## Dependencies

### Python Libraries
- `abi.integration`: Base integration framework
- `abi.services.agent`: Agent framework
- `langchain_core`: Tool integration for AI agents
- `langchain_openai`: LangChain OpenAI integration
- `pyperclip`: Cross-platform clipboard operations
- `subprocess`: Git command execution

### Modules

- `git`: System Git integration for repository operations

## Workflow

1. **Branch Setup**: Ensure you're on a feature branch with changes
2. **Commit Changes**: Stage and commit your changes
3. **Generate Description**: Run `make pull-request-description`
4. **Review**: Check the generated `pull_request_description.md`
5. **Use**: Copy from clipboard or file for your PR

## Troubleshooting

### Common Issues

1. **No Git Repository**: Ensure you're in a git repository with origin/main remote
2. **No Changes**: Make sure you have uncommitted changes or commits ahead of origin/main
3. **Branch Naming**: Branch names should include issue numbers for proper PR linking
4. **Clipboard Access**: Some systems may require additional setup for clipboard operations

### Error Handling

- **Git Commands**: Agent handles git command failures gracefully
- **File Operations**: Automatic error handling for file read/write operations
- **API Access**: OpenAI API key must be configured in environment

## Security Features

1. **Safe Git Operations**: Uses subprocess with proper error handling
2. **File Isolation**: Generated files are stored in project root
3. **No Sensitive Data**: Only analyzes code changes, not sensitive information
4. **Controlled Output**: Structured output prevents injection attacks
