import asyncio
import contextvars

import pytest

from naas_abi_sdk.call_context import (
    ANONYMOUS,
    ON_BEHALF_OF_HEADER,
    CallContext,
    current_call_context,
    on_behalf_of_header,
    service_account,
    use_call_context,
    user,
)

NEXUS = CallContext(principal=service_account("api"), on_behalf_of=user("usr-ada"))


def test_a_call_outside_any_context_is_anonymous():
    assert current_call_context() == ANONYMOUS
    assert ANONYMOUS.principal.kind == "anonymous"
    assert ANONYMOUS.user is None


def test_the_context_holds_inside_the_block_and_nests():
    worker = CallContext(principal=service_account("engine"))
    with use_call_context(NEXUS):
        assert current_call_context() is NEXUS
        with use_call_context(worker):
            assert current_call_context() is worker
        assert current_call_context() is NEXUS
    assert current_call_context() == ANONYMOUS


def test_the_block_restores_the_context_when_it_raises():
    with pytest.raises(RuntimeError), use_call_context(NEXUS):
        raise RuntimeError("boom")
    assert current_call_context() == ANONYMOUS


def test_tasks_and_threads_given_the_context_inherit_it():
    async def task() -> CallContext:
        return current_call_context()

    async def scenario():
        with use_call_context(NEXUS):
            spawned = asyncio.create_task(task())
            threaded = asyncio.to_thread(current_call_context)
            return await spawned, await threaded

    assert asyncio.run(scenario()) == (NEXUS, NEXUS)
    with use_call_context(NEXUS):
        copied = contextvars.copy_context()
    assert copied.run(current_call_context) is NEXUS


def test_the_calls_user_is_whom_it_acts_for_else_a_user_actor():
    assert NEXUS.user == user("usr-ada")
    assert CallContext(principal=user("usr-bob")).user == user("usr-bob")
    assert CallContext(principal=service_account("engine")).user is None


def test_the_header_names_the_calls_user_or_nothing():
    assert on_behalf_of_header(NEXUS) == {ON_BEHALF_OF_HEADER: "usr-ada"}
    assert on_behalf_of_header(CallContext(principal=service_account("api"))) == {}
    assert on_behalf_of_header() == {}
    with use_call_context(NEXUS):
        assert on_behalf_of_header() == {"Abi-On-Behalf-Of": "usr-ada"}


@pytest.mark.parametrize("make", [service_account, user])
def test_a_principal_needs_an_id(make):
    with pytest.raises(ValueError):
        make("")


def test_principals_are_values():
    assert service_account("api") == service_account("api")
    assert service_account("api").name == "api"
    assert user("usr-ada").name is None
    with pytest.raises(AttributeError):
        NEXUS.principal.id = "engine"  # type: ignore[misc]
