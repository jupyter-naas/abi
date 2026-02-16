"""
AI Provider Service - Handles communication with different AI backends.
Supports: Anthropic (Claude), OpenAI, Ollama, Cloudflare Workers AI, and custom OpenAI-compatible endpoints.
"""

from collections.abc import AsyncGenerator
from typing import Literal

import httpx
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from pydantic import BaseModel

# Try importing provider SDKs
try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class ProviderConfig(BaseModel):
    """Provider configuration from frontend."""

    id: str
    name: str
    type: str  # Provider type (validated against model registry)
    enabled: bool
    endpoint: str | None = None
    api_key: str | None = None
    account_id: str | None = None  # For Cloudflare
    model: str


class Message(BaseModel):
    """Chat message with optional image support."""

    role: Literal["user", "assistant", "system"]
    content: str
    images: list[str] | None = None  # List of base64-encoded images


async def complete_with_anthropic(
    messages: list[Message],
    config: ProviderConfig,
    system_prompt: str | None = None,
) -> str:
    """Complete chat using Anthropic Claude API."""
    if not HAS_ANTHROPIC:
        raise RuntimeError("anthropic package not installed. Run: uv add anthropic")

    # Use env var as fallback
    api_key = config.api_key or settings.anthropic_api_key
    if not api_key:
        raise ValueError(
            "Anthropic API key is required. Set ANTHROPIC_API_KEY env var or provide in settings."
        )

    client = anthropic.Anthropic(api_key=api_key)

    # Convert messages to Anthropic format
    anthropic_messages = []
    for msg in messages:
        if msg.role != "system":
            anthropic_messages.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                }
            )

    # Build system prompt from system messages
    system_parts = [system_prompt] if system_prompt else []
    for msg in messages:
        if msg.role == "system":
            system_parts.append(msg.content)

    response = client.messages.create(
        model=config.model,
        max_tokens=4096,
        system="\n\n".join(system_parts) if system_parts else None,
        messages=anthropic_messages,
    )

    return response.content[0].text


async def complete_with_openai(
    messages: list[Message],
    config: ProviderConfig,
    system_prompt: str | None = None,
) -> str:
    """Complete chat using OpenAI API."""
    if not HAS_OPENAI:
        raise RuntimeError("openai package not installed. Run: uv add openai")

    # Use env var as fallback
    api_key = config.api_key or settings.openai_api_key
    if not api_key:
        raise ValueError(
            "OpenAI API key is required. Set OPENAI_API_KEY env var or provide in settings."
        )

    client = openai.OpenAI(api_key=api_key)

    # Build messages list
    openai_messages = []
    if system_prompt:
        openai_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        openai_messages.append(
            {
                "role": msg.role,
                "content": msg.content,
            }
        )

    response = client.chat.completions.create(
        model=config.model,
        messages=openai_messages,
        max_tokens=4096,
    )

    return response.choices[0].message.content


async def complete_with_ollama(
    messages: list[Message],
    config: ProviderConfig,
    system_prompt: str | None = None,
) -> str:
    """Complete chat using Ollama local API (non-streaming). Supports multimodal (images)."""
    # Always default to localhost if no endpoint provided
    endpoint = (config.endpoint or "http://localhost:11434").rstrip("/")

    # Build messages list with optional images
    ollama_messages = []
    if system_prompt:
        ollama_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        message_dict: dict = {
            "role": msg.role,
            "content": msg.content,
        }
        # Add images if present (for multimodal models like qwen3-vl, llava, etc.)
        if msg.images:
            message_dict["images"] = msg.images
        ollama_messages.append(message_dict)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{endpoint}/api/chat",
            json={
                "model": config.model,
                "messages": ollama_messages,
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]


async def stream_with_ollama(
    messages: list[Message],
    config: ProviderConfig,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream chat using Ollama local API. Supports multimodal (images).

    Handles Qwen3-style models that output 'thinking' tokens separately from 'content'.
    Wraps thinking in <think></think> tags so the frontend can render them.
    """
    import json

    endpoint = (config.endpoint or "http://localhost:11434").rstrip("/")

    # Build messages list with optional images
    ollama_messages = []
    if system_prompt:
        ollama_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        message_dict: dict = {
            "role": msg.role,
            "content": msg.content,
        }
        # Add images if present (for multimodal models like qwen3-vl, llava, etc.)
        if msg.images:
            message_dict["images"] = msg.images
        ollama_messages.append(message_dict)

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{endpoint}/api/chat",
            json={
                "model": config.model,
                "messages": ollama_messages,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()

            # Ollama streams JSON lines (not SSE). Each line looks like:
            # {"model":"...","message":{"role":"assistant","content":"token"},"done":false}
            # Final line has {"done": true}
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Some implementations may send thinking tokens separately; if we
                # ever receive a dedicated field, wrap it in <think> tags. For now
                # we stream assistant content as-is and let the model emit tags.
                msg = data.get("message") or {}
                token = msg.get("content")
                if token:
                    yield token


async def stream_with_openai_compatible(
    messages: list[Message],
    config: ProviderConfig,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream chat using OpenAI-compatible API (OpenAI, XAI, Mistral, OpenRouter, etc)."""
    import json
    import logging

    logger = logging.getLogger(__name__)
    endpoint = config.endpoint.rstrip("/")

    # Build messages list
    api_messages = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        api_messages.append(
            {
                "role": msg.role,
                "content": msg.content,
            }
        )

    headers = {
        "Authorization": f"Bearer {config.api_key[:8]}...",  # Mask API key in logs
        "Content-Type": "application/json",
    }

    # OpenRouter requires HTTP-Referer header
    if "openrouter" in endpoint:
        headers["HTTP-Referer"] = "https://nexus.local"
        headers["X-Title"] = "Nexus"

    # Restore full API key for actual request
    headers["Authorization"] = f"Bearer {config.api_key}"

    payload = {
        "model": config.model,
        "messages": api_messages,
        "stream": True,
    }

    logger.info(f"🚀 Streaming to {endpoint}/chat/completions with model={config.model}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{endpoint}/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            # Check status before reading stream
            if response.status_code != 200:
                error_text = await response.aread()
                error_body = error_text.decode()
                logger.error(f"❌ HTTP {response.status_code}: {error_body[:500]}")

                # Try to extract user-friendly error message
                try:
                    error_json = json.loads(error_body)
                    if "error" in error_json:
                        if (
                            isinstance(error_json["error"], dict)
                            and "message" in error_json["error"]
                        ):
                            user_message = error_json["error"]["message"]
                        elif isinstance(error_json["error"], str):
                            user_message = error_json["error"]
                        else:
                            user_message = str(error_json["error"])
                    else:
                        user_message = f"HTTP {response.status_code}: {error_body[:200]}"
                except (json.JSONDecodeError, TypeError, ValueError):
                    user_message = f"HTTP {response.status_code}: {error_body[:200]}"

                raise httpx.HTTPStatusError(
                    user_message, request=response.request, response=response
                )

            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue

                data_str = line[6:]  # Remove "data: " prefix

                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")

                    if content:
                        yield content

                except json.JSONDecodeError:
                    continue


async def complete_with_cloudflare(
    messages: list[Message],
    config: ProviderConfig,
    system_prompt: str | None = None,
) -> str:
    """Complete chat using Cloudflare Workers AI API."""
    # Use env vars as fallback
    api_key = config.api_key or settings.cloudflare_api_token
    account_id = config.account_id or settings.cloudflare_account_id

    if not api_key:
        raise ValueError(
            "Cloudflare API token is required. Set CLOUDFLARE_API_TOKEN env var or provide in settings."
        )

    if not account_id:
        raise ValueError(
            "Cloudflare Account ID is required. Set CLOUDFLARE_ACCOUNT_ID env var or provide in settings."
        )

    # Build messages list
    cf_messages = []
    if system_prompt:
        cf_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        cf_messages.append(
            {
                "role": msg.role,
                "content": msg.content,
            }
        )

    # Cloudflare Workers AI endpoint
    # Model format: @cf/meta/llama-3.1-8b-instruct
    model_path = config.model.lstrip("@cf/")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/{model_path}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url,
            headers=headers,
            json={
                "messages": cf_messages,
            },
        )
        response.raise_for_status()
        data = response.json()

        # Cloudflare returns { "result": { "response": "..." } }
        if "result" in data:
            return data["result"].get("response", str(data["result"]))
        return str(data)


async def stream_with_cloudflare(
    messages: list[Message],
    config: ProviderConfig,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream chat using Cloudflare Workers AI API with SSE."""
    import json

    # Use env vars as fallback
    api_key = config.api_key or settings.cloudflare_api_token
    account_id = config.account_id or settings.cloudflare_account_id

    if not api_key:
        raise ValueError("Cloudflare API token is required.")

    if not account_id:
        raise ValueError("Cloudflare Account ID is required.")

    # Build messages list
    cf_messages = []
    if system_prompt:
        cf_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        cf_messages.append(
            {
                "role": msg.role,
                "content": msg.content,
            }
        )

    # Cloudflare Workers AI endpoint
    model_path = config.model.lstrip("@cf/")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/{model_path}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            url,
            headers=headers,
            json={
                "messages": cf_messages,
                "stream": True,
            },
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                raise ValueError(f"Cloudflare API error: {response.status_code} - {body.decode()}")

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if "response" in data:
                            yield data["response"]
                    except json.JSONDecodeError:
                        continue


async def complete_with_custom(
    messages: list[Message],
    config: ProviderConfig,
    system_prompt: str | None = None,
) -> str:
    """Complete chat using custom OpenAI-compatible endpoint."""
    if not config.endpoint:
        raise ValueError("Custom endpoint URL is required")

    # Build messages list (OpenAI format)
    api_messages = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        api_messages.append(
            {
                "role": msg.role,
                "content": msg.content,
            }
        )

    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{config.endpoint}/v1/chat/completions",
            headers=headers,
            json={
                "model": config.model,
                "messages": api_messages,
                "max_tokens": 4096,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def complete_chat(
    messages: list[Message],
    config: ProviderConfig,
    system_prompt: str | None = None,
) -> str:
    """
    Route chat completion to the appropriate provider.
    """
    if not config.enabled:
        raise ValueError(f"Provider '{config.name}' is not enabled")

    if config.type == "anthropic":
        return await complete_with_anthropic(messages, config, system_prompt)
    elif config.type == "openai":
        return await complete_with_openai(messages, config, system_prompt)
    elif config.type == "ollama":
        return await complete_with_ollama(messages, config, system_prompt)
    elif config.type == "cloudflare":
        return await complete_with_cloudflare(messages, config, system_prompt)
    elif config.type == "custom":
        return await complete_with_custom(messages, config, system_prompt)
    else:
        raise ValueError(f"Unknown provider type: {config.type}")


# Known multimodal (vision) model patterns
MULTIMODAL_MODEL_PATTERNS = [
    "qwen3-vl",
    "qwen2.5vl",
    "qwen2-vl",
    "llava",
    "llava-phi",
    "llava-llama",
    "moondream",
    "bakllava",
    "gemma3",  # Gemma 3 has vision
    "minicpm-v",
    "llama3.2-vision",
    "llama4",
    "mistral-small3.1",
    "mistral-small3.2",  # Vision variants
]


def is_multimodal_model(model_name: str) -> bool:
    """Check if a model supports multimodal (vision) input."""
    model_lower = model_name.lower()
    return any(pattern in model_lower for pattern in MULTIMODAL_MODEL_PATTERNS)


# ============================================
# TOOL DEFINITIONS FOR FUNCTION CALLING
# ============================================

AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information using Wikipedia or DuckDuckGo. Use this when you need to find current information, facts, or details about topics you're unsure about.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query to look up"},
                    "engine": {
                        "type": "string",
                        "enum": ["wikipedia", "duckduckgo"],
                        "description": "Search engine to use. Wikipedia for encyclopedic content, DuckDuckGo for general web search.",
                    },
                },
                "required": ["query"],
            },
        },
    }
]


async def execute_tool(tool_name: str, arguments: dict) -> str:
    """Execute a tool by calling our own local API endpoints."""
    import json
    import logging

    logger = logging.getLogger(__name__)

    if tool_name == "search_web":
        query = arguments.get("query", "")
        engine = arguments.get("engine", "wikipedia")

        # Call our own search API endpoint (already proven to work)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "http://localhost:8000/api/search/web",
                    json={"query": query, "engine": engine, "limit": 5},
                )
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])

                if results:
                    # Format results for the LLM context
                    formatted = []
                    for r in results[:5]:
                        entry = f"- **{r.get('title', 'Untitled')}**: {r.get('snippet', '')[:400]}"
                        if r.get("url"):
                            entry += f"\n  Source: {r['url']}"
                        formatted.append(entry)
                    return "\n\n".join(formatted)

                return f"No results found for '{query}' on {engine}."

        except Exception as e:
            logger.error(f"[execute_tool] search_web failed: {e}")
            return f"Search failed: {str(e)}"

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


async def stream_with_ollama_tools(
    messages: list[Message],
    config: ProviderConfig,
    system_prompt: str | None = None,
    tools: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """Stream chat with Ollama, supporting tool calls. Handles tool execution loop."""
    import json

    endpoint = (config.endpoint or "http://localhost:11434").rstrip("/")

    # Build messages list
    ollama_messages = []
    if system_prompt:
        ollama_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        message_dict: dict = {
            "role": msg.role,
            "content": msg.content,
        }
        if msg.images:
            message_dict["images"] = msg.images
        ollama_messages.append(message_dict)

    # First request - may return tool calls
    request_body = {
        "model": config.model,
        "messages": ollama_messages,
        "stream": True,
    }

    # Only add tools if provided (not all models support it)
    if tools:
        request_body["tools"] = tools

    async with httpx.AsyncClient(timeout=120.0) as client:
        full_response = ""
        tool_calls = []

        async with client.stream(
            "POST",
            f"{endpoint}/api/chat",
            json=request_body,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)

                        # Check for tool calls
                        if "message" in data:
                            msg = data["message"]
                            if "tool_calls" in msg and msg["tool_calls"]:
                                tool_calls.extend(msg["tool_calls"])
                            if "content" in msg and msg["content"]:
                                full_response += msg["content"]
                                yield msg["content"]

                    except json.JSONDecodeError:
                        continue

        # If there were tool calls, execute them and continue
        if tool_calls:
            yield "\n\n*Searching...*\n\n"

            # Execute each tool call
            for tool_call in tool_calls:
                func = tool_call.get("function", {})
                tool_name = func.get("name", "")
                arguments = func.get("arguments", {})

                # Execute the tool
                tool_result = await execute_tool(tool_name, arguments)

                # Add assistant message with tool call and tool response to messages
                ollama_messages.append(
                    {
                        "role": "assistant",
                        "content": full_response,
                        "tool_calls": tool_calls,
                    }
                )
                ollama_messages.append(
                    {
                        "role": "tool",
                        "content": tool_result,
                    }
                )

            # Continue the conversation with tool results (no tools this time to avoid loop)
            async with client.stream(
                "POST",
                f"{endpoint}/api/chat",
                json={
                    "model": config.model,
                    "messages": ollama_messages,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                        except json.JSONDecodeError:
                            continue


async def check_ollama_status(endpoint: str = "http://localhost:11434") -> dict:
    """Check if Ollama is running and list available models with multimodal info."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{endpoint}/api/tags")
            response.raise_for_status()
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            multimodal_models = [m for m in models if is_multimodal_model(m)]
            return {
                "status": "online",
                "models": models,
                "multimodal_models": multimodal_models,
            }
    except Exception as e:
        return {"status": "offline", "error": str(e), "models": [], "multimodal_models": []}


async def stream_with_abi(
    messages: list[Message],
    config: ProviderConfig,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream chat completion from ABI server (custom API).

    ABI uses a custom endpoint format:
    POST {endpoint}/agents/{agent_name}/stream-completion?token={token}

    Body format (expected):
    {
        "prompt": "user message here",
        "thread_id": "conversation_id"
    }
    """
    import logging

    logger = logging.getLogger(__name__)

    endpoint = config.endpoint.rstrip("/")
    agent_name = config.model  # e.g., "ForvisMazars_Corporate"
    token = config.api_key

    # ABI expects a single "prompt" field with the latest user message
    # and a thread_id for conversation continuity
    latest_user_message = None
    for msg in reversed(messages):
        if msg.role == "user":
            latest_user_message = msg.content
            break

    if not latest_user_message:
        logger.warning("No user message found in conversation")
        yield "Error: No user message to send"
        return

    # Build request URL with token as query param
    url = f"{endpoint}/agents/{agent_name}/stream-completion?token={token}"

    logger.info(f"🔌 Streaming from ABI: {url} (agent: {agent_name})")

    # Use conversation ID as thread_id (or generate one from messages hash)
    thread_id = str(
        hash(tuple(m.content for m in messages[-5:]))
    )  # Last 5 messages as thread context

    request_body = {
        "prompt": latest_user_message,
        "thread_id": thread_id,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                url,
                json=request_body,
                headers={"Content-Type": "application/json"},
            ) as response:
                response.raise_for_status()

                # ABI returns SSE events. Depending on the agent/runtime, content can
                # arrive under either:
                # - event: ai_message
                # - event: message
                # Some runtimes emit both (duplicate content), others only one.
                # We therefore:
                # 1) prefer ai_message when present,
                # 2) fallback to message when ai_message is absent,
                # 3) skip duplicate consecutive chunks.
                current_event = None
                saw_ai_message = False
                last_emitted_chunk = None
                async for line in response.aiter_lines():
                    if not line or not line.strip():
                        continue

                    # Parse SSE format
                    if line.startswith("event: "):
                        current_event = line[7:].strip()  # Extract event name
                    elif line.startswith("data: "):
                        content = line[6:]  # Remove "data: " prefix

                        # Skip [DONE] marker
                        if content == "[DONE]":
                            break

                        if not content.strip():
                            continue

                        should_emit = False
                        if current_event == "ai_message":
                            saw_ai_message = True
                            should_emit = True
                        elif current_event == "message" and not saw_ai_message:
                            # Fallback path when no ai_message events are emitted.
                            should_emit = True

                        if should_emit and content != last_emitted_chunk:
                            logger.debug(f"📨 ABI chunk ({current_event}): {content[:100]}...")
                            yield content
                            last_emitted_chunk = content

    except httpx.HTTPStatusError as e:
        logger.error(f"ABI API error: {e.response.status_code} - {e.response.text}")
        yield f"\n\n**Error:** ABI server returned {e.response.status_code}\n\n{e.response.text}"
    except Exception as e:
        logger.error(f"ABI streaming error: {e}")
        yield f"\n\n**Error:** Failed to connect to ABI server: {str(e)}"


def _resolve_inprocess_abi_agent(agent_name: str):
    """Resolve an ABI agent instance from in-process loaded modules."""
    import sys

    from naas_abi import ABIModule

    abi_module = ABIModule.get_instance()
    modules = getattr(getattr(abi_module, "engine", None), "modules", {}) or {}

    raw_target = (agent_name or "").strip()
    if not raw_target:
        return None

    # Support:
    # - "AgentName"
    # - "module.path/AgentName"
    # - "module.path:AgentName"
    target_module = None
    target_agent = raw_target
    for sep in ("/", ":"):
        if sep in raw_target:
            parts = raw_target.split(sep, 1)
            target_module = parts[0].strip().lower() or None
            target_agent = parts[1].strip()
            break

    target_agent_norm = target_agent.lower()

    for module in modules.values():
        module_path = module.__class__.__module__
        module_path_norm = module_path.lower()
        if target_module and target_module not in module_path_norm:
            continue

        for agent_cls in getattr(module, "agents", []) or []:
            if agent_cls is None:
                continue
            try:
                agent_mod = sys.modules.get(agent_cls.__module__)
                module_level_name = (
                    getattr(agent_mod, "NAME", None) if agent_mod is not None else None
                )
                runtime_name = (
                    module_level_name or getattr(agent_cls, "NAME", None) or agent_cls.__name__
                )
                class_name = agent_cls.__name__
                class_name_stripped = (
                    class_name[:-5] if class_name.endswith("Agent") else class_name
                )

                candidate_names = {
                    str(runtime_name).strip().lower(),
                    class_name.strip().lower(),
                    class_name_stripped.strip().lower(),
                    f"{module_path_norm}/{str(runtime_name).strip().lower()}",
                    f"{module_path_norm}/{class_name.strip().lower()}",
                    f"{module_path_norm}/{class_name_stripped.strip().lower()}",
                }

                if target_agent_norm in candidate_names or raw_target.lower() in candidate_names:
                    return agent_cls.New()
            except Exception:
                continue

    # Fallback: resolve from local naas_abi.agents package directly.
    # In some runtimes, module.agents may not include local agents (AbiAgent, etc.).
    try:
        from importlib import import_module

        from naas_abi_core.services.agent.Agent import Agent

        local_agent_module_names = [
            "AbiAgent",
            "EntitytoSPARQLAgent",
            "KnowledgeGraphBuilderAgent",
            "OntologyEngineerAgent",
        ]

        for mod_name in local_agent_module_names:
            mod = import_module(f"naas_abi.agents.{mod_name}")
            create_agent = getattr(mod, "create_agent", None)
            for _, value in mod.__dict__.items():
                if not isinstance(value, type):
                    continue
                if not issubclass(value, Agent):
                    continue

                class_name = value.__name__
                class_name_stripped = (
                    class_name[:-5] if class_name.endswith("Agent") else class_name
                )
                runtime_name = (
                    getattr(mod, "NAME", None) or getattr(value, "NAME", None) or class_name
                )
                local_path = f"naas_abi.agents.{mod_name}".lower()
                local_candidates = {
                    str(runtime_name).strip().lower(),
                    class_name.lower(),
                    class_name_stripped.lower(),
                    f"{local_path}/{str(runtime_name).strip().lower()}",
                    f"{local_path}/{class_name.lower()}",
                    f"{local_path}/{class_name_stripped.lower()}",
                }
                if target_agent_norm in local_candidates or raw_target.lower() in local_candidates:
                    if not hasattr(value, "New") and callable(create_agent):
                        value.New = create_agent
                    if hasattr(value, "New"):
                        return value.New()
    except Exception:
        pass
    return None


async def stream_with_abi_inprocess(
    messages: list[Message],
    config: ProviderConfig,
    thread_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream chat by invoking ABI agent directly in-process."""
    import asyncio
    import logging

    logger = logging.getLogger(__name__)

    latest_user_message = None
    for msg in reversed(messages):
        if msg.role == "user":
            latest_user_message = msg.content
            break

    if not latest_user_message:
        logger.warning("No user message found in conversation")
        yield "Error: No user message to send"
        return

    agent_name = config.model
    agent = _resolve_inprocess_abi_agent(agent_name)
    if agent is None:
        # Expose available names to quickly diagnose bad IDs in UI/backend mapping.
        try:
            from naas_abi import ABIModule

            available = []
            modules = (
                getattr(getattr(ABIModule.get_instance(), "engine", None), "modules", {}) or {}
            )
            for module in modules.values():
                module_path = module.__class__.__module__
                for agent_cls in getattr(module, "agents", []) or []:
                    if agent_cls is None:
                        continue
                    agent_mod = __import__(agent_cls.__module__, fromlist=["*"])
                    runtime_name = (
                        getattr(agent_mod, "NAME", None)
                        or getattr(agent_cls, "NAME", None)
                        or agent_cls.__name__
                    )
                    available.append(f"{module_path}/{runtime_name}")
            available_hint = ", ".join(sorted(set(available))[:20])
        except Exception:
            available_hint = "unavailable"
        yield (
            f"\n\n**Error:** In-process ABI agent not found: {agent_name}\n"
            f"Available (sample): {available_hint}"
        )
        return

    # Keep ABI memory continuity aligned with Nexus conversation.
    if thread_id and hasattr(agent, "state") and hasattr(agent.state, "set_thread_id"):
        try:
            agent.state.set_thread_id(str(thread_id))
        except Exception:
            pass

    stream_iter = iter(agent.stream_invoke(latest_user_message))

    while True:
        try:
            event = await asyncio.to_thread(next, stream_iter)
        except StopIteration:
            break
        except Exception as exc:
            logger.error(f"In-process ABI streaming error: {exc}")
            yield f"\n\n**Error:** Failed to stream ABI agent response: {str(exc)}"
            break

        if isinstance(event, dict):
            event_name = str(event.get("event", "")).strip()
            data = event.get("data", "")
            text = "" if data is None else str(data)

            if text == "[DONE]" or event_name == "done":
                break

            # Only forward the real-time ai_message events.
            # Skip "message" events - those are a post-hoc replay of the final
            # state and would duplicate the content already streamed via ai_message.
            if event_name == "ai_message" and text.strip():
                yield text
        elif isinstance(event, str) and event.strip():
            yield event
