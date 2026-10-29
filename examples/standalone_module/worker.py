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

from naas_abi_proto.dataset.rows import decode_row, encode_row
from naas_abi_proto.vector_store.values import decode_object, encode_object
from naas_abi_sdk import RPCError
from naas_abi_sdk.call_context import inside
from naas_abi_sdk.catalog import OPERATIONS
from naas_abi_sdk.module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
    run_module,
)
from naas_abi_sdk.permissions import default_manifest

DEPENDENCIES = ModuleDependencies(services=(*OPERATIONS, "bus"))
# Bus topics have no default: the manifest names the ones this module uses.
BUS_TOPICS = ("demo.inbox", "demo.reply", "demo.jobs", "demo.outbox")

# The identity the demo engine issues the worker's token for (engine_host): a module
# loads schemas only under module/<its own identity>/.
TOKEN_IDENTITY = "standalone-demo"
# A Nexus workspace's container: invitations and bindings name one.
DEMO_WORKSPACE = "abi:nexus:organization/org-demo/nexus:workspace/ws-demo"


class ABIModule(BaseModule):
    module_id = "standalone-demo"

    class Configuration(ModuleConfiguration):
        pass

    dependencies = DEPENDENCIES
    permissions = {
        **default_manifest(DEPENDENCIES),
        "statements": [
            *default_manifest(DEPENDENCIES)["statements"],
            {
                # The default grants sending only: the platform keeps a copy of
                # the mail it sends (sign-in codes included), so reading it back
                # is asked for by name.
                "sid": "DemoKeptMail",
                "effect": "Allow",
                "actions": ["email:ListSent", "email:GetSent", "email:DeleteSent"],
                # The platform's and those kept in any container.
                "resources": ["abi:email:message/*", "abi:*/email:message/*"],
            },
            {
                "sid": "DemoBus",
                "effect": "Allow",
                "actions": ["bus:*"],
                "resources": [f"abi:bus:topic/{topic}" for topic in BUS_TOPICS],
            },
        ],
    }
    # Actions of its own (service standalone_demo), with a container type: the
    # module registers a project, makes calls inside it and deletes it.
    iam_catalog = {
        "resource_types": [
            {"name": "project", "container": True},
            {"name": "note"},
        ],
        "actions": [
            {
                "name": "CreateProject",
                "level": "write",
                "resource_types": ["project"],
                "creates": True,
            },
            {
                "name": "DeleteProject",
                "level": "admin",
                "resource_types": ["project"],
                "deletes": True,
            },
            {"name": "ReadNote", "level": "read", "resource_types": ["note"]},
        ],
    }

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
        assert 0 < (await call("get_ttl")).seconds <= 60
        assert (
            "demo"
            in (await self.call("keyvalue", "list_keys", prefix="de", limit=10)).keys
        )
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
        assert (
            "demo"
            in (await self.call("cache", "list_keys", prefix="de", limit=10)).keys
        )
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
        # A module's secrets are named after it: that is all its manifest
        # grants by default.
        key = f"{self.module_id}/DEMO_VALUE"
        await self.call("secret", "set", key=key, value="fixture-value")
        assert (
            await self.call("secret", "get", key=key)
        ).found.value == "fixture-value"
        await self.call("secret", "set", key=key, value="updated")
        entries = (await self.call("secret", "list")).found.entries
        assert any(e.key == key and e.value == "updated" for e in entries)
        await self.call("secret", "remove", key=key)
        assert not (await self.call("secret", "get", key=key)).found.HasField("value")

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
        await self.call(
            "email",
            "send",
            to_email="recipient@example.invalid",
            from_email="demo@example.invalid",
            subject="Delete me",
            text_body="Read back, then deleted.",
        )
        sent = (await self.call("email", "list_sent", limit=10)).messages.messages
        assert {m.subject for m in sent} >= {"Standalone module", "Delete me"}
        doomed = next(m.message_id for m in sent if m.subject == "Delete me")
        message = (await self.call("email", "get_sent", message_id=doomed)).message
        assert message.summary.subject == "Delete me"
        assert b"Read back, then deleted." in message.raw
        await self.call("email", "delete_sent", message_id=doomed)
        assert doomed not in {
            m.message_id
            for m in (await self.call("email", "list_sent", limit=10)).messages.messages
        }

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
        # Recorded under the caller's identity (its service account), not "demo".
        me = self.engine.principal_id
        events = (await self.call("activity_log", "query", actor_id=me)).events.events
        assert any(e.event_type == "exercise" for e in events)
        actors = (await self.call("activity_log", "list_actors")).actors.actors
        assert me in actors
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
            t.event_type == "demo" and t.last_seq == event.seq
            for t in (await self.call("event", "list_event_types")).types.types
        )
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
        await call("write", rows=[encode_row({"id": 1, "value": "created"})], mode=1)
        await call("write", rows=[encode_row({"id": 1, "value": "updated"})], mode=3)
        result = await self.call(
            "dataset", "query", sql="SELECT * FROM demo", namespace="default"
        )
        rows = [decode_row(row) for row in result.query_result.rows]
        assert len(rows) == 1 and rows[0]["value"] == "updated"
        assert (await call("inlined_row_count")).count >= 0
        await call("flush")
        await call("compact")
        assert (await self.call("dataset", "list_snapshots")).snapshots.items
        version = await self.call("dataset", "namespace_version", namespace="default")
        assert version.HasField("version") and version.version > 0
        unused = await self.call("dataset", "namespace_version", namespace="unused")
        assert not unused.HasField("version")
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
                    "metadata": encode_object({"value": "created"}),
                }
            ],
        )
        assert (await call("count_vectors")).count == 1
        info = (await call("get_collection_info")).info
        assert (info.name, info.dimension, info.size) == ("demo", 3, 1)
        page = (await call("list_vectors", limit=10)).page
        assert [d.id for d in page.documents] == [vid]
        assert (
            await call("get_vector", vector_id=vid, include_vector=True)
        ).found.document.id == vid
        assert (
            await call("search", query_vector=[1, 0, 0], k=1, include_metadata=True)
        ).results.results[0].id == vid
        await call(
            "update_vector", vector_id=vid, metadata=encode_object({"value": "updated"})
        )
        found = (await call("get_vector", vector_id=vid)).found.document
        assert decode_object(found.metadata)["value"] == "updated"
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
        assert any(
            e.id == wid
            for e in (
                await self.call(domain, "list_all_environments")
            ).environments.environments
        )
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
        # create_repo only creates: a name that exists, in any case, is refused.
        created = await self.call(
            domain, "create_repo", owner="demo", name="fresh", auto_init=True
        )
        assert not created.HasField("error") and created.repo.name == "fresh"
        try:
            await self.call(domain, "create_repo", owner="demo", name="FRESH")
        except RPCError as exc:
            assert exc.code == "REPO_EXISTS", exc
        else:
            raise AssertionError("create_repo returned a repository that exists")

        async def call(op, **fields):
            return await self.call(domain, op, repo_id="demo/repo", **fields)

        # Granting access to a repository is an admin action: the default
        # manifest denies it, so a module cannot make anyone a collaborator.
        try:
            await call("add_collaborator", username="demo", permission="write")
        except RPCError as exc:
            assert exc.code == "PERMISSION_DENIED", exc
            self.seen.add((domain, "add_collaborator"))
        else:
            raise AssertionError("a module's default manifest granted add_collaborator")
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
        await self.call(domain, "delete_repo", repo_id="demo/repo")
        assert not any(
            r.name == repo.name
            for r in (await self.call(domain, "list_repos")).repos.repos
        )

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
        # A module's ontology: stored once, nothing written for the same content, and
        # refused under another module's id (its manifest asks LoadSchema on its own
        # sources only, so another's does not exist for it) or when it is not Turtle.
        source = f"module/{TOKEN_IDENTITY}/demo.ttl"
        ontology = b"<urn:demo:Thing> a <http://www.w3.org/2002/07/owl#Class> .\n"
        load = {"source": source, "content_ttl": ontology}
        assert (await self.call(domain, "load_schema", **load)).changed
        assert not (await self.call(domain, "load_schema", **load)).changed
        for refused, code, content in (
            ("module/another-module/demo.ttl", "NOT_FOUND", ontology),
            (source, "INVALID_ARGUMENT", b"this is not turtle"),
        ):
            try:
                await self.call(
                    domain, "load_schema", source=refused, content_ttl=content
                )
            except RPCError as exc:
                assert exc.code == code, exc
            else:
                raise AssertionError(f"load_schema of {refused} was not refused")

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
        spec = await self.call("document", "collection_spec", collection="exercise")
        assert spec.spec.name == "exercise"
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
        # Listing namespaces is reserved to the platform identities: a module is
        # refused, by its namespace-bound SDK client or else by the engine.
        try:
            await self.call("document", "namespaces")
        except PermissionError:
            self.seen.add(("document", "namespaces"))
        except RPCError as exc:
            assert exc.code == "PERMISSION_DENIED", exc.code
            self.seen.add(("document", "namespaces"))
        else:
            raise AssertionError("document.namespaces answered a module identity")

    async def _broker_refuses(self, subject: str) -> bool:
        """Whether the broker refuses this module's request on ``subject``: a
        publish it may not make is a permissions violation on its connection."""
        nc = await self.engine._client._transport.connect()
        errors: list[str] = []

        async def on_error(error):
            errors.append(str(error))

        previous, nc._error_cb = nc._error_cb, on_error
        try:
            try:
                await nc.request(subject, b"", timeout=1)
            except Exception:  # noqa: BLE001 - refused publishes get no reply
                pass
            await asyncio.sleep(0.1)
        finally:
            nc._error_cb = previous
        return any("ermissions violation" in e for e in errors)

    async def containers(self):
        """The module registers a container of its own type, finds it, makes a
        call inside it, and deletes it. A Nexus workspace is not its to make."""
        project = await self.call(
            "iam",
            "register_container",
            service="standalone_demo",
            type="project",
            id="p-1",
        )
        name = project.container.name
        assert name == "abi:standalone_demo:project/p-1", name
        assert project.container.parent == "abi:"
        found = await self.call(
            "iam", "get_container", service="standalone_demo", type="project", id="p-1"
        )
        assert found.name == name
        # Inside it, IAM names what the module declares in the project.
        with inside(name):
            note = await self.call(
                "iam",
                "authorize_declared",
                action="standalone_demo:ReadNote",
                resource_type="note",
                parts=["n-1"],
            )
        assert note.resource == f"{name}/standalone_demo:note/n-1", note.resource
        assert note.decision.allowed
        # IAM lists a container type from its registry, as the caller: the
        # project it holds; a type with no lister is offered as wildcards.
        projects = await self.call(
            "iam", "list_resources", service="standalone_demo", type="project"
        )
        assert projects.listed and [i.name for i in projects.items] == [name], projects
        notes = await self.call(
            "iam", "list_resources", service="standalone_demo", type="note", scope=name
        )
        assert not notes.listed and not notes.items, notes
        try:
            await self.call(
                "iam",
                "register_container",
                service="nexus",
                type="workspace",
                id="ws-demo",
                parent="abi:nexus:organization/org-demo",
            )
        except RPCError as exc:
            assert exc.code in ("NOT_FOUND", "PERMISSION_DENIED", "INVALID_ARGUMENT"), (
                exc
            )
        else:
            raise AssertionError("a module registered a Nexus workspace")
        deleted = await self.call(
            "iam",
            "delete_container",
            service="standalone_demo",
            type="project",
            id="p-1",
        )
        assert deleted.deleted
        gone = await self.call(
            "iam", "get_container", service="standalone_demo", type="project", id="p-1"
        )
        assert gone.name == ""

    async def iam(self):
        """A module asks IAM about itself; administering IAM is refused to it,
        by the broker for most operations and by IAM for the rest."""
        from naas_abi_proto.iam.v1 import iam_pb2 as pb

        own = "abi:document:collection/standalone-demo/runs"
        other = "abi:document:collection/someone-else/runs"
        assert (
            await self.call("iam", "authorize", action="document:Find", resource=own)
        ).decision.allowed
        assert not (
            await self.call("iam", "authorize", action="document:Find", resource=other)
        ).decision.allowed
        filtered = await self.call(
            "iam", "filter", action="document:Find", resources=[other, own]
        )
        assert list(filtered.allowed) == [own]
        # An action another module declares (discovery_demo's provider, approved
        # before this worker runs): IAM names the brief and refuses it to a
        # module its manifest does not grant.
        declared = await self.call(
            "iam",
            "authorize_declared",
            action="demo_research:ExportBrief",
            resource_type="brief",
            parts=["q3"],
        )
        assert not declared.decision.allowed
        assert declared.resource == "abi:demo_research:brief/q3"
        await self.containers()
        # What it may grant at the platform: what it holds, its own collections
        # among it.
        grantable = await self.call("iam", "grantable", scope="abi:")
        held = {
            r
            for c in grantable.catalogs
            if c.service == "document"
            for a in c.actions
            if a.action == "document:Find"
            for r in a.resources
        }
        assert any(r.startswith("${scope}/document:collection/") for r in held), held
        # The broker offers a module IAM's self-service and read-only questions
        # (token, jwks, manifest, authorize, filter, grantable) and no more: the lists and
        # every change are refused before they reach IAM, whoever's token the
        # module holds (an agent host reads its caller's).
        at_broker = [
            "list_principals",
            "list_groups",
            "list_policies",
            "list_attachments",
            "list_placements",
            "list_keys",
            "list_manifests",
        ]

        user, group = "usr_" + "0" * 26, "grp_" + "0" * 26
        document_json = json.dumps(
            {
                "version": "2026-10-13",
                "statements": [
                    {"effect": "Allow", "actions": ["*"], "resources": ["*"]}
                ],
            }
        )
        refused = {
            "explain": {"action": "document:Find", "resource": own},
            "ensure_user": {"issuer": "https://idp.example", "subject": "demo"},
            "create_service_account": {"name": "ci/demo"},
            "get_principal": {"principal_id": user},
            "suspend_principal": {"principal_id": user},
            "resume_principal": {"principal_id": user},
            "delete_principal": {"principal_id": user},
            "create_group": {"name": "demo"},
            "get_group": {"group_id": group},
            "delete_group": {"group_id": group},
            "add_group_member": {"group_id": group, "member_id": user},
            "remove_group_member": {"group_id": group, "member_id": user},
            "list_group_members": {"group_id": group},
            "map_idp_group": {
                "provider": "acme",
                "claim_value": "Sales",
                "group_id": group,
            },
            "unmap_idp_group": {
                "provider": "acme",
                "claim_value": "Sales",
                "group_id": group,
            },
            "list_idp_group_mappings": {"group_id": group},
            "create_policy": {"name": "everything", "document_json": document_json},
            "get_policy": {"policy_id": "builtin.platform_admin"},
            "update_policy": {"policy_id": "builtin.viewer", "expected_revision": 1},
            "delete_policy": {"policy_id": "builtin.viewer"},
            # Sub-policies: deriving one from a built-in policy, moving one
            # under another, and listing those below a policy are an
            # administrator's; the broker refuses each to a module.
            "list_sub_policies": {"policy_id": "builtin.viewer"},
            "attach_policy": {
                "policy_id": "builtin.platform_admin",
                "principal_id": user,
            },
            "detach_policy": {
                "policy_id": "builtin.platform_admin",
                "principal_id": user,
            },
            "put_placement": {
                "placement": pb.Placement(
                    service="document", id_key="standalone-demo", container="abi:"
                )
            },
            "delete_placement": {"service": "document", "id_key": "standalone-demo"},
            "register_catalog": {
                "catalog": pb.ActionCatalog(
                    service="standalone_demo",
                    version=1,
                    resource_types=[pb.ResourceType(name="item", id="opaque")],
                    actions=[
                        pb.ActionSpec(
                            name="GetItem", level="read", resource_types=["item"]
                        )
                    ],
                )
            },
        }
        refused.update(
            {
                "find_service_account": {"name": "engine"},
                "create_key": {"principal_id": user},
                "revoke_key": {"principal_id": user, "key_id": "a" * 16},
                "revoke_tokens": {"principal_id": user},
                # A token exchange is offered to every module (it renews the
                # delegation it holds), and refused to one that holds no
                # iam:ExchangeToken for the audience.
                "exchange_token": {
                    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                    "subject_token": user,
                    "subject_token_type": "urn:abi:params:oauth:token-type:session",
                    "audience": "abi:delegated:agent",
                },
                # Invitations: pending grants and IdP group bindings are an
                # administrator's, never a module's.
                "create_pending_grant": {
                    "provider": "acme",
                    "email": "bob@example.com",
                    "policy_id": "builtin.member",
                    "scope": DEMO_WORKSPACE,
                },
                "list_pending_grants": {"provider": "acme"},
                "revoke_pending_grant": {"grant_id": "pgr_" + "0" * 26},
                "claim_pending_grants": {"principal_id": user},
                "bind_idp_group": {
                    "provider": "acme",
                    "claim_value": "Sales",
                    "policy_id": "builtin.member",
                    "scope": DEMO_WORKSPACE,
                },
                "unbind_idp_group": {
                    "provider": "acme",
                    "claim_value": "Sales",
                    "policy_id": "builtin.member",
                    "scope": DEMO_WORKSPACE,
                },
                "list_idp_bindings": {"provider": "acme"},
                "get_manifest": {"principal_id": user},
                "approve_manifest": {"principal_id": user},
                "reject_manifest": {"principal_id": user},
                # A module submits its own manifest, never another module's.
                "submit_manifest": {
                    "module_id": "someone-else",
                    "project": "default",
                    "document_json": document_json,
                },
            }
        )
        offered = (
            "find_service_account",
            "get_manifest",
            "submit_manifest",
            "exchange_token",
        )
        at_broker += [operation for operation in refused if operation not in offered]
        for operation in at_broker:
            assert await self._broker_refuses(f"abi.iam.v1.{operation}"), operation
            self.seen.add(("iam", operation))
        for operation, fields in refused.items():
            if operation not in offered:
                continue
            try:
                await self.call("iam", operation, **fields)
            except RPCError as exc:
                assert exc.code in ("NOT_FOUND", "PERMISSION_DENIED"), (operation, exc)
                self.seen.add(("iam", operation))
            else:
                raise AssertionError(f"iam.{operation} answered a module identity")
        # The JWKS is public; a key that is not one is refused.
        jwks = json.loads((await self.call("iam", "jwks")).jwks_json)
        assert jwks["issuer"].startswith("urn:abi:engine:") and jwks["keys"]
        try:
            await self.call("iam", "token", key="abi_sk_aaaaaaaaaaaaaaaa_not-a-key")
        except RPCError as exc:
            assert exc.code == "UNAUTHENTICATED", exc
            self.seen.add(("iam", "token"))
        else:
            raise AssertionError("iam.token exchanged an unknown key")

    async def identity(self):
        """The module declares identity, so its approved manifest reaches it,
        but the demo engine has no provider: it lists none, and every sign-in
        operation is refused, for an unknown provider or a token no provider
        issued."""
        assert not (await self.call("identity", "list_providers")).providers
        challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        refused = {
            "get_provider": {"name": "acme"},
            "verify_token": {"token": "not.a.token"},
            "authenticate": {"token": "not.a.token"},
            "authorization_url": {
                "provider": "acme",
                "redirect_uri": "https://abi.example/callback",
                "state": "state",
                "nonce": "nonce",
                "code_challenge": challenge,
            },
            "exchange_code": {
                "provider": "acme",
                "code": "code",
                "code_verifier": "v" * 43,
                "redirect_uri": "https://abi.example/callback",
                "nonce": "nonce",
            },
            "refresh": {
                "provider": "acme",
                "refresh_token": "r",
                "principal_id": "usr_x",
            },
            "revoke": {"provider": "acme", "refresh_token": "r"},
            "end_session_url": {"provider": "acme"},
            "provision_user": {"provider": "acme", "email": "bob@example.com"},
            "find_provisioned_user": {"provider": "acme", "email": "bob@example.com"},
        }
        for operation, fields in refused.items():
            try:
                await self.call("identity", operation, **fields)
            except RPCError as exc:
                assert exc.code in (
                    "NOT_FOUND",
                    "PERMISSION_DENIED",
                ) or exc.code.startswith("TOKEN_"), (operation, exc)
                self.seen.add(("identity", operation))
            else:
                raise AssertionError(f"identity.{operation} answered a module identity")

    async def model_registry(self):
        from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb

        async def call(operation, **fields):
            return await self.call("model_registry", operation, **fields)

        models = await call("list_models")
        assert {m.ref.canonical_id for m in models.models} >= {
            "demo-chat",
            "demo-embedding",
        }
        resolved = await call(
            "resolve", ref=pb.ModelRef(canonical_id="demo-chat", kind="chat")
        )
        chat = pb.ChatRequest(
            ref=resolved.model.ref,
            messages=[pb.ChatMessage(type="human", data_json=b'{"content":"hello"}')],
        )
        response = await call("chat", ref=chat.ref, messages=chat.messages)
        assert (
            json.loads(response.message.data_json)["content"] == "remote model answer"
        )
        opened = await call("stream_open", chat=chat)
        content = []
        try:
            for sequence in range(100):
                response = await call(
                    "stream_next", stream_id=opened.stream_id, sequence=sequence
                )
                if response.done:
                    break
                content.append(json.loads(response.chunk.data_json)["content"])
            assert "".join(content) == "remote model answer"
        finally:
            await call("stream_close", stream_id=opened.stream_id)
        response = await call(
            "embed",
            ref=pb.ModelRef(canonical_id="demo-embedding", kind="embedding"),
            texts=["hello"],
            query=True,
        )
        assert len(response.vectors[0].values) == 8

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
    token = os.environ["ABI_SERVICE_KEY"]
    report = await run_module(
        ABIModule, url=os.environ["ABI_NATS_URL"], token=token, timeout=30
    )
    report.update(
        worker_pid=os.getpid(),
        packages=sorted(d.metadata["Name"] for d in importlib.metadata.distributions()),
        core_installed=False,
        unsupported=[
            "publishing models from SDK provider modules",
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
