from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from naas_abi_core.models.opencode.Base import OpencodeBase


class OpencodeMessage(OpencodeBase):
    __tablename__ = "opencode_messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("opencode_sessions.id"))
    role: Mapped[str] = mapped_column(Text())
    content: Mapped[str | None] = mapped_column(Text(), nullable=True)
    parts: Mapped[list[dict[str, Any]]] = mapped_column(JSON(), default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
