"""Nexus accounts (``users``) name the people IAM knows by them, through a session of its
own per call."""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any

from sqlalchemy import bindparam, text


class SqlAccountNames:
    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._sessions = session_factory

    async def names_of(self, user_ids: Collection[str]) -> dict[str, tuple[str | None, str | None]]:
        """Each account's name and email; an account missing is left out, an empty value is None."""
        ids = sorted(set(user_ids))
        if not ids:
            return {}
        async with self._sessions() as db:
            rows = await db.execute(
                text("SELECT id, name, email FROM users WHERE id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": ids},
            )
            return {str(i): (name or None, email or None) for i, name, email in rows.all()}
