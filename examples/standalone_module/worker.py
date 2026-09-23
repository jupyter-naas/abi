"""First independent module: verify the entire v1 service surface over NATS."""

from __future__ import annotations

import asyncio
import importlib
import importlib.metadata
import importlib.util
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from naas_abi_sdk import RPCError
from naas_abi_sdk.catalog import OPERATIONS
from naas_abi_sdk.module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
    run_module,
)


class ABIModule(BaseModule):
    class Configuration(ModuleConfiguration):
        pass

    dependencies = ModuleDependencies(services=(*OPERATIONS, "bus"))

    @property
    def client(self):
        return self.engine.rpc

    def __init__(self, engine, configuration):
        super().__init__(engine, configuration)
        self.lifecycle: list[str] = []
        self.seen: set[tuple[str, str]] = set()
        self.results: list[dict] = []
        self.unsupported: list[str] = []

    def on_load(self):
        self.lifecycle.append("on_load")

    async def on_initialized(self):
        self.lifecycle.append("on_initialized")

    def on_unloaded(self):
        self.lifecycle.append("on_unloaded")

    async def call(self, domain: str, operation: str, **fields):
        pb = importlib.import_module(f"naas_abi_proto.{domain}.v1.{domain}_pb2")
        name = "".join(part.title() for part in operation.split("_"))
        request = getattr(pb, name + "Request")(**fields)
        response = await getattr(getattr(self.client, domain), operation)(request)
        self.seen.add((domain, operation))
        return response

    async def object_storage(self):
        async def call(op, **fields):
            return await self.call("object_storage", op, prefix="demo", **fields)

        await call("put_object", key="hello.txt", content=b"created")
        assert (await call("get_object", key="hello.txt")).content == b"created"
        assert any(
            k.endswith("hello.txt") for k in (await call("list_objects")).keys.keys
        )
        await call("put_object", key="hello.txt", content=b"updated")
        assert (await call("get_object", key="hello.txt")).content == b"updated"
        assert (
            await call("get_object_metadata", key="hello.txt")
        ).metadata.file_size_bytes == 7
        assert any(
            k.endswith("hello.txt")
            for k in (await call("list_objects_recursive")).keys.keys
        )
        await call("delete_object", key="hello.txt")
        assert not (await call("list_objects")).keys.keys

    async def keyvalue(self):
        async def call(op, **fields):
            return await self.call("keyvalue", op, key="demo", **fields)

        assert (await call("set_if_not_exists", value=b"first")).ok_value
        assert not (await call("set_if_not_exists", value=b"again")).ok_value
        assert (await call("get")).value == b"first"
        await call("set", value=b"updated", ttl=60)
        assert (await call("get")).value == b"updated"
        assert (await call("exists")).ok_value
        assert not (await call("delete_if_value_matches", value=b"wrong")).ok_value
        assert (await call("delete_if_value_matches", value=b"updated")).ok_value
        await call("set", value=b"delete-me")
        await call("delete")
        assert not (await call("exists")).ok_value

    async def cache(self):
        await self.call("cache", "describe")

        async def call(op, **fields):
            return await self.call("cache", op, key="demo", **fields)

        value = {
            "key": "demo",
            "data": "created",
            "data_type": 1,
            "created_at": datetime.now(UTC).isoformat(),
        }
        assert (await call("set_if_absent", value=value)).value
        assert not (await call("set_if_absent", value=value)).value
        assert (await call("get")).value.data == "created"
        value["data"] = "updated"
        await call("set", value=value)
        assert (await call("get")).value.data == "updated"
        assert (await call("exists")).value
        await call("delete")
        assert not (await call("exists")).value
        from naas_abi_proto.cache.v1 import cache_pb2

        hot = self.engine.rpc.cache.tier(0)
        await hot.set(cache_pb2.SetRequest(key="tier-demo", value=value))
        assert (
            await hot.get(cache_pb2.GetRequest(key="tier-demo"))
        ).value.data == "updated"
        await hot.delete(cache_pb2.DeleteRequest(key="tier-demo"))

    async def secret(self):
        await self.call("secret", "set", key="DEMO_VALUE", value="fixture-value")
        assert (
            await self.call("secret", "get", key="DEMO_VALUE")
        ).found.value == "fixture-value"
        await self.call("secret", "set", key="DEMO_VALUE", value="updated")
        entries = (await self.call("secret", "list")).found.entries
        assert any(e.key == "DEMO_VALUE" and e.value == "updated" for e in entries)
        await self.call("secret", "remove", key="DEMO_VALUE")
        assert not (await self.call("secret", "get", key="DEMO_VALUE")).found.HasField(
            "value"
        )

    async def email(self):
        await self.call(
            "email",
            "send",
            to_email="recipient@example.invalid",
            from_email="demo@example.invalid",
            subject="Standalone module",
            text_body="Verified through the filesystem email adapter.",
            attachments=[
                {
                    "filename": "hello.txt",
                    "content": b"hello",
                    "mime_type": "text/plain",
                }
            ],
        )
        # The parent verifies the persisted message without giving this worker filesystem access to it.

    async def activity_log(self):
        await self.call(
            "activity_log",
            "record",
            event={
                "actor_id": "demo",
                "event_type": "exercise",
                "timestamp": {"seconds": int(datetime.now(UTC).timestamp())},
                "attributes": {"source": "worker"},
            },
        )
        events = (
            await self.call("activity_log", "query", actor_id="demo")
        ).events.events
        assert any(e.event_type == "exercise" for e in events)
        assert "demo" in (await self.call("activity_log", "list_actors")).actors.actors
        await self.call("activity_log", "shutdown")

    async def event(self):
        event = (
            await self.call(
                "event",
                "append",
                event_id=str(uuid.uuid4()),
                event_type="demo",
                timestamp=datetime.now(UTC).isoformat(),
                payload=b'{"value":1}',
            )
        ).event
        assert event.payload == b'{"value":1}'
        assert (await self.call("event", "max_seq", event_type="demo")).seq == event.seq
        assert any(
            e.id == event.id
            for e in (
                await self.call("event", "query", event_type="demo")
            ).events.events
        )
        pending = await self.call(
            "event", "query_for_consumer", consumer_id="demo", event_type="demo"
        )
        assert any(e.id == event.id for e in pending.events.events)
        await self.call(
            "event",
            "set_cursor",
            consumer_id="demo",
            event_type="demo",
            last_seq=event.seq,
        )
        assert (
            await self.call(
                "event", "get_cursor", consumer_id="demo", event_type="demo"
            )
        ).last_seq == event.seq
        assert not (
            await self.call(
                "event", "query_for_consumer", consumer_id="demo", event_type="demo"
            )
        ).events.events

    async def dataset(self):
        spec = {
            "name": "demo",
            "namespace": "default",
            "columns": [{"name": "id", "type": 2}, {"name": "value", "type": 1}],
            "primary_key": ["id"],
        }
        assert (await self.call("dataset", "create", spec=spec)).info.name == "demo"

        async def call(op, **fields):
            return await self.call(
                "dataset", op, name="demo", namespace="default", **fields
            )

        assert (await call("describe")).info.primary_key == ["id"]
        assert any(
            i.name == "demo"
            for i in (await self.call("dataset", "list")).datasets.items
        )
        await call("write", rows=[{"id": 1, "value": "created"}], mode=1)
        await call("write", rows=[{"id": 1, "value": "updated"}], mode=3)
        result = await self.call(
            "dataset", "query", sql="SELECT * FROM demo", namespace="default"
        )
        assert (
            len(result.query_result.rows) == 1
            and result.query_result.rows[0]["value"] == "updated"
        )
        assert (await call("inlined_row_count")).count >= 0
        await call("flush")
        await call("compact")
        assert (await self.call("dataset", "list_snapshots")).snapshots.items
        await call("drop")
        assert not any(
            i.name == "demo"
            for i in (await self.call("dataset", "list")).datasets.items
        )

    async def vector_store(self):
        async def call(op, **fields):
            return await self.call("vector_store", op, collection_name="demo", **fields)

        await self.call("vector_store", "initialize")
        await call("create_collection", dimension=3, distance_metric="cosine")
        assert (
            "demo"
            in (await self.call("vector_store", "list_collections")).collections.names
        )
        vid = str(uuid.uuid4())
        await call(
            "store_vectors",
            documents=[
                {
                    "id": vid,
                    "vector": {"values": [1, 0, 0]},
                    "metadata": {"value": "created"},
                }
            ],
        )
        assert (await call("count_vectors")).count == 1
        assert (
            await call("get_vector", vector_id=vid, include_vector=True)
        ).found.document.id == vid
        assert (
            await call("search", query_vector=[1, 0, 0], k=1, include_metadata=True)
        ).results.results[0].id == vid
        await call("update_vector", vector_id=vid, metadata={"value": "updated"})
        assert (await call("get_vector", vector_id=vid)).found.document.metadata[
            "value"
        ] == "updated"
        await call("delete_vectors", vector_ids=[vid])
        assert (await call("count_vectors")).count == 0
        await call("delete_collection")
        assert (
            "demo"
            not in (
                await self.call("vector_store", "list_collections")
            ).collections.names
        )
        await self.call("vector_store", "close")

    async def coding_environment(self):
        domain = "coding_environment"
        user = (
            await self.call(
                domain,
                "ensure_user",
                external_id="demo",
                email="demo@example.invalid",
                username="demo",
            )
        ).user_id
        templates = (await self.call(domain, "list_templates")).templates.templates
        assert templates
        status = (
            await self.call(
                domain,
                "provision",
                user_id=user,
                template_id=templates[0].id,
                name="demo",
            )
        ).status
        wid = status.id
        assert wid
        assert any(
            e.id == wid
            for e in (
                await self.call(domain, "list_environments", user_id=user)
            ).environments.environments
        )
        assert (await self.call(domain, "start", workspace_id=wid)).status.id == wid
        assert (
            await self.call(domain, "get_status", workspace_id=wid)
        ).status.id == wid
        await self.call(domain, "get_logs", workspace_id=wid)
        assert (
            await self.call(
                domain, "get_access", workspace_id=wid, user_id=user, app_slug="code"
            )
        ).access.url
        await self.call(domain, "stop", workspace_id=wid)
        await self.call(domain, "delete", workspace_id=wid)
        assert not (
            await self.call(domain, "list_environments", user_id=user)
        ).environments.environments

    async def source_control(self):
        domain = "source_control"
        user = (
            await self.call(
                domain,
                "ensure_user",
                external_id="demo",
                email="demo@example.invalid",
                username="demo",
            )
        ).user_id
        repo = (
            await self.call(
                domain,
                "ensure_repo",
                owner="demo",
                name="repo",
                private=True,
                auto_init=True,
            )
        ).repo
        assert any(
            r.name == repo.name
            for r in (await self.call(domain, "list_repos")).repos.repos
        )

        async def call(op, **fields):
            return await self.call(domain, op, repo_id="demo/repo", **fields)

        await call("add_collaborator", username="demo", permission="write")
        await call(
            "upsert_file",
            path="hello.txt",
            text_content="created",
            message="Create file",
            branch="main",
        )
        assert (await call("get_file", path="hello.txt")).file.text == "created"
        await call(
            "upsert_files",
            files=[{"path": "hello.txt", "text_content": "updated"}],
            message="Update file",
            branch="main",
        )
        assert (await call("get_file", path="hello.txt")).file.text == "updated"
        assert any(
            e.path == "hello.txt" for e in (await call("list_contents")).entries.entries
        )
        await call("list_commits", limit=10)
        assert (
            await call("create_branch", name="demo", from_ref="main")
        ).branch.name == "demo"
        assert any(
            b.name == "demo" for b in (await call("list_branches")).branches.branches
        )
        await call("get_diff", base="main", head="demo")
        proposal = (
            await call(
                "create_proposal",
                title="Demo",
                body="Local fixture",
                source_branch="demo",
                target_branch="main",
            )
        ).proposal
        num = proposal.number
        assert (await call("get_proposal", number=num)).proposal.title == "Demo"
        assert any(
            p.number == num
            for p in (await call("list_proposals", state="open")).proposals.proposals
        )
        await call("get_proposal_diff", number=num)
        await call("list_proposal_commits", number=num)
        await call("add_comment", number=num, body="Verified")
        assert any(
            c.body == "Verified"
            for c in (await call("list_comments", number=num)).comments.comments
        )
        await call("submit_review", number=num, event="APPROVE", body="Verified")
        assert (await call("list_reviews", number=num)).reviews.reviews
        await call("list_checks", number=num)
        await call("set_branch_protection", branch="main", required_approvals=1)
        assert (await call("merge", number=num, method="merge")).merge_result.merged
        await call("delete_branch", name="demo")
        assert not any(
            b.name == "demo" for b in (await call("list_branches")).branches.branches
        )
        await call("list_workflow_runs", limit=10)
        assert (await self.call(domain, "mint_git_token", user_id=user)).token

    async def triple_store(self):
        domain = "triple_store"
        graph = "urn:demo:graph"
        triple = b'<urn:demo:s> <urn:demo:p> "created" .\n'
        await self.call(domain, "create_graph", graph_name=graph)
        await self.call(domain, "insert", graph_name=graph, triples_nt=triple)
        assert (
            b"created"
            in (
                await self.call(
                    domain, "get_subject_graph", subject="urn:demo:s", graph_name=graph
                )
            ).triples_nt
        )
        assert graph in (await self.call(domain, "list_graphs")).graph_names.graph_names
        await self.call(
            domain,
            "query",
            query="SELECT ?s WHERE { GRAPH <urn:demo:graph> { ?s ?p ?o } }",
        )
        await self.call(domain, "get")
        await self.call(
            domain, "query_view", view=graph, query="SELECT ?s WHERE { ?s ?p ?o }"
        )
        try:
            await self.call(
                domain,
                "handle_view_event",
                view={"subject": "urn:demo:s"},
                event=1,
                triple={
                    "subject": "urn:demo:s",
                    "predicate": "urn:demo:p",
                    "object": '"created"',
                },
            )
        except RPCError as exc:
            if exc.code != "NOT_SUPPORTED":
                raise
            self.seen.add((domain, "handle_view_event"))
            self.unsupported.append(
                "triple_store.handle_view_event: domain service does not expose adapter-internal view callbacks"
            )
        await self.call(domain, "remove", graph_name=graph, triples_nt=triple)
        try:
            await self.call(
                domain, "get_subject_graph", subject="urn:demo:s", graph_name=graph
            )
        except RPCError as exc:
            assert exc.code == "SUBJECT_NOT_FOUND"
        else:
            raise AssertionError("Deleted subject still exists")
        await self.call(
            domain,
            "insert",
            graph_name=graph,
            triples_nt=triple.replace(b"created", b"updated"),
        )
        assert (
            b"updated"
            in (
                await self.call(
                    domain, "get_subject_graph", subject="urn:demo:s", graph_name=graph
                )
            ).triples_nt
        )
        await self.call(domain, "clear_graph", graph_name=graph)
        await self.call(domain, "drop_graph", graph_name=graph)
        assert (
            graph
            not in (await self.call(domain, "list_graphs")).graph_names.graph_names
        )

    async def bus(self):
        # Prove both directions against the engine, not a worker-only loopback.
        sub = await self.client.bus.subscribe("demo.reply", "echo")
        try:
            # Readiness probes are idempotent, disposable demo messages only.
            for _ in range(30):
                await self.client.bus.publish("demo.inbox", "echo", b"pubsub")
                try:
                    assert (await sub.next_msg(timeout=0.2)).data == b"pubsub"
                    break
                except TimeoutError:
                    continue
            else:
                raise RuntimeError("Engine bus subscriber did not become ready")
            await self.client.bus.publish_many(
                "demo.inbox", [("echo", b"batch-1"), ("echo", b"batch-2")]
            )
            received = set()
            for _ in range(32):
                received.add((await sub.next_msg(timeout=2)).data)
                if {b"batch-1", b"batch-2"} <= received:
                    break
            assert {b"batch-1", b"batch-2"} <= received
        finally:
            await sub.unsubscribe()
        jobs = await self.client.bus.dequeue("demo.outbox", "work")
        try:
            await self.client.bus.enqueue("demo.jobs", "work", b"durable")
            messages = await jobs.fetch(1, timeout=10)
            assert messages[0].data == b"durable"
            await messages[0].ack_sync()
        finally:
            await jobs.unsubscribe()
        self.results.append(
            {
                "service": "bus",
                "status": "passed",
                "operations": [
                    "publish",
                    "publish_many",
                    "subscribe",
                    "enqueue",
                    "dequeue",
                ],
            }
        )
        print(json.dumps(self.results[-1]), flush=True)

    async def document(self):
        from naas_abi_proto.document.v1 import document_pb2 as pb
        from naas_abi_proto.document.values import decode_data, encode_data

        await self.call(
            "document", "ensure_collection", spec=pb.CollectionSpec(name="exercise")
        )
        assert "exercise" in (await self.call("document", "collections")).collections
        first = await self.call(
            "document",
            "put",
            collection="exercise",
            id="one",
            data=encode_data({"value": b"created", "large": 2**60}),
            if_version=0,
        )
        assert first.document.version == 1
        await self.call(
            "document",
            "put",
            collection="exercise",
            id="one",
            data=encode_data({"value": b"updated"}),
            if_version=1,
        )
        result = await self.call("document", "get", collection="exercise", id="one")
        assert decode_data(result.document.data) == {"value": b"updated"}
        assert (
            len((await self.call("document", "find", collection="exercise")).items) == 1
        )
        assert (await self.call("document", "count", collection="exercise")).count == 1
        await self.call(
            "document", "delete", collection="exercise", id="one", if_version=2
        )
        assert (await self.call("document", "count", collection="exercise")).count == 0
        await self.call("document", "drop_collection", collection="exercise")

    async def run(self):
        for domain in OPERATIONS:
            try:
                await getattr(self, domain)()
                self.results.append(
                    {
                        "service": domain,
                        "status": "passed",
                        "operations": sorted(op for d, op in self.seen if d == domain),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - report each failed service and continue the exercise
                self.results.append(
                    {
                        "service": domain,
                        "status": "failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            print(json.dumps(self.results[-1]), flush=True)
        try:
            await self.bus()
        except Exception as exc:  # noqa: BLE001 - report each failed service and continue the exercise
            self.results.append(
                {
                    "service": "bus",
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        missing = sorted(
            f"{d}.{op}"
            for d, ops in OPERATIONS.items()
            for op in ops
            if (d, op) not in self.seen
        )
        return {
            "module": "ABIModule",
            "lifecycle": self.lifecycle,
            "results": self.results,
            "missing_operations": missing,
            "rpc_operations": len(self.seen),
            "unsupported_endpoints": self.unsupported,
        }


async def main():
    assert importlib.util.find_spec("naas_abi_core") is None, (
        "Worker must not have core installed"
    )
    token = os.environ["ABI_SERVICE_TOKEN"]
    report = await run_module(
        ABIModule, url=os.environ["ABI_NATS_URL"], token=token, timeout=30
    )
    report.update(
        worker_pid=os.getpid(),
        packages=sorted(d.metadata["Name"] for d in importlib.metadata.distributions()),
        core_installed=False,
        unsupported=[
            "object_storage streaming",
            "process-local model registry",
            "ontology/agent execution (no v1 RPC contract)",
        ],
    )
    Path(os.environ["DEMO_REPORT"]).write_text(json.dumps(report, indent=2) + "\n")
    if report["missing_operations"] or any(
        r["status"] == "failed" for r in report["results"]
    ):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
