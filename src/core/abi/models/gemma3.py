from lib.abi.models.Model import ChatModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.outputs import ChatResult
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from typing import Optional, List, Any
from abi import logger
import json
import re

class AirgapChatOpenAI(ChatOpenAI):
    """Minimal wrapper for Docker Model Runner with basic tool support"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tools = []
    
    def bind_tools(self, tools, **kwargs):
        self._tools = tools
        return self
    
    def bind(self, **kwargs):
        # Strip tool parameters that Docker Model Runner doesn't support
        clean_kwargs = {k: v for k, v in kwargs.items() if 'tool' not in k.lower()}
        return super().bind(**clean_kwargs) if clean_kwargs else self
    
    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> ChatResult:
        # Extract system prompt and user message
        system_prompt = ""
        user_msg = None
        
        for msg in messages:
            if hasattr(msg, 'content'):
                if 'SystemMessage' in str(type(msg)):
                    if isinstance(msg.content, str):
                        system_prompt += msg.content + "\n"
                elif isinstance(msg, HumanMessage):
                    user_msg = msg.content
        
        if user_msg:
            # Build complete prompt with system context
            prompt = system_prompt.strip()
            
            if self._tools:
                # Add tool info
                tool_info = "\nAvailable tools:\n"
                for tool in self._tools:
                    if hasattr(tool, 'name') and hasattr(tool, 'description'):
                        tool_info += f"- {tool.name}: {tool.description}\n"
                tool_info += "\nTo use a tool, respond with: TOOL_CALL: tool_name {json_args}\n"
                prompt += tool_info
            
            prompt += f"\n\nUser: {user_msg}"
            messages = [HumanMessage(content=prompt)]
        
        # Clean kwargs
        clean_kwargs = {k: v for k, v in kwargs.items() if k in ['temperature', 'max_tokens', 'stop']}
        
        # Get response
        result = super()._generate(messages, stop=stop, run_manager=run_manager, **clean_kwargs)
        
        # Handle tool calls if present
        if self._tools and result.generations:
            content = result.generations[0].message.content
            if isinstance(content, str):
                tool_calls = re.findall(r'TOOL_CALL:\s*(\w+)\s*({.*?})', content, re.DOTALL)
            else:
                tool_calls = []
            
            if tool_calls:
                tool_results = []
                for tool_name, args_json in tool_calls:
                    try:
                        args = json.loads(args_json)
                        tool = next((t for t in self._tools if hasattr(t, 'name') and t.name == tool_name), None)
                        if tool:
                            if hasattr(tool, 'invoke'):
                                result_text = tool.invoke(args)
                            else:
                                result_text = str(tool(**args))
                            tool_results.append(f"{tool_name}: {result_text}")
                    except Exception as e:
                        tool_results.append(f"{tool_name}: Error - {e}")
                
                if tool_results:
                    # Get final response with tool results
                    final_prompt = f"{content}\n\nTool results:\n" + "\n".join(tool_results) + "\n\nProvide a final response:"
                    result = super()._generate([HumanMessage(content=final_prompt)], stop=stop, run_manager=run_manager, **clean_kwargs)
        
        return result

ID = "ai/gemma3"
NAME = "gemma3-airgap"
DESCRIPTION = "Gemma3 model running in airgap mode via Docker Model Runner with tool support."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
CONTEXT_WINDOW = 8192
OWNER = "google"

model: Optional[ChatModel] = None
try:
    model = ChatModel(
        model_id=ID,
        name=NAME,
        description=DESCRIPTION,
        image=IMAGE,
        owner=OWNER,
        model=AirgapChatOpenAI(
            model=ID,
            temperature=0.7,
            base_url="http://localhost:12434/engines/v1",
            api_key="ignored",
        ),
        context_window=CONTEXT_WINDOW,
    )
    logger.debug("✅ Abi Agent: Gemma3 model loaded successfully in airgap mode with tool support")
except Exception as e:
    logger.error(f"Abi Agent: Gemma3 airgap model not available - {e}")
    logger.error("   Make sure Docker Model Runner is active: docker model run ai/gemma3")