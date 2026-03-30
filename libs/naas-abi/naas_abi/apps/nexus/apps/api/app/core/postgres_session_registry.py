from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class SessionBinding:
    session_id: str
    db: AsyncSession


class PostgresSessionRegistry:
    _instance: PostgresSessionRegistry | None = None

    def __new__(cls) -> PostgresSessionRegistry:
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._sessions = {}
            instance._current_session_id = ContextVar("postgres_session_id", default=None)
            cls._instance = instance
        return cls._instance

    @classmethod
    def instance(cls) -> PostgresSessionRegistry:
        return cls()

    def bind(self, session_id: str, db: AsyncSession) -> None:
        self._sessions[session_id] = db

    def unbind(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def set_current_session(self, session_id: str) -> Token:
        return self._current_session_id.set(session_id)

    def reset_current_session(self, token: Token) -> None:
        self._current_session_id.reset(token)

    def current_session_id(self) -> str | None:
        return self._current_session_id.get()

    def get(self, session_id: str) -> AsyncSession | None:
        return self._sessions.get(session_id)

    def current_session(self) -> AsyncSession | None:
        session_id = self.current_session_id()
        if session_id is None:
            return None
        return self.get(session_id)
