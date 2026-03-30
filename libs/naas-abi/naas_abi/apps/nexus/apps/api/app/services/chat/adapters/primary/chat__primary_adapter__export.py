from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi.responses import StreamingResponse
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC


def export_conversation_as_response(
    conversation_id: str,
    format: str,
    user_id: str,
    conversation: Any,
    messages: list[Any],
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
            content += f"Timestamp: {msg.created_at.isoformat()}\n"
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

        content += f"*{msg.created_at.isoformat()}*\n\n"
        content += f"{msg.content}\n\n"
        content += "---\n\n"

    return StreamingResponse(
        iter([content]),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="conversation-{conversation_id}.md"'
        },
    )
