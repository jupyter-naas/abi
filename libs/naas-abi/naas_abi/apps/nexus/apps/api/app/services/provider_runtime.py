"""
AI Provider Service - Handles communication with different AI backends.
Supports: Anthropic (Claude), OpenAI, Ollama, Cloudflare Workers AI, and custom OpenAI-compatible endpoints.
"""

import importlib
import pkgutil
import threading
from collections.abc import AsyncGenerator
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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


class UnsafeProviderEndpointError(ValueError):
    pass


_OFFICIAL_ENDPOINTS: dict[str, str] = {
    "xai": "https://api.x.ai/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "openrouter": "https://openrouter.ai/api/v1",
    "perplexity": "https://api.perplexity.ai",
}

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_SENSITIVE_QUERY_KEYS = {"token", "api_key", "key", "access_token", "auth", "authorization"}
_REDACTED = "REDACTED"

_INPROCESS_AGENT_INDEX: dict[str, callable] = {}
_INPROCESS_AGENT_HINTS: list[str] = []
_INPROCESS_AGENT_SIGNATURE: tuple[str, ...] | None = None
_INPROCESS_AGENT_LOCK = threading.Lock()
_INPROCESS_AGENT_INSTANCES: dict[str, object] = {}


def redact_url_for_logs(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.query:
        return url
    redacted_query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in _SENSITIVE_QUERY_KEYS:
            redacted_query.append((key, _REDACTED))
        else:
            redacted_query.append((key, value))
    return urlunparse(parsed._replace(query=urlencode(redacted_query, doseq=True)))


def _is_ip_literal(host: str) -> bool:
    import ipaddress

    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _is_private_or_local_ip(host: str) -> bool:
    import ipaddress

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_endpoint_url(
    endpoint: str,
    *,
    require_https: bool,
    allow_localhost: bool,
) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeProviderEndpointError("Provider endpoint must use http or https")
    if require_https and parsed.scheme != "https":
        raise UnsafeProviderEndpointError("Provider endpoint must use https")
    if not parsed.hostname:
        raise UnsafeProviderEndpointError("Provider endpoint must include a hostname")
    if parsed.username or parsed.password:
        raise UnsafeProviderEndpointError("Provider endpoint cannot include credentials")
    if parsed.query or parsed.fragment:
        raise UnsafeProviderEndpointError("Provider endpoint cannot include query parameters")

    host = parsed.hostname.lower()
    if host in {"169.254.169.254", "metadata.google.internal"}:
        raise UnsafeProviderEndpointError("Provider endpoint targets forbidden metadata host")

    if _is_ip_literal(host) and _is_private_or_local_ip(host):
        if not allow_localhost or host not in _LOCAL_HOSTS:
            raise UnsafeProviderEndpointError(
                "Provider endpoint cannot target local/private IP ranges"
            )

    if host.endswith(".local") and not allow_localhost:
        raise UnsafeProviderEndpointError("Provider endpoint cannot target local network hostnames")

    if host in _LOCAL_HOSTS and not allow_localhost:
        raise UnsafeProviderEndpointError("Provider endpoint cannot target localhost")

    return endpoint.rstrip("/")


def validated_provider_endpoint(config: ProviderConfig) -> str | None:
    if config.type == "custom":
        if not config.endpoint:
            raise UnsafeProviderEndpointError("Custom endpoint URL is required")
        return _validate_endpoint_url(config.endpoint, require_https=True, allow_localhost=False)

    if config.type in _OFFICIAL_ENDPOINTS:
        endpoint = config.endpoint or _OFFICIAL_ENDPOINTS[config.type]
        validated = _validate_endpoint_url(endpoint, require_https=True, allow_localhost=False)
        if urlparse(validated).hostname != urlparse(_OFFICIAL_ENDPOINTS[config.type]).hostname:
            raise UnsafeProviderEndpointError(
                f"Endpoint host is not allowed for provider type '{config.type}'"
            )
        return validated

    if config.type == "ollama":
        endpoint = config.endpoint or "http://localhost:11434"
        return _validate_endpoint_url(endpoint, require_https=False, allow_localhost=True)

    if config.type == "abi":
        if config.endpoint and config.endpoint.startswith("inprocess://"):
            return config.endpoint
        if config.endpoint:
            return _validate_endpoint_url(
                config.endpoint, require_https=False, allow_localhost=True
            )
    return config.endpoint.rstrip("/") if config.endpoint else None


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
    endpoint = validated_provider_endpoint(config) or "http://localhost:11434"

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

    endpoint = validated_provider_endpoint(config) or "http://localhost:11434"

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
    endpoint = validated_provider_endpoint(config)
    if not endpoint:
        raise UnsafeProviderEndpointError(f"Missing endpoint for provider type '{config.type}'")

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
                logger.error(
                    "❌ HTTP %s from provider endpoint=%s model=%s",
                    response.status_code,
                    endpoint,
                    config.model,
                )

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
    endpoint = validated_provider_endpoint(config)
    if not endpoint:
        raise UnsafeProviderEndpointError("Custom endpoint URL is required")

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
            f"{endpoint}/v1/chat/completions",
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
    thread_id: str | None = None,
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
    elif config.type == "abi":
        return await complete_with_abi(messages, config, system_prompt, thread_id=thread_id)
    else:
        raise ValueError(f"Unknown provider type: {config.type}")


async def complete_with_abi(
    messages: list[Message],
    config: ProviderConfig,
    system_prompt: str | None = None,
    thread_id: str | None = None,
) -> str:
    del system_prompt

    endpoint = (config.endpoint or "").rstrip("/")
    if endpoint.startswith("inprocess://"):
        agent = _resolve_inprocess_abi_agent(config.model)
        if agent is None:
            raise ValueError(f"In-process ABI agent not found: {config.model}")

        latest_user_message = next((m.content for m in reversed(messages) if m.role == "user"), "")
        if not latest_user_message:
            return ""

        if hasattr(agent, "ainvoke"):
            return await agent.ainvoke(latest_user_message, thread_id=thread_id)
        if hasattr(agent, "invoke"):
            return agent.invoke(latest_user_message)
        raise ValueError(f"In-process ABI agent '{config.model}' cannot be invoked")

    if not endpoint:
        raise ValueError("ABI endpoint is required")

    latest_user_message = next((m.content for m in reversed(messages) if m.role == "user"), "")
    payload = {
        "prompt": latest_user_message,
        "thread_id": thread_id or str(hash(tuple(m.content for m in messages[-5:]))),
    }
    url = f"{endpoint}/agents/{config.model}/completion?token={config.api_key or ''}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url, json=payload, headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and isinstance(data.get("completion"), str):
            return data["completion"]
        return str(data)


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
) -> AsyncGenerator[str | dict[str, Any], None]:
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

    logger.info("🔌 Streaming from ABI: %s (agent: %s)", redact_url_for_logs(url), agent_name)

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
                        elif current_event == "tool_usage" and content.strip():
                            yield {"event": "tool_usage", "tool": content.strip()}
                        elif current_event == "tool_response" and content.strip():
                            yield {"event": "tool_response", "output": content.strip()}

    except httpx.HTTPStatusError as e:
        logger.error("ABI API error: status=%s endpoint=%s", e.response.status_code, endpoint)
        yield f"\n\n**Error:** ABI server returned {e.response.status_code}\n\n{e.response.text}"
    except Exception as e:
        logger.error(f"ABI streaming error: {e}")
        yield f"\n\n**Error:** Failed to connect to ABI server: {str(e)}"


def _normalize_agent_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _agent_candidates(runtime_name: str, class_name: str, module_path: str) -> set[str]:
    class_name_stripped = class_name[:-5] if class_name.endswith("Agent") else class_name
    module_path_norm = module_path.lower()
    runtime_name_norm = runtime_name.strip().lower()
    class_name_norm = class_name.strip().lower()
    class_name_stripped_norm = class_name_stripped.strip().lower()
    return {
        runtime_name_norm,
        class_name_norm,
        class_name_stripped_norm,
        f"{module_path_norm}/{runtime_name_norm}",
        f"{module_path_norm}/{class_name_norm}",
        f"{module_path_norm}/{class_name_stripped_norm}",
    }


def _build_runtime_agent_index(modules: dict[str, object]) -> tuple[dict[str, callable], list[str]]:
    import sys

    index: dict[str, callable] = {}
    hints: set[str] = set()

    for module in modules.values():
        if module is None:
            continue
        module_path = module.__class__.__module__
        for agent_cls in getattr(module, "agents", []) or []:
            if agent_cls is None:
                continue
            agent_mod = sys.modules.get(agent_cls.__module__)
            if agent_mod is None:
                try:
                    agent_mod = importlib.import_module(agent_cls.__module__)
                except Exception:
                    agent_mod = None
            runtime_name = (
                getattr(agent_mod, "NAME", None)
                or getattr(agent_cls, "NAME", None)
                or agent_cls.__name__
            )
            candidates = _agent_candidates(str(runtime_name), agent_cls.__name__, module_path)
            hints.add(f"{module_path}/{str(runtime_name)}")
            factory = getattr(agent_cls, "New", None)
            if not callable(factory):
                continue
            for candidate in candidates:
                index.setdefault(candidate, factory)
                index.setdefault(_normalize_agent_key(candidate), factory)

    return index, sorted(hints)


def _build_local_agent_index() -> tuple[dict[str, callable], list[str]]:
    index: dict[str, callable] = {}
    hints: set[str] = set()

    try:
        from naas_abi import agents as agents_pkg
    except Exception:
        return index, []

    for module_info in pkgutil.iter_modules(agents_pkg.__path__):
        if module_info.ispkg:
            continue
        module_name = module_info.name
        module_path = f"naas_abi.agents.{module_name}"
        try:
            mod = importlib.import_module(module_path)
        except Exception:
            continue

        create_agent = getattr(mod, "create_agent", None)
        for _, value in mod.__dict__.items():
            if not isinstance(value, type):
                continue
            if getattr(value, "__module__", "") != module_path:
                continue

            runtime_name = (
                getattr(mod, "NAME", None) or getattr(value, "NAME", None) or value.__name__
            )
            candidates = _agent_candidates(str(runtime_name), value.__name__, module_path)
            hints.add(f"{module_path}/{str(runtime_name)}")

            factory = getattr(value, "New", None)
            if not callable(factory) and callable(create_agent):
                factory = create_agent
            if not callable(factory):
                continue

            for candidate in candidates:
                index.setdefault(candidate, factory)
                index.setdefault(_normalize_agent_key(candidate), factory)

    return index, sorted(hints)


def _runtime_signature(modules: dict[str, object]) -> tuple[str, ...]:
    signature: list[str] = []
    for module in modules.values():
        if module is None:
            continue
        module_path = module.__class__.__module__
        agent_names = sorted(
            [
                f"{agent_cls.__module__}.{agent_cls.__name__}"
                for agent_cls in (getattr(module, "agents", []) or [])
                if agent_cls is not None
            ]
        )
        signature.append(f"{module_path}:{'|'.join(agent_names)}")
    return tuple(sorted(signature))


def _refresh_inprocess_agent_cache_if_needed(modules: dict[str, object]) -> None:
    global _INPROCESS_AGENT_INDEX
    global _INPROCESS_AGENT_HINTS
    global _INPROCESS_AGENT_SIGNATURE

    signature = _runtime_signature(modules)
    if _INPROCESS_AGENT_SIGNATURE == signature and _INPROCESS_AGENT_INDEX:
        return

    runtime_index, runtime_hints = _build_runtime_agent_index(modules)
    local_index, local_hints = _build_local_agent_index()

    merged_index = dict(runtime_index)
    for key, factory in local_index.items():
        merged_index.setdefault(key, factory)

    _INPROCESS_AGENT_INDEX = merged_index
    _INPROCESS_AGENT_HINTS = sorted(set(runtime_hints + local_hints))
    _INPROCESS_AGENT_SIGNATURE = signature
    _INPROCESS_AGENT_INSTANCES.clear()


def _resolve_inprocess_abi_agent(agent_name: str):
    """Resolve an ABI agent instance from in-process loaded modules with caching."""
    from naas_abi import ABIModule

    raw_target = (agent_name or "").strip()
    if not raw_target:
        return None

    abi_module = ABIModule.get_instance()
    modules = getattr(getattr(abi_module, "engine", None), "modules", {}) or {}

    with _INPROCESS_AGENT_LOCK:
        _refresh_inprocess_agent_cache_if_needed(modules)
        lookup_order = [raw_target.lower(), _normalize_agent_key(raw_target)]
        if "/" in raw_target:
            _, right = raw_target.split("/", 1)
            lookup_order.extend([right.strip().lower(), _normalize_agent_key(right.strip())])

        factory = None
        for key in lookup_order:
            factory = _INPROCESS_AGENT_INDEX.get(key)
            if callable(factory):
                break

        if not callable(factory):
            return None

        factory_key = (
            f"{getattr(factory, '__module__', '')}."
            f"{getattr(factory, '__qualname__', getattr(factory, '__name__', 'factory'))}"
        )
        existing = _INPROCESS_AGENT_INSTANCES.get(factory_key)
        if existing is not None:
            return existing

        try:
            instance = factory()
        except Exception:
            return None

        _INPROCESS_AGENT_INSTANCES[factory_key] = instance
        return instance


def _extract_opencode_ui_event(event: dict[str, Any]) -> dict[str, Any] | None:
    event_type = str(event.get("type") or "")
    properties = event.get("properties") or {}

    if "question" in event_type.lower():
        question_payload = properties.get("question") or properties
        if not isinstance(question_payload, dict):
            return None
        question_text = str(question_payload.get("question") or "").strip()
        options = question_payload.get("options")
        cleaned_options: list[str] = []
        if isinstance(options, list):
            cleaned_options = [opt for opt in options if isinstance(opt, str)]
        if question_text == "":
            return None
        return {
            "event": "agent.question",
            "question": question_text,
            "options": cleaned_options,
        }

    if event_type != "message.part.updated":
        return None

    part = properties.get("part") or {}
    if not isinstance(part, dict):
        return None

    if part.get("type") != "tool":
        return None

    tool_name = str(part.get("tool") or "tool").strip()
    state = part.get("state") or {}
    if not isinstance(state, dict):
        return None

    status = str(state.get("status") or "").strip()
    if status in {"pending", "running", "completed", "failed", "error", "cancelled"}:
        payload: dict[str, Any] = {
            "event": "tool",
            "tool": tool_name,
            "status": status,
        }
        output = state.get("output")
        if isinstance(output, str) and output.strip():
            payload["output"] = output.strip()
        return payload

    return None


async def stream_with_abi_inprocess(
    messages: list[Message],
    config: ProviderConfig,
    thread_id: str | None = None,
) -> AsyncGenerator[str | dict[str, Any], None]:
    """Stream chat by invoking ABI agent directly in-process."""
    import asyncio
    import json
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
        with _INPROCESS_AGENT_LOCK:
            available_hint = ", ".join(_INPROCESS_AGENT_HINTS[:20]) or "unavailable"
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

    # New OpencodeAgent path: async event stream method.
    if hasattr(agent, "astream"):
        try:
            emitted = False
            async for raw_event in agent.astream(
                latest_user_message,
                thread_id=thread_id,
            ):
                if isinstance(raw_event, dict):
                    obj = raw_event
                else:
                    try:
                        obj = json.loads(raw_event)
                    except Exception:
                        continue

                if not isinstance(obj, dict):
                    continue

                if obj.get("type") == "message.part.delta":
                    props = obj.get("properties") or {}
                    if props.get("field") == "text":
                        delta = props.get("delta")
                        if isinstance(delta, str) and delta:
                            emitted = True
                            yield delta
                    continue

                ui_event = _extract_opencode_ui_event(obj)
                if ui_event:
                    yield ui_event

            if not emitted and hasattr(agent, "ainvoke"):
                fallback_text = await agent.ainvoke(latest_user_message, thread_id=thread_id)
                if isinstance(fallback_text, str) and fallback_text.strip():
                    yield fallback_text
        except Exception as exc:
            logger.error(f"In-process ABI streaming error: {exc}")
            yield f"\n\n**Error:** Failed to stream ABI agent response: {str(exc)}"
        return

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
            elif event_name == "tool_usage" and text.strip():
                yield {"event": "tool_usage", "tool": text}
            elif event_name == "tool_response" and text.strip():
                yield {"event": "tool_response", "output": text}
        elif isinstance(event, str) and event.strip():
            yield event
