from naas_abi_core.services.agent.OpencodeAgent import (
    OpencodeAgent,
    OpencodeAgentConfiguration,
    OpencodeStartupError,
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
