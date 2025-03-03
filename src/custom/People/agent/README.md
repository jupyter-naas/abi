# People Agent Directory

This directory contains agent implementations for People-related functionality. 

## Migration Notes

The content in this directory was migrated from the previous `src/custom/People/assistants` directory to conform with the new project structure. 

The migration involved:
1. Moving the assistant files to the agent directory
2. Updating import paths to reflect the new directory structure
3. Preserving all functionality

## Contents

- `HRAssistant.py`: Human Resources assistant implementation
- Other assistants will be added here as needed

## Usage

To use the HR Assistant:

```python
from src.custom.People.agent.HRAssistant import create_hr_agent

# Create the HR agent
hr_agent = create_hr_agent()

# Use the agent
response = hr_agent.invoke({"message": "I need to find someone with Python skills"})
``` 