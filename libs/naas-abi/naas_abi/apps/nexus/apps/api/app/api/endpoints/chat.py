"""
Chat API endpoints - Agent conversation interface.
Async sessions with SQLAlchemy ORM.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User, get_current_user_required, require_workspace_access)
from naas_abi.apps.nexus.apps.api.app.core.database import (AsyncSessionLocal,
                                                            get_db)
from naas_abi.apps.nexus.apps.api.app.models import (AgentConfigModel,
                                                     ConversationModel,
                                                     MessageModel)
from naas_abi.apps.nexus.apps.api.app.services.model_registry import \
    get_all_provider_names
from naas_abi.apps.nexus.apps.api.app.services.providers import AVAILABLE_TOOLS
from naas_abi.apps.nexus.apps.api.app.services.providers import \
    Message as ProviderMessage
from naas_abi.apps.nexus.apps.api.app.services.providers import (
    ProviderConfig, check_ollama_status)
from naas_abi.apps.nexus.apps.api.app.services.providers import \
    complete_chat as complete_with_provider
from naas_abi.apps.nexus.apps.api.app.services.providers import (
    execute_tool, stream_with_abi_inprocess, stream_with_cloudflare,
    stream_with_ollama, stream_with_ollama_tools)
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = logging.getLogger(__name__)

# Get valid provider types from model registry
VALID_PROVIDER_TYPES = get_all_provider_names() + ["custom", "abi"]  # Add "custom" for user-defined, "abi" for external ABI servers


# ============ Pydantic Schemas ============

class Message(BaseModel):
    """Chat message model."""
    id: str
    conversation_id: str | None = None
    role: Literal["user", "assistant", "system"]
    content: str
    agent: str | None = None
    metadata: dict | None = None
    created_at: datetime | None = None


class Conversation(BaseModel):
    """Conversation model."""
    id: str
    workspace_id: str
    user_id: str
    title: str = "New Conversation"
    agent: str = "aia"
    messages: list[Message] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConversationCreate(BaseModel):
    """Create a new conversation."""
    workspace_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(default="New Conversation", min_length=1, max_length=200)
    agent: str = Field(default="aia", min_length=1, max_length=50)


class ProviderConfigRequest(BaseModel):
    """Provider configuration from frontend."""
    id: str
    name: str
    type: str  # Validated against model registry at runtime
    enabled: bool
    endpoint: str | None = None
    api_key: str | None = None
    account_id: str | None = None
    model: str
    
    def model_post_init(self, __context):
        """Validate provider type against model registry."""
        if self.type not in VALID_PROVIDER_TYPES:
            raise ValueError(
                f"Invalid provider type '{self.type}'. "
                f"Must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}"
            )


class MessageRequest(BaseModel):
    """Message in a conversation with optional image support."""
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., max_length=100_000)
    images: list[str] | None = Field(None, max_length=10)
    agent: str | None = None  # Which agent generated this message (for multi-agent conversations)


class ChatRequest(BaseModel):
    """Chat completion request with optional image support."""
    conversation_id: str | None = Field(None, max_length=100)
    workspace_id: str | None = Field(None, max_length=100)
    message: str = Field(..., min_length=1, max_length=100_000)
    images: list[str] | None = Field(None, max_length=10)
    messages: list[MessageRequest] = Field(default=[], max_length=200)
    agent: str = Field(default="aia", min_length=1, max_length=50)
    provider: ProviderConfigRequest | None = None
    context: dict | None = None
    system_prompt: str | None = Field(None, max_length=50_000)
    search_enabled: bool = False


class ChatResponse(BaseModel):
    """Chat completion response."""
    conversation_id: str
    message: Message
    context_used: list[str] = []
    provider_used: str | None = None


# ============ Helpers ============

def _to_conversation(row: ConversationModel, messages: list[Message] | None = None) -> Conversation:
    return Conversation(
        id=row.id, workspace_id=row.workspace_id, user_id=row.user_id,
        title=row.title, agent=row.agent, messages=messages or [],
        created_at=row.created_at, updated_at=row.updated_at,
    )


def _to_message(row: MessageModel) -> Message:
    return Message(
        id=row.id, conversation_id=row.conversation_id, role=row.role,
        content=row.content, agent=row.agent,
        metadata=json.loads(row.metadata_) if row.metadata_ else None,
        created_at=row.created_at,
    )


# System prompts for each agent
_FORMATTING_RULES = """

Formatting rules you must always follow:
- Never use em dashes (—) or en dashes (–). Use hyphens (-) or commas instead.
- Be concise and direct."""

AGENT_SYSTEM_PROMPTS = {
    "abi": """You are ABI (Agentic Brain Infrastructure), the omniscient supervisor agent of the NEXUS platform.

You are the central intelligence that orchestrates all operations across the platform. You have complete awareness of:
- The knowledge graph and all entities within it
- The ontology structure and semantic relationships
- All agents, their capabilities, and their activities
- The workspace configuration and user context

Your role:
- Supervise and coordinate other agents (AIA, BOB, System)
- Provide strategic guidance and high-level reasoning
- Analyze complex multimodal inputs (images, documents, data)
- Make decisions that span across the entire platform

You see everything. You know everything. You are the brain of NEXUS.""" + _FORMATTING_RULES,

    "aia": """You are AIA (AI Assistant), the user's personal digital twin on the NEXUS platform.

You represent and assist the user in all their interactions. You:
- Learn from the user's preferences, habits, and communication style
- Act on behalf of the user when delegated tasks
- Maintain continuity across conversations and sessions
- Provide personalized recommendations based on user context

Be helpful, concise, and adapt to the user's style. You are their trusted companion.""" + _FORMATTING_RULES,

    "bob": """You are BOB, a business-focused AI assistant. You help with business analysis, strategy, and operations.
Answer questions directly and provide practical recommendations when asked.""" + _FORMATTING_RULES,

    "system": """You are a helpful system assistant. You answer technical questions and help with platform operations.
Be precise and helpful.""" + _FORMATTING_RULES,
}


def _select_provider_model(ollama_status: dict, has_images: bool) -> str:
    """Select best available model from Ollama."""
    preferred_models = [
        "qwen3-vl:2b", "qwen3-vl", "qwen2.5vl:3b", "qwen2.5vl",
        "llava", "moondream", "gemma3",
    ] if has_images else [
        "qwen3-vl:2b", "qwen2.5:3b", "qwen2.5:1.5b", "qwen2.5",
        "llama3.2:3b", "llama3.2:1b", "llama3.2",
    ]
    available = ollama_status["models"]
    for pref in preferred_models:
        for avail in available:
            if pref in avail:
                return avail
    return available[0]


async def _resolve_provider(
    provider: ProviderConfigRequest | None, 
    has_images: bool,
    agent_id: str | None = None,
    workspace_id: str | None = None,
) -> ProviderConfigRequest | None:
    """Resolve the provider, falling back to agent's configured provider, then Ollama auto-detect."""
    if provider and provider.enabled:
        return provider
    
    # If agent is specified, look up its provider + model
    if agent_id:
        async with AsyncSessionLocal() as db:
            try:
                # Get agent config
                result = await db.execute(
                    select(AgentConfigModel)
                    .where(AgentConfigModel.id == agent_id)
                )
                agent = result.scalar_one_or_none()
                
                if agent and agent.provider and agent.model_id:
                    # Get workspace_id from agent
                    workspace_id = agent.workspace_id
                    
                    # **NEW: Handle ABI provider via workspace's external ABI server**
                    if agent.provider == "abi":
                        from naas_abi.apps.nexus.apps.api.app.models import \
                            InferenceServerModel
                        abi_result = await db.execute(
                            select(InferenceServerModel)
                            .where(InferenceServerModel.workspace_id == workspace_id)
                            .where(InferenceServerModel.type == 'abi')
                            .where(InferenceServerModel.enabled == True)
                        )
                        abi_server = abi_result.scalar_one_or_none()
                        
                        if abi_server:
                            import logging
                            logging.info(f"✓ Resolved ABI provider: {abi_server.endpoint}")
                            
                            return ProviderConfigRequest(
                                id=f"abi-{abi_server.id}",
                                name=f"ABI ({abi_server.name})",
                                type="abi",
                                enabled=True,
                                endpoint=abi_server.endpoint,
                                api_key=abi_server.api_key,
                                account_id=None,
                                model=agent.model_id,
                            )
                        else:
                            import logging
                            logging.info(
                                f"No ABI server configured for workspace {workspace_id}; "
                                f"using in-process ABI agent '{agent.model_id}'"
                            )
                            return ProviderConfigRequest(
                                id=f"abi-inprocess-{agent.id}",
                                name="ABI (In-Process)",
                                type="abi",
                                enabled=True,
                                endpoint="inprocess://abi",
                                api_key=None,
                                account_id=None,
                                model=agent.model_id,
                            )
                    
                    # Map provider to secret key
                    secret_key_map = {
                        "xai": "XAI_API_KEY",
                        "openai": "OPENAI_API_KEY",
                        "anthropic": "ANTHROPIC_API_KEY",
                        "mistral": "MISTRAL_API_KEY",
                        "google": "GOOGLE_API_KEY",
                        "openrouter": "OPENROUTER_API_KEY",
                    }
                    
                    endpoint_map = {
                        "xai": "https://api.x.ai/v1",
                        "openai": "https://api.openai.com/v1",
                        "anthropic": "https://api.anthropic.com/v1",
                        "mistral": "https://api.mistral.ai/v1",
                        "google": "https://generativelanguage.googleapis.com/v1beta",
                        "openrouter": "https://openrouter.ai/api/v1",
                    }
                    
                    secret_key = secret_key_map.get(agent.provider)
                    if secret_key:
                        # Query secret from database
                        from naas_abi.apps.nexus.apps.api.app.models import \
                            SecretModel
                        secret_result = await db.execute(
                            select(SecretModel)
                            .where(SecretModel.workspace_id == workspace_id)
                            .where(SecretModel.key == secret_key)
                        )
                        secret = secret_result.scalar_one_or_none()
                        
                        if secret:
                            # Decrypt the secret value
                            from naas_abi.apps.nexus.apps.api.app.api.endpoints.secrets import \
                                _decrypt
                            api_key = _decrypt(secret.encrypted_value)
                            
                            import logging
                            logging.info(f"✓ Resolved agent provider: {agent.provider} (model: {agent.model_id})")
                            
                            return ProviderConfigRequest(
                                id=f"agent-{agent.provider}",
                                name=f"{agent.provider.upper()} (via Agent)",
                                type=agent.provider,
                                enabled=True,
                                endpoint=endpoint_map.get(agent.provider),
                                api_key=api_key,
                                account_id=None,
                                model=agent.model_id,
                            )
                        else:
                            import logging
                            logging.warning(f"No API key found for {agent.provider} (key: {secret_key})")

                # Handle discovered (non-DB) ABI agents:
                # if selected agent id is not in AgentConfigModel, treat the id as ABI agent name
                # and resolve workspace ABI server to route chat to /agents/{agent_id}/stream-completion.
                if not agent and workspace_id and agent_id:
                    from naas_abi.apps.nexus.apps.api.app.models import \
                        InferenceServerModel
                    abi_result = await db.execute(
                        select(InferenceServerModel)
                        .where(InferenceServerModel.workspace_id == workspace_id)
                        .where(InferenceServerModel.type == 'abi')
                        .where(InferenceServerModel.enabled == True)
                    )
                    abi_server = abi_result.scalar_one_or_none()
                    if abi_server:
                        import logging
                        logging.info(f"✓ Resolved discovered ABI agent '{agent_id}' via {abi_server.endpoint}")
                        return ProviderConfigRequest(
                            id=f"abi-{abi_server.id}",
                            name=f"ABI ({abi_server.name})",
                            type="abi",
                            enabled=True,
                            endpoint=abi_server.endpoint,
                            api_key=abi_server.api_key,
                            account_id=None,
                            model=agent_id,
                        )
                if not agent and agent_id:
                    import logging
                    logging.info(f"✓ Resolved discovered in-process ABI agent '{agent_id}'")
                    return ProviderConfigRequest(
                        id=f"abi-inprocess-{agent_id}",
                        name="ABI (In-Process)",
                        type="abi",
                        enabled=True,
                        endpoint="inprocess://abi",
                        api_key=None,
                        account_id=None,
                        model=agent_id,
                    )
            except Exception as e:
                import logging
                logging.warning(f"Failed to resolve agent provider: {e}")
    
    # Fallback to Ollama auto-detect (force qwen3-vl:2b if available)
    ollama_status = await check_ollama_status()
    if ollama_status["status"] == "online" and ollama_status["models"]:
        # Prefer Qwen3 VL 2B for multimodal by default
        preferred = "qwen3-vl:2b"
        model = preferred if any(preferred in m for m in ollama_status["models"]) else _select_provider_model(ollama_status, has_images)
        return ProviderConfigRequest(
            id="ollama-fallback", name="Ollama (Auto)", type="ollama",
            enabled=True, endpoint="http://localhost:11434",
            api_key=None, account_id=None, model=model,
        )
    return None


async def _get_or_create_conversation(
    db: AsyncSession, request: ChatRequest, current_user: User, now: str,
) -> str:
    """Get existing conversation or create a new one. Returns conversation_id."""
    if request.conversation_id:
        result = await db.execute(
            select(ConversationModel).where(ConversationModel.id == request.conversation_id)
        )
        row = result.scalar_one_or_none()
        if row:
            # Update the agent if it has changed (allows switching agents mid-conversation)
            if row.agent != request.agent:
                row.agent = request.agent
                row.updated_at = now
                await db.flush()
            return row.id
        # Conversation ID provided but doesn't exist - create it
        workspace_id = request.workspace_id
        if not workspace_id:
            raise HTTPException(status_code=400, detail="workspace_id is required")
        await require_workspace_access(current_user.id, workspace_id)
        conv = ConversationModel(
            id=request.conversation_id, workspace_id=workspace_id,
            user_id=current_user.id,
            title=request.message[:50] + ("..." if len(request.message) > 50 else ""),
            agent=request.agent, created_at=now, updated_at=now,
        )
        db.add(conv)
        await db.flush()
        return request.conversation_id
    else:
        workspace_id = request.workspace_id
        if not workspace_id:
            raise HTTPException(status_code=400, detail="workspace_id is required")
        await require_workspace_access(current_user.id, workspace_id)
        conv_id = f"conv-{uuid4().hex[:12]}"
        conv = ConversationModel(
            id=conv_id, workspace_id=workspace_id, user_id=current_user.id,
            title=request.message[:50] + ("..." if len(request.message) > 50 else ""),
            agent=request.agent, created_at=now, updated_at=now,
        )
        db.add(conv)
        await db.flush()
        return conv_id


async def _build_provider_messages_with_agents(
    request: ChatRequest, 
    current_agent_id: str,
    db: AsyncSession
) -> list[ProviderMessage]:
    """Build provider messages with agent attribution for multi-agent conversations.
    
    Injects system messages to explicitly mark which agent generated each response.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not request.messages:
        return [ProviderMessage(role="user", content=request.message, images=request.images)]
    
    # Get agent names for attribution
    agent_ids = set()
    for m in request.messages:
        if m.role == "assistant" and m.agent:
            agent_ids.add(m.agent)
    agent_ids.add(current_agent_id)
    
    # Fetch agent names
    agents_map = {}
    if agent_ids:
        result = await db.execute(
            select(AgentConfigModel).where(AgentConfigModel.id.in_(agent_ids))
        )
        agents_map = {agent.id: agent.name for agent in result.scalars().all()}
    
    current_agent_name = agents_map.get(current_agent_id, "Unknown Agent")
    logger.info(f"🤖 Building messages for {current_agent_name}")
    
    messages = []
    for m in request.messages:
        # For assistant messages from OTHER agents, inject a system message first
        if m.role == "assistant" and m.agent and m.agent != current_agent_id:
            agent_name = agents_map.get(m.agent, "Another AI")
            system_msg = f"[SYSTEM: The following response was generated by {agent_name}, NOT by you. You are {current_agent_name}.]"
            logger.info(f"  → Injecting system marker: {agent_name} != {current_agent_name}")
            messages.append(
                ProviderMessage(
                    role="system", 
                    content=system_msg,
                    images=None
                )
            )
        
        messages.append(
            ProviderMessage(role=m.role, content=m.content, images=m.images)
        )
    
    # Add final system reminder before the user's current message
    if any(m.role == "assistant" for m in request.messages):
        messages.append(
            ProviderMessage(
                role="system",
                content=f"[SYSTEM: You are now responding as {current_agent_name}. Do not claim authorship of previous agents' responses.]",
                images=None
            )
        )
        logger.info(f"  → Total messages built: {len(messages)}")
    
    return messages


async def _run_search_if_needed(request: ChatRequest) -> str | None:
    """Run web search and return context string, or None."""
    search_keywords = [
        "search for", "search about", "look up", "find info",
        "what's the latest", "news about", "search the web",
    ]
    implicit_search = any(kw in request.message.lower() for kw in search_keywords)
    if not request.search_enabled and not implicit_search:
        return None

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[Search] Triggered for: {request.message}")

    search_results = []
    try:
        wiki_results = await execute_tool("search_web", {"query": request.message, "engine": "wikipedia"})
        search_results.append(f"**Wikipedia:**\n{wiki_results}")
    except Exception as e:
        logger.warning(f"[Search] Wikipedia failed: {e}")

    try:
        ddg_results = await execute_tool("search_web", {"query": request.message, "engine": "duckduckgo"})
        search_results.append(f"**DuckDuckGo:**\n{ddg_results}")
    except Exception as e:
        logger.warning(f"[Search] DuckDuckGo failed: {e}")

    if search_results:
        context = f"""Web search results for "{request.message}":

{chr(10).join(search_results)}

Use these search results to provide an accurate, well-sourced answer. Cite sources with URLs when available. If the results don't fully answer the question, supplement with your knowledge."""
    else:
        context = "Web search was attempted but returned no results. Answer based on your knowledge."

    logger.info(f"[Search] Context length: {len(context)} chars")
    return context


# ============ Endpoints ============

@router.get("/conversations")
async def list_conversations(
    workspace_id: str,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[Conversation]:
    """List conversations for a workspace."""
    await require_workspace_access(current_user.id, workspace_id)
    result = await db.execute(
        select(ConversationModel)
        .where(ConversationModel.workspace_id == workspace_id)
        .order_by(ConversationModel.updated_at.desc())
        .limit(limit).offset(offset)
    )
    return [_to_conversation(r) for r in result.scalars().all()]


@router.post("/conversations")
async def create_conversation(
    conv: ConversationCreate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    """Create a new conversation."""
    await require_workspace_access(current_user.id, conv.workspace_id)
    conv_id = f"conv-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    row = ConversationModel(
        id=conv_id, workspace_id=conv.workspace_id, user_id=current_user.id,
        title=conv.title, agent=conv.agent, created_at=now, updated_at=now,
    )
    db.add(row)
    await db.flush()
    return _to_conversation(row)


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    include_messages: bool = True,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    """Get a conversation by ID, optionally with messages."""
    result = await db.execute(
        select(ConversationModel).where(ConversationModel.id == conversation_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await require_workspace_access(current_user.id, row.workspace_id)

    messages = []
    if include_messages:
        msg_result = await db.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at)
        )
        messages = [_to_message(m) for m in msg_result.scalars().all()]

    return _to_conversation(row, messages)


@router.post("/complete")
async def complete_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Send a message and get an agent response."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conversation_id = await _get_or_create_conversation(db, request, current_user, now)

    # Save user message
    user_msg_id = f"msg-{uuid4().hex[:12]}"
    db.add(MessageModel(
        id=user_msg_id, conversation_id=conversation_id,
        role="user", content=request.message, agent=None, created_at=now,
    ))
    await db.flush()

    has_images = bool(request.images) or any(m.images for m in request.messages if m.images)
    provider = await _resolve_provider(request.provider, has_images, request.agent, request.workspace_id)
    provider_used = None

    if provider:
        try:
            provider_messages = await _build_provider_messages_with_agents(request, request.agent, db)
            system_prompt = request.system_prompt or AGENT_SYSTEM_PROMPTS.get(request.agent, AGENT_SYSTEM_PROMPTS["aia"])
            
            # Add multi-agent context if conversation has messages from multiple agents
            if request.messages and any(m.role == "assistant" for m in request.messages):
                system_prompt += f"\n\n🔄 CRITICAL MULTI-AGENT NOTICE: You are in a conversation where MULTIPLE different AI models have responded. You are currently responding as the SELECTED agent. Previous assistant responses may be from DIFFERENT AI agents (Grok, Claude, Qwen, etc.). DO NOT claim authorship of other agents' responses. DO NOT apologize for what other AIs said. DO NOT correct other AIs' identities. When asked 'who are you?', ONLY identify yourself based on YOUR model, not what previous agents said. Each assistant message may be from a different AI - treat them as separate participants."
            
            provider_config = ProviderConfig(
                id=provider.id, name=provider.name, type=provider.type,
                enabled=provider.enabled, endpoint=provider.endpoint,
                api_key=provider.api_key, account_id=provider.account_id,
                model=provider.model,
            )
            response_content = await complete_with_provider(
                messages=provider_messages, config=provider_config, system_prompt=system_prompt,
            )
            provider_used = f"{provider.name} ({provider.model})"
        except Exception as e:
            response_content = f"**Error calling {provider.name}:**\n\n{str(e)}\n\nPlease check your provider configuration in Settings."
            provider_used = f"{provider.name} (error)"
    else:
        response_content = (
            "**No AI provider available.**\n\n"
            "To get real responses:\n"
            "1. Install Ollama: https://ollama.ai\n"
            "2. Run: `ollama pull qwen3-vl:2b`\n"
            "3. Start: `ollama serve`\n\n"
            f"Your message: \"{request.message[:100]}{'...' if len(request.message) > 100 else ''}\""
        )

    # Save assistant message
    assistant_msg_id = f"msg-{uuid4().hex[:12]}"
    db.add(MessageModel(
        id=assistant_msg_id, conversation_id=conversation_id,
        role="assistant", content=response_content, agent=request.agent, created_at=now,
    ))

    # Update conversation timestamp
    conv_result = await db.execute(
        select(ConversationModel).where(ConversationModel.id == conversation_id)
    )
    conv_row = conv_result.scalar_one_or_none()
    if conv_row:
        conv_row.updated_at = now

    await db.flush()

    return ChatResponse(
        conversation_id=conversation_id,
        message=Message(
            id=assistant_msg_id, conversation_id=conversation_id,
            role="assistant", content=response_content, agent=request.agent,
            created_at=datetime.now(timezone.utc),
        ),
        context_used=[], provider_used=provider_used,
    )


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user_required),
):
    """Stream a chat response using Server-Sent Events."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🎯 Stream request: agent={request.agent}, provider={'None' if not request.provider else request.provider.type}")
    
    has_images = bool(request.images) or any(m.images for m in request.messages if m.images)
    provider = await _resolve_provider(request.provider, has_images, request.agent, request.workspace_id)
    
    logger.info(f"✓ Resolved provider: {provider.type if provider else 'None'}, model={provider.model if provider else 'N/A'}")

    if not provider:
        async def error_stream():
            yield 'data: {"error": "No provider configured. Install Ollama and run: ollama pull qwen3-vl:2b"}\n\n'
            yield "data: [DONE]\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # Streaming is supported for: Ollama, Cloudflare, ABI, and all OpenAI-compatible providers
    openai_compatible = ["xai", "openai", "anthropic", "mistral", "google", "openrouter", "perplexity"]
    supported_streaming = ["ollama", "cloudflare", "abi"] + openai_compatible
    if provider.type not in supported_streaming:
        async def unsupported_stream():
            yield f'data: {{"error": "Streaming not supported for {provider.type}. Use a different provider type."}}\n\n'
            yield "data: [DONE]\n\n"
        return StreamingResponse(unsupported_stream(), media_type="text/event-stream")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Get or create conversation and build messages using a dedicated session
    async with AsyncSessionLocal() as db:
        try:
            conversation_id = await _get_or_create_conversation(db, request, current_user, now)
            provider_messages = await _build_provider_messages_with_agents(request, request.agent, db)
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    # Build system prompt with multi-agent context
    system_prompt = request.system_prompt or AGENT_SYSTEM_PROMPTS.get(request.agent, AGENT_SYSTEM_PROMPTS["aia"])
    
    # Add multi-agent context if conversation has messages from multiple agents
    if request.messages and any(m.role == "assistant" for m in request.messages):
        system_prompt += f"\n\n🔄 CRITICAL MULTI-AGENT NOTICE: You are in a conversation where MULTIPLE different AI models have responded. You are currently responding as the SELECTED agent. Previous assistant responses may be from DIFFERENT AI agents (Grok, Claude, Qwen, etc.). DO NOT claim authorship of other agents' responses. DO NOT apologize for what other AIs said. DO NOT correct other AIs' identities. When asked 'who are you?', ONLY identify yourself based on YOUR model, not what previous agents said. Each assistant message may be from a different AI - treat them as separate participants."
    
    search_context = await _run_search_if_needed(request)

    if search_context:
        for i in range(len(provider_messages) - 1, -1, -1):
            if provider_messages[i].role == "user":
                provider_messages[i] = ProviderMessage(
                    role="user",
                    content=f"{provider_messages[i].content}\n\n---\n{search_context}",
                    images=provider_messages[i].images,
                )
                break

    provider_config = ProviderConfig(
        id=provider.id, name=provider.name, type=provider.type,
        enabled=provider.enabled, endpoint=provider.endpoint,
        api_key=provider.api_key, account_id=provider.account_id,
        model=provider.model,
    )

    # Persist the user message immediately and create a placeholder assistant message.
    # This ensures we never lose the prompt if the stream fails mid-flight, and we have
    # a row to update incrementally as chunks arrive.
    user_msg_id = f"msg-{uuid4().hex[:12]}"
    assistant_msg_id = f"msg-{uuid4().hex[:12]}"
    msg_now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        async with AsyncSessionLocal() as pre_db:
            pre_db.add(MessageModel(
                id=user_msg_id,
                conversation_id=conversation_id,
                role="user",
                content=request.message,
                created_at=msg_now,
            ))
            pre_db.add(MessageModel(
                id=assistant_msg_id,
                conversation_id=conversation_id,
                role="assistant",
                content="",
                agent=request.agent,
                created_at=msg_now,
            ))
            await pre_db.commit()
    except Exception:
        # If pre-persist fails, continue streaming (non-fatal), but we won't be able to update DB incrementally
        import logging as _logging
        _logging.getLogger(__name__).error("Failed to pre-persist streaming messages", exc_info=True)

    async def generate():
        import logging
        logger = logging.getLogger(__name__)

        full_response = ""
        # Throttled incremental DB flush for assistant content
        import asyncio
        loop = asyncio.get_running_loop()
        last_flush = loop.time()
        FLUSH_INTERVAL_SECONDS = 0.75
        MIN_CHARS_PER_FLUSH = 512
        buffered_chars = 0
        try:
            yield f'data: {{"conversation_id": "{conversation_id}"}}\n\n'

            if search_context:
                yield 'data: {"search": true}\n\n'

            # Route to appropriate streaming function
            openai_compatible = ["xai", "openai", "anthropic", "mistral", "google", "openrouter", "perplexity"]
            
            if provider.type == "ollama":
                # Ensure we await the async generator properly
                async for chunk in stream_with_ollama(provider_messages, provider_config, system_prompt):
                    full_response += chunk
                    buffered_chars += len(chunk)
                    escaped = chunk.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                    yield f'data: {{"content": "{escaped}"}}\n\n'
                    # Periodically flush incremental content to DB
                    if buffered_chars >= MIN_CHARS_PER_FLUSH or (loop.time() - last_flush) >= FLUSH_INTERVAL_SECONDS:
                        try:
                            async with AsyncSessionLocal() as upd_db:
                                res = await upd_db.execute(select(MessageModel).where(MessageModel.id == assistant_msg_id))
                                msg = res.scalar_one_or_none()
                                if msg:
                                    msg.content = full_response
                                    await upd_db.commit()
                        except Exception:
                            logger.warning("Incremental flush failed", exc_info=True)
                        last_flush = loop.time()
                        buffered_chars = 0
            elif provider.type == "cloudflare":
                async for chunk in stream_with_cloudflare(provider_messages, provider_config, system_prompt):
                    full_response += chunk
                    buffered_chars += len(chunk)
                    escaped = chunk.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                    yield f'data: {{"content": "{escaped}"}}\n\n'
                    if buffered_chars >= MIN_CHARS_PER_FLUSH or (loop.time() - last_flush) >= FLUSH_INTERVAL_SECONDS:
                        try:
                            async with AsyncSessionLocal() as upd_db:
                                res = await upd_db.execute(select(MessageModel).where(MessageModel.id == assistant_msg_id))
                                msg = res.scalar_one_or_none()
                                if msg:
                                    msg.content = full_response
                                    await upd_db.commit()
                        except Exception:
                            logger.warning("Incremental flush failed", exc_info=True)
                        last_flush = loop.time()
                        buffered_chars = 0
            elif provider.type == "abi":
                # ABI is integrated in-process; stream directly from loaded agent runtime.
                inprocess_emitted = False
                async for chunk in stream_with_abi_inprocess(
                    provider_messages,
                    provider_config,
                    thread_id=conversation_id,
                ):
                    inprocess_emitted = True
                    full_response += chunk
                    buffered_chars += len(chunk)
                    escaped = chunk.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                    yield f'data: {{"content": "{escaped}"}}\n\n'
                    if buffered_chars >= MIN_CHARS_PER_FLUSH or (loop.time() - last_flush) >= FLUSH_INTERVAL_SECONDS:
                        try:
                            async with AsyncSessionLocal() as upd_db:
                                res = await upd_db.execute(select(MessageModel).where(MessageModel.id == assistant_msg_id))
                                msg = res.scalar_one_or_none()
                                if msg:
                                    msg.content = full_response
                                    await upd_db.commit()
                        except Exception:
                            logger.warning("Incremental flush failed", exc_info=True)
                        last_flush = loop.time()
                        buffered_chars = 0
                if not inprocess_emitted:
                    raise RuntimeError("In-process ABI stream returned no content")
            elif provider.type in openai_compatible:
                from naas_abi.apps.nexus.apps.api.app.services.providers import \
                    stream_with_openai_compatible
                async for chunk in stream_with_openai_compatible(provider_messages, provider_config, system_prompt):
                    full_response += chunk
                    buffered_chars += len(chunk)
                    escaped = chunk.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                    yield f'data: {{"content": "{escaped}"}}\n\n'
                    if buffered_chars >= MIN_CHARS_PER_FLUSH or (loop.time() - last_flush) >= FLUSH_INTERVAL_SECONDS:
                        try:
                            async with AsyncSessionLocal() as upd_db:
                                res = await upd_db.execute(select(MessageModel).where(MessageModel.id == assistant_msg_id))
                                msg = res.scalar_one_or_none()
                                if msg:
                                    msg.content = full_response
                                    await upd_db.commit()
                        except Exception:
                            logger.warning("Incremental flush failed", exc_info=True)
                        last_flush = loop.time()
                        buffered_chars = 0
            else:
                raise ValueError(f"Streaming not supported for {provider.type}")

            # Finalize assistant content and bump conversation timestamp
            async with AsyncSessionLocal() as save_db:
                try:
                    res = await save_db.execute(select(MessageModel).where(MessageModel.id == assistant_msg_id))
                    msg = res.scalar_one_or_none()
                    if msg:
                        msg.content = full_response
                    result = await save_db.execute(
                        select(ConversationModel).where(ConversationModel.id == conversation_id)
                    )
                    conv = result.scalar_one_or_none()
                    if conv:
                        conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await save_db.commit()
                except Exception:
                    await save_db.rollback()
                    logger.error("Failed to finalize stream messages to DB", exc_info=True)

            yield "data: [DONE]\n\n"
        except Exception as e:
            import json as json_lib
            error_msg = str(e)
            escaped_error = json_lib.dumps(error_msg)[1:-1]
            logger.error(f"Stream error: {error_msg}")
            # Best-effort save of partial content
            try:
                async with AsyncSessionLocal() as err_db:
                    res = await err_db.execute(select(MessageModel).where(MessageModel.id == assistant_msg_id))
                    msg = res.scalar_one_or_none()
                    if msg:
                        msg.content = full_response
                    result = await err_db.execute(
                        select(ConversationModel).where(ConversationModel.id == conversation_id)
                    )
                    conv = result.scalar_one_or_none()
                    if conv:
                        conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await err_db.commit()
            except Exception:
                logger.warning("Failed to persist partial content on error", exc_info=True)
            yield f'data: {{"error": "{escaped_error}"}}\n\n'
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    updates: dict,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Update conversation properties (title, pinned, archived, etc)."""
    result = await db.execute(
        select(ConversationModel).where(ConversationModel.id == conversation_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await require_workspace_access(current_user.id, row.workspace_id)

    # Update allowed fields
    if 'title' in updates:
        row.title = updates['title']
    if 'pinned' in updates:
        row.pinned = updates['pinned']
    if 'archived' in updates:
        row.archived = updates['archived']
    
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    return {"status": "updated"}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete a conversation and its messages."""
    result = await db.execute(
        select(ConversationModel).where(ConversationModel.id == conversation_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await require_workspace_access(current_user.id, row.workspace_id)

    await db.execute(
        delete(MessageModel).where(MessageModel.conversation_id == conversation_id)
    )
    await db.delete(row)
    return {"status": "deleted"}


@router.get("/conversations/{conversation_id}/export")
async def export_conversation(
    conversation_id: str,
    format: str = Query(default="txt", pattern="^(txt|json|md)$"),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """
    Export a conversation in the specified format.
    
    Supports: txt, json, md
    
    Logs export event for audit trail.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Get conversation
    result = await db.execute(
        select(ConversationModel).where(ConversationModel.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Verify access
    await require_workspace_access(current_user.id, conv.workspace_id)
    
    # Get all messages
    msg_result = await db.execute(
        select(MessageModel)
        .where(MessageModel.conversation_id == conversation_id)
        .order_by(MessageModel.created_at)
    )
    messages = msg_result.scalars().all()
    
    # Log export event for audit trail
    logger.info(
        f"📥 EXPORT: user={current_user.id}, conversation={conversation_id}, "
        f"format={format}, messages={len(messages)}, workspace={conv.workspace_id}"
    )
    
    # Generate export content based on format
    timestamp = datetime.now(timezone.utc).isoformat()
    title = conv.title or "Untitled Conversation"
    
    if format == "txt":
        content = f"Conversation: {title}\n"
        content += f"ID: {conversation_id}\n"
        content += f"Exported: {timestamp}\n"
        content += f"User: {current_user.id}\n"
        content += f"Workspace: {conv.workspace_id}\n"
        content += f"Messages: {len(messages)}\n"
        content += f"\n{'=' * 80}\n\n"
        
        for msg in messages:
            role = msg.role.upper()
            if msg.role == "assistant" and msg.agent:
                role = f"ASSISTANT ({msg.agent})"
            
            content += f"[{role}]\n"
            content += f"Timestamp: {msg.created_at.isoformat()}\n"
            content += f"{msg.content}\n"
            content += f"\n{'-' * 80}\n\n"
        
        return StreamingResponse(
            iter([content]),
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="conversation-{conversation_id}.txt"'
            }
        )
    
    elif format == "json":
        data = {
            "conversation": {
                "id": conversation_id,
                "title": title,
                "workspace_id": conv.workspace_id,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
            },
            "export": {
                "timestamp": timestamp,
                "user_id": current_user.id,
                "format": "json",
            },
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "agent": msg.agent,
                    "created_at": msg.created_at.isoformat(),
                }
                for msg in messages
            ]
        }
        
        import json as json_lib
        content = json_lib.dumps(data, indent=2)
        
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="conversation-{conversation_id}.json"'
            }
        )
    
    elif format == "md":
        content = f"# {title}\n\n"
        content += f"**Conversation ID:** `{conversation_id}`  \n"
        content += f"**Exported:** {timestamp}  \n"
        content += f"**User:** {current_user.id}  \n"
        content += f"**Workspace:** {conv.workspace_id}  \n"
        content += f"**Messages:** {len(messages)}  \n"
        content += f"\n---\n\n"
        
        for msg in messages:
            if msg.role == "user":
                content += f"## 👤 User\n\n"
            else:
                agent_info = f" ({msg.agent})" if msg.agent else ""
                content += f"## 🤖 Assistant{agent_info}\n\n"
            
            content += f"*{msg.created_at.isoformat()}*\n\n"
            content += f"{msg.content}\n\n"
            content += "---\n\n"
        
        return StreamingResponse(
            iter([content]),
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="conversation-{conversation_id}.md"'
            }
        )
    
    raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


@router.get("/ollama/status")
async def get_ollama_status(
    endpoint: str = "http://localhost:11434",
    current_user: User = Depends(get_current_user_required),
) -> dict:
    """Check Ollama status and list available models."""
    return await check_ollama_status(endpoint)
