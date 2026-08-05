from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GatekeeperGrantRecord:
    chat_id: str
    resource_type: str
    resource_id: str
    actions: tuple[str, ...]
    granted_at: datetime


@dataclass(frozen=True)
class GatekeeperGrantCreateInput:
    resource_type: str
    resource_id: str
    actions: tuple[str, ...]
