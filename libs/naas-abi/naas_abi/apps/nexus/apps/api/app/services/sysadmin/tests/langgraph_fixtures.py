"""LangGraph checkpoint documents exactly as the savers write them (schema 2), and
as schema 1 savers did (full snapshots), for the same two-step conversation."""

import asyncio
from typing import Any, cast

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import empty_checkpoint
from naas_abi_proto.document.values import decode_data
from naas_abi_sdk.langgraph import DocumentCheckpointSaver
from pydantic import SecretStr


class _Capture:
    """A DocumentClient that keeps what the SDK saver writes, as document data."""

    def __init__(self) -> None:
        self.puts: list[tuple[str, str, dict]] = []

    async def put(self, request):
        self.puts.append((request.collection, request.id, decode_data(request.data)))

    async def ensure_collection(self, request):
        return None


def conversation():
    return [
        SystemMessage("You answer briefly."),
        HumanMessage("What is JetStream?"),
        AIMessage(
            "",
            tool_calls=[{"name": "Researcher", "args": {"prompt": "JetStream"}, "id": "call-1"}],
            usage_metadata={"input_tokens": 120, "output_tokens": 8, "total_tokens": 128},
            response_metadata={"model_name": "gpt-5.5"},
        ),
        ToolMessage("NATS persistence.", tool_call_id="call-1", name="Researcher"),
        AIMessage(
            [
                {"type": "text", "text": "JetStream is "},
                {"type": "text", "text": "NATS persistence."},
            ]
        ),
    ]


def _steps(token: str):
    first = empty_checkpoint()
    first["channel_values"] = {"messages": conversation()[:2]}
    first["channel_versions"] = {"messages": 1}
    second = empty_checkpoint()
    second["channel_values"] = {
        "messages": conversation(),
        "credentials": SecretStr(token),
        "current_active_agent": "Researcher",
    }
    second["channel_versions"] = {"messages": 2, "credentials": 1, "current_active_agent": 1}
    return first, second


WRITTEN = (
    [("messages", [AIMessage("Partial answer")]), ("branch:to:tools", None)],
    "task-1",
    "~__pregel_pull, call_model",
)


def written(token: str) -> list[tuple[str, str, dict]]:
    """Two checkpoints of thread t-1 (the second a child of the first) and its writes."""
    capture = _Capture()
    saver = DocumentCheckpointSaver(cast(Any, capture), agent_id="agent-a")
    first, second = _steps(token)

    async def scenario():
        config = await saver.aput(
            {"configurable": {"thread_id": "t-1", "checkpoint_ns": ""}},
            first,
            {"source": "input", "step": -1, "parents": {}},
            {},
        )
        config = await saver.aput(config, second, {"source": "loop", "step": 3, "parents": {}}, {})
        await saver.aput_writes(config, *WRITTEN)

    asyncio.run(scenario())
    return capture.puts


def written_v1(token: str) -> list[tuple[str, str, dict]]:
    """The same conversation in schema 1 documents."""
    from naas_abi_core.services.agent.tests.legacy_checkpoints import put_v1, put_writes_v1

    puts: list[tuple[str, str, dict]] = []

    class _Documents:
        def put(self, collection, key, data):
            puts.append((collection, key, data))

    documents = _Documents()
    first, second = _steps(token)
    config = put_v1(
        documents,
        "agent-a",
        {"configurable": {"thread_id": "t-1", "checkpoint_ns": ""}},
        first,
        {"source": "input", "step": -1, "parents": {}},
    )
    config = put_v1(
        documents, "agent-a", config, second, {"source": "loop", "step": 3, "parents": {}}
    )
    put_writes_v1(documents, "agent-a", config, WRITTEN[0], WRITTEN[1])
    # Schema 1 kept the task path; the shared writer leaves it empty.
    return [(c, k, d | {"task_path": WRITTEN[2]} if "task_id" in d else d) for c, k, d in puts]
