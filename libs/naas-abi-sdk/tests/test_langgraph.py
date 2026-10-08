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


def test_checkpoint_versions_continue_threads_migrated_from_postgres():
    pytest.importorskip("langgraph.checkpoint.base")
    from naas_abi_sdk.langgraph import DocumentCheckpointSaver

    saver = DocumentCheckpointSaver(AsyncMock(), agent_id="agent")
    assert saver.get_next_version(None, None) == 1
    assert saver.get_next_version("00000000000000000000000000000004.25", None) > (
        "00000000000000000000000000000004.25"
    )


def test_latest_checkpoint_lookup_reads_a_single_document():
    pytest.importorskip("langgraph.checkpoint.base")
    from naas_abi_proto.document.v1 import document_pb2 as pb

    from naas_abi_sdk.langgraph import DocumentCheckpointSaver

    documents = AsyncMock()
    documents.find.return_value = pb.FindResponse()
    saver = DocumentCheckpointSaver(documents, agent_id="agent")
    assert asyncio.run(saver.aget_tuple({"configurable": {"thread_id": "t"}})) is None
    # Every turn starts here: a page of full snapshots would be wasted transfer.
    assert documents.find.await_args.args[0].limit == 1
