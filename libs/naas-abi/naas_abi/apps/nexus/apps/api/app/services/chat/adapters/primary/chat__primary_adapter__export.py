from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi.responses import StreamingResponse
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC


def _parse_metadata(msg: Any, override: dict | None = None) -> dict:
    """Stored metadata, with the caller's live values layered on top.

    The frontend sends execution time / steps / sources it may not have PATCHed
    yet, so those win; everything else the row carries (regenerate lineage,
    reviewer feedback) still makes it into the export.
    """
    stored: dict = {}
    raw = getattr(msg, "metadata_", None) or getattr(msg, "metadata", None)
    if isinstance(raw, dict):
        stored = raw
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                stored = parsed
        except Exception:
            pass
    return {**stored, **override} if override else stored


def _lineage_lines(meta: dict, label_format: str) -> str:
    """Regenerate ("refresh") bookkeeping, so an export shows the full history.

    Superseded answers and replayed prompts stay in the export even though the
    chat UI hides them; these lines say how each one relates to the others.
    """
    entries = []
    if meta.get("regenerate_of"):
        prefix = "Replayed prompt of" if meta.get("regenerate_replay") else "Regenerated from"
        entries.append((prefix, meta["regenerate_of"]))
    if meta.get("superseded_by"):
        entries.append(("Superseded by", meta["superseded_by"]))
    return "".join(label_format.format(label=label, value=value) for label, value in entries)


def export_conversation_as_response(
    conversation_id: str,
    format: str,
    user_id: str,
    conversation: Any,
    messages: list[Any],
    messages_metadata: dict[str, dict] | None = None,
) -> StreamingResponse:
    timestamp = datetime.now(UTC).isoformat()
    title = conversation.title or "Untitled Conversation"

    if format == "txt":
        content = f"Conversation: {title}\n"
        content += f"ID: {conversation_id}\n"
        content += f"Exported: {timestamp}\n"
        content += f"User: {user_id}\n"
        content += f"Workspace: {conversation.workspace_id}\n"
        content += f"Messages: {len(messages)}\n"
        content += f"\n{'=' * 80}\n\n"

        for msg in messages:
            role = msg.role.upper()
            if msg.role == "assistant" and msg.agent:
                role = f"ASSISTANT ({msg.agent})"

            content += f"[{role}]\n"
            content += f"ID: {msg.id}\n"
            content += f"Timestamp: {msg.created_at.isoformat()}\n"
            meta = _parse_metadata(msg, (messages_metadata or {}).get(msg.id))
            content += _lineage_lines(meta, "{label}: {value}\n")
            if meta.get("execution_time") is not None:
                content += f"Execution time: {meta['execution_time']:.1f}s\n"
            feedback = meta.get("feedback")
            if feedback in ("like", "dislike"):
                content += f"Feedback: {feedback}\n"
                if feedback == "dislike":
                    fb_type = meta.get("feedback_type")
                    if fb_type:
                        content += f"Feedback type: {fb_type}\n"
                    fb_severity = meta.get("feedback_severity")
                    if fb_severity is not None:
                        content += f"Feedback severity: {fb_severity}/5\n"
                    fb_detail = meta.get("feedback_detail")
                    if fb_detail:
                        content += f"Feedback detail: {fb_detail}\n"
            steps = meta.get("steps", [])
            if steps:
                content += "Steps:\n"
                for s in steps:
                    prefix = s.get("prefix") or "Tool"
                    name = s.get("tool_name") or ""
                    status = s.get("status") or ""
                    content += f"  - [{prefix}] {name} — {status}\n"
                    if s.get("input"):
                        content += f"      input: {s['input']}\n"
                    if s.get("output"):
                        content += f"      output: {s['output']}\n"
                content += "\n"
            if msg.role == "assistant":
                content += "Message:\n"
            content += f"{msg.content}\n"
            content += f"\n{'-' * 80}\n\n"

        return StreamingResponse(
            iter([content]),
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="conversation-{conversation_id}.txt"'
            },
        )

    if format == "json":
        data = {
            "conversation": {
                "id": conversation_id,
                "title": title,
                "workspace_id": conversation.workspace_id,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
            },
            "export": {
                "timestamp": timestamp,
                "user_id": user_id,
                "format": "json",
            },
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "agent": msg.agent,
                    "created_at": msg.created_at.isoformat(),
                    **_parse_metadata(msg, (messages_metadata or {}).get(msg.id)),
                }
                for msg in messages
            ],
        }

        content = json.dumps(data, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="conversation-{conversation_id}.json"'
            },
        )

    content = f"# {title}\n\n"
    content += f"**Conversation ID:** `{conversation_id}`  \n"
    content += f"**Exported:** {timestamp}  \n"
    content += f"**User:** {user_id}  \n"
    content += f"**Workspace:** {conversation.workspace_id}  \n"
    content += f"**Messages:** {len(messages)}  \n"
    content += "\n---\n\n"

    for msg in messages:
        if msg.role == "user":
            content += "## 👤 User\n\n"
        else:
            agent_info = f" ({msg.agent})" if msg.agent else ""
            content += f"## 🤖 Assistant{agent_info}\n\n"

        content += f"*{msg.created_at.isoformat()}* · `{msg.id}`\n\n"
        meta = _parse_metadata(msg, (messages_metadata or {}).get(msg.id))
        content += _lineage_lines(meta, "**{label}:** `{value}`\n\n")
        if meta.get("execution_time") is not None:
            content += f"⏱ **Execution time:** {meta['execution_time']:.1f}s\n\n"
        feedback = meta.get("feedback")
        if feedback in ("like", "dislike"):
            content += f"**Feedback:** {feedback}\n\n"
            if feedback == "dislike":
                fb_type = meta.get("feedback_type")
                if fb_type:
                    content += f"**Feedback type:** {fb_type}\n\n"
                fb_severity = meta.get("feedback_severity")
                if fb_severity is not None:
                    content += f"**Feedback severity:** {fb_severity}/5\n\n"
                fb_detail = meta.get("feedback_detail")
                if fb_detail:
                    content += f"**Feedback detail:** {fb_detail}\n\n"
        steps = meta.get("steps", [])
        if steps:
            content += f"🔧 **Steps ({len(steps)}):** " + ", ".join(
                s.get("tool_name", "") for s in steps
            ) + "\n\n"
        content += f"{msg.content}\n\n"
        content += "---\n\n"

    return StreamingResponse(
        iter([content]),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="conversation-{conversation_id}.md"'
        },
    )
