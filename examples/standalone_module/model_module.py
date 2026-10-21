"""Run with naas-abi-sdk[models]; no ABI core or provider credentials needed."""

import asyncio
import importlib.util
import json
import os
from pathlib import Path

from naas_abi_sdk import BaseModule, ModuleDependencies, run_module


class ABIModule(BaseModule):
    dependencies = ModuleDependencies(services=("model_registry",))

    async def run(self):
        registry = self.engine.services.model_registry
        chat = (await registry.get_chat_model("demo-chat")).model
        embeddings = (await registry.get_embedding_model("demo-embedding")).model
        answer = await chat.ainvoke("Hello from a separate process")
        chunks = [chunk.content async for chunk in chat.astream("Stream a response")]
        vector = await embeddings.aembed_query("Shared remote embeddings")
        assert answer.content == "remote model answer"
        assert "".join(chunks) == answer.content
        assert len(vector) == 8
        return {
            "answer": answer.content,
            "stream": "".join(chunks),
            "embedding_dimensions": len(vector),
            "pid": os.getpid(),
            "core_installed": False,
        }


async def main():
    assert importlib.util.find_spec("naas_abi_core") is None
    result = await run_module(
        ABIModule,
        url=os.environ["ABI_NATS_URL"],
        token=os.environ["ABI_SERVICE_TOKEN"],
        timeout=120,
    )
    Path(os.environ["DEMO_REPORT"]).write_text(json.dumps(result))


if __name__ == "__main__":
    asyncio.run(main())
