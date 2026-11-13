"""
ABI MCP Server - Lightweight HTTP-based Implementation

Exposes the agents a person may use as MCP tools. The server holds no
credential of its own: every call goes to Nexus's OpenAI-compatible gateway
(``/api/v1/models``, ``/api/v1/chat/completions``, the agent is the model) with
the caller's own personal API key (``abi_pk_...``), and Nexus decides which
agents that person may use.

- ``stdio`` (the default; a desktop client starts the process): the key is
  ``NEXUS_ACCESS_TOKEN`` in the environment of the person who runs it.
- ``sse`` / ``http``: every request carries ``Authorization: Bearer <key>``.
  A request without one, or with one Nexus refuses, gets 401. Host and Origin
  are checked whatever the bind address: ``MCP_ALLOWED_HOSTS`` and
  ``MCP_ALLOWED_ORIGINS`` (comma-separated, ``host:*`` for any port), loopback
  by default.
"""

import asyncio
import hashlib
import os
import re
import sys
import time

import httpx
from dotenv import load_dotenv
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# Load environment variables from .env file if present
load_dotenv()

# The ABI API that serves Nexus (``/api``): the gateway every call goes through.
ABI_API_BASE = os.environ.get("ABI_API_BASE", "http://localhost:9879").rstrip("/")
GATEWAY = f"{ABI_API_BASE}/api/v1"

# MCP_HOST: the address the HTTP transports listen on (0.0.0.0 in a container,
# where the port is published); MCP_PORT: their port.
MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))

_LOOPBACK_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
_LOOPBACK_ORIGINS = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
# How long a key Nexus accepted is taken as valid without asking again.
_TOKEN_CACHE_SECONDS = 60.0


def _listed(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


def transport_security() -> TransportSecuritySettings:
    """Host and Origin checks, on whatever address the server listens."""
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_listed("MCP_ALLOWED_HOSTS", _LOOPBACK_HOSTS),
        allowed_origins=_listed("MCP_ALLOWED_ORIGINS", _LOOPBACK_ORIGINS),
    )


class NexusKeyVerifier:
    """A bearer is valid when Nexus accepts it: its gateway lists the agents
    of the key's owner. Answers are kept for a minute, by the key's hash."""

    def __init__(self) -> None:
        self._accepted: dict[str, float] = {}

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        now = time.monotonic()
        if self._accepted.get(digest, 0.0) > now:
            return AccessToken(token=token, client_id="nexus", scopes=[])
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{GATEWAY}/models", headers=_headers(token)
                )
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            self._accepted.pop(digest, None)
            return None
        # Forget what expired, so the map holds only the last minute's keys.
        self._accepted = {k: t for k, t in self._accepted.items() if t > now}
        self._accepted[digest] = now + _TOKEN_CACHE_SECONDS
        return AccessToken(token=token, client_id="nexus", scopes=[])


# Initialize FastMCP server. The HTTP transports require a bearer that Nexus
# accepts; stdio has no requests and uses NEXUS_ACCESS_TOKEN.
mcp = FastMCP(
    "abi",
    host=MCP_HOST,
    port=MCP_PORT,
    token_verifier=NexusKeyVerifier(),
    auth=AuthSettings(
        issuer_url=os.environ.get("MCP_AUTH_ISSUER_URL", ABI_API_BASE),  # type: ignore[arg-type]
        resource_server_url=os.environ.get(  # type: ignore[arg-type]
            "MCP_PUBLIC_URL", f"http://127.0.0.1:{MCP_PORT}"
        ),
    ),
    transport_security=transport_security(),
)


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "ABI-MCP/1.0",
    }


def caller_token(ctx: Context | None) -> str | None:
    """The key of the person calling: the bearer of the HTTP request that
    carried the call, else (stdio) NEXUS_ACCESS_TOKEN."""
    request = None
    if ctx is not None:
        try:
            request = ctx.request_context.request
        except (AttributeError, ValueError, LookupError):
            request = None
    if request is not None:
        authorization = getattr(request, "headers", {}).get("authorization") or ""
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return token.strip()
        return None
    return os.environ.get("NEXUS_ACCESS_TOKEN") or None


async def list_agent_ids(token: str) -> list[str]:
    """The agents the key's owner may use."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{GATEWAY}/models", headers=_headers(token))
        response.raise_for_status()
        return [
            str(item.get("id"))
            for item in response.json().get("data", [])
            if isinstance(item, dict) and item.get("id")
        ]


async def call_abi_agent_http(agent_name: str, prompt: str, token: str | None) -> str:
    """Ask ``agent_name`` through the Nexus gateway, as the key's owner."""
    if not token:
        return "🔒 No credential: send your personal API key (abi_pk_...) as a bearer token."
    try:
        data = {
            "model": agent_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{GATEWAY}/chat/completions", json=data, headers=_headers(token)
            )
            response.raise_for_status()
            choices = response.json().get("choices") or [{}]
            return str((choices[0].get("message") or {}).get("content") or "")

    except httpx.ConnectError:
        return (
            f"❌ ABI API server not running at {ABI_API_BASE}. Please start it first."
        )
    except httpx.TimeoutException:
        return f"⏱️ Timeout calling {agent_name} agent. The agent might be processing a complex request."
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return "🔒 Authentication failed. Check your personal API key."
        if e.response.status_code in (403, 404):
            return f"❓ Agent '{agent_name}' is not one you may use."
        return f"❌ HTTP {e.response.status_code} error calling {agent_name} agent."
    except Exception as e:  # noqa: BLE001
        return f"❌ Error calling {agent_name} agent: {e!s}"


def agent_name_to_function_name(agent_name: str) -> str:
    """Convert agent name to valid Python function name"""
    # Replace spaces and special chars with underscores, convert to lowercase
    function_name = re.sub(r"[^a-zA-Z0-9_]", "_", agent_name.lower())
    # Remove multiple consecutive underscores
    function_name = re.sub(r"_+", "_", function_name)
    # Remove leading/trailing underscores
    function_name = function_name.strip("_")
    # Ensure it doesn't start with a number
    if function_name and function_name[0].isdigit():
        function_name = f"agent_{function_name}"
    return function_name or "unknown_agent"


def create_agent_function(agent_name: str, description: str):
    """Create a tool that asks one agent, as the caller."""

    async def agent_function(prompt: str, ctx: Context) -> str:
        return await call_abi_agent_http(agent_name, prompt, caller_token(ctx))

    # Set function metadata
    agent_function.__name__ = agent_name_to_function_name(agent_name)
    agent_function.__doc__ = f"""{description}

    Args:
        prompt: Your question or request for the {agent_name} agent
    """

    return agent_function


@mcp.tool()
async def list_agents(ctx: Context) -> list[str]:
    """List the agents you may use (the names ask_agent takes)."""
    token = caller_token(ctx)
    if not token:
        return []
    return await list_agent_ids(token)


@mcp.tool()
async def ask_agent(agent: str, prompt: str, ctx: Context) -> str:
    """Ask one of your agents (see list_agents) a question.

    Args:
        agent: The agent's name, as list_agents gives it
        prompt: Your question or request
    """
    return await call_abi_agent_http(agent, prompt, caller_token(ctx))


async def register_agents_dynamically() -> None:
    """stdio: one tool per agent the key's owner may use."""
    token = os.environ.get("NEXUS_ACCESS_TOKEN")
    if not token:
        return
    print("🔍 Discovering your agents...", file=sys.stderr)
    try:
        agents = await list_agent_ids(token)
    except httpx.HTTPError as e:
        print(f"⚠️ Could not list your agents: {e}", file=sys.stderr)
        return
    for agent_name in agents:
        mcp.tool()(create_agent_function(agent_name, f"Ask the {agent_name} agent."))
    print(f"✅ {len(agents)} agents registered", file=sys.stderr)


_LOOPBACK_BINDS = ("127.0.0.1", "localhost", "::1")


def http_transport_problem(
    host: str = MCP_HOST, public_url: str | None = None
) -> str | None:
    """Why an HTTP transport may not start: listening beyond loopback needs
    MCP_PUBLIC_URL, the address its clients use (published in its 401s)."""
    public_url = os.environ.get("MCP_PUBLIC_URL") if public_url is None else public_url
    if host not in _LOOPBACK_BINDS and not public_url:
        return (
            f"MCP_HOST={host} listens beyond this machine: set MCP_PUBLIC_URL to the "
            "address clients use, and MCP_ALLOWED_HOSTS / MCP_ALLOWED_ORIGINS to match."
        )
    return None


def run():
    """Entry point for the script"""
    # Determine transport type from environment
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    print(f"📡 ABI API at {ABI_API_BASE}", file=sys.stderr)
    problem = http_transport_problem() if transport in ("sse", "http") else None
    if problem:
        print(f"❌ {problem}", file=sys.stderr)
        sys.exit(1)

    if transport == "sse":
        print(
            f"🌐 MCP server, SSE transport, on {MCP_HOST}:{MCP_PORT}", file=sys.stderr
        )
        mcp.run(transport="sse")
    elif transport == "http":
        print(
            f"🌐 MCP server, streamable HTTP transport, on {MCP_HOST}:{MCP_PORT}",
            file=sys.stderr,
        )
        mcp.run(transport="streamable-http")
    else:
        if not os.environ.get("NEXUS_ACCESS_TOKEN"):
            print(
                "❌ NEXUS_ACCESS_TOKEN not set: your personal API key (abi_pk_...), "
                "made in Nexus under Account, API keys.",
                file=sys.stderr,
            )
            sys.exit(1)
        asyncio.run(register_agents_dynamically())
        mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
