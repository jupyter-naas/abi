"""Optional SDK LangGraph integration against real document RPCs."""

import asyncio
import sys
from typing import TypedDict

import pytest
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.engine.nats_rpc_integration_test import (  # noqa: F401 - pytest fixture
    SECRET,
    broker,
)
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterNATSClient_test import (
    document_host,  # noqa: F401 - pytest fixture
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.parametrize("broker", [8 * 1024 * 1024], indirect=True),
]


def test_checkpoint_resume_from_second_process_and_isolation(document_host):  # noqa: F811 - imported pytest fixture
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt
    from naas_abi_sdk import ABIClient
    from naas_abi_sdk.langgraph import DocumentCheckpointSaver

    class State(TypedDict):
        value: str

    def approval(state):
        answer = interrupt("approve")
        return {"value": state["value"] + ":" + answer}

    builder = StateGraph(State)
    builder.add_node("approval", approval)
    builder.add_edge(START, "approval")
    builder.add_edge("approval", END)
    token = issue_service_token("checkpoint-test", SECRET)
    config = {"configurable": {"thread_id": "conversation"}}

    async def scenario():
        async with ABIClient(document_host, token) as client:
            saver = DocumentCheckpointSaver(
                client.document.for_namespace("module.agent"), agent_id="reviewer"
            )
            await saver.setup()
            graph = builder.compile(checkpointer=saver)
            await graph.ainvoke({"value": "persisted"}, config)
            saved = await saver.aget_tuple(config)
            assert saved is not None
            assert saved.pending_writes
        # A new interpreter must reconstruct the graph and resume from documents,
        # without carrying any in-memory saver state across the boundary.
        code = """
import asyncio,sys
from typing import TypedDict
from langgraph.graph import StateGraph,START,END
from langgraph.types import interrupt,Command
from naas_abi_sdk import ABIClient
from naas_abi_sdk.langgraph import DocumentCheckpointSaver
class State(TypedDict):
    value: str
def approval(state):
    answer=interrupt('approve')
    return {'value': state['value']+':'+answer}
async def main():
    async with ABIClient(sys.argv[1],sys.argv[2]) as client:
        saver=DocumentCheckpointSaver(client.document.for_namespace('module.agent'),agent_id='reviewer')
        await saver.setup()
        builder=StateGraph(State)
        builder.add_node('approval',approval);builder.add_edge(START,'approval');builder.add_edge('approval',END)
        result=await builder.compile(checkpointer=saver).ainvoke(Command(resume='yes'),{'configurable':{'thread_id':'conversation'}})
        assert result['value']=='persisted:yes',result
asyncio.run(main())
"""
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            code,
            document_host,
            token,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        assert process.returncode == 0, (stdout, stderr)
        async with ABIClient(document_host, token) as client:
            saver = DocumentCheckpointSaver(
                client.document.for_namespace("module.agent"), agent_id="reviewer"
            )
            assert (await saver.aget_tuple(config)).checkpoint["channel_values"][
                "value"
            ] == "persisted:yes"
            history = [item async for item in saver.alist(config)]
            assert len(history) >= 3
            assert len([item async for item in saver.alist(config, limit=1)]) == 1
            assert (
                len(
                    [
                        item
                        async for item in saver.alist(config, before=history[0].config)
                    ]
                )
                == len(history) - 1
            )
            other = DocumentCheckpointSaver(
                client.document.for_namespace("module.agent"), agent_id="other"
            )
            await other.setup()
            assert await other.aget_tuple(config) is None
            separate = DocumentCheckpointSaver(
                client.document.for_namespace("module.other"), agent_id="reviewer"
            )
            await separate.setup()
            assert await separate.aget_tuple(config) is None
            from langgraph.checkpoint.base import empty_checkpoint
            from langgraph.constants import ERROR
            from naas_abi_sdk.transport import RPCError

            write_config = {
                "configurable": {"thread_id": "pending", "checkpoint_ns": "nested"}
            }
            checkpoint = empty_checkpoint()
            metadata = {"source": "input", "step": 0, "parents": {}}
            saved_config = await saver.aput(write_config, checkpoint, metadata, {})
            await saver.aput(write_config, checkpoint, metadata, {})
            with pytest.raises(RPCError, match="VERSION_CONFLICT"):
                await saver.aput(
                    write_config,
                    checkpoint | {"channel_values": {"different": True}},
                    metadata,
                    {},
                )
            await saver.aput_writes(
                saved_config, [("value", "first"), (ERROR, "old")], "task"
            )
            await saver.aput_writes(
                saved_config, [("value", "second"), (ERROR, "new")], "task"
            )
            writes = (await saver.aget_tuple(saved_config)).pending_writes
            assert ("task", "value", "first") in writes
            assert ("task", ERROR, "new") in writes
            assert not [
                item
                async for item in saver.alist(write_config, filter={"source": "loop"})
            ]
            await saver.adelete_thread("conversation")
            assert await saver.aget_tuple(config) is None

    asyncio.run(scenario())
