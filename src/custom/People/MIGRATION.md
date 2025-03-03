# Migration: `assistants` → `agent`

## Overview
This document outlines the migration of assistant classes from the `src/custom/People/assistants/` directory to the new `src/custom/People/agent/` directory.

## Migration Status
- [x] Created new `src/custom/People/agent/` directory
- [x] Copied `HRAssistant.py` from `assistants` to `agent`
- [x] Updated imports in `src/core/apps/terminal_agent/main.py`
- [x] Removed the old `assistants` directory after testing and validation

## Import Path Changes
The following import path changes have been made:

Old:
```python
from src.custom.assistants.HRAssistant import create_hr_agent
```

New:
```python
from src.custom.People.agent.HRAssistant import create_hr_agent
```

## Completion
- [x] Verified that all code using the imported modules works as expected (tested with `make chat-hr-agent`)
- [x] Removed the old `assistants` directory after confirming functionality

The migration is now complete. All HR assistant functionality has been successfully moved to the new directory structure. 