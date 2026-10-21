"""Running engine tools from a module: the facade and the LangChain proxy.

The engine's side (who may run what) is core's; here the request carries only names,
JSON and a deadline, a failure keeps its code, and a proxy holds no credential.
"""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb

from naas_abi_sdk.services.errors import (
    ToolExecutionError,
    ToolNotFound,
    ToolPermissionDenied,
)
from naas_abi_sdk.services.tool_registry import ToolRegistryService
from naas_abi_sdk.transport import RPCError

CREDENTIAL = "ghp_platform_token_that_no_module_may_read"


def definition(name="open_issue", *, remote=False):
    return pb.ToolDefinition(
        id=f"acme.github/{name}@1",
        namespace="acme.github",
        name=name,
        version="1",
        module="acme.github",
        description="Open an issue in a repository.",
        input_schema_json=json.dumps(
            {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            }
        ).encode(),
        requirements=pb.ToolRequirements(
            config=[pb.ConfigRequirement(key="access_token", secret=True)]
        ),
        remote=remote,
    )


def registry(result=b'{"number": 7}', error=None):
    client = AsyncMock()
    if error is not None:
        client.invoke_tool.side_effect = error
    else:
        client.invoke_tool.return_value = pb.InvokeToolResponse(result_json=result)
    client.get_tool.return_value = pb.GetToolResponse(
        tool=pb.ToolEntry(
            definition=definition(), availability=pb.ToolAvailability(available=True)
        )
    )
    return ToolRegistryService(client), client


def test_invoke_sends_names_json_and_the_deadline_never_a_value():
    service, client = registry()

    result = asyncio.run(
        service.invoke(
            "acme.github/open_issue",
            {"title": "bug"},
            config={"base_url": "https://ghe.example"},
            secrets={"access_token": "GITHUB_ACCESS_TOKEN"},
            timeout=30,
        )
    )

    assert result == {"number": 7}
    request = client.invoke_tool.call_args.args[0]
    assert request.tool == "acme.github/open_issue"
    assert json.loads(request.arguments_json) == {"title": "bug"}
    assert json.loads(request.config_json) == {"base_url": "https://ghe.example"}
    assert dict(request.secret_refs) == {"access_token": "GITHUB_ACCESS_TOKEN"}
    assert client.invoke_tool.call_args.kwargs == {"timeout": 30, "grace": 5.0}


def test_invoke_with_nothing_but_a_reference():
    service, client = registry(b'"done"')

    assert asyncio.run(service.invoke("acme.github/open_issue", version="1")) == "done"

    request = client.invoke_tool.call_args.args[0]
    assert (request.version, request.arguments_json) == ("1", b"{}")
    assert request.config_json == b"" and dict(request.secret_refs) == {}


@pytest.mark.parametrize(
    "arguments, error",
    [
        ({"ref": ""}, ValueError),
        ({"timeout": 0}, ValueError),
        ({"timeout": 301}, ValueError),
        ({"timeout": float("nan")}, ValueError),
        ({"arguments": {"x": float("nan")}}, ValueError),
        ({"arguments": {"x": object()}}, ValueError),
        ({"config": {"x": b"bytes"}}, ValueError),
        ({"arguments": {"x": "y" * (256 * 1024)}}, ValueError),
        ({"secrets": {"k": "S"} | {f"k{i}": "S" for i in range(16)}}, ValueError),
        ({"secrets": {"key": 3}}, TypeError),
        ({"secrets": {3: "NAME"}}, TypeError),
    ],
)
def test_invoke_refuses_what_the_engine_would_before_sending(arguments, error):
    service, client = registry()
    call = {"ref": "acme.github/open_issue"} | arguments

    with pytest.raises(error):
        asyncio.run(service.invoke(call.pop("ref"), **call))

    client.invoke_tool.assert_not_called()


@pytest.mark.parametrize(
    "code, expected",
    [
        ("TOOL_NOT_FOUND", ToolNotFound),
        ("PERMISSION_DENIED", ToolPermissionDenied),
        ("TOOL_ERROR", ToolExecutionError),
    ],
)
def test_a_failure_keeps_its_code_and_a_domain_class(code, expected):
    service, _ = registry(error=RPCError(code, "refused"))

    with pytest.raises(expected) as raised:
        asyncio.run(service.invoke("acme.github/open_issue", {"title": "x"}))

    assert raised.value.code == code


def test_other_codes_stay_service_errors():
    from naas_abi_sdk.services.errors import ServiceError

    service, _ = registry(error=RPCError("RESOURCE_EXHAUSTED", "busy"))

    with pytest.raises(ServiceError) as raised:
        asyncio.run(service.invoke("acme.github/open_issue", {"title": "x"}))

    assert raised.value.code == "RESOURCE_EXHAUSTED"


# ----------------------------------------------------------------- the proxy
def test_a_proxy_runs_the_tool_on_the_engine_with_fixed_secret_names():
    pytest.importorskip("langchain_core")
    service, client = registry(b'"opened #7"')

    async def scenario():
        tool = await service.as_tool(
            "acme.github/open_issue",
            secrets={"access_token": "GITHUB_ACCESS_TOKEN"},
            config={"base_url": "https://ghe.example"},
        )
        assert tool.name == "open_issue"
        assert tool.description == "Open an issue in a repository."
        assert tool.args_schema["required"] == ["title"]
        return await tool.ainvoke({"title": "bug"})

    assert asyncio.run(scenario()) == "opened #7"
    request = client.invoke_tool.call_args.args[0]
    assert request.tool == "acme.github/open_issue@1"
    assert json.loads(request.arguments_json) == {"title": "bug"}
    assert dict(request.secret_refs) == {"access_token": "GITHUB_ACCESS_TOKEN"}
    assert json.loads(request.config_json) == {"base_url": "https://ghe.example"}


def test_a_proxy_from_a_search_match_and_a_sync_call_from_another_thread():
    pytest.importorskip("langchain_core")
    from naas_abi_sdk.services.tool_registry import (
        ToolAvailability,
        ToolMatch,
    )
    from naas_abi_sdk.services.tool_registry import (
        _definition as to_definition,
    )

    service, client = registry(b'{"issue": 7}')

    async def scenario():
        match = ToolMatch(to_definition(definition()), ToolAvailability(True), 0.9)
        tool = await service.as_tool(match, name="github issue!")
        assert tool.name == "github_issue_"
        return await asyncio.to_thread(tool.invoke, {"title": "bug"})

    assert json.loads(asyncio.run(scenario())) == {"issue": 7}


def test_a_failure_reaches_the_model_as_the_tools_output():
    pytest.importorskip("langchain_core")
    service, _ = registry(
        error=RPCError("PERMISSION_DENIED", "Caller may not run this tool")
    )

    async def scenario():
        tool = await service.as_tool("acme.github/open_issue")
        return await tool.ainvoke({"title": "bug"})

    assert "Caller may not run this tool" in asyncio.run(scenario())


def test_a_proxy_of_a_module_tool_is_refused():
    pytest.importorskip("langchain_core")
    from naas_abi_sdk.engine_tools import engine_tool
    from naas_abi_sdk.services.tool_registry import _definition as to_definition

    service, _ = registry()

    with pytest.raises(ValueError, match="served by a module"):
        engine_tool(service, to_definition(definition(remote=True)))


def test_the_proxy_holds_no_credential():
    pytest.importorskip("langchain_core")
    service, _ = registry()

    async def scenario():
        return await service.as_tool(
            "acme.github/open_issue", secrets={"access_token": "GITHUB_ACCESS_TOKEN"}
        )

    tool = asyncio.run(scenario())

    assert CREDENTIAL not in repr(tool.args_schema) + repr(tool.description)
    assert "GITHUB_ACCESS_TOKEN" not in tool.description


def test_an_sdk_agent_calls_a_tool_whose_schema_is_a_json_schema_dict():
    """Regression: ``call_tools`` read a tool's fields from a pydantic input model, so
    an engine tool (its ``args_schema`` is the definition's JSON Schema) failed with
    ``KeyError: 'properties'`` before it ran."""
    pytest.importorskip("langgraph.graph")
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    from naas_abi_sdk.agents import Agent, AgentConfiguration

    class Scripted(BaseChatModel):
        calls: int = 0

        @property
        def _llm_type(self):
            return "scripted"

        def bind_tools(self, tools, **kwargs):
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            self.calls += 1
            message = (
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "open_issue", "args": {"title": "bug"}, "id": "c1"}
                    ],
                )
                if self.calls == 1
                else AIMessage(content="done")
            )
            return ChatResult(generations=[ChatGeneration(message=message)])

    service, client = registry(b'"opened"')

    async def scenario():
        tool = await service.as_tool("acme.github/open_issue")
        agent = Agent(
            "support",
            "Opens issues",
            Scripted(),
            tools=[tool],
            enable_default_tools=False,
            configuration=AgentConfiguration(system_prompt="test"),
        )
        return await agent.invoke("open an issue")

    assert asyncio.run(scenario()) == "done"
    assert json.loads(client.invoke_tool.call_args.args[0].arguments_json) == {
        "title": "bug"
    }


# ------------------------------------------------- failures of the call itself
def test_the_caller_waits_beyond_the_deadline_so_the_engines_verdict_arrives():
    service, client = registry()

    asyncio.run(service.invoke("acme.github/open_issue", {"title": "x"}, timeout=30))

    assert client.invoke_tool.call_args.kwargs == {"timeout": 30, "grace": 5.0}


def test_a_reply_lost_past_the_wait_is_deadline_exceeded_not_a_raw_timeout():
    from naas_abi_sdk.services.errors import ServiceError

    service, _ = registry(error=asyncio.TimeoutError())

    with pytest.raises(ServiceError) as raised:
        asyncio.run(service.invoke("acme.github/open_issue", {"title": "x"}, timeout=2))

    assert raised.value.code == "DEADLINE_EXCEEDED"
    assert "may still have run" in str(raised.value)


@pytest.mark.parametrize(
    "error, expected",
    [
        (asyncio.TimeoutError(), "DEADLINE_EXCEEDED"),
        (OSError("connect to 10.0.0.7:4222 refused"), "UNAVAILABLE"),
        (RPCError("RESOURCE_EXHAUSTED", "busy"), "RESOURCE_EXHAUSTED"),
    ],
)
def test_a_failure_of_the_call_reaches_the_model_not_the_agent_run(error, expected):
    pytest.importorskip("langchain_core")
    service, _ = registry(error=error)

    async def scenario():
        tool = await service.as_tool("acme.github/open_issue")
        return await tool.ainvoke({"title": "bug"})

    out = asyncio.run(scenario())

    assert expected in out
    assert "10.0.0.7" not in out


def test_a_nats_connection_error_reaches_the_model_without_its_message():
    pytest.importorskip("langchain_core")
    import nats.errors

    service, _ = registry(error=nats.errors.NoServersError())

    async def scenario():
        tool = await service.as_tool("acme.github/open_issue")
        return await tool.ainvoke({"title": "bug"})

    assert "UNAVAILABLE" in asyncio.run(scenario())


def test_arguments_the_engine_could_not_take_reach_the_model_too():
    pytest.importorskip("langchain_core")
    service, client = registry()

    async def scenario():
        tool = await service.as_tool("acme.github/open_issue")
        too_big = await tool.ainvoke({"title": "x" * (256 * 1024)})
        not_json = await tool.ainvoke({"title": float("nan")})
        return too_big, not_json

    too_big, not_json = asyncio.run(scenario())

    assert "256 KiB" in too_big
    assert "JSON" in not_json
    client.invoke_tool.assert_not_called()
