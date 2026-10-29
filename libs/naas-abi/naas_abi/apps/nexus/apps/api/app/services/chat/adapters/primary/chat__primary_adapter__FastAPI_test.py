"""The chat routes decide with IAM: conversations are personal, so a viewer reads
their own and writes none, and nobody reaches a conversation that is not theirs."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary import (
    chat__primary_adapter__dependencies as chat_dependencies,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary import (
    chat__primary_adapter__FastAPI as chat_api,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__dependencies import (
    get_chat_service,
    get_object_storage_service,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.port import (
    ChatAgentRecord,
    ChatConversationRecord,
    ChatMessageRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam

NOW = datetime(2026, 1, 1, 12, 0, 0)


class FakeChat:
    """Enough of ``ChatService`` for the routes: conversations kept in a dict."""

    def __init__(self) -> None:
        self.conversations: dict[str, ChatConversationRecord] = {}
        self.agents: dict[str, ChatAgentRecord] = {}
        self.completed: list[Any] = []
        self.deleted: list[str] = []

    def add(self, owner: str, conversation_id: str, workspace_id: str = "ws-1") -> None:
        self.conversations[conversation_id] = ChatConversationRecord(
            id=conversation_id,
            workspace_id=workspace_id,
            user_id=owner,
            title="Title",
            agent="aia",
            created_at=NOW,
            updated_at=NOW,
        )

    async def get_conversation_for_user(self, user_id, conversation_id):
        row = self.conversations.get(conversation_id)
        return row if row and row.user_id == user_id else None

    async def find_conversation(self, conversation_id):
        return self.conversations.get(conversation_id)

    async def list_conversations(self, user_id, workspace_id, limit, offset):
        return [
            c
            for c in self.conversations.values()
            if c.user_id == user_id and c.workspace_id == workspace_id
        ]

    async def create_conversation(
        self, user_id, workspace_id, title, agent, now, conversation_id=None
    ):
        self.add(user_id, conversation_id or "conv-new", workspace_id)
        return self.conversations[conversation_id or "conv-new"]

    async def list_messages(self, user_id, conversation_id):
        return [
            ChatMessageRecord(
                id="m-1",
                conversation_id=conversation_id,
                role="user",
                content="hello",
                agent=None,
                metadata_=None,
                created_at=NOW,
            )
        ]

    async def update_conversation(self, user_id, conversation_id, now, **fields):
        return None

    async def delete_conversation_with_messages(self, user_id, conversation_id):
        self.deleted.append(conversation_id)
        return True

    async def update_message_metadata(self, user_id, conversation_id, message_id, metadata):
        return True

    async def get_agent(self, agent_id):
        return self.agents.get(agent_id)

    async def complete_chat_request(self, user_id, request, now):
        self.completed.append((user_id, request.conversation_id))
        return SimpleNamespace(
            conversation_id=request.conversation_id or "conv-new",
            assistant_message_id="m-2",
            assistant_content="hi",
            assistant_agent=request.agent,
            context_sources=[],
            provider_used=None,
        )


class FakeAgents:
    async def list_workspace_agents(self, workspace_id):
        return []


class FakeDb:
    async def commit(self) -> None:
        return None


class FakeStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[str, str]] = []

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.puts.append((prefix, key))


class FakeJobs:
    created: list[dict[str, Any]] = []
    for_user: dict[str, SimpleNamespace] = {}

    def __init__(self, db) -> None:
        pass

    async def create_job(self, **fields):
        FakeJobs.created.append(fields)
        return SimpleNamespace(
            id=fields["job_id"],
            status="queued",
            embedding_model=fields["embedding_model"],
            embedding_dimension=fields["embedding_dimension"],
            **{k: fields[k] for k in ("conversation_id", "workspace_id", "user_id")},
            source_type=fields["source_type"],
            source_path=fields["source_path"],
        )

    async def get_job_for_user(self, job_id, user_id):
        job = FakeJobs.for_user.get(job_id)
        return job if job and job.user_id == user_id else None


@pytest.fixture
def world(team: NexusIam, monkeypatch: pytest.MonkeyPatch):
    chat = FakeChat()
    storage = FakeStorage()
    published: list[dict[str, Any]] = []
    FakeJobs.created = []
    FakeJobs.for_user = {}

    @contextmanager
    def bind(db):
        yield SimpleNamespace(chat=chat, agents=FakeAgents())

    class Session:
        async def __aenter__(self):
            return FakeDb()

        async def __aexit__(self, *exc):
            return False

    streamed: list[str] = []

    async def stream(request, current_user):
        streamed.append(current_user.id)
        return JSONResponse({"streamed": True})

    for module in (chat_api, chat_dependencies):
        monkeypatch.setattr(module, "bind_registry", bind)
    monkeypatch.setattr(chat_dependencies, "AsyncSessionLocal", Session)
    monkeypatch.setattr(chat_api, "stream_chat_response", stream)
    monkeypatch.setattr(chat_api, "ChatIngestionJobService", FakeJobs)
    monkeypatch.setattr(chat_api, "publish_chat_ingestion_job", published.append)

    app = FastAPI()
    app.include_router(chat_api.router, prefix="/api/chat")

    def current_user(request: Request) -> User:
        return User.model_construct(id=request.headers["x-user"], email="u@example.com")

    app.dependency_overrides[get_current_user_required] = current_user
    app.dependency_overrides[get_chat_service] = lambda: chat
    app.dependency_overrides[get_db] = lambda: FakeDb()
    app.dependency_overrides[get_object_storage_service] = lambda: storage
    client = TestClient(app, raise_server_exceptions=True)
    return SimpleNamespace(
        iam=team,
        chat=chat,
        storage=storage,
        published=published,
        streamed=streamed,
        client=client,
    )


def call(world, user: str, method: str, path: str, **kwargs):
    return world.client.request(method, path, headers={"x-user": user}, **kwargs)


# -- lists and reads: a viewer reads their own ---------------------------------


@pytest.mark.parametrize("user", ["viewer", "member", "admin", "owner"])
def test_every_role_lists_its_own_conversations(world, user: str) -> None:
    world.chat.add(user, f"conv-{user}")
    world.chat.add("someone", "conv-other")

    response = call(world, user, "GET", "/api/chat/conversations?workspace_id=ws-1")

    assert response.status_code == 200
    assert [c["id"] for c in response.json()] == [f"conv-{user}"]


def test_a_stranger_cannot_list(world) -> None:
    assert (
        call(world, "stranger", "GET", "/api/chat/conversations?workspace_id=ws-1").status_code
        == 403
    )


def test_a_viewer_reads_and_exports_their_own_conversation(world) -> None:
    world.chat.add("viewer", "conv-v")

    read = call(world, "viewer", "GET", "/api/chat/conversations/conv-v")
    export = call(world, "viewer", "POST", "/api/chat/conversations/conv-v/export", json={})

    assert read.status_code == 200
    assert [m["content"] for m in read.json()["messages"]] == ["hello"]
    assert export.status_code == 200


def test_nobody_reaches_a_conversation_that_is_not_theirs(world) -> None:
    world.chat.add("member", "conv-m")
    # Members of the workspace: there is no such conversation for them. Someone
    # with no role in it is told they have no access there.
    for user, status in (("owner", 404), ("admin", 404), ("viewer", 404), ("stranger", 403)):
        assert call(world, user, "GET", "/api/chat/conversations/conv-m").status_code == status
        assert call(world, user, "DELETE", "/api/chat/conversations/conv-m").status_code == status
        assert (
            call(world, user, "POST", "/api/chat/conversations/conv-m/export", json={}).status_code
            == status
        )
    assert world.chat.deleted == []


def test_a_conversation_of_a_workspace_the_user_left_is_closed(world) -> None:
    world.chat.add("stranger", "conv-old")

    assert call(world, "stranger", "GET", "/api/chat/conversations/conv-old").status_code == 403


# -- writes: members and up ----------------------------------------------------


def test_a_viewer_cannot_create_update_or_delete(world) -> None:
    world.chat.add("viewer", "conv-v")

    created = call(
        world, "viewer", "POST", "/api/chat/conversations", json={"workspace_id": "ws-1"}
    )
    updated = call(world, "viewer", "PATCH", "/api/chat/conversations/conv-v", json={"title": "x"})
    deleted = call(world, "viewer", "DELETE", "/api/chat/conversations/conv-v")
    metadata = call(
        world,
        "viewer",
        "PATCH",
        "/api/chat/conversations/conv-v/messages/m-1/metadata",
        json={},
    )

    assert [r.status_code for r in (created, updated, deleted, metadata)] == [403] * 4
    assert world.chat.deleted == []
    assert list(world.chat.conversations) == ["conv-v"]


@pytest.mark.parametrize("user", ["member", "admin", "owner"])
def test_members_and_up_manage_their_conversations(world, user: str) -> None:
    created = call(world, user, "POST", "/api/chat/conversations", json={"workspace_id": "ws-1"})
    assert created.status_code == 200
    conv = created.json()["id"]

    assert (
        call(
            world, user, "PATCH", f"/api/chat/conversations/{conv}", json={"title": "t"}
        ).status_code
        == 200
    )
    assert (
        call(
            world, user, "PATCH", f"/api/chat/conversations/{conv}/messages/m-1/metadata", json={}
        ).status_code
        == 200
    )
    assert call(world, user, "DELETE", f"/api/chat/conversations/{conv}").status_code == 200
    assert world.chat.deleted == [conv]


def test_a_stranger_cannot_create_in_the_workspace(world) -> None:
    response = call(
        world, "stranger", "POST", "/api/chat/conversations", json={"workspace_id": "ws-1"}
    )

    assert response.status_code == 403
    assert world.chat.conversations == {}


def test_chat_is_closed_when_the_feature_is_off_for_the_role(team: NexusIam, world) -> None:
    flags = FeatureFlagsConfig(
        enabled_features=["files"], role_baseline={"owner": ["files"], "member": ["files"]}
    )
    muted = NexusIam(flags)
    scope = muted.workspace("org-1", "ws-1")
    muted.grant("member", "member", scope)
    world.chat.add("member", "conv-m")

    with muted.installed():
        listed = call(world, "member", "GET", "/api/chat/conversations?workspace_id=ws-1")
        sent = call(
            world,
            "member",
            "POST",
            "/api/chat/complete",
            json={"message": "hi", "conversation_id": "conv-m"},
        )

    assert listed.status_code == 403
    assert sent.status_code == 403
    assert world.chat.completed == []


# -- turns: SendMessage ---------------------------------------------------------


def test_a_member_sends_a_message_in_their_conversation(world) -> None:
    world.chat.add("member", "conv-m")

    response = call(
        world,
        "member",
        "POST",
        "/api/chat/complete",
        json={"message": "hi", "conversation_id": "conv-m"},
    )

    assert response.status_code == 200
    assert world.chat.completed == [("member", "conv-m")]


def test_a_member_opens_a_conversation_with_a_first_message(world) -> None:
    response = call(
        world,
        "member",
        "POST",
        "/api/chat/complete",
        json={"message": "hi", "workspace_id": "ws-1"},
    )

    assert response.status_code == 200
    assert world.chat.completed == [("member", None)]


def test_a_viewer_cannot_send_to_their_conversation_nor_open_one(world) -> None:
    world.chat.add("viewer", "conv-v")

    existing = call(
        world,
        "viewer",
        "POST",
        "/api/chat/complete",
        json={"message": "hi", "conversation_id": "conv-v"},
    )
    opening = call(
        world,
        "viewer",
        "POST",
        "/api/chat/complete",
        json={"message": "hi", "workspace_id": "ws-1"},
    )
    streaming = call(
        world,
        "viewer",
        "POST",
        "/api/chat/stream",
        json={"message": "hi", "conversation_id": "conv-v"},
    )

    assert [r.status_code for r in (existing, opening, streaming)] == [403, 403, 403]
    assert world.chat.completed == []
    assert world.streamed == []


def test_a_stranger_cannot_send_into_the_workspace(world) -> None:
    complete = call(
        world,
        "stranger",
        "POST",
        "/api/chat/complete",
        json={"message": "hi", "workspace_id": "ws-1"},
    )
    stream = call(
        world,
        "stranger",
        "POST",
        "/api/chat/stream",
        json={"message": "hi", "workspace_id": "ws-1"},
    )

    assert complete.status_code == 403
    assert stream.status_code == 403
    assert world.chat.completed == [] and world.streamed == []


def test_a_member_streams_a_turn(world) -> None:
    world.chat.add("member", "conv-m")

    response = call(
        world,
        "member",
        "POST",
        "/api/chat/stream",
        json={"message": "hi", "conversation_id": "conv-m"},
    )

    assert response.status_code == 200
    assert world.streamed == ["member"]


def test_a_turn_cannot_borrow_the_workspace_of_another(world) -> None:
    """The conversation sits in ws-1; naming ws-2 in the body must not reach ws-2's settings."""
    world.iam.workspace("org-1", "ws-2")
    world.chat.add("member", "conv-m")

    response = call(
        world,
        "member",
        "POST",
        "/api/chat/complete",
        json={"message": "hi", "conversation_id": "conv-m", "workspace_id": "ws-2"},
    )

    assert response.status_code == 403
    assert world.chat.completed == []


def test_an_agent_of_another_workspace_cannot_be_run(world) -> None:
    """The agent row carries the provider key of its workspace: its own workspace decides."""
    world.iam.workspace("org-1", "ws-2")
    world.chat.agents["agent-2"] = ChatAgentRecord(
        id="agent-2",
        workspace_id="ws-2",
        name="Other",
        class_name=None,
        model_id="gpt",
        provider="openai",
    )
    world.chat.agents["agent-1"] = ChatAgentRecord(
        id="agent-1",
        workspace_id="ws-1",
        name="Mine",
        class_name=None,
        model_id="gpt",
        provider="openai",
    )
    world.chat.add("member", "conv-m")
    turn = {"message": "hi", "conversation_id": "conv-m"}

    foreign = call(world, "member", "POST", "/api/chat/complete", json={**turn, "agent": "agent-2"})
    foreign_stream = call(
        world, "member", "POST", "/api/chat/stream", json={**turn, "agent": "agent-2"}
    )
    own = call(world, "member", "POST", "/api/chat/complete", json={**turn, "agent": "agent-1"})

    assert foreign.status_code == 403
    assert foreign_stream.status_code == 403
    assert own.status_code == 200
    assert world.chat.completed == [("member", "conv-m")]


def test_a_module_agent_needs_its_module_scope(world) -> None:
    """Zero trust: a member runs a module's agent (remote or in-process) only
    once a policy grants that agent; another agent of the module stays refused."""
    for agent_id, class_name, provider in (
        ("remote-a", "acme.p/A", "remote"),
        ("remote-b", "acme.p/B", "remote"),
        ("abi", "naas_abi.agents.AbiAgent/AbiAgent", "abi"),
    ):
        world.chat.agents[agent_id] = ChatAgentRecord(
            id=agent_id,
            workspace_id="ws-1",
            name=agent_id,
            class_name=class_name,
            model_id=None,
            provider=provider,
        )
    world.chat.add("member", "conv-m")
    turn = {"message": "hi", "conversation_id": "conv-m"}

    def run(agent: str, user: str = "member"):
        return call(world, user, "POST", "/api/chat/complete", json={**turn, "agent": agent})

    assert run("remote-a").status_code == 403
    world.iam.allow_scope("member", ModuleScope("agent", "acme.p", "A"), "abi:org-1:ws-1")
    assert run("remote-a").status_code == 200
    assert run("remote-b").status_code == 403
    assert run("abi").status_code == 403


def test_iam_alone_decides_an_agent_and_no_role_holds_a_module_agent(world) -> None:
    """No workspace switch: an agent's stored ``enabled`` is not read. A module's
    agent is refused to an owner with no policy granting it (no role holds a
    module scope), and runs once one does; one the workspace built runs for who
    holds ``nexus:UseAgent``."""
    for agent_id, class_name, provider in (
        ("remote-a", "acme.p/A", "remote"),
        ("built", None, "openai"),
    ):
        world.chat.agents[agent_id] = ChatAgentRecord(
            id=agent_id,
            workspace_id="ws-1",
            name=agent_id,
            class_name=class_name,
            model_id="gpt",
            provider=provider,
        )

    def turn(user: str, agent: str):
        return call(
            world,
            user,
            "POST",
            "/api/chat/complete",
            json={"message": "hi", "conversation_id": f"conv-{user}", "agent": agent},
        )

    for user in ("member", "owner"):
        world.chat.add(user, f"conv-{user}")
        assert turn(user, "remote-a").status_code == 403, user
        assert turn(user, "built").status_code == 200, user
    world.iam.allow_scope("owner", ModuleScope("agent", "acme.p", "A"), "abi:org-1:ws-1")
    assert turn("owner", "remote-a").status_code == 200
    assert turn("member", "remote-a").status_code == 403


# -- file ingestion ------------------------------------------------------------


def _upload(world, user: str, conversation: str, **form):
    return call(
        world,
        user,
        "POST",
        f"/api/chat/conversations/{conversation}/files/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data=form,
    )


def _placed(world, service: str) -> list[str]:
    from naas_abi_core.engine.call_context import as_service_account

    with as_service_account("api"):
        return [p.id_key for p in world.iam.iam.list_placements(service)]


def test_a_viewer_cannot_add_files_to_a_conversation(world) -> None:
    world.chat.add("viewer", "conv-v")

    upload = _upload(world, "viewer", "conv-v")
    ingest = call(
        world,
        "viewer",
        "POST",
        "/api/chat/conversations/conv-v/files/ingest",
        json={"source_path": "naas_abi/my-drive/viewer/a.txt"},
    )

    assert upload.status_code == 403
    assert ingest.status_code == 403
    assert world.storage.puts == []
    assert FakeJobs.created == [] and world.published == []


def test_a_member_uploads_and_the_index_is_placed_in_the_workspace(world) -> None:
    world.chat.add("member", "conv-m")

    response = _upload(world, "member", "conv-m")

    assert response.status_code == 200, response.text
    assert world.storage.puts == [("naas_abi/my-drive/member/uploads", "notes.txt")]
    assert [j["workspace_id"] for j in FakeJobs.created] == ["ws-1"]
    assert len(world.published) == 1
    vector_keys = _placed(world, "vector_store")
    assert "chat_conv-m" in vector_keys and "chat_conv-m/*" in vector_keys
    assert any(key.startswith("embeddings%3Aws-1%3A") for key in _placed(world, "cache"))


def test_upload_to_a_new_conversation_needs_the_right_to_create_it(world) -> None:
    created = _upload(world, "member", "conv-new", workspace_id="ws-1")
    refused = _upload(world, "viewer", "conv-v-new", workspace_id="ws-1")
    nowhere = _upload(world, "member", "conv-lost")

    assert created.status_code == 200
    assert refused.status_code == 403
    assert nowhere.status_code == 404
    assert list(world.chat.conversations) == ["conv-new"]


def test_the_workspace_named_by_the_upload_does_not_move_the_conversation(world) -> None:
    world.chat.add("member", "conv-m")

    response = _upload(world, "member", "conv-m", workspace_id="ws-elsewhere")

    assert response.status_code == 200
    assert [j["workspace_id"] for j in FakeJobs.created] == ["ws-1"]


def test_an_ingestion_job_is_read_by_its_owner_only(world) -> None:
    now = NOW
    FakeJobs.for_user["job-1"] = SimpleNamespace(
        id="job-1",
        conversation_id="conv-v",
        workspace_id="ws-1",
        user_id="viewer",
        source_path="p",
        status="ready",
        progress=100,
        cache_hit=False,
        file_sha256="x",
        collection_name="chat_conv-v",
        chunks_count=1,
        error_code=None,
        error_message=None,
        attempt=1,
        max_attempts=3,
        created_at=now,
        updated_at=now,
        started_at=None,
        finished_at=None,
    )

    owner = call(world, "viewer", "GET", "/api/chat/ingestion-jobs/job-1")
    other = call(world, "member", "GET", "/api/chat/ingestion-jobs/job-1")

    assert owner.status_code == 200
    assert other.status_code == 404


# -- local model runtime status ---------------------------------------------------


def test_the_runtime_status_is_read_by_every_role_but_only_the_platform_picks_the_address(
    world, monkeypatch: pytest.MonkeyPatch
) -> None:
    probed: list[str | None] = []

    async def status(endpoint=None):
        probed.append(endpoint)
        return {"status": "offline", "models": []}

    monkeypatch.setattr(chat_api, "check_ollama_status", status)
    world.iam.platform_admin("root")

    assert call(world, "viewer", "GET", "/api/chat/ollama/status").status_code == 200
    assert (
        call(
            world, "admin", "GET", "/api/chat/ollama/status?endpoint=http://169.254.169.254"
        ).status_code
        == 403
    )
    assert probed == [None]
    assert (
        call(
            world, "root", "GET", "/api/chat/ollama/status?endpoint=http://ollama:11434"
        ).status_code
        == 200
    )
    assert probed == [None, "http://ollama:11434"]
