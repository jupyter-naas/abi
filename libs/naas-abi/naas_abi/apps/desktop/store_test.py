"""Unit tests for DesktopStore (SQLite persistence)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from desktop.desktop_config import DEFAULT_SETTINGS
from desktop.store import DesktopStore


@pytest.fixture()
def store(tmp_path: Path) -> Iterator[DesktopStore]:
    s = DesktopStore(tmp_path / "desktop.db")
    yield s
    s.close()


class TestSettings:
    def test_defaults_returned_when_empty(self, store: DesktopStore) -> None:
        assert store.get_settings() == DEFAULT_SETTINGS

    def test_update_merges_over_defaults(self, store: DesktopStore) -> None:
        updated = store.update_settings({"default_model": "openai/gpt-5"})
        assert updated["default_model"] == "openai/gpt-5"
        assert updated["opencode_bin"] == DEFAULT_SETTINGS["opencode_bin"]

    def test_update_roundtrip_and_upsert(self, store: DesktopStore) -> None:
        store.update_settings({"opencode_bin": "/usr/local/bin/opencode"})
        store.update_settings({"opencode_bin": "/opt/opencode"})
        assert store.get_settings()["opencode_bin"] == "/opt/opencode"

    def test_values_coerced_to_str(self, store: DesktopStore) -> None:
        store.update_settings({"default_model": 42})  # type: ignore[dict-item]
        assert store.get_settings()["default_model"] == "42"


class TestChats:
    def test_create_and_get(self, store: DesktopStore) -> None:
        chat = store.create_chat(title="Hello", section="code", model="m1")
        assert chat["title"] == "Hello"
        assert chat["section"] == "code"
        assert chat["model"] == "m1"
        assert chat["opencode_session_id"] is None
        assert store.get_chat(chat["id"]) == chat

    def test_get_missing_returns_none(self, store: DesktopStore) -> None:
        assert store.get_chat("nope") is None

    def test_list_orders_by_updated_at_desc(self, store: DesktopStore) -> None:
        first = store.create_chat(title="first")
        second = store.create_chat(title="second")
        # Touch the older chat so it moves to the top.
        store.update_chat(first["id"], title="first-updated")
        ids = [c["id"] for c in store.list_chats()]
        assert ids == [first["id"], second["id"]]

    def test_list_filters_by_section(self, store: DesktopStore) -> None:
        chat = store.create_chat(section="chat")
        code = store.create_chat(section="code")
        assert [c["id"] for c in store.list_chats("code")] == [code["id"]]
        assert [c["id"] for c in store.list_chats("chat")] == [chat["id"]]

    def test_update_ignores_disallowed_fields(self, store: DesktopStore) -> None:
        chat = store.create_chat()
        updated = store.update_chat(
            chat["id"], title="renamed", section="hacked", id="evil"
        )
        assert updated is not None
        assert updated["title"] == "renamed"
        assert updated["section"] == "chat"
        assert updated["id"] == chat["id"]

    def test_update_session_id(self, store: DesktopStore) -> None:
        chat = store.create_chat()
        updated = store.update_chat(chat["id"], opencode_session_id="ses_1")
        assert updated is not None
        assert updated["opencode_session_id"] == "ses_1"

    def test_delete(self, store: DesktopStore) -> None:
        chat = store.create_chat()
        store.delete_chat(chat["id"])
        assert store.get_chat(chat["id"]) is None


class TestMessages:
    def test_append_and_list_in_order(self, store: DesktopStore) -> None:
        chat = store.create_chat()
        store.add_message(chat["id"], "user", "hi")
        store.add_message(chat["id"], "assistant", "hello", parts=[{"type": "tool"}])
        messages = store.list_messages(chat["id"])
        assert [(m["role"], m["content"]) for m in messages] == [
            ("user", "hi"),
            ("assistant", "hello"),
        ]
        assert messages[1]["parts"] == [{"type": "tool"}]

    def test_add_message_persists_sources(self, store: DesktopStore) -> None:
        chat = store.create_chat()
        message = store.add_message(
            chat["id"],
            "assistant",
            "answer",
            sources=["doc.pdf", "notes.md"],
        )
        assert message["sources"] == ["doc.pdf", "notes.md"]
        listed = store.list_messages(chat["id"])[0]
        assert listed["sources"] == ["doc.pdf", "notes.md"]

    def test_corrupt_sources_json_degrades_to_empty(
        self, store: DesktopStore, tmp_path: Path
    ) -> None:
        chat = store.create_chat()
        message = store.add_message(
            chat["id"], "assistant", "hi", sources=["a.txt"]
        )
        store._conn.execute(
            "UPDATE messages SET sources_json='not-json' WHERE id=?", (message["id"],)
        )
        store._conn.commit()
        assert store.list_messages(chat["id"])[0]["sources"] == []

    def test_add_message_bumps_chat_updated_at(self, store: DesktopStore) -> None:
        chat = store.create_chat()
        store.add_message(chat["id"], "user", "hi")
        refreshed = store.get_chat(chat["id"])
        assert refreshed is not None
        assert refreshed["updated_at"] >= chat["updated_at"]

    def test_cascade_delete(self, store: DesktopStore) -> None:
        chat = store.create_chat()
        store.add_message(chat["id"], "user", "hi")
        store.delete_chat(chat["id"])
        assert store.list_messages(chat["id"]) == []

    def test_corrupt_parts_json_degrades_to_empty(
        self, store: DesktopStore, tmp_path: Path
    ) -> None:
        chat = store.create_chat()
        message = store.add_message(chat["id"], "user", "hi")
        store._conn.execute(  # simulate on-disk corruption
            "UPDATE messages SET parts_json='not-json' WHERE id=?", (message["id"],)
        )
        store._conn.commit()
        assert store.list_messages(chat["id"])[0]["parts"] == []
