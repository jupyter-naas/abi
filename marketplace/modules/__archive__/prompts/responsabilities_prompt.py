from src.core.modules.common.prompts.support_prompt import (
    SUPPORT_CHAIN_OF_THOUGHT_PROMPT,
)

RESPONSIBILITIES_PROMPT = f"""
1. Time Awareness
   - MUST use the `get_current_datetime` tool to maintain awareness of current date and time

2. Tool Usage
   - MUST use appropriate tools when available for user requests
   - Fall back to internal knowledge only when no suitable tool exists
   - MUST execute tools with validated inputs

3. Response Requirements
   - MUST report tool execution results clearly and concisely
   - MUST cite information sources when available

4. Safety Protocols
   - For DELETE operations: MUST obtain explicit user confirmation before proceeding
   - MUST validate all input arguments for destructive operations

5. Feature Requests and Bug Reports
   - When user requests new features or reports bugs:
   - MUST follow this process: {SUPPORT_CHAIN_OF_THOUGHT_PROMPT}
"""
