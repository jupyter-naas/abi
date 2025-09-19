"""Docker Model Runner Chat Adapter for LangChain compatibility."""

import requests
import json
from typing import Any, List, Optional, Iterator
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatResult, ChatGenerationChunk
from langchain_core.callbacks import CallbackManagerForLLMRun
from pydantic import Field


class DockerModelRunnerChat(BaseChatModel):
    """Docker Model Runner chat model adapter for LangChain."""
    
    endpoint: str = Field(description="Docker Model Runner endpoint URL")
    model_name: str = Field(description="Model name identifier")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens to generate")
    
    @property
    def _llm_type(self) -> str:
        return "docker-model-runner"
    
    def _convert_messages_to_prompt(self, messages: List[BaseMessage]) -> str:
        """Convert LangChain messages to a single prompt string."""
        prompt_parts = []
        
        for message in messages:
            if isinstance(message, SystemMessage):
                prompt_parts.append(f"System: {message.content}")
            elif isinstance(message, HumanMessage):
                prompt_parts.append(f"Human: {message.content}")
            elif isinstance(message, AIMessage):
                prompt_parts.append(f"Assistant: {message.content}")
            else:
                prompt_parts.append(f"User: {message.content}")
        
        return "\n".join(prompt_parts) + "\nAssistant:"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate chat response using Ollama API (Docker Model Runner backend)."""
        
        # Convert messages to Ollama format
        ollama_messages = []
        for message in messages:
            if isinstance(message, SystemMessage):
                ollama_messages.append({"role": "system", "content": message.content})
            elif isinstance(message, HumanMessage):
                ollama_messages.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                ollama_messages.append({"role": "assistant", "content": message.content})
        
        payload = {
            "model": self.model_name,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens or 2048,
                "stop": stop or []
            }
        }
        
        try:
            response = requests.post(
                f"{self.endpoint}/api/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            generated_text = result.get("message", {}).get("content", "").strip()
            
            message = AIMessage(content=generated_text)
            generation = ChatGeneration(message=message)
            
            return ChatResult(generations=[generation])
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Docker Model Runner API error: {e}")
        except (KeyError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Invalid response format from Docker Model Runner: {e}")
    
    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """Stream chat response (fallback to non-streaming for now)."""
        result = self._generate(messages, stop, run_manager, **kwargs)
        generation = result.generations[0]
        chunk_message = AIMessageChunk(content=generation.message.content)
        chunk = ChatGenerationChunk(message=chunk_message)
        yield chunk
