"""What analytics count of a chat message, kept beside it when it is written.

A message's metadata (JSON text) holds its ``feedback`` (``like``/``dislike``), the
``feedback_type`` of a dislike and its ``steps`` (the tools it called). The chat
adapter writes them to ``messages.feedback``, ``messages.feedback_type`` and
``message_tools`` with every write of the metadata, so analytics count them in SQL
(``analytics/adapters/secondary/analytics__secondary_adapter__postgres.py``)
instead of loading and parsing every message.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.models import MessageModel, MessageToolModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

FEEDBACK = ("like", "dislike")
# A step named so is the model's reasoning, not a tool.
NOT_TOOLS = frozenset({"thinking"})


@dataclass(frozen=True)
class MessageFacts:
    feedback: str | None = None
    feedback_type: str | None = None
    tools: dict[str, int] = field(default_factory=dict)


def _metadata(raw: str | dict | None) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def facts_of(raw: str | dict | None) -> MessageFacts:
    meta = _metadata(raw)
    feedback = meta.get("feedback")
    feedback = feedback if feedback in FEEDBACK else None
    kind = meta.get("feedback_type")
    kind = kind[:100] if feedback == "dislike" and isinstance(kind, str) and kind else None
    tools: Counter[str] = Counter()
    steps = meta.get("steps")
    for step in steps if isinstance(steps, list) else []:
        name = step.get("tool_name") if isinstance(step, dict) else None
        if isinstance(name, str) and name and name.lower() not in NOT_TOOLS:
            tools[name[:200]] += 1
    return MessageFacts(feedback=feedback, feedback_type=kind, tools=dict(tools))


async def write_message_facts(
    db: AsyncSession, message: Any, raw: str | dict | None, *, replace: bool
) -> None:
    """Set the message's facts from its metadata ``raw`` (flushed by the caller).
    ``replace``: the message had tools recorded already."""
    facts = facts_of(raw)
    message.feedback = facts.feedback
    message.feedback_type = facts.feedback_type
    if replace:
        await db.execute(delete(MessageToolModel).where(MessageToolModel.message_id == message.id))
    for name, uses in facts.tools.items():
        db.add(MessageToolModel(message_id=message.id, tool_name=name, uses=uses))


async def index_message_facts(db: AsyncSession, since: datetime, *, batch: int = 500) -> int:
    """Write the facts of the messages since ``since`` that carry metadata (those
    written before the facts were kept). Commits per batch; returns how many."""
    done = 0
    last_id = ""
    while True:
        rows = (
            (
                await db.execute(
                    select(MessageModel)
                    .where(
                        MessageModel.created_at >= since,
                        MessageModel.metadata_.is_not(None),
                        MessageModel.id > last_id,
                    )
                    .order_by(MessageModel.id)
                    .limit(batch)
                    # A chat write on one of them (feedback, metadata) waits for the
                    # batch, or the batch for it: its facts are never rewritten from
                    # stale metadata, nor its tools inserted twice.
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            return done
        for message in rows:
            await write_message_facts(db, message, str(message.metadata_), replace=True)
        await db.commit()
        done += len(rows)
        last_id = str(rows[-1].id)
