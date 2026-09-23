"""SDK-only application module: no protobuf or ABI core imports."""

import asyncio
import importlib.util
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from naas_abi_sdk import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
    current_module,
    run_module,
)
from naas_abi_sdk.services.event import Event
from naas_abi_sdk.services.models import (
    ActivityEvent,
    CollectionSpec,
    ColumnSpec,
    DatasetSpec,
    FileWrite,
)


class ReportWriter:
    """Normal components receive their module or a narrower service dependency."""

    def __init__(self, module):
        self.storage = module.engine.services.object_storage
        self.prefix = module.configuration.prefix

    async def write(self, content: bytes) -> str:
        key = "report.txt"
        await self.storage.put_object(self.prefix, key, content)
        return key


class ABIModule(BaseModule):
    @dataclass
    class Configuration(ModuleConfiguration):
        prefix: str = "ergonomic"

    dependencies = ModuleDependencies(
        services=(
            "object_storage",
            "document",
            "kv",
            "cache",
            "secret",
            "email",
            "activity_log",
            "events",
            "dataset",
            "coding_environment",
            "source_control",
            "vector_store",
            "bus",
        )
    )

    async def on_initialized(self):
        self.writer = ReportWriter(self)
        assert current_module() is self
        await self.engine.services.document.ensure_collection(
            CollectionSpec(name="runs")
        )

    async def run(self):
        services = current_module().engine.services
        key = await self.writer.write(b"created")
        assert (
            await services.object_storage.get_object(self.configuration.prefix, key)
            == b"created"
        )
        assert await services.object_storage.list_objects(self.configuration.prefix)
        assert (
            await services.object_storage.get_object_metadata(
                self.configuration.prefix, key
            )
        ).file_size_bytes == 7
        await self.writer.write(b"updated")
        assert (
            await services.object_storage.get_object(self.configuration.prefix, key)
            == b"updated"
        )
        await services.object_storage.delete_object(self.configuration.prefix, key)

        doc = await services.document.put(
            "runs", "one", {"binary": b"\x00", "large": 2**60}, if_version=0
        )
        assert doc.version == 1 and doc.data["large"] == 2**60
        await services.document.put(
            "runs", "one", {"status": "updated"}, if_version=doc.version
        )
        assert (
            await services.document.find_one("runs", [("status", "eq", "updated")])
        ).id == "one"
        assert len([d async for d in services.document.iterate("runs", batch=1)]) == 1
        assert await services.document.delete_many("runs", []) == 1
        await services.document.drop_collection("runs")

        await services.kv.set("ergonomic", b"value")
        assert await services.kv.get("ergonomic") == b"value"
        assert not await services.kv.set_if_not_exists("ergonomic", b"other")
        assert await services.kv.delete_if_value_matches("ergonomic", b"value")

        await services.cache.cold.set_json("ergonomic", {"tier": "cold"})
        assert await services.cache.get("ergonomic") == {"tier": "cold"}
        assert await services.cache.hot_available()
        await services.cache.hot.set_binary("ergonomic", b"hot")
        assert await services.cache.get("ergonomic") == b"hot"
        await services.cache.delete("ergonomic")
        assert not await services.cache.exists("ergonomic")

        await services.secret.set("ERGONOMIC_DEMO", "demo-value")
        assert await services.secret.get("ERGONOMIC_DEMO") == "demo-value"
        assert (await services.secret.list())["ERGONOMIC_DEMO"] == "demo-value"
        await services.secret.remove("ERGONOMIC_DEMO")
        await services.email.send(
            to_email="demo@example.invalid",
            subject="SDK facade",
            text_body="Hello",
            from_email="sdk@example.invalid",
        )
        await services.activity_log.record(
            ActivityEvent(
                actor_id="sdk:ergonomic",
                event_type="demo.facade",
                timestamp=datetime.now(UTC),
                attributes={"ok": True},
            )
        )
        assert (await services.activity_log.query("sdk:ergonomic"))[
            0
        ].event_type == "demo.facade"
        await services.events.publish(
            Event("urn:demo:Ergonomic", {"value": "recorded"})
        )
        assert (await services.events.query("urn:demo:Ergonomic"))[0][
            "value"
        ] == "recorded"

        info = await services.dataset.create(
            DatasetSpec(name="ergonomic", columns=[ColumnSpec("name", "string")])
        )
        assert info.name == "ergonomic"
        await services.dataset.write("ergonomic", [{"name": "one"}])
        result = await services.dataset.query("SELECT * FROM ergonomic")
        assert result.rows[0]["name"] == "one"
        await services.dataset.drop("ergonomic")

        coding = services.coding_environment
        uid = await coding.ensure_user(
            external_id="ergonomic",
            email="ergonomic@example.invalid",
            username="ergonomic",
        )
        templates = await coding.list_templates()
        status = await coding.provision(
            user_id=uid, template_id=templates[0].id, name="ergonomic"
        )
        assert (await coding.start(workspace_id=status.id)).id == status.id
        assert (await coding.get_status(workspace_id=status.id)).id == status.id
        await coding.stop(workspace_id=status.id)
        await coding.delete(workspace_id=status.id)

        source = services.source_control
        user = await source.ensure_user(
            external_id="ergonomic",
            email="ergonomic@example.invalid",
            username="ergonomic",
        )
        repo = await source.ensure_repo(owner=user, name="ergonomic")
        await source.upsert_files(
            repo_id=f"{repo.owner}/{repo.name}",
            files=[FileWrite("report.txt", "hello")],
            message="create report",
            branch=repo.default_branch,
        )
        assert (
            await source.get_file(
                repo_id=f"{repo.owner}/{repo.name}", path="report.txt"
            )
        ).text == "hello"
        assert any(r.id == repo.id for r in await source.list_repos())

        vectors = services.vector_store
        await vectors.ensure_collection("ergonomic", 3)
        vid = str(uuid4())
        await vectors.add_documents(
            "ergonomic", [vid], [[1, 0, 0]], metadata=[{"value": "one"}]
        )
        assert (await vectors.get_document("ergonomic", vid)).id == vid
        assert (await vectors.search_similar("ergonomic", [1, 0, 0]))[0].id == vid
        await vectors.update_document("ergonomic", vid, metadata={"value": "two"})
        assert await vectors.get_collection_size("ergonomic") == 1
        await vectors.delete_documents("ergonomic", [vid])
        await vectors.delete_collection("ergonomic")
        return {
            "status": "passed",
            "module": type(self).__name__,
            "core_installed": False,
            "protobuf_imports": False,
        }

    def on_unloaded(self):
        assert current_module() is self


async def main():
    assert importlib.util.find_spec("naas_abi_core") is None
    report = await run_module(
        ABIModule,
        url=os.environ["ABI_NATS_URL"],
        token=os.environ["ABI_SERVICE_TOKEN"],
        timeout=30,
    )
    Path(os.environ["DEMO_REPORT"]).write_text(json.dumps(report))
    print(json.dumps({"ergonomic_module": report}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
