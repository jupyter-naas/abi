from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from naas_abi_core.models.opencode.Base import OpencodeBase


class OpencodeFileEvent(OpencodeBase):
    __tablename__ = "opencode_file_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("opencode_sessions.id"))
    message_id: Mapped[str] = mapped_column(ForeignKey("opencode_messages.id"))
    event_type: Mapped[str] = mapped_column(Text())
    file_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    diff: Mapped[str | None] = mapped_column(Text(), nullable=True)
    command: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
