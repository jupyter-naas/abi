import asyncio

from naas_abi_core.engine.call_context import (
    CallContext,
    current_call_context,
    service_account,
    use_call_context,
)
from naas_abi_core.services.agent.OpencodeAgent import (
    OpencodeAgent,
    OpencodeAgentConfiguration,
    OpencodeStartupError,
    _run_coroutine_sync,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        del args, kwargs
        self._session_created = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False

    async def get(self, url: str):
        if "/session/thread-1" in url:
            return _FakeResponse(404, {})
        return _FakeResponse(200, {})

    async def post(self, url: str, json=None):
        if url.endswith("/session"):
            self._session_created = True
            return _FakeResponse(200, {"id": "sess-1"})

        if url.endswith("/message"):
            if json and json.get("noReply"):
                return _FakeResponse(200, {"parts": []})
            return _FakeResponse(
                200,
                {
                    "parts": [
                        {"type": "text", "text": "done"},
                        {
                            "type": "tool_use",
                            "name": "read",
                            "input": {"path": "main.py"},
                        },
                    ]
                },
            )

        return _FakeResponse(500, {})


class _FakeSessionService:
    def __init__(self):
        self.calls = []

    async def get_or_create_session(self, **kwargs):
        self.calls.append(("get_or_create_session", kwargs))

        class _Session:
            id = "abi-session-id"

        return _Session()

    async def persist_message(self, session, role, parts):
        self.calls.append(("persist_message", {"role": role, "parts": parts}))

        class _Message:
            id = "message-id"
            session_id = session.id

        return _Message()

    async def persist_file_events(self, message, parts):
        self.calls.append(("persist_file_events", {"parts": parts}))


def test_invoke_returns_text_and_persists(monkeypatch):
    from naas_abi_core.services.agent import OpencodeAgent as module

    monkeypatch.setattr(module.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(OpencodeAgent, "start", lambda self: None)

    service = _FakeSessionService()
    agent = OpencodeAgent(
        configuration=OpencodeAgentConfiguration(
            workdir=".",
            port=4096,
            name="backend-coder",
            description="Backend coder",
            system_prompt="You are a coder",
        ),
        session_service=service,
    )

    result = agent.invoke("Do it", thread_id="thread-1")

    assert result == "done"
    assert any(call[0] == "get_or_create_session" for call in service.calls)
    assert any(call[0] == "persist_file_events" for call in service.calls)


def test_dynamic_port_is_assigned_when_missing():
    agent = OpencodeAgent(
        configuration=OpencodeAgentConfiguration(
            workdir=".",
            port=None,
            name="backend-coder",
            description="Backend coder",
        )
    )

    agent._ensure_port()

    assert isinstance(agent.conf.port, int)
    assert agent.conf.port > 0
    assert agent._is_port_available(agent.conf.port) is True


def test_start_fails_if_configured_port_is_busy(monkeypatch):
    from naas_abi_core.services.agent import OpencodeAgent as module

    agent = OpencodeAgent(
        configuration=OpencodeAgentConfiguration(
            workdir=".",
            port=4096,
            name="backend-coder",
            description="Backend coder",
        )
    )

    monkeypatch.setattr(agent, "_is_port_available", lambda port: False)
    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("busy")),
    )

    try:
        agent.start()
        assert False, "Expected OpencodeStartupError"
    except OpencodeStartupError as exc:
        assert "already in use" in str(exc)


def test_ensure_opencode_auth_file_from_engine_configuration(monkeypatch, tmp_path):
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )

    auth_path = tmp_path / "auth.json"

    class _Provider:
        id = "openrouter"
        key = "sk-test"
        metadata = {"env": "local"}

    class _Opencode:
        auth_file_path = str(auth_path)
        providers = [_Provider()]

    class _Conf:
        opencode = _Opencode()

    monkeypatch.setattr(
        EngineConfiguration,
        "load_configuration",
        classmethod(lambda cls: _Conf()),
    )

    OpencodeAgent._ensure_opencode_auth_file()

    assert auth_path.exists()
    content = auth_path.read_text(encoding="utf-8")
    assert '"openrouter"' in content
    assert '"type": "api"' in content
    assert '"key": "sk-test"' in content


def test_a_sync_run_inside_a_loop_keeps_the_callers_context():
    """``invoke`` from a running loop hops to a thread; the caller goes with it."""

    async def caller_seen():
        return current_call_context()

    async def invoke_from_a_loop():
        return _run_coroutine_sync(caller_seen())

    caller = CallContext(principal=service_account("api"))
    with use_call_context(caller):
        assert asyncio.run(invoke_from_a_loop()) == caller


def test_the_opencode_server_keeps_the_process_environment_out(tmp_path, monkeypatch):
    """OpenCode starts without a shell and without the process's own
    environment: its keys and service credentials stay where they are."""
    import json
    import stat

    import pytest

    record = tmp_path / "seen.json"
    fake = tmp_path / "opencode"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        f"json.dump({{'env': dict(os.environ), 'cwd': os.getcwd()}}, open({str(record)!r}, 'w'))\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("ENGINE_ONLY_SECRET", "kept-by-the-engine")
    monkeypatch.setattr(OpencodeAgent, "_ensure_opencode_auth_file_once", lambda *_: None)
    workdir = tmp_path / "work"
    agent = OpencodeAgent(
        configuration=OpencodeAgentConfiguration(
            workdir=str(workdir),
            port=None,
            name="coder",
            description="coder",
            opencode_bin=str(fake),
            startup_timeout=1,
        )
    )
    with pytest.raises(OpencodeStartupError):
        agent.start()
    seen = json.loads(record.read_text())
    assert "ENGINE_ONLY_SECRET" not in seen["env"]
    assert seen["cwd"] == str(workdir)


def test_opencode_permission_requests_keep_to_the_users_choice():
    """No permission is granted on the user's behalf: every request is refused."""
    sent: list[tuple[str, dict]] = []

    class _Client:
        async def post(self, url, json=None):
            sent.append((url, json))
            return _FakeResponse(200, {})

    agent = OpencodeAgent(
        configuration=OpencodeAgentConfiguration(
            workdir=".", port=4096, name="coder", description="coder"
        )
    )
    event = {"type": "permission.updated", "properties": {"id": "per_123"}}
    asyncio.run(agent._handle_event(_Client(), "ses_1", event))  # type: ignore[arg-type]
    assert sent == [
        ("http://127.0.0.1:4096/session/ses_1/permissions/per_123", {"response": "reject"})
    ]
    assert all(payload["response"] not in ("always", "once") for _, payload in sent)


def test_opencode_sessions_keep_to_their_server(monkeypatch):
    """A conversation that moves to another OpenCode server gets a session
    there, primed with the system prompt, never the old server's id."""
    from naas_abi_core.services.agent import OpencodeAgent as module

    posts: list[tuple[str, bool]] = []

    class _Client(_FakeAsyncClient):
        async def post(self, url: str, json=None):
            posts.append((url, bool(json and json.get("noReply"))))
            return await super().post(url, json=json)

    monkeypatch.setattr(module.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(OpencodeAgent, "start", lambda self: None)
    agent = OpencodeAgent(
        configuration=OpencodeAgentConfiguration(
            workdir=".",
            port=4096,
            name="coder",
            description="coder",
            system_prompt="You are a coder",
        )
    )
    assert agent.invoke("one", thread_id="thread-1") == "done"
    agent.conf.port = 4097
    assert agent.invoke("two", thread_id="thread-1") == "done"

    on_second = [(url, primed) for url, primed in posts if ":4097/" in url]
    assert ("http://127.0.0.1:4097/session", False) in on_second
    assert any(primed for _, primed in on_second)


def test_opencode_keeps_missing_provider_credentials_visible(monkeypatch, tmp_path):
    from naas_abi_core.services.agent import OpencodeAgent as module

    class _Opencode:
        auth_file_path = str(tmp_path / "auth.json")
        providers: list = []

    warned: list[str] = []
    monkeypatch.setattr(OpencodeAgent, "_opencode_configuration", staticmethod(_Opencode))
    monkeypatch.setattr(module, "warn_no_opencode_credentials", lambda: warned.append("x"))
    OpencodeAgent._ensure_opencode_auth_file()
    assert warned == ["x"]
    assert not (tmp_path / "auth.json").exists()
