from lib.abi.models.Model import ChatModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.outputs import ChatResult
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.outputs.chat_generation import ChatGenerationChunk
from langchain_core.messages import AIMessage, AIMessageChunk
from typing import Optional, List, Any, Iterator
from abi import logger
import json
import requests

class AirgapChatOpenAI(ChatOpenAI):
    """Minimal wrapper for Docker Model Runner with basic tool support"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tools = []
    
    def bind_tools(self, tools, **kwargs):
        # Just return self without storing tools - we don't need complex tool handling
        return self

    def bind(self, **kwargs):
        # Just return self - keep it simple
        return self
    
    @property
    def _llm_type(self) -> str:
        return "airgap_chat_openai"
    
    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> ChatResult:
        # Extract system prompt and user message with improved formatting
        system_prompt = ""
        user_msg : str | None = None
        
        for msg in messages:
            if hasattr(msg, 'content') and msg.content:
                if 'SystemMessage' in str(type(msg)):
                    if isinstance(msg.content, str):
                        system_prompt += msg.content + "\n"
                elif isinstance(msg, HumanMessage):
                    assert isinstance(msg.content, str)
                    user_msg = msg.content
                    
        
        # Always ensure we have a valid user message
        if not user_msg or (isinstance(user_msg, str) and not user_msg.strip()):
            user_msg = "Hello"
        elif not isinstance(user_msg, str):
            user_msg = str(user_msg)
        
        # Build GPT-style prompt with clear instruction formatting
        if system_prompt.strip():
            prompt = f"System: {system_prompt.strip()}\n\n"
        else:
            prompt = ""
        
        
        prompt += f"User: {user_msg}\n\nAssistant:"
        messages = [HumanMessage(content=prompt)]
        
        # Clean kwargs
        clean_kwargs = {k: v for k, v in kwargs.items() if k in ['temperature', 'max_tokens', 'stop']}
        
        # Get response
        result = super()._generate(messages, stop=stop, run_manager=run_manager, **clean_kwargs)
        
        # Simple tool call handling - just ensure we have proper AIMessage format
        if result.generations:
            content = result.generations[0].message.content
            
            # Always create AIMessage with empty tool_calls to prevent routing issues
            ai_message = AIMessage(
                content=content,
                additional_kwargs={}
            )
            ai_message.tool_calls = []
            result.generations[0].message = ai_message
        
        return result
    
    def _stream(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        """Stream tokens from the Docker Model Runner"""
        # Extract system prompt and user message with improved formatting
        system_prompt = ""
        user_msg : str | None = None
        
        for msg in messages:
            if hasattr(msg, 'content') and msg.content:
                if 'SystemMessage' in str(type(msg)):
                    if isinstance(msg.content, str):
                        system_prompt += msg.content + "\n"
                elif isinstance(msg, HumanMessage):
                    assert isinstance(msg.content, str)
                    user_msg = msg.content
        
        # Always ensure we have a valid user message
        if not user_msg or (isinstance(user_msg, str) and not user_msg.strip()):
            user_msg = "Hello"
        elif not isinstance(user_msg, str):
            user_msg = str(user_msg)
        
        # Build GPT-style prompt with clear instruction formatting
        if system_prompt.strip():
            prompt = f"System: {system_prompt.strip()}\n\n"
        else:
            prompt = ""
        
        
        prompt += f"User: {user_msg}\n\nAssistant:"
        
        # Make streaming request to Docker Model Runner
        try:
            response = requests.post(
                f"{self.openai_api_base}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": True,
                    "temperature": kwargs.get('temperature', self.temperature),
                    "max_tokens": kwargs.get('max_tokens', 512),
                },
                stream=True,
                timeout=30
            )
            response.raise_for_status()
            
            # Process streaming response
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]  # Remove 'data: ' prefix
                        if data.strip() == '[DONE]':
                            break
                        try:
                            chunk_data = json.loads(data)
                            if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                choice = chunk_data['choices'][0]
                                if 'delta' in choice and 'content' in choice['delta']:
                                    content = choice['delta']['content']
                                    if content:
                                        yield ChatGenerationChunk(
                                            message=AIMessageChunk(content=content),
                                            generation_info={"finish_reason": choice.get('finish_reason')}
                                        )
                        except json.JSONDecodeError:
                            continue
            
        except requests.exceptions.Timeout:
            logger.error("Docker Model Runner timeout - model may be overloaded")
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="⚠️ Model response timeout. Try a shorter message or switch to cloud mode."),
                generation_info={"finish_reason": "timeout"}
            )
        except requests.exceptions.ConnectionError:
            logger.error("Docker Model Runner connection failed")
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="❌ Local model unavailable. Use 'make model-up' or switch to cloud mode."),
                generation_info={"finish_reason": "connection_error"}
            )
        except Exception as e:
            logger.error(f"Docker Model Runner error: {e}")
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="🔄 Model error. Try restarting with 'make model-down && make model-up'"),
                generation_info={"finish_reason": "error"}
            )

ID = "ai/gemma3"
NAME = "gemma3-airgap"
DESCRIPTION = "Gemma3 model running in airgap mode via Docker Model Runner with tool support."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
CONTEXT_WINDOW = 8192
OWNER = "google"

model: ChatModel = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=AirgapChatOpenAI(
        model=ID,
        temperature=0.2,  # Even lower temperature for faster, more focused responses
        max_tokens=512,   # Shorter responses for speed
        openai_api_base="http://localhost:12434/engines/v1",
        api_key="ignored",
    ),
    context_window=CONTEXT_WINDOW,
)