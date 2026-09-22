import asyncio
from unittest.mock import AsyncMock

import pytest


def test_checkpoint_transport_errors_propagate_without_local_fallback():
    pytest.importorskip("langgraph.checkpoint.base")
    from naas_abi_sdk.langgraph import DocumentCheckpointSaver

    documents = AsyncMock()
    documents.find.side_effect = ConnectionError("offline")
    saver = DocumentCheckpointSaver(documents, agent_id="agent")
    with pytest.raises(ConnectionError, match="offline"):
        asyncio.run(saver.aget_tuple({"configurable": {"thread_id": "conversation"}}))
    documents.find.assert_awaited_once()


def test_checkpoint_requires_stable_agent_identity():
    pytest.importorskip("langgraph.checkpoint.base")
    from naas_abi_sdk.langgraph import DocumentCheckpointSaver

    with pytest.raises(ValueError, match="agent_id"):
        DocumentCheckpointSaver(AsyncMock(), agent_id="")
