"""Tests for EventSQLiteAdapter."""

from __future__ import annotations

import datetime

import pytest

from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.tests.event__secondary_adapter__generic_test import (
    EventStorageContract,
)


def _ts(offset_seconds: int = 0) -> str:
    return (
        datetime.datetime(2026, 1, 1, 0, 0, 0)  # noqa: DTZ001
        + datetime.timedelta(seconds=offset_seconds)
    ).isoformat()


# ---------------------------------------------------------------------------
# durability
# ---------------------------------------------------------------------------


def test_events_persist_across_reopens(tmp_path):
    db = str(tmp_path / "events.sqlite")
    a1 = EventSQLiteAdapter(db)
    a1.append("urn:e1", "urn:Type:A", _ts(0), b"payload")
    a1.close()

    a2 = EventSQLiteAdapter(db)
    try:
        rows = a2.query()
        assert [r.id for r in rows] == ["urn:e1"]
        assert rows[0].payload == b"payload"
    finally:
        a2.close()


class TestEventSQLiteAdapter(EventStorageContract):
    @pytest.fixture
    def adapter(self, tmp_path):
        adapter = EventSQLiteAdapter(str(tmp_path / "contract.sqlite"))
        yield adapter
        adapter.close()
