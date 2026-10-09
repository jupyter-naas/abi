"""Route an office slash the same way an open workbook, deck, or document does.

Sheets, slides, and documents stay catalog rows. When the matching office
agent is on the workspace roster, the turn is that agent and the skill body
is not pasted into the provider prompt. When the agent is missing, the slash
keeps the old expansion.
"""

from __future__ import annotations

import re

from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentRecord
from naas_abi.skills.catalog import OFFICE_HANDOFF_SLUGS

# First line of the user message. Later lines may be retrieved document context.
_SLASH_COMMAND_RE = re.compile(r"^/([A-Za-z0-9][A-Za-z0-9-]*)(?:\s+(.*))?$")


def slash_on_first_line(content: str) -> tuple[str, str, str] | None:
    first, sep, rest = (content or "").partition("\n")
    match = _SLASH_COMMAND_RE.match(first.strip())
    if not match:
        return None
    slug = match.group(1).lower()
    args = (match.group(2) or "").strip()
    tail = f"{sep}{rest}" if sep else ""
    return slug, args, tail


def office_slash_slug(message: str | None) -> str | None:
    parsed = slash_on_first_line(message or "")
    if parsed is None:
        return None
    slug = parsed[0]
    if slug in OFFICE_HANDOFF_SLUGS:
        return slug
    return None


def _pick_office_agent_id(agents: list[AgentRecord], slug: str) -> str | None:
    from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (
        pick_workspace_documents_agent_id,
        pick_workspace_sheets_agent_id,
        pick_workspace_slides_agent_id,
    )

    pickers = {
        "sheets": pick_workspace_sheets_agent_id,
        "slides": pick_workspace_slides_agent_id,
        "documents": pick_workspace_documents_agent_id,
    }
    picker = pickers.get(slug)
    if picker is None:
        return None
    return picker(agents)


def open_file_agent_id(
    agents: list[AgentRecord],
    client_context: dict | None,
) -> str | None:
    """The agent an open workbook, deck, or document already selects.

    Sheets yields to an open deck or document, matching the streaming adapter.
    """
    from naas_abi.agents.documents.policy import open_documents_slug
    from naas_abi.agents.sheets.policy import open_sheets_slug
    from naas_abi.agents.slides.policy import open_slides_slug

    slides_agent = None
    if open_slides_slug(client_context):
        slides_agent = _pick_office_agent_id(agents, "slides")
    documents_agent = None
    if open_documents_slug(client_context):
        documents_agent = _pick_office_agent_id(agents, "documents")
    sheets_agent = None
    if (
        open_sheets_slug(client_context)
        and not open_slides_slug(client_context)
        and not open_documents_slug(client_context)
    ):
        sheets_agent = _pick_office_agent_id(agents, "sheets")
    if sheets_agent:
        return sheets_agent
    if slides_agent:
        return slides_agent
    if documents_agent:
        return documents_agent
    return None


def resolve_workspace_turn_agent(
    agents: list[AgentRecord],
    requested_id: str | None,
    message: str = "",
    client_context: dict | None = None,
) -> str | None:
    """Workspace agent for this turn.

    An open file wins, then an office slash whose agent is listed, then the
    requested chat agent.
    """
    from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (
        pick_workspace_chat_agent_id,
    )

    resolved = pick_workspace_chat_agent_id(agents, requested_id)
    open_agent = open_file_agent_id(agents, client_context)
    if open_agent:
        return open_agent
    slug = office_slash_slug(message)
    if slug:
        office = _pick_office_agent_id(agents, slug)
        if office:
            return office
    return resolved


def suppressed_office_skill_slug(
    agents: list[AgentRecord],
    message: str | None,
) -> str | None:
    """Slug whose procedure must stay out of the provider prompt.

    None when the office agent is not on the roster, so the slash keeps
    expanding into the current agent.
    """
    slug = office_slash_slug(message)
    if slug and _pick_office_agent_id(agents, slug):
        return slug
    return None
