from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from naas_abi.apps.nexus.apps.api.app.services.workflows.adapters.secondary.sql import (
    SqlRunOwners,
)
from naas_abi.apps.nexus.apps.api.app.services.workflows.port import RunOwner

T0 = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_run_owners_are_recorded_read_and_listed_newest_first(nexus_db) -> None:
    owners = SqlRunOwners(nexus_db)
    for minute, (run_id, user, workspace) in enumerate(
        [
            ("a:1", "ada", "ws-1"),
            ("a:2", "ada", "ws-1"),
            ("a:3", "bob", "ws-1"),
            ("a:4", "ada", "ws-2"),
        ]
    ):
        await owners.record(
            RunOwner("acme", run_id, "a", user, workspace, T0 + timedelta(minutes=minute))
        )

    found = await owners.get("acme", "a:2")
    assert found is not None and (found.user_id, found.workspace_id) == ("ada", "ws-1")
    assert await owners.get("acme", "a:9") is None
    assert [o.run_id for o in await owners.list_for("ada", "ws-1", 10)] == ["a:2", "a:1"]
    assert [o.run_id for o in await owners.list_for("ada", "ws-1", 1)] == ["a:2"]

    # A run id the jobs stream reuses names the new run.
    await owners.record(RunOwner("acme", "a:1", "a", "bob", "ws-1", T0 + timedelta(hours=1)))
    reused = await owners.get("acme", "a:1")
    assert reused is not None and reused.user_id == "bob"
