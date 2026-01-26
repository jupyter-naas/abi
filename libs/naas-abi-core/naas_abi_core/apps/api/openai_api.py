"""OpenAI-compatible API routes for ABI.

This module provides OpenAI-compatible endpoints that allow standard OpenAI clients
(like openai-python, LangChain, and OpenWebUI) to work with ABI agents.
"""

import json
import time
from typing import Any, AsyncGenerator, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from naas_abi_core import logger
from naas_abi_core.engine.Engine import Engine


# OpenAI Request/Response Models
class OpenAIMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: Optional[str] = None


class OpenAIChatCompletionRequest(BaseModel):
    model: str = Field(..., description="The model/agent to use")
    messages: list[OpenAIMessage] = Field(..., description="List of messages")
    temperature: Optional[float] = Field(default=1.0, ge=0, le=2)
    top_p: Optional[float] = Field(default=1.0, ge=0, le=1)
    n: Optional[int] = Field(default=1, ge=1)
    stream: Optional[bool] = Field(default=False)
    stop: Optional[str | list[str]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = Field(default=0, ge=-2, le=2)
    frequency_penalty: Optional[float] = Field(default=0, ge=-2, le=2)
    logit_bias: Optional[dict[str, float]] = None
    user: Optional[str] = None


class OpenAIUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OpenAIChoice(BaseModel):
    index: int
    message: OpenAIMessage
    finish_reason: Literal["stop", "length", "content_filter", "tool_calls"] = "stop"


class OpenAIChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[OpenAIChoice]
    usage: OpenAIUsage


class OpenAIStreamChoice(BaseModel):
    index: int
    delta: dict[str, Any]
    finish_reason: Optional[
        Literal["stop", "length", "content_filter", "tool_calls"]
    ] = None


class OpenAIChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[OpenAIStreamChoice]


class OpenAIModel(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str


class OpenAIModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[OpenAIModel]


def create_openai_router(engine: Engine, auth_dependency: Any) -> APIRouter:
    """Create an OpenAI-compatible API router.

    Args:
        engine: The ABI engine instance with loaded agents
        auth_dependency: The authentication dependency to use

    Returns:
        APIRouter configured with OpenAI-compatible endpoints
    """
    router = APIRouter(prefix="/v1", tags=["OpenAI Compatible"])

    # Get all available agents
    all_agents = []
    for module in engine.modules.values():
        for agent in module.agents:
            if agent is not None:
                all_agents.append(agent.New())

    # Create a mapping of agent names to agents
    agents_by_name = {agent.name: agent for agent in all_agents}

    @router.get("/models", dependencies=[Depends(auth_dependency)])
    async def list_models() -> OpenAIModelList:
        """List all available models (ABI agents)."""
        models = []
        for agent in all_agents:
            models.append(
                OpenAIModel(
                    id=agent.name,
                    created=int(time.time()),
                    owned_by="abi",
                )
            )
        return OpenAIModelList(data=models)

    @router.post(
        "/chat/completions",
        dependencies=[Depends(auth_dependency)],
        response_model=None,  # Dynamic response based on stream parameter
    )
    async def create_chat_completion(
        request: OpenAIChatCompletionRequest, http_request: Request
    ):
        """Create a chat completion using an ABI agent.

        This endpoint is compatible with OpenAI's chat completion API.
        """
        # Validate model exists
        if request.model not in agents_by_name:
            raise HTTPException(
                status_code=404,
                detail=f"Model '{request.model}' not found. Available models: {list(agents_by_name.keys())}",
            )

        # Get the agent
        agent = agents_by_name[request.model]

        # Convert OpenAI messages to a single prompt
        # In ABI, we typically work with a single prompt string
        # We'll combine all messages into a context-aware prompt
        prompt_parts = []
        for msg in request.messages:
            if msg.role == "system":
                prompt_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                prompt_parts.append(msg.content)
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")

        # Use the last user message as the main prompt if available
        # Otherwise, combine all messages
        user_messages = [m for m in request.messages if m.role == "user"]
        if user_messages:
            prompt = user_messages[-1].content
        else:
            prompt = "\n\n".join(prompt_parts)

        # Generate a unique thread ID based on the user or create a new one
        import uuid

        thread_id = request.user if request.user else str(uuid.uuid4())

        # Handle streaming vs non-streaming
        if request.stream:
            return EventSourceResponse(
                stream_completion(agent, prompt, request, thread_id),
                media_type="text/event-stream",
            )
        else:
            return await non_streaming_completion(agent, prompt, request, thread_id)

    async def non_streaming_completion(
        agent, prompt: str, request: OpenAIChatCompletionRequest, thread_id: str
    ) -> OpenAIChatCompletionResponse:
        """Handle non-streaming completion."""
        import uuid

        # Duplicate agent with the thread ID
        new_agent = agent.duplicate()
        new_agent.state.set_thread_id(thread_id)

        # Get the response
        response_text = new_agent.invoke(prompt)

        # Create OpenAI-compatible response
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created_time = int(time.time())

        # Estimate token usage (rough estimate)
        prompt_tokens = len(prompt.split())
        completion_tokens = len(response_text.split())

        return OpenAIChatCompletionResponse(
            id=completion_id,
            created=created_time,
            model=request.model,
            choices=[
                OpenAIChoice(
                    index=0,
                    message=OpenAIMessage(role="assistant", content=response_text),
                    finish_reason="stop",
                )
            ],
            usage=OpenAIUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    async def stream_completion(
        agent, prompt: str, request: OpenAIChatCompletionRequest, thread_id: str
    ) -> AsyncGenerator[str, None]:
        """Handle streaming completion in OpenAI format."""
        import uuid

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created_time = int(time.time())

        # Duplicate agent with the thread ID
        new_agent = agent.duplicate()
        new_agent.state.set_thread_id(thread_id)

        # Track if we've started sending content
        content_started = False

        # Stream the response
        for chunk in new_agent.stream(prompt):
            # Parse the chunk
            if isinstance(chunk, tuple):
                source, payload = chunk
            else:
                payload = chunk

            # Extract messages from payload
            if isinstance(payload, dict):
                values = list(payload.values())
                if values:
                    value = values[0]
                    if isinstance(value, dict) and "messages" in value:
                        messages = value["messages"]
                        if messages:
                            last_message = messages[-1]

                            # Check if it's an AI message
                            if hasattr(last_message, "content") and hasattr(
                                last_message, "__class__"
                            ):
                                if last_message.__class__.__name__ == "AIMessage":
                                    content = last_message.content

                                    if not content_started:
                                        # Send initial chunk with role
                                        chunk_data = OpenAIChatCompletionChunk(
                                            id=completion_id,
                                            created=created_time,
                                            model=request.model,
                                            choices=[
                                                OpenAIStreamChoice(
                                                    index=0,
                                                    delta={"role": "assistant"},
                                                )
                                            ],
                                        )
                                        yield f"data: {chunk_data.model_dump_json()}\n\n"
                                        content_started = True

                                    # Send content chunk
                                    if content:
                                        chunk_data = OpenAIChatCompletionChunk(
                                            id=completion_id,
                                            created=created_time,
                                            model=request.model,
                                            choices=[
                                                OpenAIStreamChoice(
                                                    index=0, delta={"content": content}
                                                )
                                            ],
                                        )
                                        yield f"data: {chunk_data.model_dump_json()}\n\n"

        # Send final chunk with finish_reason
        final_chunk = OpenAIChatCompletionChunk(
            id=completion_id,
            created=created_time,
            model=request.model,
            choices=[OpenAIStreamChoice(index=0, delta={}, finish_reason="stop")],
        )
        yield f"data: {final_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    @router.get("/models/{model_id}", dependencies=[Depends(auth_dependency)])
    async def retrieve_model(model_id: str) -> OpenAIModel:
        """Retrieve information about a specific model."""
        if model_id not in agents_by_name:
            raise HTTPException(
                status_code=404,
                detail=f"Model '{model_id}' not found",
            )

        return OpenAIModel(
            id=model_id,
            created=int(time.time()),
            owned_by="abi",
        )

    return router
