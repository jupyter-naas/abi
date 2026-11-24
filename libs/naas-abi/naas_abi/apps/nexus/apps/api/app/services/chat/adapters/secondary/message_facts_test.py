"""A message's feedback and tools are kept beside it whenever its metadata is written."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core.database import Base
from naas_abi.apps.nexus.apps.api.app.models import (
    ConversationModel,
    MessageModel,
    MessageToolModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.secondary.message_facts import (
    facts_of,
    index_message_facts,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.secondary.postgres import (
    ChatSecondaryAdapterPostgres,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

T0 = datetime(2026, 11, 19, 9, 0)
STEPS = {
    "steps": [
        {"tool_name": "search"},
        {"tool_name": "search"},
        {"tool_name": "Thinking"},
        {"tool_name": "sql"},
        "not a step",
    ]
}


def test_the_facts_of_a_metadata() -> None:
    assert facts_of(None).feedback is None
    assert facts_of("not json").tools == {}
    facts = facts_of(json.dumps({**STEPS, "feedback": "dislike", "feedback_type": "wrong"}))
    assert (facts.feedback, facts.feedback_type, facts.tools) == (
        "dislike",
        "wrong",
        {"search": 2, "sql": 1},
    )
    # A like has no type; an unknown feedback is none.
    assert facts_of({"feedback": "like", "feedback_type": "wrong"}).feedback_type is None
    assert facts_of({"feedback": "meh"}).feedback is None


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        session.add(UserModel(id="u", email="u@example.com", name="U"))
        session.add(WorkspaceModel(id="ws", name="W", slug="w", owner_id="u"))
        session.add(ConversationModel(id="c", workspace_id="ws", user_id="u", title="T"))
        await session.commit()
        yield session
    await engine.dispose()


async def _tools(db: AsyncSession, message_id: str) -> dict[str, int]:
    rows = await db.execute(
        select(MessageToolModel.tool_name, MessageToolModel.uses).where(
            MessageToolModel.message_id == message_id
        )
    )
    return dict(rows.all())


@pytest.mark.asyncio
async def test_the_chat_adapter_writes_the_facts_with_the_metadata(db) -> None:
    adapter = ChatSecondaryAdapterPostgres(db=db)
    await adapter.create_message("m", "c", "assistant", "hi", T0, metadata_=json.dumps(STEPS))
    assert await _tools(db, "m") == {"search": 2, "sql": 1}

    await adapter.update_message_metadata(
        "m",
        json.dumps(
            {"steps": [{"tool_name": "sql"}], "feedback": "dislike", "feedback_type": "slow"}
        ),
    )
    message = (await db.execute(select(MessageModel).where(MessageModel.id == "m"))).scalar_one()
    assert (message.feedback, message.feedback_type) == ("dislike", "slow")
    assert await _tools(db, "m") == {"sql": 1}

    await adapter.update_message_metadata("m", json.dumps({}))
    assert (message.feedback, message.feedback_type) == (None, None)
    assert await _tools(db, "m") == {}


@pytest.mark.asyncio
async def test_older_messages_are_indexed_once(db) -> None:
    db.add(
        MessageModel(
            id="old",
            conversation_id="c",
            role="assistant",
            content="…",
            metadata_=json.dumps({**STEPS, "feedback": "like"}),
            created_at=T0,
        )
    )
    db.add(
        MessageModel(
            id="older",
            conversation_id="c",
            role="assistant",
            content="…",
            metadata_=json.dumps({"feedback": "like"}),
            created_at=datetime(2025, 1, 1),
        )
    )
    await db.commit()
    assert await index_message_facts(db, datetime(2026, 10, 1), batch=1) == 1
    assert await _tools(db, "old") == {"search": 2, "sql": 1}
    old = (
        await db.execute(
            select(MessageModel)
            .where(MessageModel.id == "old")
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert old.feedback == "like"
    # Run again: the same facts, not twice the tools.
    assert await index_message_facts(db, datetime(2026, 10, 1)) == 1
    assert await _tools(db, "old") == {"search": 2, "sql": 1}


@pytest.mark.asyncio
async def test_a_pass_goes_batch_by_batch_and_rewrites_stale_facts(db) -> None:
    """Several batches, each committed after ``after_batch``; a message whose facts
    no longer match its metadata gets them rewritten (feedback cleared, tools replaced),
    and a message without tools gets none."""
    for index, meta in enumerate(
        [
            {**STEPS, "feedback": "like"},
            {"feedback": "dislike", "feedback_type": "slow"},
            {"steps": [{"tool_name": "sql"}]},
        ]
    ):
        db.add(
            MessageModel(
                id=f"m-{index}",
                conversation_id="c",
                role="assistant",
                content="…",
                metadata_=json.dumps(meta),
                created_at=T0,
            )
        )
    await db.flush()
    # Stale facts on m-2: a feedback and a tool its metadata no longer holds.
    stale = (await db.execute(select(MessageModel).where(MessageModel.id == "m-2"))).scalar_one()
    stale.feedback = "like"
    db.add(MessageToolModel(message_id="m-2", tool_name="search", uses=4))
    await db.commit()

    seen: list[int] = []

    async def after_batch(done: int) -> None:
        seen.append(done)

    assert await index_message_facts(db, T0, batch=2, after_batch=after_batch) == 3
    assert seen == [2, 3]
    rows = await db.execute(
        select(MessageModel.id, MessageModel.feedback, MessageModel.feedback_type).order_by(
            MessageModel.id
        )
    )
    assert rows.all() == [("m-0", "like", None), ("m-1", "dislike", "slow"), ("m-2", None, None)]
    assert await _tools(db, "m-0") == {"search": 2, "sql": 1}
    assert await _tools(db, "m-1") == {}
    assert await _tools(db, "m-2") == {"sql": 1}
