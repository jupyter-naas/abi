from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from naas_abi_core.models.opencode.Base import OpencodeBase
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class OpencodeSession(OpencodeBase):
    __tablename__ = "opencode_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    opencode_id: Mapped[str] = mapped_column(Text(), index=True)
    agent_name: Mapped[str] = mapped_column(Text())
    workdir: Mapped[str] = mapped_column(Text())
    abi_thread_id: Mapped[str | None] = mapped_column(Text(), nullable=True)
    title: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
