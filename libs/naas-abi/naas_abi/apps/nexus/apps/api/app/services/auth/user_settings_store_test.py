from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store_test import MemoryStorage
from naas_abi.apps.nexus.apps.api.app.services.auth.user_settings_store import (
    save_user_settings,
)

T1 = datetime(2026, 10, 14, 9, 30, 0)
T2 = datetime(2026, 10, 14, 10, 0, 5)
PREFIX = "naas_abi/my-drive/user-1/.settings/user"


@dataclass
class FakeUser:
    id: str = "user-1"
    email: str = "alice@example.com"
    name: str = "Alice"
    organization: str | None = "Acme"
    job_title: str | None = "CTO"
    bio: str | None = None
    avatar: str | None = None
    is_superadmin: bool = False
    created_at: datetime = datetime(2026, 1, 1)
    hashed_password: str = "secret-hash"


def test_first_save_writes_user_json_without_the_password() -> None:
    storage = MemoryStorage()

    result = save_user_settings(storage, FakeUser(), T1)

    assert result.changed is True and result.archived_key is None
    assert storage.paths() == {f"{PREFIX}/user.json"}
    document = json.loads(storage.get_object(PREFIX, "user.json"))
    assert document["schema_version"] == 1
    assert document["user"] == {
        "id": "user-1",
        "email": "alice@example.com",
        "name": "Alice",
        "organization": "Acme",
        "job_title": "CTO",
        "bio": None,
        "avatar": None,
        "is_superadmin": False,
        "created_at": "2026-01-01T00:00:00",
    }
    assert "secret-hash" not in storage.get_object(PREFIX, "user.json").decode()


def test_unchanged_info_writes_nothing() -> None:
    storage = MemoryStorage()
    save_user_settings(storage, FakeUser(), T1)

    assert save_user_settings(storage, FakeUser(), T2).changed is False
    assert len(storage.paths()) == 1


def test_changed_info_archives_the_previous_version() -> None:
    storage = MemoryStorage()
    save_user_settings(storage, FakeUser(), T1)

    result = save_user_settings(storage, replace(FakeUser(), organization="Forvis Mazars"), T2)

    assert result.archived_key == "20261014T100005Z_user.json"
    archived = json.loads(storage.get_object(f"{PREFIX}/archives", "20261014T100005Z_user.json"))
    assert archived["user"]["organization"] == "Acme"
    assert (
        json.loads(storage.get_object(PREFIX, "user.json"))["user"]["organization"]
        == "Forvis Mazars"
    )
