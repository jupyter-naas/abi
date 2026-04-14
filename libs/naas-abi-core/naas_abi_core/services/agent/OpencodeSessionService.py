from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from naas_abi_core.models.opencode.OpencodeFileEvent import OpencodeFileEvent
from naas_abi_core.models.opencode.OpencodeMessage import OpencodeMessage
from naas_abi_core.models.opencode.OpencodeSession import OpencodeSession
from naas_abi_core.utils.Logger import logger


class OpencodeSessionService:
    def __init__(self, db_session: AsyncSession | None = None):
        self._db_session = db_session
        self._sessions_by_opencode_id: dict[str, OpencodeSession] = {}
        self._messages: list[OpencodeMessage] = []
        self._file_events: list[OpencodeFileEvent] = []

    async def get_or_create_session(
        self,
        opencode_id: str,
        agent_name: str,
        workdir: str,
        abi_thread_id: str | None,
        title: str | None,
    ) -> OpencodeSession:
        if self._db_session is not None:
            stmt = select(OpencodeSession).where(
                OpencodeSession.opencode_id == opencode_id
            )
            result = await self._db_session.execute(stmt)
            session = result.scalars().first()
            if session is None:
                session = OpencodeSession(
                    opencode_id=opencode_id,
                    agent_name=agent_name,
                    workdir=workdir,
                    abi_thread_id=abi_thread_id,
                    title=title,
                )
                self._db_session.add(session)
            else:
                session.updated_at = datetime.now(timezone.utc)
                if abi_thread_id:
                    session.abi_thread_id = abi_thread_id
                if title and not session.title:
                    session.title = title
            await self._flush_best_effort()
            return session

        session = self._sessions_by_opencode_id.get(opencode_id)
        if session is None:
            session = OpencodeSession(
                opencode_id=opencode_id,
                agent_name=agent_name,
                workdir=workdir,
                abi_thread_id=abi_thread_id,
                title=title,
            )
            self._sessions_by_opencode_id[opencode_id] = session
        else:
            session.updated_at = datetime.now(timezone.utc)
            if abi_thread_id:
                session.abi_thread_id = abi_thread_id
            if title and not session.title:
                session.title = title

        await self._flush_best_effort()
        return session

    async def persist_message(
        self,
        session: OpencodeSession,
        role: str,
        parts: list[dict[str, Any]],
    ) -> OpencodeMessage:
        message = OpencodeMessage(
            session_id=session.id,
            role=role,
            content=self.extract_text(parts),
            parts=parts,
        )

        if self._db_session is not None:
            self._db_session.add(message)
            await self._flush_best_effort()
            return message

        self._messages.append(message)
        await self._flush_best_effort()
        return message

    async def persist_file_events(
        self,
        message: OpencodeMessage,
        parts: list[dict[str, Any]],
    ) -> None:
        for event in self.extract_file_events(parts):
            file_event = OpencodeFileEvent(
                session_id=message.session_id,
                message_id=message.id,
                event_type=event["event_type"],
                file_path=event.get("file_path"),
                diff=event.get("diff"),
                command=event.get("command"),
            )
            if self._db_session is not None:
                self._db_session.add(file_event)
            else:
                self._file_events.append(file_event)

        await self._flush_best_effort()

    @staticmethod
    def extract_text(parts: list[dict[str, Any]]) -> str | None:
        chunks: list[str] = []
        for part in parts:
            text = part.get("text") or part.get("content")
            if isinstance(text, str) and text:
                chunks.append(text)
        if not chunks:
            return None
        return "\n".join(chunks)

    @staticmethod
    def extract_file_events(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        for part in parts:
            if part.get("type") != "tool_use":
                continue

            tool_name = part.get("name")
            tool_input = part.get("input") or {}

            if tool_name == "read":
                events.append(
                    {
                        "event_type": "read",
                        "file_path": tool_input.get("path"),
                    }
                )
            elif tool_name == "write":
                events.append(
                    {
                        "event_type": "write",
                        "file_path": tool_input.get("path"),
                        "diff": tool_input.get("diff") or tool_input.get("content"),
                    }
                )
            elif tool_name == "edit":
                events.append(
                    {
                        "event_type": "edit",
                        "file_path": tool_input.get("path"),
                        "diff": tool_input.get("diff")
                        or tool_input.get("new_string")
                        or tool_input.get("replace"),
                    }
                )
            elif tool_name == "bash":
                events.append(
                    {
                        "event_type": "bash",
                        "command": tool_input.get("command"),
                    }
                )

        return events

    async def _flush_best_effort(self) -> None:
        try:
            if self._db_session is not None:
                await self._db_session.flush()
                await self._db_session.commit()
        except Exception as e:
            logger.error(f"Opencode persistence failed: {e}")
