from openai import OpenAI
from typing import Dict, List, Optional
import os
from workflows.functions import handle_function_calls, get_function_definitions

class AssistantManager:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.assistants: Dict[str, str] = {}
        
    async def create_assistant(
        self,
        name: str,
        instructions: str,
        tools: Optional[List[Dict]] = None,
        model: str = "gpt-4-turbo-preview"
    ):
        # If no tools provided, use default function definitions
        if tools is None:
            tools = get_function_definitions()
            
        assistant = await self.client.beta.assistants.create(
            name=name,
            instructions=instructions,
            tools=tools,
            model=model
        )
        self.assistants[name] = assistant.id
        return assistant
        
    async def handle_run(self, run):
        """Handle assistant run including function calls."""
        if run.status == "requires_action":
            tool_outputs = handle_function_calls(run)
            return await self.client.beta.threads.runs.submit_tool_outputs(
                thread_id=self.thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )
        return run