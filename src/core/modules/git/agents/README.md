# Git Module

## Description

The Git Module provides AI-powered tools for Git workflow automation, specifically focused on pull request management and description generation. It integrates with the ABI framework to automate common Git development tasks.

Key Features:
- Automated pull request description generation
- Git diff analysis and branch information extraction
- Clipboard integration for easy PR description sharing
- Integration with ABI framework's agent system

## TL;DR

Generate a pull request description from your branch:
```bash
make pull-request-description
```

## Overview

### Structure

```
src/core/modules/git/
└── agents/                                        # Git automation agents
    ├── PullRequestDescriptionAgent.py            # PR description generator
    └── README.md                                 # This documentation
```

### Core Components

- **PullRequestDescriptionAgent**: AI agent that analyzes git diffs and generates structured pull request descriptions
- **Git Integration**: Tools for accessing git diff, branch information, and file operations
- **Clipboard Support**: Automatic copying of generated descriptions to clipboard

## Agents

### Pull Request Description Agent

An AI agent that automatically generates pull request descriptions from git diffs:

1. **Git Analysis**: Extracts branch name and diff information
2. **Content Generation**: Creates structured PR descriptions with issue references
3. **File Storage**: Saves description to `storage/datastore/git/pull_request_description.md`
4. **Clipboard Integration**: Copies description to system clipboard for easy pasting

```python
from src.core.modules.git.agents.PullRequestDescriptionAgent import create_agent

# Create agent
agent = create_agent()

# Agent automatically:
# 1. Gets git diff and branch info
# 2. Generates PR description
# 3. Saves to file and clipboard
```

## Tools

### Git Diff Tool
- **Function**: `git_diff()`
- **Purpose**: Retrieves current branch name and diff against origin/main
- **Output**: Formatted string with branch name and diff content
- **Exclusions**: Automatically excludes `uv.lock` from diff

### Description Storage Tools
- **`store_pull_request_description(description)`**: Saves description to `storage/datastore/git/pull_request_description.md`
- **`store_pull_request_description_to_clipboard()`**: Copies description from file to clipboard

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

### Core Dependencies
- **abi**: Core ABI framework for agent system
- **langchain-openai**: OpenAI integration for AI model access
- **pyperclip**: Cross-platform clipboard operations
- **subprocess**: Git command execution

### System Requirements
- **Git**: Must be in a git repository with origin/main remote
- **Python 3.10+**: Required for ABI framework compatibility

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
