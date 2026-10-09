from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

import numpy as np
from naas_abi.agents.conversation_title import conversation_title_from_prompt
from naas_abi.agents.feature.context import render_feature_context_block
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthPersistencePort
from naas_abi.apps.nexus.apps.api.app.services.chat.chat__schema import (
    CompleteChatInput,
    CompleteChatResult,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_embeddings import (
    DEFAULT_EMBEDDING_DIMENSION,
    DEFAULT_EMBEDDING_MODEL,
    build_chat_collection_name,
    embed_text,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.port import (
    ChatAgentRecord,
    ChatConversationRecord,
    ChatInferenceServerRecord,
    ChatMessageRecord,
    ChatPersistencePort,
    ChatSecretRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authorization import (
    ensure_scope,
    ensure_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext
from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMService
from naas_abi.apps.nexus.apps.api.app.services.ollama import (
    DEFAULT_CHAT_MODEL_TAG,
    FALLBACK_CHAT_MODEL_TAGS,
    resolve_endpoint,
)
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import Message as ProviderMessage
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    ProviderConfig,
    check_ollama_status,
)
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    complete_chat as complete_with_provider,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets_crypto import decrypt_secret_value
from naas_abi.apps.nexus.apps.api.app.services.skills.service import (
    RESERVED_SLUGS,
    SkillService,
)
from naas_abi.skills.catalog import CatalogEntry, render_catalog


@dataclass
class ResolvedProvider:
    id: str
    name: str
    type: str
    enabled: bool
    endpoint: str | None
    api_key: str | None
    account_id: str | None
    model: str
    llm_model: str | None = None


def _catalog_already_disclosed(prior_messages: list) -> bool:
    """True once this thread has already received an assistant reply."""
    return any(getattr(message, "role", None) == "assistant" for message in prior_messages)


# Metadata keys tracking "refresh" (regenerate) lineage on messages.
# Nothing is ever deleted: the replayed prompt and the superseded answer stay in
# the database — and therefore in exports and analytics — they are only left out
# of the live thread and of the context handed to the model on later turns.
REGENERATE_OF_KEY = "regenerate_of"
SUPERSEDED_BY_KEY = "superseded_by"
REGENERATE_REPLAY_KEY = "regenerate_replay"

# Prepended to the replayed prompt on the way to the provider — never stored.
# Dropping the previous answer from the transcript is not enough: agents run with
# their own thread memory (the in-process ABI agent only ever receives the latest
# user message), so an identical question gets answered from that memory without
# re-running any tool. This says the point of the turn out loud.
REGENERATION_DIRECTIVE = (
    "[REFRESH REQUESTED] The user asked you to run this exact request again. "
    "Any answer you previously gave for it is stale and must be ignored: call the "
    "tools again, read the current data, and build your answer from those fresh "
    "results. Never repeat or summarise a previous answer from memory, even if "
    "the question is identical to one you have already handled.\n\n"
)

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

You see everything. You know everything. You are the brain of NEXUS."""
    + _FORMATTING_RULES,
    "aia": """You are AIA (AI Assistant), the user's personal digital twin on the NEXUS platform.

You represent and assist the user in all their interactions. You:
- Learn from the user's preferences, habits, and communication style
- Act on behalf of the user when delegated tasks
- Maintain continuity across conversations and sessions
- Provide personalized recommendations based on user context

Be helpful, concise, and adapt to the user's style. You are their trusted companion."""
    + _FORMATTING_RULES,
    "bob": """You are BOB, a business-focused AI assistant. You help with business analysis, strategy, and operations.
Answer questions directly and provide practical recommendations when asked."""
    + _FORMATTING_RULES,
    "system": """You are a helpful system assistant. You answer technical questions and help with platform operations.
Be precise and helpful."""
    + _FORMATTING_RULES,
}

_MULTI_AGENT_NOTICE = (
    "\n\n🔄 CRITICAL MULTI-AGENT NOTICE: You are in a conversation where MULTIPLE different AI models "
    "have responded. You are currently responding as the SELECTED agent. Previous assistant responses "
    "may be from DIFFERENT AI agents (Grok, Claude, Qwen, etc.). DO NOT claim authorship of other "
    "agents' responses. DO NOT apologize for what other AIs said. DO NOT correct other AIs' identities. "
    "When asked 'who are you?', ONLY identify yourself based on YOUR model, not what previous agents "
    "said. Each assistant message may be from a different AI - treat them as separate participants."
)

logger = logging.getLogger(__name__)

# Skills are written and saved by the Skills office agent (naas_abi
# SkillsAgent), which calls create_skill. Nothing here asks a model to draft
# one into the conversation: a JSON block the user has to save by hand was
# both a worse experience and a dead end for clients with no Nexus UI.
_SKILLS_HANDOFF_NOTE = (
    "\n\n## Creating skills\n"
    "Creating, editing and deleting skills is the Skills agent's job: it writes the prompt "
    "and saves the skill itself. When the user asks for a new skill (or starts a message with "
    "`/create-skill`), hand the request to the Skills agent when you can transfer, otherwise "
    "tell them to ask Skills in the chat or to use Settings > Skills. Never draft a skill as a "
    "fenced `skill` block or any other payload for the user to save by hand.\n"
)

_SKILLS_CATALOG_HEADER = (
    "\n## Available skills\n"
    "Each enabled skill is listed by slug, name, description, and when_to_use. "
    "The skill body is not in this prompt. "
    "Before following a skill, call read_workspace_skill with its slug and follow the prompt it returns. "
    "If the user message starts with /<slug>, that invocation already includes the body, "
    "except when /sheets, /slides, or /documents handed the turn to the office agent. "
    "Follow an included body, and treat any args as extra input. "
    "Do not guess the procedure from the description alone. "
    "/sheets, /slides, and /documents hand the turn to the Sheets, Slides, and Documents agents. "
    "Their procedures are not listed in this catalog. "
    "/skills and /create-skill are reserved commands, not skill rows.\n\n"
)


def _coerce_index(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


_ELEMENT_PATH_RE = re.compile(r"^(\d+):([a-z][a-z0-9]*):(\d+)$")
_ELEMENT_TEXT_MAX = 120


def _resolved_slide_cursor(slides: dict) -> tuple[int | None, int | None]:
    """``(slide_count, selected_index)`` after dropping empty or out-of-range values."""
    count = _coerce_index(slides.get("slide_count"))
    index = _coerce_index(slides.get("selected_index"))
    if count is not None and count <= 0:
        count = None
    if index is not None and (index < 0 or (count is not None and index >= count)):
        index = None
    return count, index


def _selected_slide_lines(slides: dict) -> list[str]:
    """Selected slide from the editor, in tool index space (0-based).

    ``slide_count`` alone is still useful; ``selected_index`` without a count
    is emitted as-is. Out-of-range or negative indexes are dropped.
    """
    count, index = _resolved_slide_cursor(slides)
    lines: list[str] = []
    if count is not None:
        lines.append(f"- slide_count: {count}")
    if index is not None:
        human = f"{index + 1} of {count}" if count is not None else str(index + 1)
        lines.append(f"- selected_slide_index: {index} (slide {human} in the editor)")
    return lines


def _selected_element_lines(slides: dict) -> list[str]:
    """Clicked preview node, same ``slideIndex:tag:nth`` as ``data-nexus-edit``."""
    raw_path = slides.get("selected_element_path")
    if not isinstance(raw_path, str):
        return []
    path = raw_path.strip().lower()
    parsed = _ELEMENT_PATH_RE.match(path)
    if not parsed:
        return []
    slide_index = int(parsed.group(1))
    count, selected = _resolved_slide_cursor(slides)
    if count is not None and slide_index >= count:
        return []
    if selected is not None and slide_index != selected:
        return []
    lines = [f"- selected_element_path: {path}"]
    raw_text = slides.get("selected_element_text")
    if isinstance(raw_text, str):
        text = re.sub(r"\s+", " ", raw_text).strip()[:_ELEMENT_TEXT_MAX]
        if text:
            lines.append(f"- selected_element_text: {text}")
    return lines


def _untitled_slides_rename_hint(title: str, slug: str) -> str:
    try:
        from naas_abi.agents.slides.title import is_placeholder_deck_title
    except Exception:
        return ""
    if not is_placeholder_deck_title(title or slug):
        return ""
    return (
        "If the open deck is still Untitled, call rename_deck first with a "
        "short topic title, then write.\n"
    )


def _untitled_documents_rename_hint(title: str, slug: str) -> str:
    try:
        from naas_abi.agents.documents.title import is_placeholder_document_title
    except Exception:
        return ""
    if not is_placeholder_document_title(title or slug):
        return ""
    return (
        "If the open document is still Untitled, call rename_document first "
        "with a short topic title, then fill the open template. "
        "Do not leave seed placeholder copy. Do not append after the footer.\n"
    )


def _render_slides_context_block(
    client_context: dict | None,
    workspace_id: str | None = None,
) -> str:
    """Inject open Slides deck so Abi researches, then edits that file."""
    if not isinstance(client_context, dict):
        return ""
    slides = client_context.get("slides")
    if not isinstance(slides, dict):
        return ""
    slug = str(slides.get("slug") or "").strip()
    if not slug:
        return ""
    ws = str(slides.get("workspace_id") or workspace_id or "").strip()
    default_path = f"slides/{ws}/{slug}/deck.html" if ws else f"slides/{slug}/deck.html"
    default_branch = f"slides/{ws}/{slug}" if ws else f"slides/{slug}"
    path = str(slides.get("path") or default_path).strip()
    branch = str(slides.get("branch") or default_branch).strip()
    title = str(slides.get("title") or "").strip()
    mode = str(slides.get("mode") or "").strip()
    today = datetime.now().date().isoformat()
    year = today[:4]
    lines = [
        f"- slug: {slug}",
        f"- path: {path}",
        f"- branch: {branch}",
        f"- today: {today}",
    ]
    if ws:
        lines.append(f"- workspace_id: {ws}")
    if title:
        lines.append(f"- title: {title}")
    if mode:
        lines.append(f"- editor_mode: {mode}")
    lines.extend(_selected_slide_lines(slides))
    lines.extend(_selected_element_lines(slides))
    return (
        "\n\n## Open Slides presentation\n"
        "The user is editing this presentation in the Slides overlay right now. "
        "If you do not have replace_in_slides_deck, write_slides_section, "
        "write_slides_sections, or write_slides_deck, call transfer_to_Slides "
        "immediately and stop. Do not "
        "web_search, read the deck, or write files yourself.\n"
        "You are operating on its Coder workspace files (sidecar) when available; "
        "Forgejo remains the Save/history snapshot. Preview loads from sidecar when "
        "ready. Do not ask which deck, slug, file, or template. "
        "Omit slug on Slides tool calls; tools default to this open deck.\n"
        "selected_slide_index below is the slide the user has selected in the "
        "editor, 0-based, same index space as section_index / index / "
        "after_index on the Slides tools. When the user says this slide, here, "
        "the current slide, or gives no slide, target that index. Do not ask "
        "which slide.\n"
        "selected_element_path, when present, is the element the user clicked "
        "in Preview. It matches data-nexus-edit and looks like "
        "slideIndex:tag:nth. selected_element_text is a short snippet of that "
        "element. When the user says this, this heading, this text, or make "
        "this bigger, call replace_in_slides_deck with element_path set to "
        "selected_element_path. Do not ask which element.\n"
        "Plan, then write. For news, current events, "
        '"what is going on", country or company briefings, or any factual deck:\n'
        f"1. Call web_search 2 to 4 times first (latest developments, context, "
        f"key actors, dates). Include {year}. Stop after 4 searches. "
        "One successful search this turn unlocks every write; do not search again "
        "before each slide.\n"
        "2. Call list_slides_sections once. Do not read every section. "
        "Do not re-read a slide you just wrote.\n"
        "3. Write the whole deck in one write_slides_sections or write_slides_deck. "
        "Do not write one section per tool call when the brief is a full-deck rewrite. "
        "Seed decks can be 8 to 32 slides.\n"
        "4. After that write, report what changed. Do not list or read the "
        "whole deck again. No lorem. No Context / Approach / Plan filler when "
        "the user asked for a situation brief.\n"
        + _untitled_slides_rename_hint(title, slug)
        + "Keep the seed template CSS and structure. Cite sources in footer or "
        "source lines if the layout allows. "
        "A tiny copy edit (title typo, color tweak) may skip search. "
        "Edit HTML sections only. Preview is the HTML stage. PPTX export "
        "reconstructs the live .slide DOM at 1280x720; do not edit buildPptx or "
        "FOOTER_TXT. For a small copy edit after research (or a title-only tweak), "
        "call replace_in_slides_deck with section_index=0 and "
        "occurrence=0 (matches &amp; on cover h1; do not use occurrence=1 "
        "for the title).\n" + "\n".join(lines) + "\n"
    )


def _selected_document_lines(documents_ctx: dict) -> list[str]:
    count_raw = documents_ctx.get("section_count")
    index_raw = documents_ctx.get("selected_index")
    count: int | None = None
    index: int | None = None
    try:
        if count_raw is not None:
            count = int(count_raw)
    except (TypeError, ValueError):
        count = None
    try:
        if index_raw is not None:
            index = int(index_raw)
    except (TypeError, ValueError):
        index = None
    lines: list[str] = []
    if count is not None:
        lines.append(f"- section_count: {count}")
    if index is not None:
        human = f"{index + 1} of {count}" if count is not None else str(index + 1)
        lines.append(f"- selected_section_index: {index} (section {human} in the editor)")
    return lines


def _render_documents_context_block(
    client_context: dict | None,
    workspace_id: str | None = None,
) -> str:
    """Inject open Documents file so the agent researches, then edits that file."""
    if not isinstance(client_context, dict):
        return ""
    documents = client_context.get("documents")
    if not isinstance(documents, dict):
        return ""
    slug = str(documents.get("slug") or "").strip()
    if not slug:
        return ""
    ws = str(documents.get("workspace_id") or workspace_id or "").strip()
    default_path = (
        f"documents/{ws}/{slug}/document.html" if ws else f"documents/{slug}/document.html"
    )
    default_branch = f"documents/{ws}/{slug}" if ws else f"documents/{slug}"
    path = str(documents.get("path") or default_path).strip()
    branch = str(documents.get("branch") or default_branch).strip()
    title = str(documents.get("title") or "").strip()
    mode = str(documents.get("mode") or "").strip()
    today = datetime.now().date().isoformat()
    year = today[:4]
    lines = [
        f"- slug: {slug}",
        f"- path: {path}",
        f"- branch: {branch}",
        f"- today: {today}",
    ]
    if ws:
        lines.append(f"- workspace_id: {ws}")
    if title:
        lines.append(f"- title: {title}")
    if mode:
        lines.append(f"- editor_mode: {mode}")
    lines.extend(_selected_document_lines(documents))
    return (
        "\n\n## Open Documents file\n"
        "The user is editing this document in the Documents overlay right now. "
        "If you do not have apply_document_commands, insert_heading, "
        "insert_paragraph, replace_in_document, or write_document, call "
        "transfer_to_Documents immediately and stop.\n"
        "You are operating on its Coder workspace files (sidecar) when available; "
        "Forgejo remains the Save/history snapshot. Do not ask which document, slug, "
        "file, or template. Omit slug on Documents tool calls; tools default to this "
        "open file.\n"
        "selected_section_index below is the heading the user has selected in the "
        "editor, 0-based, same index space as after_heading on the Documents tools.\n"
        "Plan, then write. For news, current events, or factual briefs:\n"
        f"1. Call web_search once first (at most 4). Include {year}. Then write.\n"
        "2. Do not list leftover sections. Do not read or write leftover <section> blocks.\n"
        "3. Fill the open template with one fill_document_slots call "
        "(title, subtitle, intro, note, quote, sections, tables). "
        "Do not call apply_document_commands on a fill turn. "
        "Do not leave seed placeholder copy. Do not append after the footer. "
        "Do not write the memo only in chat. "
        "Do not call read_document after writing. "
        "replace_in_document is not bound. Writes go into .doc-body.\n"
        "4. After that one write, stop and reply. leftover empty is done. "
        "leftover_placeholders wait for a later turn. "
        "Do not call fill_document_slots again. Do not reread.\n"
        + _untitled_documents_rename_hint(title, slug)
        + "\n".join(lines)
        + "\n"
    )


def _render_sheets_context_block(
    client_context: dict | None,
    workspace_id: str | None = None,
) -> str:
    if not isinstance(client_context, dict):
        return ""
    sheets = client_context.get("sheets")
    if not isinstance(sheets, dict):
        return ""
    slug = str(sheets.get("slug") or "").strip()
    if not slug:
        return ""
    ws = str(sheets.get("workspace_id") or workspace_id or "").strip()
    default_path = (
        f"sheets/{ws}/{slug}/workbook.html" if ws else f"sheets/{slug}/workbook.html"
    )
    default_branch = f"sheets/{ws}/{slug}" if ws else f"sheets/{slug}"
    path = str(sheets.get("path") or default_path).strip()
    branch = str(sheets.get("branch") or default_branch).strip()
    title = str(sheets.get("title") or "").strip()
    lines = [
        f"- slug: {slug}",
        f"- path: {path}",
        f"- branch: {branch}",
    ]
    if ws:
        lines.append(f"- workspace_id: {ws}")
    if title:
        lines.append(f"- title: {title}")
    return (
        "\n\n## Open Sheets workbook\n"
        "The user is editing this spreadsheet in Nexus Sheets. "
        "If you lack write_sheets_workbook, call transfer_to_Sheets and stop.\n"
        "Edit the JSON model via Sheets tools; omit slug (defaults to this workbook).\n"
        + "\n".join(lines)
        + "\n"
    )


def _render_coding_context_block(client_context: dict | None) -> str:
    """Inject open Code repo/branch so Abi edits the sandbox checkout."""
    if not isinstance(client_context, dict):
        return ""
    coding = client_context.get("coding")
    if not isinstance(coding, dict):
        return ""
    repo_id = str(coding.get("repo_id") or "").strip()
    if not repo_id:
        return ""
    branch = str(coding.get("branch") or "main").strip()
    path = str(coding.get("path") or ".").strip()
    lines = [
        f"- repo_id: {repo_id}",
        f"- branch: {branch}",
        f"- cwd: {path}",
    ]
    return (
        "\n\n## Open Code repository\n"
        "The user is browsing this repository in the Code overlay. You are operating "
        "on the live sandbox checkout via coding tools when the sidecar runtime is "
        "ready. Do not ask which repository or branch. Prefer read_coding_file, "
        "write_coding_file, list_coding_dir, and run_in_coding_sandbox for direct "
        "edits. For larger multi-file refactors, use run_coding_harness_task to "
        "delegate to the managed OpenCode harness in the same checkout.\n" + "\n".join(lines) + "\n"
    )


class UserProfile(Protocol):
    """The fields the profile block reads, on whatever record carries them.

    Two callers hold a different record for the same person: this service has
    the auth adapter's ``AuthUserRecord``, and the OpenAI-compatible gateway
    has the API ``User`` schema its auth dependency already resolved. Naming
    the fields instead of one of the two classes is what lets both render the
    same block, rather than one of them growing a second copy of the wording
    that then drifts from this one.
    """

    id: str
    name: str
    email: str
    company: str | None
    role: str | None
    bio: str | None


def render_user_context_block(
    user: UserProfile,
    workspace_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    fields: list[tuple[str, str | None]] = [
        ("Name", user.name),
        ("Email", user.email),
        ("Company", user.company),
        ("Role", user.role),
        ("Bio", user.bio),
    ]
    lines = [f"- {label}: {value}" for label, value in fields if value]
    if not lines:
        return ""
    technical_fields: list[tuple[str, str | None]] = [
        ("user_id", user.id),
        ("workspace_id", workspace_id),
        ("conversation_id", conversation_id),
    ]
    technical_lines = [f"- {label}: {value}" for label, value in technical_fields if value]
    technical_block = (
        ("\n\nTechnical context:\n" + "\n".join(technical_lines)) if technical_lines else ""
    )
    return (
        "\n\nYou are speaking with the following user. Use this profile to "
        "personalize your responses naturally; do not repeat it back verbatim "
        "unless asked.\n" + "\n".join(lines) + technical_block
    )


class ChatService:
    def __init__(
        self,
        adapter: ChatPersistencePort,
        iam_service: IAMService | None = None,
        auth_adapter: AuthPersistencePort | None = None,
        skills_service: SkillService | None = None,
    ):
        self.adapter = adapter
        self.iam_service = iam_service
        self.auth_adapter = auth_adapter
        self.skills_service = skills_service

    async def build_system_prompt(
        self,
        agent: str,
        explicit_system_prompt: str | None,
        prior_messages: list,
        user_id: str | None,
        workspace_id: str | None = None,
        conversation_id: str | None = None,
        context: RequestContext | None = None,
        client_context: dict | None = None,
        include_skills: bool = True,
    ) -> str:
        system_prompt = explicit_system_prompt or AGENT_SYSTEM_PROMPTS.get(
            agent, AGENT_SYSTEM_PROMPTS["aia"]
        )
        if include_skills:
            # Cloud requests are stateless: prior assistant replies do not
            # preserve the system prompt sent on the first turn.
            system_prompt += await self._build_skills_block(
                context, workspace_id
            )
        slides_block = _render_slides_context_block(client_context, workspace_id)
        if slides_block:
            system_prompt += slides_block
        documents_block = _render_documents_context_block(client_context, workspace_id)
        if documents_block:
            system_prompt += documents_block
        sheets_block = _render_sheets_context_block(client_context, workspace_id)
        if sheets_block:
            system_prompt += sheets_block
        coding_block = _render_coding_context_block(client_context)
        if coding_block:
            system_prompt += coding_block
        feature_block = render_feature_context_block(client_context)
        if feature_block:
            system_prompt += feature_block

        has_prior_assistant = any(getattr(m, "role", None) == "assistant" for m in prior_messages)
        if has_prior_assistant:
            system_prompt += _MULTI_AGENT_NOTICE
            return system_prompt

        addendum = await self.build_user_context_addendum(
            prior_messages, user_id, workspace_id, conversation_id
        )
        return system_prompt + addendum

    async def build_abi_injection_preamble(
        self,
        prior_messages: list,
        user_id: str | None,
        workspace_id: str | None = None,
        conversation_id: str | None = None,
        context: RequestContext | None = None,
        client_context: dict | None = None,
        include_skills: bool = True,
    ) -> str | None:
        """Context prepended to the user message for in-process ABI agents.

        ABI agents keep their own system prompt and ignore the Nexus
        ``system_prompt`` passed to cloud providers, so the skills catalog and
        first-turn user profile must be injected via the user message instead.
        Cloud turns pass include_skills=False here: they already carry the
        catalog on the system prompt, and this preamble is not sent.
        """
        parts: list[str] = []
        if include_skills:
            skills_block = await self._build_skills_block(
                context, workspace_id, prior_messages
            )
            if skills_block.strip():
                parts.append(skills_block.strip())

        slides_block = _render_slides_context_block(client_context, workspace_id)
        if slides_block.strip():
            parts.append(slides_block.strip())

        documents_block = _render_documents_context_block(client_context, workspace_id)
        if documents_block.strip():
            parts.append(documents_block.strip())
        sheets_block = _render_sheets_context_block(client_context, workspace_id)
        if sheets_block.strip():
            parts.append(sheets_block.strip())

        coding_block = _render_coding_context_block(client_context)
        if coding_block.strip():
            parts.append(coding_block.strip())

        feature_block = render_feature_context_block(client_context)
        if feature_block.strip():
            parts.append(feature_block.strip())

        has_prior_assistant = any(getattr(m, "role", None) == "assistant" for m in prior_messages)
        if has_prior_assistant:
            parts.append(_MULTI_AGENT_NOTICE.strip())
        else:
            addendum = await self.build_user_context_addendum(
                prior_messages,
                user_id,
                workspace_id,
                conversation_id,
            )
            if addendum.strip():
                parts.append(addendum.strip())

        return "\n\n".join(parts) if parts else None

    async def _build_skills_block(
        self,
        context: RequestContext | None,
        workspace_id: str | None,
        prior_messages: list | None = None,
    ) -> str:
        """Catalog of enabled skills: slug, name, description, and when_to_use.

        The body is not included. The model loads it with read_workspace_skill,
        or receives it when a /slug message is expanded before the agent runs.
        /sheets, /slides, and /documents are not expanded when that office agent
        is on the workspace roster: the turn is handed to that agent instead.
        The catalog is sent once per thread: a later turn that already has an
        assistant message does not get it again.
        """
        block = _SKILLS_HANDOFF_NOTE
        if _catalog_already_disclosed(prior_messages or []):
            return block
        if not self.skills_service or not context or not workspace_id:
            return block
        try:
            skills = await self.skills_service.list_visible_skills(context, workspace_id)
        except Exception:
            logger.warning("Failed to load skills catalog for system prompt", exc_info=True)
            return block
        enabled = [s for s in skills if s.enabled]
        if not enabled:
            return block
        entries = [
            CatalogEntry(
                slug=s.slug,
                name=s.name,
                description=(getattr(s, "description", None) or ""),
                when_to_use=(getattr(s, "when_to_use", None) or ""),
            )
            for s in enabled
        ]
        catalog = render_catalog(entries, header=_SKILLS_CATALOG_HEADER)
        return block + catalog

    async def _enabled_skill_by_slug(
        self,
        context: RequestContext | None,
        workspace_id: str | None,
        slug: str,
    ):
        """Enabled visible skill for a slug, or None. Reserved slugs stay None."""
        needle = (slug or "").strip().lstrip("/").lower()
        if not needle or needle in RESERVED_SLUGS:
            return None
        if not self.skills_service or not context or not workspace_id:
            return None
        try:
            skills = await self.skills_service.list_visible_skills(context, workspace_id)
        except Exception:
            logger.warning("Failed to resolve skill %s", needle, exc_info=True)
            return None
        for skill in skills:
            if skill.enabled and str(skill.slug).lower() == needle:
                if getattr(skill, "source", "user") == "module":
                    loaded = await self.skills_service.get_skill(context, skill.id)
                    return replace(loaded, slug=skill.slug) if loaded else None
                return skill
        return None

    async def read_enabled_skill_body(
        self,
        context: RequestContext | None,
        workspace_id: str | None,
        slug: str,
    ) -> str | None:
        """Full prompt for one enabled skill. None when the slug is unknown or reserved."""
        skill = await self._enabled_skill_by_slug(context, workspace_id, slug)
        if skill is None:
            return None
        return skill.prompt or ""

    def _slash_on_first_line(self, content: str) -> tuple[str, str, str] | None:
        from naas_abi.apps.nexus.apps.api.app.services.chat.office_handoff import (
            slash_on_first_line,
        )

        return slash_on_first_line(content)

    async def expand_invoked_skill_messages(
        self,
        messages: list,
        context: RequestContext | None,
        workspace_id: str | None,
        suppress_slugs: set[str] | frozenset[str] | None = None,
    ) -> list:
        """If the latest user message is /slug plus optional args, prepend that skill's prompt.

        Unknown slugs and the reserved commands /skills and /create-skill are left unchanged.
        Slugs in ``suppress_slugs`` stay as the user typed them. Office handoff uses that
        so /sheets, /slides, and /documents do not paste a procedure into the turn.
        The stored chat row stays the slash text; only the message sent to the model changes.
        """
        if not messages:
            return messages
        index = next(
            (i for i in range(len(messages) - 1, -1, -1) if getattr(messages[i], "role", None) == "user"),
            None,
        )
        if index is None:
            return messages
        content = messages[index].content or ""
        parsed = self._slash_on_first_line(content)
        if parsed is None:
            return messages
        slug, args, tail = parsed
        if slug in RESERVED_SLUGS or slug in (suppress_slugs or ()):
            return messages
        skill = await self._enabled_skill_by_slug(context, workspace_id, slug)
        if skill is None:
            return messages
        first_line = content.partition("\n")[0].strip()
        parts = [
            f"Invoked skill /{skill.slug} ({skill.name}). Follow this skill body.",
            "",
            skill.prompt or "",
        ]
        if args:
            parts.extend(["", f"Arguments: {args}"])
        parts.extend(["", f"User message: {first_line}"])
        expanded = "\n".join(parts) + tail
        updated = list(messages)
        message = messages[index]
        if hasattr(message, "model_copy"):
            updated[index] = message.model_copy(update={"content": expanded})
        else:
            updated[index] = replace(message, content=expanded)
        return updated

    async def build_user_context_addendum(
        self,
        prior_messages: list,
        user_id: str | None,
        workspace_id: str | None = None,
        conversation_id: str | None = None,
    ) -> str:
        """Return the user-profile addendum to inject on the first conversation turn.

        Returns empty string when:
        - a prior assistant message exists (not the first turn),
        - no auth adapter is wired,
        - no user_id is provided,
        - the lookup fails or returns no user.
        """
        has_prior_assistant = any(getattr(m, "role", None) == "assistant" for m in prior_messages)
        if has_prior_assistant:
            return ""
        if self.auth_adapter is None or not user_id:
            return ""
        try:
            user = await self.auth_adapter.get_user_by_id(user_id)
        except Exception:
            return ""
        if user is None:
            return ""
        return render_user_context_block(user, workspace_id, conversation_id)

    def _inject_chat_vector_context(
        self,
        provider_messages: list[ProviderMessage],
        conversation_id: str | None,
        user_id: str,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        embedding_dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        top_k: int = 5,
    ) -> tuple[list[ProviderMessage], list[str]]:
        _empty: tuple[list[ProviderMessage], list[str]] = (provider_messages, [])

        if not conversation_id:
            return _empty

        latest_user_index = -1
        latest_user_content = ""
        for index in range(len(provider_messages) - 1, -1, -1):
            if provider_messages[index].role == "user":
                latest_user_index = index
                latest_user_content = provider_messages[index].content
                break

        if latest_user_index < 0 or not latest_user_content.strip():
            return _empty

        try:
            from naas_abi import ABIModule

            vector_store = ABIModule.get_instance().engine.services.vector_store
        except Exception:
            return _empty

        collection_name = build_chat_collection_name(conversation_id)
        try:
            if collection_name not in vector_store.list_collections():
                return _empty
        except Exception:
            return _empty

        try:
            query_vector = embed_text(
                latest_user_content,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension,
            )
            matches = vector_store.search_similar(
                collection_name=collection_name,
                query_vector=np.array(query_vector, dtype=float),
                k=top_k,
                include_vectors=False,
                include_metadata=True,
            )
        except Exception:
            return _empty

        context_chunks: list[str] = []
        seen_filenames: list[str] = []
        for match in matches:
            metadata = match.metadata or {}
            if metadata.get("user_id") != user_id:
                continue

            chunk_text = ""
            payload = match.payload
            if isinstance(payload, dict) and isinstance(payload.get("text"), str):
                chunk_text = payload["text"]
            elif isinstance(metadata.get("chunk_text"), str):
                chunk_text = metadata["chunk_text"]

            if not chunk_text.strip():
                continue

            filename = str(metadata.get("filename") or "document")
            context_chunks.append(f"[{filename}] {chunk_text.strip()}")
            if filename not in seen_filenames:
                seen_filenames.append(filename)

        if not context_chunks:
            return _empty

        context_block = "\n\n".join(context_chunks)
        augmented = list(provider_messages)
        augmented[latest_user_index] = ProviderMessage(
            role="user",
            content=(
                f"{latest_user_content}\n\n"
                "---\n"
                "DOCUMENT CONTEXT (retrieved from chat file index):\n"
                f"{context_block}"
            ),
            images=augmented[latest_user_index].images,
        )
        return augmented, seen_filenames

    async def list_conversations(
        self,
        context: RequestContext,
        workspace_id: str,
        limit: int,
        offset: int,
    ) -> list[ChatConversationRecord]:
        await self._ensure_workspace_access(context=context, workspace_id=workspace_id)
        return await self.adapter.list_conversations_by_workspace(
            workspace_id=workspace_id,
            user_id=context.actor_user_id,
            limit=limit,
            offset=offset,
        )

    async def create_conversation(
        self,
        context: RequestContext,
        workspace_id: str,
        title: str,
        agent: str,
        now: datetime,
        conversation_id: str | None = None,
    ) -> ChatConversationRecord:
        await self._ensure_workspace_access(context=context, workspace_id=workspace_id)
        conv_id = conversation_id or f"conv-{uuid4().hex[:12]}"
        return await self.adapter.create_conversation(
            conversation_id=conv_id,
            workspace_id=workspace_id,
            user_id=context.actor_user_id,
            title=title,
            agent=agent,
            now=now,
        )

    async def get_conversation(
        self,
        context: RequestContext,
        conversation_id: str,
    ) -> ChatConversationRecord | None:
        self._ensure_scope(
            context=context,
            required_scope="chat.conversation.read",
            denied_message="Conversation access denied",
        )
        return await self.adapter.get_conversation_by_id_for_user(
            conversation_id,
            context.actor_user_id,
        )

    async def get_conversation_for_user(
        self,
        context: RequestContext,
        conversation_id: str,
    ) -> ChatConversationRecord | None:
        self._ensure_scope(
            context=context,
            required_scope="chat.conversation.read",
            denied_message="Conversation access denied",
        )
        return await self.adapter.get_conversation_by_id_for_user(
            conversation_id,
            context.actor_user_id,
        )

    def _ensure_scope(
        self,
        context: RequestContext,
        required_scope: str,
        denied_message: str,
    ) -> None:
        ensure_scope(
            context=context,
            required_scope=required_scope,
            denied_message=denied_message,
            iam_service=self.iam_service,
        )

    async def _ensure_conversation_access(
        self,
        context: RequestContext,
        conversation_id: str,
        action: str = "chat.conversation.read",
        required_scope: str | None = None,
    ) -> ChatConversationRecord:
        self._ensure_scope(
            context=context,
            required_scope=required_scope or action,
            denied_message="Conversation access denied",
        )

        conversation = await self.adapter.get_conversation_by_id_for_user(
            conversation_id,
            context.actor_user_id,
        )
        if not conversation:
            raise PermissionError("Conversation not found")
        return conversation

    async def _ensure_workspace_access(
        self,
        context: RequestContext,
        workspace_id: str,
        action: str = "workspace.read",
        required_scope: str | None = None,
    ) -> None:
        await ensure_workspace_access(
            context=context,
            workspace_id=workspace_id,
            denied_message="Workspace access denied",
            required_scope=required_scope or action,
            iam_service=self.iam_service,
            workspace_service=None,
        )

    @staticmethod
    def _unwrap_json_content(raw: str) -> str:
        if not raw or not raw.strip().startswith("{"):
            return raw
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict) and "content" in obj and isinstance(obj["content"], str):
                return obj["content"]
        except (json.JSONDecodeError, TypeError):
            pass
        return raw

    async def list_messages(
        self,
        context: RequestContext,
        conversation_id: str,
    ) -> list[ChatMessageRecord]:
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.message.read",
        )
        return await self.adapter.list_messages_by_conversation(conversation_id)

    async def get_or_create_conversation(
        self,
        context: RequestContext,
        conversation_id: str | None,
        workspace_id: str | None,
        request_message: str,
        agent: str,
        now: datetime,
    ) -> str:
        if conversation_id:
            row = await self.adapter.get_conversation_by_id_for_user(
                conversation_id,
                context.actor_user_id,
            )
            if row:
                if row.agent != agent:
                    await self.adapter.update_conversation_agent(
                        conversation_id=conversation_id,
                        agent=agent,
                        now=now,
                    )
                return row.id

            existing_conversation = await self.adapter.get_conversation_by_id(conversation_id)
            if existing_conversation and existing_conversation.user_id != context.actor_user_id:
                if not workspace_id:
                    raise PermissionError("Conversation not found")

                await self._ensure_workspace_access(
                    context=context,
                    workspace_id=workspace_id,
                    action="chat.conversation.create",
                )

                created = await self.create_conversation(
                    context=context,
                    workspace_id=workspace_id,
                    title=conversation_title_from_prompt(request_message),
                    agent=agent,
                    now=now,
                )
                return created.id

            if not workspace_id:
                raise ValueError("workspace_id is required")

            await self._ensure_workspace_access(
                context=context,
                workspace_id=workspace_id,
                action="chat.conversation.create",
            )

            await self.create_conversation(
                context=context,
                conversation_id=conversation_id,
                workspace_id=workspace_id,
                title=conversation_title_from_prompt(request_message),
                agent=agent,
                now=now,
            )
            return conversation_id

        if not workspace_id:
            raise ValueError("workspace_id is required")

        await self._ensure_workspace_access(
            context=context,
            workspace_id=workspace_id,
            action="chat.conversation.create",
        )

        created = await self.create_conversation(
            context=context,
            workspace_id=workspace_id,
            title=conversation_title_from_prompt(request_message),
            agent=agent,
            now=now,
        )
        return created.id

    @staticmethod
    def _parse_message_metadata(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    async def get_message(
        self,
        context: RequestContext,
        conversation_id: str,
        message_id: str,
    ) -> ChatMessageRecord | None:
        messages = await self.list_messages(context=context, conversation_id=conversation_id)
        return next((m for m in messages if m.id == message_id), None)

    async def update_message_metadata(
        self,
        context: RequestContext,
        conversation_id: str,
        message_id: str,
        metadata: dict,
    ) -> bool:
        """Merge ``metadata`` into whatever the message already carries.

        Merging (rather than replacing) keeps bookkeeping written elsewhere —
        regenerate lineage, reviewer feedback — alive when the frontend PATCHes
        its execution time / steps / sources payload at the end of a stream.
        """
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.message.update",
        )
        existing = await self.get_message(
            context=context,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        merged = {
            **self._parse_message_metadata(existing.metadata_ if existing else None),
            **metadata,
        }
        return await self.adapter.update_message_metadata(
            message_id=message_id,
            metadata=json.dumps(merged),
        )

    async def mark_message_superseded(
        self,
        context: RequestContext,
        conversation_id: str,
        message_id: str,
        superseded_by: str,
    ) -> bool:
        """Flag an assistant message as replaced by a regenerated answer.

        The row is kept as-is; only its metadata gains a pointer to the newer
        message so the UI and the model context can skip it.
        """
        return await self.update_message_metadata(
            context=context,
            conversation_id=conversation_id,
            message_id=message_id,
            metadata={SUPERSEDED_BY_KEY: superseded_by},
        )

    async def create_message(
        self,
        context: RequestContext,
        conversation_id: str,
        role: str,
        content: str,
        created_at: datetime,
        agent: str | None = None,
        message_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.message.create",
        )
        msg_id = message_id or f"msg-{uuid4().hex[:12]}"
        await self.adapter.create_message(
            message_id=msg_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            agent=agent,
            created_at=created_at,
            metadata_=json.dumps(metadata) if metadata else None,
        )
        return msg_id

    async def create_streaming_message_pair(
        self,
        context: RequestContext,
        conversation_id: str,
        user_content: str,
        assistant_agent: str | None,
        created_at: datetime,
        regenerate_of: str | None = None,
    ) -> tuple[str, str]:
        user_metadata: dict | None = None
        assistant_metadata: dict | None = None
        if regenerate_of:
            # The replayed prompt is a duplicate of an earlier one: persisted for
            # the audit trail, hidden from the thread the user and the model see.
            user_metadata = {
                REGENERATE_REPLAY_KEY: True,
                REGENERATE_OF_KEY: regenerate_of,
            }
            assistant_metadata = {REGENERATE_OF_KEY: regenerate_of}

        user_msg_id = await self.create_message(
            context=context,
            conversation_id=conversation_id,
            role="user",
            content=user_content,
            created_at=created_at,
            metadata=user_metadata,
        )
        assistant_msg_id = await self.create_message(
            context=context,
            conversation_id=conversation_id,
            role="assistant",
            content="",
            created_at=created_at,
            agent=assistant_agent,
            metadata=assistant_metadata,
        )
        return user_msg_id, assistant_msg_id

    async def update_message_content(
        self,
        context: RequestContext,
        conversation_id: str,
        message_id: str,
        content: str,
    ) -> bool:
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.message.update",
        )
        return await self.adapter.update_message_content(message_id, content)

    async def finalize_streaming_response(
        self,
        context: RequestContext,
        conversation_id: str,
        assistant_message_id: str,
        content: str,
        now: datetime,
    ) -> None:
        await self.update_message_content(
            context=context,
            conversation_id=conversation_id,
            message_id=assistant_message_id,
            content=content,
        )
        await self.touch_conversation(context, conversation_id, now)

    async def touch_conversation(
        self,
        context: RequestContext,
        conversation_id: str,
        now: datetime,
    ) -> None:
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.conversation.update",
        )
        await self.adapter.touch_conversation(conversation_id, now)

    async def complete_chat_request(
        self,
        context: RequestContext,
        request: CompleteChatInput,
        now: datetime,
    ) -> CompleteChatResult:
        conversation_id = await self.get_or_create_conversation(
            context=context,
            conversation_id=request.conversation_id,
            workspace_id=request.workspace_id,
            request_message=request.message,
            agent=request.agent,
            now=now,
        )

        await self.create_message(
            context=context,
            conversation_id=conversation_id,
            role="user",
            content=request.message,
            created_at=now,
            metadata=(
                {
                    REGENERATE_REPLAY_KEY: True,
                    REGENERATE_OF_KEY: request.regenerate_of,
                }
                if request.regenerate_of
                else None
            ),
        )

        has_images = bool(request.images) or any(m.images for m in request.messages if m.images)
        provider = await self.resolve_provider(
            context=context,
            provider=request.provider,
            has_images=has_images,
            agent_id=request.agent,
            workspace_id=request.workspace_id,
        )

        provider_used: str | None = None
        context_sources: list[str] = []
        if provider:
            try:
                provider_messages = await self.build_provider_messages_with_agents(
                    request=request,
                    context=context,
                    current_agent_id=request.agent,
                    conversation_id=conversation_id,
                )
                provider_messages, context_sources = self._inject_chat_vector_context(
                    provider_messages=provider_messages,
                    conversation_id=conversation_id,
                    user_id=context.actor_user_id,
                )
                provider_messages = await self.expand_invoked_skill_messages(
                    provider_messages,
                    context,
                    request.workspace_id,
                )
                prior_messages = list(request.messages or [])
                abi_turn = provider.type == "abi"
                system_prompt = await self.build_system_prompt(
                    agent=request.agent,
                    explicit_system_prompt=request.system_prompt,
                    prior_messages=prior_messages,
                    user_id=context.actor_user_id,
                    workspace_id=request.workspace_id,
                    conversation_id=conversation_id,
                    context=context,
                    client_context=request.context,
                    include_skills=not abi_turn,
                )
                injection_preamble = None
                if abi_turn:
                    injection_preamble = await self.build_abi_injection_preamble(
                        prior_messages=prior_messages,
                        user_id=context.actor_user_id,
                        workspace_id=request.workspace_id,
                        conversation_id=conversation_id,
                        context=context,
                        client_context=request.context,
                        include_skills=True,
                    )

                from naas_abi.agents.feature import bind_feature_context
                from naas_abi.agents.slides import (
                    apply_slides_model_override,
                    bind_slides_research_policy,
                )

                bind_feature_context(request.context)
                has_prior_assistant = any(
                    getattr(m, "role", None) == "assistant" for m in prior_messages
                )
                bind_slides_research_policy(
                    request.message,
                    has_prior_assistant,
                    request.context,
                )
                llm_model = apply_slides_model_override(
                    provider.llm_model, request.context, request.message
                )

                response_content = await complete_with_provider(
                    messages=provider_messages,
                    config=ProviderConfig(
                        id=provider.id,
                        name=provider.name,
                        type=provider.type,
                        enabled=provider.enabled,
                        endpoint=provider.endpoint,
                        api_key=provider.api_key,
                        account_id=provider.account_id,
                        model=provider.model,
                        llm_model=llm_model,
                    ),
                    system_prompt=system_prompt,
                    thread_id=conversation_id,
                    injection_preamble=injection_preamble,
                )
                response_content = self._unwrap_json_content(response_content)
                provider_used = f"{provider.name} ({provider.model})"
            except Exception as exc:
                response_content = (
                    f"**Error calling {provider.name}:**\n\n{str(exc)}\n\n"
                    "Please check your provider configuration in Settings."
                )
                provider_used = f"{provider.name} (error)"
        else:
            response_content = (
                "**No AI provider available.**\n\n"
                "To get real responses:\n"
                "1. Install Ollama: https://ollama.ai\n"
                f"2. Run: `ollama pull {DEFAULT_CHAT_MODEL_TAG}`\n"
                "3. Start: `ollama serve`\n\n"
                f'Your message: "{request.message[:100]}{"..." if len(request.message) > 100 else ""}"'
            )

        assistant_message_id = await self.create_message(
            context=context,
            conversation_id=conversation_id,
            role="assistant",
            content=response_content,
            agent=request.agent,
            created_at=now,
            metadata=(
                {REGENERATE_OF_KEY: request.regenerate_of} if request.regenerate_of else None
            ),
        )
        if request.regenerate_of:
            await self.mark_message_superseded(
                context=context,
                conversation_id=conversation_id,
                message_id=request.regenerate_of,
                superseded_by=assistant_message_id,
            )
        await self.touch_conversation(
            context,
            conversation_id,
            now,
        )

        return CompleteChatResult(
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            assistant_content=response_content,
            assistant_agent=request.agent,
            provider_used=provider_used,
            created_at=now,
            context_sources=context_sources,
        )

    async def update_conversation(
        self,
        context: RequestContext,
        conversation_id: str,
        now: datetime,
        title: str | None = None,
        pinned: bool | None = None,
        archived: bool | None = None,
    ) -> None:
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.conversation.update",
        )
        await self.adapter.update_conversation_fields(
            conversation_id=conversation_id,
            now=now,
            title=title,
            pinned=pinned,
            archived=archived,
        )

    async def delete_conversation_with_messages(
        self,
        context: RequestContext,
        conversation_id: str,
    ) -> bool:
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.conversation.delete",
        )
        await self.adapter.delete_messages_by_conversation(conversation_id)
        return await self.adapter.delete_conversation(conversation_id)

    async def get_agent(
        self,
        context: RequestContext,
        agent_id: str,
    ) -> ChatAgentRecord | None:
        self._ensure_scope(
            context=context,
            required_scope="chat.agent.read",
            denied_message="Agent access denied",
        )
        agent = await self.adapter.get_agent_by_id(agent_id)
        if agent:
            await self._ensure_workspace_access(context=context, workspace_id=agent.workspace_id)
        return agent

    async def get_abi_server(
        self,
        context: RequestContext,
        workspace_id: str,
    ) -> ChatInferenceServerRecord | None:
        self._ensure_scope(
            context=context,
            required_scope="chat.provider.read",
            denied_message="Provider access denied",
        )
        await self._ensure_workspace_access(context=context, workspace_id=workspace_id)
        return await self.adapter.get_enabled_workspace_abi_server(workspace_id)

    async def get_workspace_secret(
        self,
        context: RequestContext,
        workspace_id: str,
        key: str,
    ) -> ChatSecretRecord | None:
        self._ensure_scope(
            context=context,
            required_scope="chat.secret.read",
            denied_message="Secret access denied",
        )
        await self._ensure_workspace_access(context=context, workspace_id=workspace_id)
        return await self.adapter.get_workspace_secret(workspace_id, key)

    async def list_agent_names_by_ids(
        self,
        context: RequestContext,
        agent_ids: set[str],
    ) -> dict[str, str]:
        self._ensure_scope(
            context=context,
            required_scope="chat.agent.read",
            denied_message="Agent access denied",
        )
        return await self.adapter.list_agent_names_by_ids(agent_ids)

    @staticmethod
    def _select_provider_model(ollama_status: dict[str, Any], has_images: bool) -> str:
        preferred_models = (
            [
                "qwen3-vl:2b",
                "qwen3-vl",
                "qwen2.5vl:3b",
                "qwen2.5vl",
                "llava",
                "moondream",
                "gemma3",
            ]
            if has_images
            else list(FALLBACK_CHAT_MODEL_TAGS)
        )
        available = ollama_status["models"]
        for pref in preferred_models:
            for avail in available:
                if pref in avail:
                    return avail
        return available[0]

    async def resolve_provider(
        self,
        context: RequestContext,
        provider: Any | None,
        has_images: bool,
        agent_id: str | None = None,
        workspace_id: str | None = None,
    ) -> ResolvedProvider | None:
        incoming_llm = getattr(provider, "llm_model", None) if provider else None
        if provider and getattr(provider, "enabled", False):
            return ResolvedProvider(
                id=provider.id,
                name=provider.name,
                type=provider.type,
                enabled=provider.enabled,
                endpoint=provider.endpoint,
                api_key=provider.api_key,
                account_id=provider.account_id,
                model=provider.model,
                llm_model=incoming_llm,
            )

        if agent_id:
            try:
                agent = await self.get_agent(context=context, agent_id=agent_id)
                if agent and agent.provider:
                    workspace_id = agent.workspace_id
                    if agent.provider == "abi":
                        inprocess_agent_ref = (
                            agent.class_name or agent.name or agent.model_id or agent.id
                        )
                        external_agent_ref = (
                            agent.model_id or agent.class_name or agent.name or agent.id
                        )
                        abi_server = await self.get_abi_server(
                            context=context,
                            workspace_id=workspace_id,
                        )
                        if abi_server:
                            return ResolvedProvider(
                                id=f"abi-{abi_server.id}",
                                name=f"ABI ({abi_server.name})",
                                type="abi",
                                enabled=True,
                                endpoint=abi_server.endpoint,
                                api_key=abi_server.api_key,
                                account_id=None,
                                model=external_agent_ref,
                                llm_model=incoming_llm,
                            )
                        return ResolvedProvider(
                            id=f"abi-inprocess-{agent.id}",
                            name="ABI (In-Process)",
                            type="abi",
                            enabled=True,
                            endpoint="inprocess://abi",
                            api_key=None,
                            account_id=None,
                            model=inprocess_agent_ref,
                            llm_model=incoming_llm,
                        )

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
                    if secret_key and agent.model_id:
                        secret = await self.get_workspace_secret(
                            context=context,
                            workspace_id=workspace_id,
                            key=secret_key,
                        )
                        if secret:
                            return ResolvedProvider(
                                id=f"agent-{agent.provider}",
                                name=f"{agent.provider.upper()} (via Agent)",
                                type=agent.provider,
                                enabled=True,
                                endpoint=endpoint_map.get(agent.provider),
                                api_key=decrypt_secret_value(secret.encrypted_value),
                                account_id=None,
                                model=agent.model_id,
                            )

                if not agent and workspace_id and agent_id:
                    abi_server = await self.get_abi_server(
                        context=context,
                        workspace_id=workspace_id,
                    )
                    if abi_server:
                        return ResolvedProvider(
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
                    return ResolvedProvider(
                        id=f"abi-inprocess-{agent_id}",
                        name="ABI (In-Process)",
                        type="abi",
                        enabled=True,
                        endpoint="inprocess://abi",
                        api_key=None,
                        account_id=None,
                        model=agent_id,
                    )
            except Exception:
                logging.getLogger(__name__).warning(
                    "Failed to resolve agent provider", exc_info=True
                )

        ollama_status = await check_ollama_status()
        if ollama_status["status"] == "online" and ollama_status["models"]:
            # An image request needs a vision model; anything else should land
            # on the model a keyless project actually installs.
            preferred = "qwen3-vl:2b" if has_images else DEFAULT_CHAT_MODEL_TAG
            model = (
                preferred
                if any(preferred in m for m in ollama_status["models"])
                else self._select_provider_model(ollama_status, has_images)
            )
            return ResolvedProvider(
                id="ollama-fallback",
                name="Ollama (Auto)",
                type="ollama",
                enabled=True,
                endpoint=resolve_endpoint(),
                api_key=None,
                account_id=None,
                model=model,
            )
        return None

    @classmethod
    def _is_regeneration_leftover(
        cls,
        message: ChatMessageRecord,
        regenerate_of: str | None = None,
    ) -> bool:
        """True when a stored message must stay out of the model's context.

        Covers the answer being refreshed right now (``regenerate_of``), answers
        a previous refresh already replaced, and the duplicated prompts those
        refreshes wrote. All of them remain in the database for the audit trail.
        """
        if regenerate_of and message.id == regenerate_of:
            return True
        metadata = cls._parse_message_metadata(message.metadata_)
        return bool(metadata.get(SUPERSEDED_BY_KEY) or metadata.get(REGENERATE_REPLAY_KEY))

    @staticmethod
    def _apply_regeneration_directive(
        messages: list[ProviderMessage],
    ) -> list[ProviderMessage]:
        """Mark the prompt being replayed so the agent recomputes it.

        Targets the last user message — the one every provider treats as the
        current turn, and the only one the in-process ABI agent receives.
        """
        for index in range(len(messages) - 1, -1, -1):
            if messages[index].role == "user":
                messages[index] = ProviderMessage(
                    role="user",
                    content=f"{REGENERATION_DIRECTIVE}{messages[index].content}",
                    images=messages[index].images,
                )
                break
        return messages

    async def build_provider_messages_with_agents(
        self,
        context: RequestContext,
        request: CompleteChatInput,
        current_agent_id: str,
        conversation_id: str | None = None,
    ) -> list[ProviderMessage]:
        effective_conversation_id = conversation_id or request.conversation_id
        db_messages: list[Any] = []
        if effective_conversation_id:
            rows = await self.list_messages(
                context=context, conversation_id=effective_conversation_id
            )
            db_messages = [
                {
                    "role": m.role,
                    "content": m.content,
                    "images": None,
                    "agent": m.agent,
                }
                for m in rows
                if m.role in {"user", "assistant", "system"}
                and not self._is_regeneration_leftover(m, request.regenerate_of)
            ]
            if request.message:
                if (
                    not db_messages
                    or db_messages[-1]["role"] != "user"
                    or db_messages[-1]["content"] != request.message
                ):
                    db_messages.append(
                        {
                            "role": "user",
                            "content": request.message,
                            "images": request.images,
                            "agent": None,
                        }
                    )
        source_messages = db_messages or [
            {
                "role": m.role,
                "content": m.content,
                "images": m.images,
                "agent": m.agent,
            }
            for m in request.messages
        ]
        if not source_messages:
            messages = [
                ProviderMessage(role="user", content=request.message, images=request.images)
            ]
            return (
                self._apply_regeneration_directive(messages) if request.regenerate_of else messages
            )

        agent_ids = {
            m["agent"] for m in source_messages if m["role"] == "assistant" and m.get("agent")
        }
        agent_ids.add(current_agent_id)
        agents_map = await self.list_agent_names_by_ids(context=context, agent_ids=agent_ids)
        current_agent_name = agents_map.get(current_agent_id, "Unknown Agent")

        messages: list[ProviderMessage] = []
        for m in source_messages:
            if m["role"] == "assistant" and m.get("agent") and m["agent"] != current_agent_id:
                agent_name = agents_map.get(m["agent"], "Another AI")
                messages.append(
                    ProviderMessage(
                        role="system",
                        content=(
                            f"[SYSTEM: The following response was generated by {agent_name}, "
                            f"NOT by you. You are {current_agent_name}.]"
                        ),
                        images=None,
                    )
                )
            messages.append(
                ProviderMessage(
                    role=m["role"],
                    content=m["content"],
                    images=m.get("images"),
                )
            )

        if any(m["role"] == "assistant" for m in source_messages):
            messages.append(
                ProviderMessage(
                    role="system",
                    content=(
                        f"[SYSTEM: You are now responding as {current_agent_name}. "
                        "Do not claim authorship of previous agents' responses.]"
                    ),
                    images=None,
                )
            )
        if request.regenerate_of:
            self._apply_regeneration_directive(messages)
        return messages

    # async def run_search_if_needed(self, message: str, search_enabled: bool) -> str | None:
    #     search_keywords = [
    #         "search for",
    #         "search about",
    #         "look up",
    #         "find info",
    #         "what's the latest",
    #         "news about",
    #         "search the web",
    #     ]
    #     implicit_search = any(kw in message.lower() for kw in search_keywords)
    #     if not search_enabled and not implicit_search:
    #         return None
    #
    #     search_results: list[str] = []
    #     try:
    #         wiki_results = await execute_tool(
    #             "search_web", {"query": message, "engine": "wikipedia"}
    #         )
    #         search_results.append(f"**Wikipedia:**\n{wiki_results}")
    #     except Exception:
    #         pass
    #     try:
    #         ddg_results = await execute_tool(
    #             "search_web", {"query": message, "engine": "duckduckgo"}
    #         )
    #         search_results.append(f"**DuckDuckGo:**\n{ddg_results}")
    #     except Exception:
    #         pass
    #
    #     if search_results:
    #         return (
    #             f'Web search results for "{message}":\n\n'
    #             f"{chr(10).join(search_results)}\n\n"
    #             "Use these search results to provide an accurate, well-sourced answer. "
    #             "Cite sources with URLs when available. If the results don't fully answer "
    #             "the question, supplement with your knowledge."
    #         )
    #     return "Web search was attempted but returned no results. Answer based on your knowledge."
