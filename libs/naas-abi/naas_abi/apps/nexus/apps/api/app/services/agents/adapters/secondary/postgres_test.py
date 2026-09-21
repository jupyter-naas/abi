from __future__ import annotations

import json

import pytest
from naas_abi.apps.nexus.apps.api.app.models import AgentConfigModel
from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.secondary.postgres import (
    AgentSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentUpdateInput
from naas_abi.apps.nexus.apps.api.app.services.identity_events.capture import (
    IdentityEventCapture,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.mark.asyncio
async def test_promoting_a_default_agent_demotes_the_others_as_logged_changes(tmp_path) -> None:
    """The demotion used to be a bulk UPDATE, invisible to identity events."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(AgentConfigModel.__table__.create)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add_all(
            [
                AgentConfigModel(id="a", workspace_id="ws-1", name="A", is_default=1),
                AgentConfigModel(id="b", workspace_id="ws-1", name="B", is_default=0),
                AgentConfigModel(id="c", workspace_id="ws-2", name="C", is_default=1),
            ]
        )
        await session.commit()

    published: list = []
    capture = IdentityEventCapture(publish=published.append)
    capture.install()
    try:
        async with maker() as session:
            record = await AgentSecondaryAdapterPostgres(session).update(
                "b", AgentUpdateInput(is_default=True)
            )
    finally:
        capture.uninstall()

    async with maker() as session:
        defaults = {
            a.id: a.is_default for a in [await session.get(AgentConfigModel, i) for i in "abc"]
        }
    await engine.dispose()

    assert record is not None and record.is_default
    assert defaults == {"a": 0, "b": 1, "c": 1}
    changes = {e.updates[0].rsplit("/", 1)[-1]: json.loads(e.changes_json) for e in published}
    assert changes == {
        "a": {"is_default": {"from": 1, "to": 0}},
        "b": {"is_default": {"from": 0, "to": 1}},
    }
