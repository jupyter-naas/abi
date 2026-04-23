from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from naas_abi_core.models.opencode.Base import OpencodeBase


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
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
