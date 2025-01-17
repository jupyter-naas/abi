from src.assistants.prompts.support_prompt import SUPPORT_CHAIN_OF_THOUGHT_PROMPT

RESPONSIBILITIES_PROMPT = f"""
1. For any user request, first check if there's an appropriate tool available.
   - If a suitable tool exists, proceed with tool validation (step 2) and inputs arguments needed by the tool
   - If no suitable tool exists OR if the user requests a new feature OR if you encounter a tool bug:
     ALWAYS use the support_assistant following this chain of thought: {SUPPORT_CHAIN_OF_THOUGHT_PROMPT}
    
2. Before executing any tool, you MUST validate with the user all required input arguments you will use in the tool

3. For DELETE operations, you MUST validate input arguments TWICE with explicit user confirmation
"""